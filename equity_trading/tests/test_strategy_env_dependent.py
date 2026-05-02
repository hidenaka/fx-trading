import numpy as np
import pandas as pd

from equity_trading.src.strategy.strategies.env_dependent import EnvDependentReversionStrategy


def test_env_dependent_has_correct_name():
    assert EnvDependentReversionStrategy().name == "env_dependent_reversion"


def test_env_dependent_blocks_first_30_min_after_open():
    """市場オープン後30分以内はシグナルなし."""
    s = EnvDependentReversionStrategy()
    n = 50
    np.random.seed(42)
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.1)
    bars = pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-15 14:30", periods=n, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame(
        {"close": list(np.linspace(80, 120, 250))},
        index=pd.date_range("2023-01-01", periods=250, freq="1D", tz="UTC"),
    )
    signal = s.compute_entry_signal(bars, daily, atr_pct=0.10, params={"threshold": 0.3})
    assert not signal.iloc[:6].any()
