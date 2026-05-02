import numpy as np
import pandas as pd

from equity_trading.src.strategy.strategies.mean_reversion import MeanReversionStrategy


def _make_bars(n: int) -> pd.DataFrame:
    np.random.seed(42)
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.1)
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes + 0.05,
            "low": closes - 0.05,
            "close": closes,
            "volume": [10000] * n,
        },
        index=pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC"),
    )


def _make_daily_above_ma(n: int = 250) -> pd.DataFrame:
    """200d MAより上にある日足."""
    closes = pd.Series(100.0 + np.linspace(0, 20, n))
    return pd.DataFrame(
        {"close": closes.values},
        index=pd.date_range("2023-01-01", periods=n, freq="1D", tz="UTC"),
    )


def test_mean_reversion_has_correct_name():
    s = MeanReversionStrategy()
    assert s.name == "mean_reversion"


def test_mean_reversion_returns_bool_series():
    s = MeanReversionStrategy()
    bars = _make_bars(100)
    daily = _make_daily_above_ma()
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={"threshold": 0.5})
    assert len(signal) == len(bars)
    assert signal.dtype == bool or signal.dtype == "bool"


def test_mean_reversion_blocks_when_below_200ma():
    """SPY が 200d MA 下では取引せず."""
    s = MeanReversionStrategy()
    bars = _make_bars(100)
    daily_below = pd.DataFrame(
        {"close": [50.0] * 250},  # 200d MA より下
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )
    signal = s.compute_entry_signal(bars, daily_below, atr_pct=0.10, params={"threshold": 0.5})
    assert not signal.any()
