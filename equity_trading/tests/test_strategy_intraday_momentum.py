"""Tests for IntradayMomentumStrategy (Heston-Korajczyk-Sadka style).

First-30-min return predicts last-30-min return on broad-index ETFs.
"""
import numpy as np
import pandas as pd

from equity_trading.src.phase0.strategy_simulator import simulate_strategy
from equity_trading.src.strategy.strategies.intraday_momentum import IntradayMomentumStrategy


def _bars_for_two_full_days(
    bullish_morning_day1: bool,
    bullish_morning_day2: bool,
    n_bars_per_day: int = 78,
) -> pd.DataFrame:
    """Build 5-min OHLCV for trading days with controlled morning patterns.

    Adds a 3rd "buffer" day so the simulator can time-exit any day-2 trade
    (the simulator iterates `for i in range(n-1)` and time-exit needs the
    target bar in-range).
    Each day starts at 9:30 ET (=14:30 UTC). Bars: 0..77 cover 9:30..15:55 ET.
    """
    rows = []
    base_price = 100.0
    flags = [bullish_morning_day1, bullish_morning_day2, False]  # day 3 is filler
    for day_idx, bullish in enumerate(flags):
        day_start = pd.Timestamp(f"2024-01-{2 + day_idx} 14:30", tz="UTC")
        for bar in range(n_bars_per_day):
            ts = day_start + pd.Timedelta(minutes=5 * bar)
            if bar < 6 and bullish:
                px = base_price + 0.001 * base_price * (bar + 1)
            elif bar < 6 and not bullish:
                px = base_price - 0.001 * base_price * (bar + 1)
            else:
                drift = 0.0005 if bullish else -0.0005
                px = base_price * (1 + drift * (bar - 5)) if bar >= 6 else base_price
            rows.append({
                "timestamp": ts, "open": px, "high": px + 0.05, "low": px - 0.05,
                "close": px, "volume": 10000,
            })
    df = pd.DataFrame(rows).set_index("timestamp").sort_index()
    return df


def _flat_daily() -> pd.DataFrame:
    return pd.DataFrame(
        {"close": [100.0] * 250},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )


def test_strategy_has_name():
    s = IntradayMomentumStrategy()
    assert s.name == "intraday_momentum"


def test_no_signal_on_bearish_morning():
    """If first 30-min return is negative, no signal should fire."""
    bars = _bars_for_two_full_days(bullish_morning_day1=False, bullish_morning_day2=False)
    s = IntradayMomentumStrategy()
    sig = s.compute_entry_signal(bars, _flat_daily(), atr_pct=0.10,
                                 params={"threshold": 0.001})
    assert not sig.any()


def test_signal_fires_on_bullish_morning_at_entry_bar():
    """If first 30-min return > threshold, signal at entry_bar_pos."""
    bars = _bars_for_two_full_days(bullish_morning_day1=True, bullish_morning_day2=True)
    s = IntradayMomentumStrategy()
    sig = s.compute_entry_signal(bars, _flat_daily(), atr_pct=0.10,
                                 params={"threshold": 0.001, "entry_bar_pos": 71})
    # Should fire on bar 71 of each day (relative)
    assert sig.sum() == 2
    # Confirm bar position
    ny_dates = pd.Series(bars.index.tz_convert("America/New_York").date, index=bars.index)
    bar_pos = bars.groupby(ny_dates).cumcount()
    fire_positions = bar_pos[sig].unique()
    assert list(fire_positions) == [71]


def test_threshold_filters_marginal_morning():
    """Tight threshold should suppress weak bullish mornings."""
    # Build a day with very small bullish morning (well below threshold=0.005)
    rows = []
    day_start = pd.Timestamp("2024-01-02 14:30", tz="UTC")
    base = 100.0
    for bar in range(78):
        ts = day_start + pd.Timedelta(minutes=5 * bar)
        if bar < 6:
            px = base + 0.0001 * base * (bar + 1)  # tiny +0.01%/bar = ~0.06% over 30 min
        else:
            px = base
        rows.append({"timestamp": ts, "open": px, "high": px + 0.05, "low": px - 0.05,
                     "close": px, "volume": 10000})
    bars = pd.DataFrame(rows).set_index("timestamp")
    s = IntradayMomentumStrategy()
    sig = s.compute_entry_signal(bars, _flat_daily(), atr_pct=0.10,
                                 params={"threshold": 0.005, "entry_bar_pos": 71})
    assert not sig.any()


def test_simulator_integration_one_trade_per_bullish_morning():
    """End-to-end: 2 bullish mornings → 2 trades."""
    bars = _bars_for_two_full_days(bullish_morning_day1=True, bullish_morning_day2=True)
    s = IntradayMomentumStrategy()
    summary = simulate_strategy(
        strategy=s, bars_5min=bars, daily=_flat_daily(),
        atr_pct=0.10, params={
            "threshold": 0.001,
            "entry_bar_pos": 71,
            "_max_hold_bars": 5,
        },
    )
    assert summary["trade_count"] == 2


def test_holds_within_same_day_only():
    """Trade entered at bar 72 (15:35 ET) should exit at bar 77 (16:00 close), not spill into next day."""
    bars = _bars_for_two_full_days(bullish_morning_day1=True, bullish_morning_day2=False)
    s = IntradayMomentumStrategy()
    summary, trades = simulate_strategy(
        strategy=s, bars_5min=bars, daily=_flat_daily(),
        atr_pct=0.10, params={
            "threshold": 0.001,
            "entry_bar_pos": 71,
            "_max_hold_bars": 5,
        },
        return_trades=True,
    )
    assert summary["trade_count"] == 1
    # bars_held should be ≤ 5 (i.e. trade exits same day)
    assert int(trades.iloc[0]["bars_held"]) <= 5
