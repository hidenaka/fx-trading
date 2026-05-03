import numpy as np
import pandas as pd
import pytest

from equity_trading.src.strategy.strategies.opening_range_breakout import OpeningRangeBreakoutStrategy


def _daily_above_ma(n: int = 250) -> pd.DataFrame:
    closes = pd.Series(100.0 + np.linspace(0, 20, n))
    return pd.DataFrame(
        {"close": closes.values},
        index=pd.date_range("2023-01-01", periods=n, freq="1D", tz="UTC"),
    )


def _make_one_day_bars(or_high: float, or_low: float, breakout_at_bar: int) -> pd.DataFrame:
    """Build 50 bars on a single NY day (UTC 14:30 = NY 09:30 winter).

    First 6 bars sit between or_low and or_high (the OR window). After bar 6,
    bars hold at (or_high - 0.05) until `breakout_at_bar`, then jump to or_high+0.30.
    """
    n = 50
    closes = []
    highs = []
    lows = []
    for i in range(n):
        if i < 6:
            # OR window: alternate between or_low and or_high
            if i % 2 == 0:
                closes.append((or_high + or_low) / 2)
                highs.append(or_high)
                lows.append(or_low)
            else:
                closes.append((or_high + or_low) / 2)
                highs.append(or_high - 0.02)
                lows.append(or_low + 0.02)
        elif i < breakout_at_bar:
            # After OR, just below or_high
            closes.append(or_high - 0.05)
            highs.append(or_high - 0.02)
            lows.append(or_high - 0.10)
        else:
            # Breakout
            closes.append(or_high + 0.30)
            highs.append(or_high + 0.40)
            lows.append(or_high + 0.20)
    return pd.DataFrame(
        {"open": closes, "high": highs, "low": lows, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-15 14:30", periods=n, freq="5min", tz="UTC"),
    )


def test_orb_has_correct_name():
    assert OpeningRangeBreakoutStrategy().name == "opening_range_breakout"


def test_orb_no_signal_inside_or_window():
    """During the first 6 bars (OR window), even if high > prior bars' highs, no signal."""
    s = OpeningRangeBreakoutStrategy()
    bars = _make_one_day_bars(or_high=100.5, or_low=100.0, breakout_at_bar=10)
    signal = s.compute_entry_signal(bars, _daily_above_ma(), atr_pct=0.10, params={"or_window_bars": 6})
    # No signals in bars 0..5
    assert not signal.iloc[:6].any()


def test_orb_signals_on_first_breakout_after_or():
    s = OpeningRangeBreakoutStrategy()
    bars = _make_one_day_bars(or_high=100.5, or_low=100.0, breakout_at_bar=10)
    signal = s.compute_entry_signal(bars, _daily_above_ma(), atr_pct=0.10, params={"or_window_bars": 6})
    # First breakout at bar 10
    assert signal.iloc[10] == True
    # Subsequent bars (also above or_high) get NO signal — only first breakout fires
    assert not signal.iloc[11:].any()


def test_orb_resets_per_day():
    """Two trading days, each gets one breakout signal."""
    s = OpeningRangeBreakoutStrategy()
    # Day 1: NY 2024-01-15, 50 bars at UTC 14:30+
    day1 = _make_one_day_bars(or_high=100.5, or_low=100.0, breakout_at_bar=10)
    # Day 2: NY 2024-01-16
    day2 = _make_one_day_bars(or_high=101.5, or_low=101.0, breakout_at_bar=8)
    day2.index = day2.index + pd.Timedelta(days=1)
    bars = pd.concat([day1, day2])
    signal = s.compute_entry_signal(bars, _daily_above_ma(), atr_pct=0.10, params={"or_window_bars": 6})
    assert signal.sum() == 2  # exactly one signal per day


def test_orb_compute_exit_levels_default_multipliers():
    """V0 defaults: stop=OR_low (stop_mult=0), target=OR_high+1R (target_mult=1).

    V2.1 (stop=0.25, target=2.0) was REJECTED on holdout 2026-05-03 — see
    equity_trading/phase0/validation/2026-05-03_orb_v2_1.md.
    """
    s = OpeningRangeBreakoutStrategy()
    bars = _make_one_day_bars(or_high=100.5, or_low=100.0, breakout_at_bar=10)
    entry_price = float(bars["close"].iloc[10])
    stop, target = s.compute_exit_levels(
        bars_5min=bars, entry_idx=10, entry_price=entry_price, atr_pct=0.10,
        params={"or_window_bars": 6},
    )
    # OR_low = 100.0, OR_high = 100.5, range = 0.5
    # Stop   = 100.0 + 0.0 * 0.5 = 100.0
    # Target = 100.5 + 1.0 * 0.5 = 101.0
    assert stop == pytest.approx(100.0, abs=1e-6)
    assert target == pytest.approx(101.0, abs=1e-6)


def test_orb_compute_exit_levels_overridable_via_params():
    """stop_mult/target_mult params override defaults (used by validation framework)."""
    s = OpeningRangeBreakoutStrategy()
    bars = _make_one_day_bars(or_high=100.5, or_low=100.0, breakout_at_bar=10)
    entry_price = float(bars["close"].iloc[10])
    stop, target = s.compute_exit_levels(
        bars_5min=bars, entry_idx=10, entry_price=entry_price, atr_pct=0.10,
        params={"or_window_bars": 6, "stop_mult": 0.25, "target_mult": 2.0},
    )
    # Stop   = 100.0 + 0.25 * 0.5 = 100.125
    # Target = 100.5 + 2.0  * 0.5 = 101.5
    assert stop == pytest.approx(100.125, abs=1e-6)
    assert target == pytest.approx(101.5, abs=1e-6)


def test_orb_vix_filter_suppresses_signals_on_high_vix_days():
    """With vix_halve_threshold=22.0, signals on synthetic high-VIX days are zero."""
    from equity_trading.src.strategy.strategies.opening_range_breakout import (
        OpeningRangeBreakoutStrategy,
    )
    import pandas as pd
    import numpy as np

    # 2 trading days × 78 bars (full RTH session) of 5-min data
    day1_idx = pd.date_range("2024-01-02 14:30", periods=78, freq="5min", tz="UTC")
    day2_idx = pd.date_range("2024-01-03 14:30", periods=78, freq="5min", tz="UTC")
    idx = day1_idx.union(day2_idx)
    closes = np.concatenate([
        np.linspace(100, 105, 78),  # day 1: rising → breakout
        np.linspace(100, 105, 78),  # day 2: rising → breakout
    ])
    bars = pd.DataFrame({
        "open": closes, "high": closes + 0.5, "low": closes - 0.5,
        "close": closes, "volume": [10000] * len(closes),
    }, index=idx)
    daily = pd.DataFrame({
        "close": [100.0] * 250 + [102.0, 103.0],
    }, index=pd.date_range("2023-04-01", periods=252, freq="1D", tz="UTC"))
    # Synthetic VIX: day 1 close = 30 (HIGH), day 2 close = 15 (LOW)
    vix = pd.DataFrame({
        "close": [30.0, 15.0],
    }, index=pd.to_datetime(["2024-01-02", "2024-01-03"], utc=True))

    s = OpeningRangeBreakoutStrategy()
    sig_unfiltered = s.compute_entry_signal(bars, daily, atr_pct=0.5, params={
        "or_window_bars": 12,
    })
    sig_filtered = s.compute_entry_signal(bars, daily, atr_pct=0.5, params={
        "or_window_bars": 12,
        "vix_halve_threshold": 22.0,
        "_vix_daily": vix,
    })
    # Map signals back to NY date to count by day.
    ny_dates = bars.index.tz_convert("America/New_York").date
    day1_idx_mask = pd.Series(ny_dates == ny_dates[0], index=bars.index)
    day2_idx_mask = pd.Series(ny_dates == ny_dates[-1], index=bars.index)
    # Day 1: VIX 30 > 22 → all signals suppressed
    assert sig_filtered[day1_idx_mask].sum() == 0
    # Day 2: VIX 15 < 22 → signal preserved
    assert sig_filtered[day2_idx_mask].sum() == sig_unfiltered[day2_idx_mask].sum()


def test_orb_vix_threshold_omitted_unchanged():
    """vix_halve_threshold not in params → identical to pre-change behavior."""
    from equity_trading.src.strategy.strategies.opening_range_breakout import (
        OpeningRangeBreakoutStrategy,
    )
    import pandas as pd
    import numpy as np
    idx = pd.date_range("2024-01-02 14:30", periods=78, freq="5min", tz="UTC")
    closes = np.linspace(100, 105, 78)
    bars = pd.DataFrame({
        "open": closes, "high": closes + 0.5, "low": closes - 0.5,
        "close": closes, "volume": [10000] * 78,
    }, index=idx)
    daily = pd.DataFrame({
        "close": [100.0] * 250 + [102.0],
    }, index=pd.date_range("2023-04-01", periods=251, freq="1D", tz="UTC"))
    s = OpeningRangeBreakoutStrategy()
    sig_a = s.compute_entry_signal(bars, daily, atr_pct=0.5, params={"or_window_bars": 12})
    sig_b = s.compute_entry_signal(bars, daily, atr_pct=0.5, params={
        "or_window_bars": 12,
        "vix_halve_threshold": 22.0,
        # _vix_daily intentionally absent
    })
    # No VIX data → silent no-op, signals identical
    assert (sig_a == sig_b).all()
