"""Tests for OvernightHoldStrategy."""
import datetime as dt
import numpy as np
import pandas as pd

from equity_trading.src.phase0.strategy_simulator import simulate_strategy
from equity_trading.src.strategy.strategies.overnight_hold import OvernightHoldStrategy


def _flat_daily() -> pd.DataFrame:
    return pd.DataFrame(
        {"close": [100.0] * 250},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )


def _build_rth_bars(n_days: int = 3) -> pd.DataFrame:
    """78 bars/day RTH (9:30-16:00 ET = 14:30-21:00 UTC during EST)."""
    rows = []
    for d in range(n_days):
        day_start = pd.Timestamp(f"2024-01-{2 + d} 14:30", tz="UTC")
        for bar in range(78):
            ts = day_start + pd.Timedelta(minutes=5 * bar)
            px = 100.0 + d * 0.5  # tiny upward drift between days
            rows.append({"timestamp": ts, "open": px, "high": px + 0.05,
                         "low": px - 0.05, "close": px, "volume": 10000})
    return pd.DataFrame(rows).set_index("timestamp")


def test_strategy_has_name():
    assert OvernightHoldStrategy().name == "overnight_hold"


def test_signal_fires_only_at_bar_76():
    bars = _build_rth_bars(n_days=3)
    s = OvernightHoldStrategy()
    sig = s.compute_entry_signal(bars, _flat_daily(), 0.10, params={})

    bar_pos = bars.groupby(
        bars.index.tz_convert("America/New_York").date
    ).cumcount()
    fired_positions = bar_pos[sig].unique()
    assert list(fired_positions) == [76]
    # 3 days × 1 fire/day
    assert sig.sum() == 3


def test_simulator_holds_one_bar_overnight():
    """Each entry exits at bars_held=1 (next bar = next day's bar 0)."""
    bars = _build_rth_bars(n_days=4)  # 3 trades + buffer day
    s = OvernightHoldStrategy()
    summary, trades = simulate_strategy(
        strategy=s, bars_5min=bars, daily=_flat_daily(),
        atr_pct=0.10, params={"_max_hold_bars": 1},
        return_trades=True,
    )
    # 3 entries (one per day on bar 76) — last day is buffer for time-exit
    assert summary["trade_count"] == 3
    assert (trades["bars_held"] == 1).all()
    assert (trades["exit_type"] == "time").all()
