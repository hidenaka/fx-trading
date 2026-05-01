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
