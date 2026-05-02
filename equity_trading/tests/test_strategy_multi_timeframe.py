import numpy as np
import pandas as pd

from equity_trading.src.strategy.strategies.multi_timeframe import MultiTimeframeStrategy


def test_multi_timeframe_has_correct_name():
    assert MultiTimeframeStrategy().name == "multi_timeframe"


def test_multi_timeframe_returns_bool_series():
    s = MultiTimeframeStrategy()
    np.random.seed(42)
    n = 500
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.1)
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-01 14:30", periods=n, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": list(np.linspace(80, 120, 250))},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={})
    assert len(signal) == n


def test_multi_timeframe_no_signal_when_below_200ma():
    s = MultiTimeframeStrategy()
    n = 500
    closes = np.full(n, 50.0)
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-01 14:30", periods=n, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": [100.0] * 250},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={})
    assert not signal.any()


def test_multi_timeframe_no_lookahead_at_first_bar_of_higher_tf_bucket():
    """A 5-min bar at the start of a 15-min bucket must not see RSI based on
    the close of a 5-min bar later in the same bucket."""
    s = MultiTimeframeStrategy()
    n = 500
    np.random.seed(123)
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.5)
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-01 14:30", periods=n, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": list(np.linspace(80, 200, 250))},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )
    # Run twice: once with full bars, once truncated to before the start of the
    # last full 15-min bucket. The signal value at the truncation boundary
    # should be identical between the two runs (no future data leaked in).
    full = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={})

    # Truncate so the last 5-min bar is exactly the start of a fresh 15-min bucket.
    # Find a 5-min bar at minute % 15 == 0
    boundary_idx = None
    for i, ts in enumerate(bars.index):
        if i > 100 and ts.minute % 15 == 0:
            boundary_idx = i
            break
    assert boundary_idx is not None
    truncated_bars = bars.iloc[: boundary_idx + 1]
    truncated_signal = s.compute_entry_signal(truncated_bars, daily, atr_pct=0.10, params={})
    # The signal at the boundary bar must be the same in both runs (within
    # floating point) — i.e., truncating future bars doesn't change the past.
    assert bool(truncated_signal.iloc[-1]) == bool(full.iloc[boundary_idx])
