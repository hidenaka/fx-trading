import numpy as np
import pandas as pd

from equity_trading.src.strategy.strategies.trend_follow import TrendFollowStrategy


def test_trend_follow_has_correct_name():
    assert TrendFollowStrategy().name == "trend_follow"


def test_trend_follow_returns_bool_series():
    s = TrendFollowStrategy()
    np.random.seed(42)
    n = 100
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.1)
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": list(np.linspace(80, 120, 250))},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={})
    assert len(signal) == len(bars)


def test_trend_follow_no_signal_when_below_200ma():
    s = TrendFollowStrategy()
    n = 100
    closes = np.full(n, 50.0)
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": [100.0] * 250},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={})
    assert not signal.any()


def test_trend_follow_signals_on_breakout():
    """直近20本高値を上抜けた瞬間にシグナル."""
    s = TrendFollowStrategy()
    closes = np.array([100.0] * 80 + list(np.linspace(100.0, 120.0, 20)))
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.5, "low": closes - 0.05, "close": closes, "volume": [10000] * 100},
        index=pd.date_range("2024-01-01 09:30", periods=100, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": list(np.linspace(80, 120, 250))},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={"breakout_period": 20})
    assert signal.iloc[80:].any()
