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
