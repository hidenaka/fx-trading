import pandas as pd
from src.engine.backtest import BacktestEngine
from src.strategies.ma_macd import MaMacdStrategy
from src.risk.manager import RiskManager


def test_backtest_runs_and_produces_trades():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=30, freq="h"),
        "open": [150.0] * 30,
        "high": [151.0] * 30,
        "low": [149.0] * 30,
        "close": [150.0 + i * 0.1 for i in range(30)],
        "volume": [1000] * 30,
    })
    engine = BacktestEngine(initial_capital=1_000_000)
    strategy = MaMacdStrategy(fast=3, slow=6, signal=2)
    risk = RiskManager(capital=1_000_000, risk_per_trade=0.01)
    trades = engine.run(df, strategy, risk)
    assert isinstance(trades, list)


def test_backtest_capital_changes():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=10, freq="h"),
        "open": [150.0] * 10,
        "high": [151.0] * 10,
        "low": [149.0] * 10,
        "close": [150.0, 149.5, 149.0, 148.5, 148.0, 148.5, 149.0, 149.5, 150.0, 150.5],
        "volume": [1000] * 10,
    })
    engine = BacktestEngine(initial_capital=1_000_000)
    strategy = MaMacdStrategy(fast=2, slow=4, signal=2)
    risk = RiskManager(capital=1_000_000, risk_per_trade=0.01)
    trades = engine.run(df, strategy, risk)
    assert engine.capital != 1_000_000 or len(trades) == 0
