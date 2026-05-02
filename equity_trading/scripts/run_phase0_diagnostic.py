"""診断ラン：勝者と敗者の取引ログを比較する."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd

from equity_trading.src.phase0.analysis_report import generate_analysis_report
from equity_trading.src.phase0.strategy_simulator import simulate_strategy
from equity_trading.src.phase0.trade_analyzer import analyze_trades
from equity_trading.src.strategy.strategies.env_dependent import EnvDependentReversionStrategy
from equity_trading.src.strategy.strategies.mean_reversion import MeanReversionStrategy
from equity_trading.src.strategy.strategies.trend_follow import TrendFollowStrategy


DIAGNOSTIC_CASES = [
    (MeanReversionStrategy, "XLK", {"threshold": 0.40}, "winner"),
    (MeanReversionStrategy, "XLK", {"threshold": 0.50}, "winner_strict"),
    (MeanReversionStrategy, "SPY", {"threshold": 0.40}, "lost_on_spy"),
    (TrendFollowStrategy, "XLK", {"breakout_period": 50, "rsi_threshold": 55.0}, "high_freq_loser"),
    (EnvDependentReversionStrategy, "XLK", {"threshold": 0.40}, "winner_filtered"),
]


def _load_cached_bars(cache_dir: Path, symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
    s = start.strftime("%Y-%m-%dT%H%M")
    e = end.strftime("%Y-%m-%dT%H%M")
    fname = f"{symbol}_{timeframe}_{s}_{e}.parquet"
    path = cache_dir / fname
    if not path.exists():
        raise FileNotFoundError(f"Cached file missing: {path}")
    return pd.read_parquet(path)


def _atr_median_pct(bars_5min: pd.DataFrame, period: int = 14) -> float:
    """Quick 5min ATR median, returned as a percent of price."""
    high = bars_5min["high"]
    low = bars_5min["low"]
    close = bars_5min["close"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    atr_pct = (atr / close) * 100.0
    return float(atr_pct.median())


def main(
    cache_dir: Path | None = None,
    report_path: Path | None = None,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> int:
    project_root = Path(__file__).resolve().parents[1]
    if cache_dir is None:
        cache_dir = project_root / "data" / "prices"
    if report_path is None:
        report_path = project_root / "phase0" / "analysis_report.md"
    if period_start is None:
        period_start = datetime(2024, 5, 1, tzinfo=timezone.utc)
    if period_end is None:
        period_end = datetime(2026, 5, 1, tzinfo=timezone.utc)

    # Pre-load SPY daily for regime classification
    spy_daily = _load_cached_bars(cache_dir, "SPY", "1day", period_start, period_end)

    analyses: dict[tuple[str, str], dict] = {}
    for strategy_cls, symbol, params, label in DIAGNOSTIC_CASES:
        bars5 = _load_cached_bars(cache_dir, symbol, "5min", period_start, period_end)
        daily = _load_cached_bars(cache_dir, symbol, "1day", period_start, period_end)
        atr = _atr_median_pct(bars5)
        strat = strategy_cls()
        summary, trades_df = simulate_strategy(
            strategy=strat,
            bars_5min=bars5,
            daily=daily,
            atr_pct=atr,
            params=params,
            return_trades=True,
        )
        analysis = analyze_trades(trades_df, bars5, daily, spy_daily=spy_daily)
        key = (f"{strat.name}__{label}", symbol)
        analyses[key] = analysis
        wr = summary.get("win_rate")
        wr_str = f"{wr:.3f}" if wr is not None and wr == wr else "nan"
        ev = summary.get("avg_pnl_pct")
        ev_str = f"{ev:.4f}" if ev is not None and ev == ev else "nan"
        print(f"[{strat.name}/{symbol}/{label}] trades={summary['trade_count']} wr={wr_str} ev={ev_str}")

    generate_analysis_report(
        analyses=analyses,
        output_path=report_path,
        period_start=period_start.date().isoformat(),
        period_end=period_end.date().isoformat(),
    )
    print(f"\nDiagnostic report written: {report_path}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 0 diagnostic run")
    args = parser.parse_args()
    sys.exit(main())
