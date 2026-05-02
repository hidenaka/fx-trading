import numpy as np
import pandas as pd

from equity_trading.src.phase0.multi_strategy_runner import (
    run_all_strategies,
)
from equity_trading.src.strategy.strategies.mean_reversion import MeanReversionStrategy
from equity_trading.src.strategy.strategies.trend_follow import TrendFollowStrategy


def _make_bars(n: int = 300) -> pd.DataFrame:
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


def test_run_all_strategies_returns_dataframe_per_strategy():
    data_map = {
        ("SPY", 5): _make_bars(),
        ("SPY", 1440): _make_daily(),
        ("QQQ", 5): _make_bars(),
        ("QQQ", 1440): _make_daily(),
    }
    atr_map = {"SPY": 0.10, "QQQ": 0.13}

    strategies = [MeanReversionStrategy(), TrendFollowStrategy()]
    results = run_all_strategies(
        strategies=strategies,
        symbols=["SPY", "QQQ"],
        data_map=data_map,
        atr_map=atr_map,
        param_grid={
            "mean_reversion": [{"threshold": 0.5}, {"threshold": 0.6}],
            "trend_follow": [{}],
        },
    )

    assert "mean_reversion" in results
    assert "trend_follow" in results
    assert isinstance(results["mean_reversion"], pd.DataFrame)
    assert len(results["mean_reversion"]) == 4
    assert len(results["trend_follow"]) == 2
    cols = {"strategy", "symbol", "params", "trade_count", "win_count", "win_rate", "avg_pnl_pct"}
    assert cols.issubset(results["mean_reversion"].columns)
