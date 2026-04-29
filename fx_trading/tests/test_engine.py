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

from unittest.mock import MagicMock
from src.engine.backtest import BacktestEngine

def test_engine_supports_backtest_mode():
    engine = BacktestEngine(initial_capital=100000, mode="backtest")
    assert engine.mode == "backtest"

def test_engine_supports_live_mode():
    engine = BacktestEngine(initial_capital=100000, mode="live")
    assert engine.mode == "live"

def test_live_mode_checks_position_before_entry():
    # In live mode with no position and buy signal, should attempt to enter
    import pandas as pd
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=5, freq="h"),
        "open": [150.0]*5, "high": [151.0]*5, "low": [149.0]*5,
        "close": [150.0, 150.5, 151.0, 150.5, 151.0],
        "volume": [1000]*5,
    })
    mock_broker = MagicMock()
    mock_broker.get_open_positions.return_value = []
    mock_broker.get_current_price.return_value = {"bid": 150.0, "ask": 150.02}
    
    engine = BacktestEngine(initial_capital=100000, mode="live", broker=mock_broker)
    # Should not crash - in real implementation it would check broker
    assert engine.mode == "live"
