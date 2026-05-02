import numpy as np
import pandas as pd

from equity_trading.src.strategy.strategies.momentum_breakout import MomentumBreakoutStrategy


def test_momentum_breakout_has_correct_name():
    assert MomentumBreakoutStrategy().name == "momentum_breakout"


def test_momentum_breakout_signals_with_volume():
    s = MomentumBreakoutStrategy()
    n = 200
    closes = np.array([100.0] * (n - 5) + [100.5, 101.0, 101.5, 102.0, 102.5])
    volumes = [10000] * (n - 5) + [20000, 22000, 25000, 28000, 30000]
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.1, "low": closes - 0.05, "close": closes, "volume": volumes},
        index=pd.date_range("2024-01-01 09:30", periods=n, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": list(np.linspace(80, 120, 250))},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={"breakout_period": 78})
    assert signal.iloc[-5:].any()


def test_momentum_breakout_no_signal_without_volume():
    s = MomentumBreakoutStrategy()
    n = 200
    closes = np.array([100.0] * (n - 5) + [100.5, 101.0, 101.5, 102.0, 102.5])
    volumes = [10000] * n
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.1, "low": closes - 0.05, "close": closes, "volume": volumes},
        index=pd.date_range("2024-01-01 09:30", periods=n, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": list(np.linspace(80, 120, 250))},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={"breakout_period": 78})
    assert not signal.iloc[-5:].any()
