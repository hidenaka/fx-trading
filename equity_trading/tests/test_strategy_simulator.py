import numpy as np
import pandas as pd

from equity_trading.src.phase0.strategy_simulator import simulate_strategy
from equity_trading.src.strategy.strategies.mean_reversion import MeanReversionStrategy


def _make_bars(n: int = 200) -> pd.DataFrame:
    np.random.seed(42)
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.1)
    return pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes, "volume": [10000] * n},
        index=pd.date_range("2024-01-01 14:30", periods=n, freq="5min", tz="UTC"),
    )


def _make_daily(n: int = 250) -> pd.DataFrame:
    return pd.DataFrame(
        {"close": list(np.linspace(80, 120, n))},
        index=pd.date_range("2023-01-01", periods=n, freq="1D", tz="UTC"),
    )


def test_simulate_strategy_returns_dict():
    s = MeanReversionStrategy()
    bars = _make_bars()
    daily = _make_daily()
    result = simulate_strategy(
        strategy=s,
        bars_5min=bars,
        daily=daily,
        atr_pct=0.10,
        params={"threshold": 0.5},
    )
    assert "trade_count" in result
    assert "win_count" in result
    assert "win_rate" in result
    assert "avg_pnl_pct" in result


def test_simulate_strategy_zero_signal_returns_zero_trades():
    """全シグナルが False の戦略は trade_count=0."""
    class ZeroStrategy(MeanReversionStrategy):
        name = "zero"

        def compute_entry_signal(self, bars_5min, daily, atr_pct, params):
            return pd.Series([False] * len(bars_5min), index=bars_5min.index, dtype=bool)

    s = ZeroStrategy()
    result = simulate_strategy(
        strategy=s,
        bars_5min=_make_bars(),
        daily=_make_daily(),
        atr_pct=0.10,
        params={},
    )
    assert result["trade_count"] == 0
