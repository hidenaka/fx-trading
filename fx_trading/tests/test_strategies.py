import pandas as pd
from src.strategies.ma_macd import MaMacdStrategy
from src.strategies.ma_cross import MaCrossStrategy
from src.strategies.dow_theory import DowTheoryStrategy


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
