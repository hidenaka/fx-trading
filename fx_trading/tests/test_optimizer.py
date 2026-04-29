import pandas as pd
from src.optimizer.grid_search import GridSearchOptimizer
from src.strategies.ma_macd import MaMacdStrategy
from src.engine.backtest import BacktestEngine
from src.risk.manager import RiskManager

def test_grid_search_runs():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=30, freq="h"),
        "open": [150.0] * 30,
        "high": [151.0] * 30,
        "low": [149.0] * 30,
        "close": [150.0 + i * 0.1 for i in range(30)],
        "volume": [1000] * 30,
    })
    optimizer = GridSearchOptimizer(df)
    param_grid = {
        "fast": [3, 5],
        "slow": [6, 10],
        "signal": [2, 3],
    }
    results = optimizer.search(MaMacdStrategy, param_grid)
    assert len(results) == 8
    assert all("params" in r and "profit_factor" in r for r in results)

def test_grid_search_finds_best():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=30, freq="h"),
        "open": [150.0] * 30,
        "high": [151.0] * 30,
        "low": [149.0] * 30,
        "close": [150.0 + i * 0.1 for i in range(30)],
        "volume": [1000] * 30,
    })
    optimizer = GridSearchOptimizer(df)
    param_grid = {
        "fast": [3],
        "slow": [6],
        "signal": [2],
    }
    results = optimizer.search(MaMacdStrategy, param_grid)
    best = optimizer.get_best(results)
    assert best["params"]["fast"] == 3
