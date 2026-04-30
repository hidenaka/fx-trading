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


def _noisy_df(n=200, seed=7):
    import numpy as np
    rng = np.random.default_rng(seed)
    close = 150 + rng.standard_normal(n).cumsum() * 0.1
    return pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=n, freq="h"),
        "open": close,
        "high": close + 0.05,
        "low": close - 0.05,
        "close": close,
        "volume": [1000] * n,
    })


def test_walk_forward_reports_efficiency():
    df = _noisy_df()
    wfa = WalkForwardAnalyzer(train_size=80, test_size=40)
    param_grid = {"fast": [3, 5], "slow": [6, 10], "signal": [2, 3]}
    results = wfa.analyze(df, MaMacdStrategy, param_grid)
    assert all("wfa_efficiency" in r for r in results)
    assert all("test_trades_obj" in r for r in results)


def test_walk_forward_summary_aggregates_oos():
    df = _noisy_df()
    wfa = WalkForwardAnalyzer(train_size=80, test_size=40)
    param_grid = {"fast": [3, 5], "slow": [6, 10], "signal": [2]}
    results = wfa.analyze(df, MaMacdStrategy, param_grid)
    summary = wfa.summarize(results)
    # Aggregated OOS trade count must equal sum of per-window OOS trades.
    assert summary["windows"] == len(results)
    assert summary["oos_total_trades"] == sum(r["test_trades"] for r in results)
    assert 0.0 <= summary["param_change_ratio"] <= 1.0
    assert "avg_wfa_efficiency" in summary


def test_walk_forward_summary_handles_empty():
    wfa = WalkForwardAnalyzer(train_size=50, test_size=25)
    summary = wfa.summarize([])
    assert summary["windows"] == 0
    assert summary["oos_total_trades"] == 0
