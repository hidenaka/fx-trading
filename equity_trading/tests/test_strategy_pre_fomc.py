"""Tests for PreFOMCDriftStrategy (Lucca-Moench 2015).

Long bias on the trading day before FOMC announcement;
exit before the announcement (~14:00 ET).
"""
import datetime as dt
import numpy as np
import pandas as pd

from equity_trading.src.phase0.strategy_simulator import simulate_strategy
from equity_trading.src.strategy.strategies.pre_fomc import PreFOMCDriftStrategy


def _build_bars(num_days: int, start: pd.Timestamp) -> pd.DataFrame:
    """Build flat 5-min bars over `num_days` consecutive trading days starting at `start`."""
    rows = []
    for d in range(num_days):
        day_start = start + pd.Timedelta(days=d)
        # Skip weekends (mock — assume sequential days are trading days for tests)
        for bar in range(78):
            ts = day_start + pd.Timedelta(minutes=5 * bar)
            px = 100.0
            rows.append({
                "timestamp": ts, "open": px, "high": px + 0.05,
                "low": px - 0.05, "close": px, "volume": 10000,
            })
    return pd.DataFrame(rows).set_index("timestamp")


def _flat_daily() -> pd.DataFrame:
    return pd.DataFrame(
        {"close": [100.0] * 250},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )


def test_strategy_has_name():
    s = PreFOMCDriftStrategy()
    assert s.name == "pre_fomc_drift"


def test_no_signal_when_no_fomc_dates_in_range():
    """If fomc_dates list is empty, no signal should fire."""
    bars = _build_bars(3, pd.Timestamp("2024-06-10 14:30", tz="UTC"))
    s = PreFOMCDriftStrategy()
    sig = s.compute_entry_signal(bars, _flat_daily(), 0.10,
                                 params={"fomc_dates": []})
    assert not sig.any()


def test_signal_fires_on_pre_fomc_day_at_entry_bar():
    """Signal fires at bar 0 of trading day immediately before FOMC date."""
    # Build 3 days: Jun 10 (pre-FOMC), Jun 11 (FOMC), Jun 12 (post)
    bars = _build_bars(3, pd.Timestamp("2024-06-10 13:30", tz="UTC"))
    s = PreFOMCDriftStrategy()
    fomc_dates = [dt.date(2024, 6, 11)]
    sig = s.compute_entry_signal(bars, _flat_daily(), 0.10,
                                 params={"fomc_dates": fomc_dates,
                                         "entry_bar_pos": 0})
    # Should fire exactly once: at bar 0 of Jun 10 (the pre-FOMC day)
    assert sig.sum() == 1
    fire_idx = bars.index[sig].tolist()
    assert len(fire_idx) == 1
    fire_ts = fire_idx[0]
    fire_ny_date = fire_ts.tz_convert("America/New_York").date()
    assert fire_ny_date == dt.date(2024, 6, 10)


def test_signal_does_not_fire_on_fomc_day_or_after():
    """FOMC day itself and post-FOMC day must not trigger entries."""
    bars = _build_bars(3, pd.Timestamp("2024-06-10 13:30", tz="UTC"))
    s = PreFOMCDriftStrategy()
    fomc_dates = [dt.date(2024, 6, 11)]
    sig = s.compute_entry_signal(bars, _flat_daily(), 0.10,
                                 params={"fomc_dates": fomc_dates,
                                         "entry_bar_pos": 0})
    ny_dates = pd.Series(bars.index.tz_convert("America/New_York").date,
                         index=bars.index)
    fired_dates = set(ny_dates[sig].unique())
    assert dt.date(2024, 6, 11) not in fired_dates
    assert dt.date(2024, 6, 12) not in fired_dates


def test_default_fomc_dates_are_populated():
    """Strategy should ship with a hardcoded FOMC schedule for our 2024-2026 data window."""
    s = PreFOMCDriftStrategy()
    assert len(s.DEFAULT_FOMC_DATES) >= 10
    # Verify a known FOMC date is present
    assert dt.date(2025, 1, 29) in s.DEFAULT_FOMC_DATES


def test_simulator_integration_executes_pre_fomc_trade():
    """End-to-end: pre-FOMC day → entry, time exit on FOMC day."""
    bars = _build_bars(3, pd.Timestamp("2024-06-10 13:30", tz="UTC"))
    s = PreFOMCDriftStrategy()
    summary = simulate_strategy(
        strategy=s, bars_5min=bars, daily=_flat_daily(),
        atr_pct=0.10,
        params={
            "fomc_dates": [dt.date(2024, 6, 11)],
            "entry_bar_pos": 0,
            "_max_hold_bars": 130,  # span ~24 hours of trading bars
        },
    )
    assert summary["trade_count"] == 1
