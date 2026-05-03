"""LastHourMomentumStrategy tests."""
from __future__ import annotations

import numpy as np
import pandas as pd

from equity_trading.src.strategy.strategies.last_hour_momentum import (
    LastHourMomentumStrategy,
)


def _bars_with_bullish_yesterday_close():
    """Two NY days. Day 0 (yesterday): last 30-min strongly up.
    Day 1 (today): bar 0 is the signal candidate."""
    day0_idx = pd.date_range("2024-01-02 14:30", periods=78, freq="5min", tz="UTC")
    day1_idx = pd.date_range("2024-01-03 14:30", periods=78, freq="5min", tz="UTC")
    idx = day0_idx.append(day1_idx)
    closes = np.concatenate([
        np.linspace(100, 100, 72),       # day 0 bars 0..71 flat
        np.linspace(100, 105, 6),        # day 0 bars 72..77 up 5%
        np.full(78, 105.0),              # day 1 flat
    ])
    return pd.DataFrame({
        "open": closes, "high": closes + 0.1, "low": closes - 0.1,
        "close": closes, "volume": [10000] * len(closes),
    }, index=idx)


def test_lhm_signals_at_today_bar_0_when_yesterday_bullish():
    bars = _bars_with_bullish_yesterday_close()
    daily = pd.DataFrame({"close": [100.0]},
                          index=pd.date_range("2024-01-01", periods=1, freq="1D", tz="UTC"))
    s = LastHourMomentumStrategy()
    sig = s.compute_entry_signal(bars, daily, atr_pct=0.2, params={"threshold": 0.001})
    # signal exists somewhere on day 1
    day1_mask = bars.index >= pd.Timestamp("2024-01-03 14:30", tz="UTC")
    assert sig[day1_mask].any()


def test_lhm_vix_filter_suppresses_high_vix_day():
    bars = _bars_with_bullish_yesterday_close()
    daily = pd.DataFrame({"close": [100.0]},
                          index=pd.date_range("2024-01-01", periods=1, freq="1D", tz="UTC"))
    # VIX on the signal day (Jan 3 NY) = 30 (HIGH); on Jan 2 = 15
    vix = pd.DataFrame({"close": [15.0, 30.0]},
                        index=pd.to_datetime(["2024-01-02", "2024-01-03"], utc=True))
    s = LastHourMomentumStrategy()
    sig_unfiltered = s.compute_entry_signal(bars, daily, atr_pct=0.2,
                                              params={"threshold": 0.001})
    sig_filtered = s.compute_entry_signal(bars, daily, atr_pct=0.2, params={
        "threshold": 0.001,
        "vix_halve_threshold": 22.0,
        "_vix_daily": vix,
    })
    day1_mask = bars.index >= pd.Timestamp("2024-01-03 14:30", tz="UTC")
    assert sig_unfiltered[day1_mask].any()
    assert sig_filtered[day1_mask].sum() == 0


def test_lhm_vix_threshold_omitted_unchanged():
    bars = _bars_with_bullish_yesterday_close()
    daily = pd.DataFrame({"close": [100.0]},
                          index=pd.date_range("2024-01-01", periods=1, freq="1D", tz="UTC"))
    s = LastHourMomentumStrategy()
    sig_a = s.compute_entry_signal(bars, daily, atr_pct=0.2, params={"threshold": 0.001})
    sig_b = s.compute_entry_signal(bars, daily, atr_pct=0.2, params={
        "threshold": 0.001,
        "vix_halve_threshold": 22.0,
        # _vix_daily intentionally absent
    })
    assert (sig_a == sig_b).all()
