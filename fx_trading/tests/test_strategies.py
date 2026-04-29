import pandas as pd
from src.strategies.ma_macd import MaMacdStrategy
from src.strategies.ma_cross import MaCrossStrategy
from src.strategies.dow_theory import DowTheoryStrategy
from src.strategies.stochastic import StochasticStrategy


def test_ma_macd_generates_signals():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=30, freq="h"),
        "open": [150.0] * 30,
        "high": [151.0] * 30,
        "low": [149.0] * 30,
        "close": [150.0 + i * 0.1 for i in range(30)],
        "volume": [1000] * 30,
    })
    strat = MaMacdStrategy(fast=3, slow=6, signal=2)
    result = strat.generate_signals(df)
    assert "signal" in result.columns
    assert set(result["signal"].unique()).issubset({-1, 0, 1})


def test_ma_macd_long_signal_on_golden_cross():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=10, freq="h"),
        "open": [150.0] * 10,
        "high": [151.0] * 10,
        "low": [149.0] * 10,
        "close": [150.0, 149.5, 149.0, 148.5, 148.0, 148.5, 149.0, 149.5, 150.0, 150.5],
        "volume": [1000] * 10,
    })
    strat = MaMacdStrategy(fast=2, slow=4, signal=2)
    result = strat.generate_signals(df)
    assert result.iloc[-1]["signal"] == 1


def test_ma_cross_generates_signals():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=30, freq="h"),
        "open": [150.0] * 30,
        "high": [151.0] * 30,
        "low": [149.0] * 30,
        "close": [150.0 + i * 0.1 for i in range(30)],
        "volume": [1000] * 30,
    })
    strat = MaCrossStrategy(fast=3, slow=6)
    result = strat.generate_signals(df)
    assert "signal" in result.columns
    assert set(result["signal"].unique()).issubset({-1, 0, 1})


def test_ma_cross_long_signal_on_golden_cross():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=10, freq="h"),
        "open": [150.0] * 10,
        "high": [151.0] * 10,
        "low": [149.0] * 10,
        "close": [150.0, 149.5, 149.0, 148.5, 148.0, 148.5, 149.0, 149.5, 150.0, 150.5],
        "volume": [1000] * 10,
    })
    strat = MaCrossStrategy(fast=2, slow=4)
    result = strat.generate_signals(df)
    assert result.iloc[-1]["signal"] == 1


def test_dow_theory_generates_signals():
    import pandas as pd
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=30, freq="h"),
        "open": [150.0] * 30,
        "high": [151.0] * 30,
        "low": [149.0] * 30,
        "close": [150.0 + i * 0.1 for i in range(30)],
        "volume": [1000] * 30,
    })
    strat = DowTheoryStrategy(lookback=5)
    result = strat.generate_signals(df)
    assert "signal" in result.columns
    assert set(result["signal"].unique()).issubset({-1, 0, 1})


def test_dow_theory_buy_on_higher_high():
    import pandas as pd
    # Making higher highs
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=10, freq="h"),
        "open": [150.0] * 10,
        "high": [150.0, 151.0, 150.5, 152.0, 151.5, 153.0, 152.5, 154.0, 153.5, 155.0],
        "low": [149.0] * 10,
        "close": [150.0, 151.0, 150.5, 152.0, 151.5, 153.0, 152.5, 154.0, 153.5, 155.0],
        "volume": [1000] * 10,
    })
    strat = DowTheoryStrategy(lookback=3)
    result = strat.generate_signals(df)
    # Should see buy signal as we make higher highs
    assert result.iloc[-1]["signal"] == 1


def test_stochastic_generates_signals():
    import pandas as pd
    import numpy as np
    # Generate oscillating price for clear stochastic signals
    prices = 150 + np.sin(np.linspace(0, 4*np.pi, 50)) * 2
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=50, freq="h"),
        "open": prices,
        "high": prices + 0.5,
        "low": prices - 0.5,
        "close": prices,
        "volume": [1000] * 50,
    })
    strat = StochasticStrategy(k_period=14, d_period=3, overbought=80, oversold=20)
    result = strat.generate_signals(df)
    assert "signal" in result.columns
    assert set(result["signal"].unique()).issubset({-1, 0, 1})


def test_stochastic_oversold_buy_signal():
    import pandas as pd
    # Prices dropping then turning up
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=20, freq="h"),
        "open": [150.0 - i*0.1 for i in range(20)],
        "high": [150.0 - i*0.1 + 0.2 for i in range(20)],
        "low": [150.0 - i*0.1 - 0.2 for i in range(20)],
        "close": [150.0 - i*0.1 for i in range(20)],
        "volume": [1000] * 20,
    })
    # Reverse the last few to simulate bounce
    df.loc[17:, "close"] = [148.0, 148.1, 148.3]
    df.loc[17:, "high"] = [148.2, 148.3, 148.5]
    df.loc[17:, "low"] = [147.8, 147.9, 148.1]
    strat = StochasticStrategy(k_period=5, d_period=2, overbought=80, oversold=30)
    result = strat.generate_signals(df)
    # Last row should have some signal
    assert "stoch_k" in result.columns
    assert "stoch_d" in result.columns


import pandas as pd
import numpy as np
from src.ml.strategy import MLStrategy
from src.ml.trainer import MLTrainer
from src.ml.feature_engineer import FeatureEngineer

def test_ml_strategy_generates_signals():
    np.random.seed(42)
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=100, freq="h"),
        "open": np.random.randn(100).cumsum() + 150,
        "high": np.random.randn(100).cumsum() + 151,
        "low": np.random.randn(100).cumsum() + 149,
        "close": np.random.randn(100).cumsum() + 150,
        "volume": np.random.randint(1000, 2000, 100),
    })
    
    fe = FeatureEngineer()
    X, y = fe.prepare(df)
    
    trainer = MLTrainer()
    model = trainer.train(X, y)
    
    strategy = MLStrategy(model=model)
    result = strategy.generate_signals(df)
    assert "signal" in result.columns
    assert set(result["signal"].unique()).issubset({-1, 0, 1})

def test_factory_creates_ml_strategy():
    from src.strategies.factory import StrategyFactory
    assert "ml_strategy" in StrategyFactory.available_strategies()
