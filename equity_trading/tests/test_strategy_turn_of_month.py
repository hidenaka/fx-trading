"""Tests for TurnOfMonthStrategy (Lakonishok-Smidt 1988 / McConnell-Xu 2008).

Long bias on the last trading day of a month + first 3 trading days of the
next month. Hold intraday only.
"""
import datetime as dt
import numpy as np
import pandas as pd

from equity_trading.src.phase0.strategy_simulator import simulate_strategy
from equity_trading.src.strategy.strategies.turn_of_month import TurnOfMonthStrategy


def _build_bars_for_dates(dates: list[dt.date]) -> pd.DataFrame:
    """Build flat 5-min bars (78 per day) for the given list of NY trading dates."""
    rows = []
    for d in dates:
        day_start = pd.Timestamp(f"{d.isoformat()} 14:30", tz="UTC")  # 9:30 ET
        for bar in range(78):
            ts = day_start + pd.Timedelta(minutes=5 * bar)
            px = 100.0
            rows.append({
                "timestamp": ts, "open": px, "high": px + 0.05,
                "low": px - 0.05, "close": px, "volume": 10000,
            })
    return pd.DataFrame(rows).set_index("timestamp").sort_index()


def _flat_daily() -> pd.DataFrame:
    return pd.DataFrame(
        {"close": [100.0] * 250},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )


def test_strategy_has_name():
    s = TurnOfMonthStrategy()
    assert s.name == "turn_of_month"


def test_signal_fires_on_last_day_of_month_and_first_three_of_next():
    """Last trading day of month + first 3 of next month = signal days (4 total per month boundary)."""
    # July 29-31 + Aug 1-5 spans a month boundary
    dates = [dt.date(2024, 7, 29), dt.date(2024, 7, 30), dt.date(2024, 7, 31),
             dt.date(2024, 8, 1), dt.date(2024, 8, 2), dt.date(2024, 8, 5)]
    bars = _build_bars_for_dates(dates)
    s = TurnOfMonthStrategy()
    sig = s.compute_entry_signal(bars, _flat_daily(), 0.10,
                                 params={"entry_bar_pos": 0})
    ny_dates = pd.Series(bars.index.tz_convert("America/New_York").date,
                         index=bars.index)
    fired = set(ny_dates[sig].unique())
    # Expected TOM days: Jul 31 (last of Jul), Aug 1, Aug 2, Aug 5 (first 3 trading days of Aug)
    expected = {dt.date(2024, 7, 31), dt.date(2024, 8, 1),
                dt.date(2024, 8, 2), dt.date(2024, 8, 5)}
    assert fired == expected


def test_signal_does_not_fire_on_mid_month_days():
    """Days in the middle of a month should NOT fire."""
    dates = [dt.date(2024, 7, 15), dt.date(2024, 7, 16), dt.date(2024, 7, 17)]
    bars = _build_bars_for_dates(dates)
    s = TurnOfMonthStrategy()
    sig = s.compute_entry_signal(bars, _flat_daily(), 0.10,
                                 params={"entry_bar_pos": 0})
    # No month-boundary in this slice → no signals (boundary detection requires next-month data)
    assert not sig.any()


def test_signal_fires_at_specified_entry_bar_position():
    """entry_bar_pos parameter controls which bar of the day fires."""
    dates = [dt.date(2024, 7, 30), dt.date(2024, 7, 31), dt.date(2024, 8, 1)]
    bars = _build_bars_for_dates(dates)
    s = TurnOfMonthStrategy()
    sig = s.compute_entry_signal(bars, _flat_daily(), 0.10,
                                 params={"entry_bar_pos": 6})
    bar_pos = bars.groupby(
        bars.index.tz_convert("America/New_York").date
    ).cumcount()
    fire_bar_positions = bar_pos[sig].unique()
    assert list(fire_bar_positions) == [6]


def test_simulator_integration_one_trade_per_tom_day():
    """End-to-end: each TOM day generates one trade with default _max_hold_bars=70."""
    dates = [dt.date(2024, 7, 29), dt.date(2024, 7, 30), dt.date(2024, 7, 31),
             dt.date(2024, 8, 1), dt.date(2024, 8, 2), dt.date(2024, 8, 5),
             dt.date(2024, 8, 6)]  # extra buffer day
    bars = _build_bars_for_dates(dates)
    s = TurnOfMonthStrategy()
    summary = simulate_strategy(
        strategy=s, bars_5min=bars, daily=_flat_daily(),
        atr_pct=0.10,
        params={"entry_bar_pos": 0, "_max_hold_bars": 70},
    )
    # 4 TOM days expected
    assert summary["trade_count"] == 4
