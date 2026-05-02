"""マルチ戦略 Phase 0 統合スクリプト.

5戦略すべてを過去データで検証して比較レポートを出す.

実行：
    cd /Users/hideakimacbookair/自動トレード
    python3 equity_trading/scripts/run_phase0_multi.py --days 730
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from equity_trading.src.broker.alpaca_client import AlpacaClient
from equity_trading.src.config import load_config
from equity_trading.src.data.price_fetcher import PriceFetcher
from equity_trading.src.monitor.logger import setup_logger
from equity_trading.src.phase0.atr_analyzer import analyze_atr_distribution
from equity_trading.src.phase0.comparison_report import generate_comparison_report
from equity_trading.src.phase0.data_collector import collect_phase0_data
from equity_trading.src.phase0.multi_strategy_runner import run_all_strategies
from equity_trading.src.strategy.strategies.analysis_driven_reversion import AnalysisDrivenReversionStrategy
from equity_trading.src.strategy.strategies.env_dependent import EnvDependentReversionStrategy
from equity_trading.src.strategy.strategies.gap_fill import GapFillStrategy
from equity_trading.src.strategy.strategies.intraday_momentum import IntradayMomentumStrategy
from equity_trading.src.strategy.strategies.mean_reversion import MeanReversionStrategy
from equity_trading.src.strategy.strategies.momentum_breakout import MomentumBreakoutStrategy
from equity_trading.src.strategy.strategies.multi_timeframe import MultiTimeframeStrategy
from equity_trading.src.strategy.strategies.opening_range_breakout import OpeningRangeBreakoutStrategy
from equity_trading.src.strategy.strategies.trend_follow import TrendFollowStrategy
from equity_trading.src.strategy.strategies.vwap_scalp import VWAPScalpStrategy


DEFAULT_SYMBOLS = ["SPY", "QQQ", "IWM", "DIA", "XLK"]


PARAM_GRID = {
    "mean_reversion": [
        {"threshold": 0.40},
        {"threshold": 0.50},
        {"threshold": 0.60},
    ],
    "trend_follow": [
        {"breakout_period": 20, "rsi_threshold": 50.0},
        {"breakout_period": 50, "rsi_threshold": 55.0},
    ],
    "momentum_breakout": [
        {"breakout_period": 78, "volume_multiplier": 1.5},
        {"breakout_period": 78, "volume_multiplier": 2.0},
    ],
    "env_dependent_reversion": [
        {"threshold": 0.40},
        {"threshold": 0.50},
    ],
    "multi_timeframe": [
        {"rsi_5min_threshold": 30.0, "rsi_15min_threshold": 35.0, "rsi_60min_threshold": 40.0},
        {"rsi_5min_threshold": 25.0, "rsi_15min_threshold": 30.0, "rsi_60min_threshold": 35.0},
    ],
    "analysis_driven_reversion": [
        {"threshold": 0.30, "block_lunch_hours": [11, 12], "require_spy_up": True},
        {"threshold": 0.25, "block_lunch_hours": [11, 12], "require_spy_up": True},
        {"threshold": 0.20, "block_lunch_hours": [11, 12], "require_spy_up": True},
    ],
    "vwap_scalp": [
        {"k_entry": 1.0},
        {"k_entry": 1.5},
        {"k_entry": 2.0},
    ],
    "opening_range_breakout": [
        {"or_window_bars": 6},   # 30 min
        {"or_window_bars": 12},  # 60 min
    ],
    "gap_fill": [
        {"gap_threshold": 0.003, "stop_extension": 0.005},  # 0.3% gap, 0.5% stop
        {"gap_threshold": 0.005, "stop_extension": 0.005},  # 0.5% gap, 0.5% stop
        {"gap_threshold": 0.010, "stop_extension": 0.010},  # 1.0% gap, 1.0% stop
    ],
    "intraday_momentum": [
        # entry_bar_pos=71 → fill at bar 72 close (~15:35 ET); _max_hold_bars=5 → exit ~16:00
        {"threshold": 0.0, "entry_bar_pos": 71, "_max_hold_bars": 5},      # any positive morning
        {"threshold": 0.001, "entry_bar_pos": 71, "_max_hold_bars": 5},    # +0.1% morning
        {"threshold": 0.003, "entry_bar_pos": 71, "_max_hold_bars": 5},    # +0.3% morning
        # last-hour variant: entry at ~15:00, hold 1h
        {"threshold": 0.001, "entry_bar_pos": 65, "_max_hold_bars": 11},
        {"threshold": 0.003, "entry_bar_pos": 65, "_max_hold_bars": 11},
    ],
}


def main(
    symbols: Sequence[str] = DEFAULT_SYMBOLS,
    start: datetime | None = None,
    end: datetime | None = None,
    cache_dir: Path | None = None,
    report_path: Path | None = None,
) -> int:
    log = setup_logger("equity_trading.phase0_multi")

    if end is None:
        end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    if start is None:
        start = end - timedelta(days=730)

    project_root = Path(__file__).resolve().parents[1]
    if cache_dir is None:
        cache_dir = project_root / "data" / "prices"
    if report_path is None:
        report_path = project_root / "phase0" / "comparison_report.md"

    log.info("phase0_multi_start", extra={"symbols": list(symbols)})

    env_path = project_root / ".env"
    cfg = load_config(env_path=env_path if env_path.exists() else None)
    broker = AlpacaClient(
        api_key=cfg.alpaca_api_key,
        secret_key=cfg.alpaca_secret_key,
        base_url=cfg.alpaca_base_url,
    )
    fetcher = PriceFetcher(broker=broker, cache_dir=cache_dir)

    log.info("phase0_multi_collecting_data")
    data_map = collect_phase0_data(
        fetcher=fetcher,
        symbols=symbols,
        start=start,
        end=end,
        timeframes=[5, 1440],
    )

    log.info("phase0_multi_analyzing_atr")
    atr_results: dict[str, dict[str, float]] = {}
    atr_map: dict[str, float] = {}
    for sym in symbols:
        atr_results[sym] = analyze_atr_distribution(data_map[(sym, 5)], period=14)
        atr_map[sym] = atr_results[sym]["median_pct"]

    log.info("phase0_multi_running_strategies")
    strategies = [
        MeanReversionStrategy(),
        TrendFollowStrategy(),
        MomentumBreakoutStrategy(),
        EnvDependentReversionStrategy(),
        MultiTimeframeStrategy(),
        AnalysisDrivenReversionStrategy(),
        VWAPScalpStrategy(),
        OpeningRangeBreakoutStrategy(),
        GapFillStrategy(),
        IntradayMomentumStrategy(),
    ]
    results = run_all_strategies(
        strategies=strategies,
        symbols=list(symbols),
        data_map=data_map,
        atr_map=atr_map,
        param_grid=PARAM_GRID,
    )

    log.info("phase0_multi_generating_report", extra={"output": str(report_path)})
    generate_comparison_report(
        results=results,
        atr_results=atr_results,
        output_path=report_path,
        period_start=start.date().isoformat(),
        period_end=end.date().isoformat(),
    )

    log.info("phase0_multi_done", extra={"report_path": str(report_path)})
    print(f"\n✅ Phase 0 Multi-Strategy 完了。レポート：{report_path}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-strategy Phase 0")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    parser.add_argument("--days", type=int, default=730)
    args = parser.parse_args()

    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=args.days)
    sys.exit(main(symbols=args.symbols, start=start, end=end))
