"""Phase 0 キャリブレーション統合スクリプト.

実行：
    cd /Users/hideakimacbookair/自動トレード
    python3 -m equity_trading.scripts.run_phase0

または引数を渡したい場合：
    python3 equity_trading/scripts/run_phase0.py --days 30
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

# プロジェクトルートを sys.path に追加
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from equity_trading.src.broker.alpaca_client import AlpacaClient
from equity_trading.src.config import load_config
from equity_trading.src.data.price_fetcher import PriceFetcher
from equity_trading.src.monitor.logger import setup_logger
from equity_trading.src.phase0.atr_analyzer import analyze_atr_distribution
from equity_trading.src.phase0.data_collector import collect_phase0_data
from equity_trading.src.phase0.report_generator import generate_calibration_report
from equity_trading.src.phase0.signal_simulator import sweep_thresholds


DEFAULT_SYMBOLS = ["SPY", "QQQ", "IWM", "DIA", "XLK"]
DEFAULT_THRESHOLDS = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75]


def main(
    symbols: Sequence[str] = DEFAULT_SYMBOLS,
    start: datetime | None = None,
    end: datetime | None = None,
    thresholds: Sequence[float] = DEFAULT_THRESHOLDS,
    cache_dir: Path | None = None,
    report_path: Path | None = None,
) -> int:
    log = setup_logger("equity_trading.phase0")

    if end is None:
        end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    if start is None:
        start = end - timedelta(days=730)

    project_root = Path(__file__).resolve().parents[1]
    if cache_dir is None:
        cache_dir = project_root / "data" / "prices"
    if report_path is None:
        report_path = project_root / "phase0" / "calibration_report.md"

    log.info("phase0_start", extra={"symbols": list(symbols), "start": start.isoformat(), "end": end.isoformat()})

    # API キーは .env から、または既存環境変数から
    env_path = project_root / ".env"
    cfg = load_config(env_path=env_path if env_path.exists() else None)
    broker = AlpacaClient(
        api_key=cfg.alpaca_api_key,
        secret_key=cfg.alpaca_secret_key,
        base_url=cfg.alpaca_base_url,
    )
    fetcher = PriceFetcher(broker=broker, cache_dir=cache_dir)

    log.info("phase0_collecting_data")
    data_map = collect_phase0_data(
        fetcher=fetcher,
        symbols=symbols,
        start=start,
        end=end,
        timeframes=[5, 1440],
    )

    log.info("phase0_analyzing_atr")
    atr_results: dict[str, dict[str, float]] = {}
    for sym in symbols:
        bars_5 = data_map[(sym, 5)]
        atr_results[sym] = analyze_atr_distribution(bars_5, period=14)

    log.info("phase0_sweeping_thresholds")
    sweep_results: dict[str, "pd.DataFrame"] = {}  # type: ignore[name-defined]
    for sym in symbols:
        bars_5 = data_map[(sym, 5)]
        daily = data_map[(sym, 1440)]
        atr_pct = atr_results[sym]["median_pct"]
        sweep = sweep_thresholds(
            bars_5min=bars_5,
            daily=daily,
            thresholds=thresholds,
            atr_pct=atr_pct,
        )
        sweep_results[sym] = sweep

    log.info("phase0_generating_report", extra={"output": str(report_path)})
    generate_calibration_report(
        atr_results=atr_results,
        sweep_results=sweep_results,
        output_path=report_path,
        period_start=start.date().isoformat(),
        period_end=end.date().isoformat(),
    )

    log.info("phase0_done", extra={"report_path": str(report_path)})
    print(f"\n✅ Phase 0 完了。レポート：{report_path}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 0 キャリブレーション実行")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=DEFAULT_SYMBOLS,
        help="対象ETFティッカー（デフォルト: 5本）",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=730,
        help="過去何日分のデータを取るか（デフォルト730=2年）",
    )
    args = parser.parse_args()

    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=args.days)
    sys.exit(main(symbols=args.symbols, start=start, end=end))
