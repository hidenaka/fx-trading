import pandas as pd
from src.wfa.walker import WalkForwardAnalyzer
from src.strategies.ma_macd import MaMacdStrategy

def test_walk_forward_splits_data():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=100, freq="h"),
        "open": [150.0] * 100,
        "high": [151.0] * 100,
        "low": [149.0] * 100,
        "close": [150.0 + i * 0.01 for i in range(100)],
        "volume": [1000] * 100,
    })
    wfa = WalkForwardAnalyzer(train_size=50, test_size=25)
    windows = wfa.split(df)
    assert len(windows) == 2
    assert len(windows[0]["train"]) == 50
    assert len(windows[0]["test"]) == 25

def test_walk_forward_runs_analysis():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=100, freq="h"),
        "open": [150.0] * 100,
        "high": [151.0] * 100,
        "low": [149.0] * 100,
        "close": [150.0 + i * 0.01 for i in range(100)],
        "volume": [1000] * 100,
    })
    wfa = WalkForwardAnalyzer(train_size=50, test_size=25)
    param_grid = {"fast": [3, 5], "slow": [6, 10], "signal": [2]}
    results = wfa.analyze(df, MaMacdStrategy, param_grid)
    assert len(results) == 2
    assert all("train_pf" in r and "test_pf" in r for r in results)
