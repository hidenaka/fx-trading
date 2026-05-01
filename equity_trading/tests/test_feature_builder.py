import numpy as np
import pandas as pd
import pytest

from equity_trading.src.data.feature_builder import compute_rsi


def test_rsi_constant_prices_returns_neutral():
    prices = pd.Series([100.0] * 30)
    rsi = compute_rsi(prices, period=14)
    last = rsi.iloc[-1]
    assert pd.isna(last) or abs(last - 50.0) < 0.01


def test_rsi_strictly_rising_approaches_100():
    prices = pd.Series([100.0 + i for i in range(30)])
    rsi = compute_rsi(prices, period=14)
    assert rsi.iloc[-1] > 99.0


def test_rsi_strictly_falling_approaches_0():
    prices = pd.Series([100.0 - i for i in range(30)])
    rsi = compute_rsi(prices, period=14)
    assert rsi.iloc[-1] < 1.0


def test_rsi_mixed_movement_in_valid_range():
    np.random.seed(42)
    prices = pd.Series(100.0 + np.cumsum(np.random.randn(50)))
    rsi = compute_rsi(prices, period=14)
    valid = rsi.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()


def test_rsi_first_period_values_are_nan():
    prices = pd.Series([100.0 + i for i in range(20)])
    rsi = compute_rsi(prices, period=14)
    assert rsi.iloc[:13].isna().all()


from equity_trading.src.data.feature_builder import compute_bollinger_bands


def test_bollinger_bands_constant_prices_yields_zero_width():
    prices = pd.Series([100.0] * 30)
    upper, middle, lower = compute_bollinger_bands(prices, period=20, num_std=2.0)
    assert middle.iloc[-1] == 100.0
    assert upper.iloc[-1] == 100.0
    assert lower.iloc[-1] == 100.0


def test_bollinger_middle_equals_simple_moving_average():
    np.random.seed(42)
    prices = pd.Series(100.0 + np.cumsum(np.random.randn(30)))
    _, middle, _ = compute_bollinger_bands(prices, period=20, num_std=2.0)
    sma = prices.rolling(20).mean()
    pd.testing.assert_series_equal(middle.dropna(), sma.dropna())


def test_bollinger_upper_above_lower():
    np.random.seed(42)
    prices = pd.Series(100.0 + np.cumsum(np.random.randn(30)))
    upper, _, lower = compute_bollinger_bands(prices, period=20, num_std=2.0)
    valid = upper.notna() & lower.notna()
    assert (upper[valid] >= lower[valid]).all()


def test_bollinger_first_period_values_are_nan():
    prices = pd.Series(np.arange(30, dtype=float))
    upper, middle, lower = compute_bollinger_bands(prices, period=20, num_std=2.0)
    assert upper.iloc[:19].isna().all()
