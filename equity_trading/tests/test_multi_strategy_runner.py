import numpy as np
import pandas as pd

from equity_trading.src.phase0.multi_strategy_runner import (
    run_all_strategies,
)
from equity_trading.src.strategy.strategies.mean_reversion import MeanReversionStrategy
from equity_trading.src.strategy.strategies.trend_follow import TrendFollowStrategy
import json


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


def test_run_all_strategies_injects_spy_5min_when_available():
    """SPY 5min が data_map にある場合、params に '_spy_5min' が注入されているか."""
    captured_params: list[dict] = []

    class CaptureStrategy(MeanReversionStrategy):
        name = "capture"

        def compute_entry_signal(self, bars_5min, daily, atr_pct, params):
            captured_params.append(params)
            return pd.Series([False] * len(bars_5min), index=bars_5min.index, dtype=bool)

    bars = _make_bars()
    daily = _make_daily()
    data_map = {
        ("SPY", 5): bars,
        ("SPY", 1440): daily,
        ("XLK", 5): bars,
        ("XLK", 1440): daily,
    }
    atr_map = {"SPY": 0.10, "XLK": 0.13}

    results = run_all_strategies(
        strategies=[CaptureStrategy()],
        symbols=["SPY", "XLK"],
        data_map=data_map,
        atr_map=atr_map,
        param_grid={"capture": [{"foo": 1}]},
    )
    # Both calls (SPY and XLK) should see _spy_5min injected
    assert all("_spy_5min" in p for p in captured_params)
    assert len(captured_params) == 2
    # The reported params (in DataFrame) must NOT include _spy_5min in the JSON
    df = results["capture"]
    for params_str in df["params"]:
        assert "_spy_5min" not in params_str
        assert '"foo": 1' in params_str
