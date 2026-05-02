"""Run phase0 multi using REGULAR-HOURS-ONLY bars (9:30-16:00 ET = 78 bars/day).

Diagnostic to quantify how much of the existing EV came from pre-market /
after-hours fills that are unrealistic in live trading.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd

from equity_trading.src.broker.alpaca_client import AlpacaClient
from equity_trading.src.config import load_config
from equity_trading.src.data.price_fetcher import PriceFetcher
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
from equity_trading.src.strategy.strategies.pre_fomc import PreFOMCDriftStrategy
from equity_trading.src.strategy.strategies.trend_follow import TrendFollowStrategy
from equity_trading.src.strategy.strategies.turn_of_month import TurnOfMonthStrategy
from equity_trading.src.strategy.strategies.vwap_scalp import VWAPScalpStrategy


SYMBOLS = ["SPY", "QQQ", "IWM", "DIA", "XLK"]


def filter_rth(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only regular trading hours (9:30-16:00 ET) bars."""
    if df.index.tz is None:
        return df
    ny = df.index.tz_convert("America/New_York")
    # 9:30 ET start, 16:00 ET end (last bar covers 15:55-16:00 with timestamp 15:55)
    minutes_since_open = (ny.hour * 60 + ny.minute) - (9 * 60 + 30)
    mask = (minutes_since_open >= 0) & (minutes_since_open < 6 * 60 + 30)
    return df[mask]


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    cache_dir = project_root / "data" / "prices"
    env_path = project_root / ".env"
    cfg = load_config(env_path=env_path if env_path.exists() else None)
    broker = AlpacaClient(api_key=cfg.alpaca_api_key, secret_key=cfg.alpaca_secret_key,
                         base_url=cfg.alpaca_base_url)
    fetcher = PriceFetcher(broker=broker, cache_dir=cache_dir)

    period_start = datetime(2019, 5, 1, tzinfo=timezone.utc)
    period_end = datetime(2026, 5, 1, tzinfo=timezone.utc)

    print("loading + filtering to RTH...")
    data_map = collect_phase0_data(fetcher=fetcher, symbols=SYMBOLS,
                                   start=period_start, end=period_end, timeframes=[5, 1440])
    rth_map: dict = {}
    for (sym, tf), df in data_map.items():
        if tf == 5:
            before = len(df)
            df = filter_rth(df)
            after = len(df)
            print(f"  {sym} 5min: {before} → {after} ({after/before*100:.1f}% kept)")
        rth_map[(sym, tf)] = df

    atr_map = {s: analyze_atr_distribution(rth_map[(s, 5)], period=14)["median_pct"]
               for s in SYMBOLS}

    PARAM_GRID = {
        "gap_fill": [
            {"gap_threshold": 0.003, "stop_extension": 0.005},
            {"gap_threshold": 0.005, "stop_extension": 0.005},
            {"gap_threshold": 0.010, "stop_extension": 0.010},
        ],
        "pre_fomc_drift": [
            # 78 RTH bars/day. Day 1 entry at bar (entry_bar_pos+1), Day 2 bar 53 = 14:00 ET.
            # entry_bar_pos=0  → fill at bar 1 (9:35 ET).  Exit 78-1+53 = 130 bars later.
            # entry_bar_pos=36 → fill at bar 37 (12:35 ET). Exit 78-37+53 = 94 bars later.
            {"entry_bar_pos": 0,  "_max_hold_bars": 130},
            {"entry_bar_pos": 36, "_max_hold_bars": 94},
            # Same-day-only variant for comparison: midday entry, exit at close
            {"entry_bar_pos": 36, "_max_hold_bars": 41},
        ],
        "mean_reversion": [{"threshold": 0.40}, {"threshold": 0.50}, {"threshold": 0.60}],
        "intraday_momentum": [
            {"threshold": 0.001, "entry_bar_pos": 71, "_max_hold_bars": 5},
            {"threshold": 0.003, "entry_bar_pos": 71, "_max_hold_bars": 5},
        ],
    }

    strategies = [
        GapFillStrategy(),
        PreFOMCDriftStrategy(),
        MeanReversionStrategy(),
        IntradayMomentumStrategy(),
    ]

    print("\nrunning strategies on RTH-only data...")
    results = run_all_strategies(
        strategies=strategies, symbols=SYMBOLS,
        data_map=rth_map, atr_map=atr_map, param_grid=PARAM_GRID,
    )

    # Build a mini comparison report
    md = ["# RTH-only diagnostic — does pre-market data inflate EV?", "",
          "Compares strategy EV on full extended-hours data vs regular-trading-hours-only.", ""]
    for strat_name, df in results.items():
        if len(df) == 0:
            continue
        md.append(f"## {strat_name}")
        md.append("")
        md.append("| Symbol | Params | Trades | WR | EV |")
        md.append("|--------|--------|-------:|----:|---:|")
        for _, row in df.iterrows():
            ev = row['avg_pnl_pct'] * row['trade_count']
            md.append(f"| {row['symbol']} | {row['params']} | {row['trade_count']} | "
                      f"{row['win_rate']:.3f} | {ev:+.2f} |")
        md.append("")

    out_path = project_root / "phase0" / "rth_diagnostic.md"
    out_path.write_text("\n".join(md), encoding="utf-8")
    print(f"\n[saved] {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
