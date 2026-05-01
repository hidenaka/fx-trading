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


from equity_trading.src.data.feature_builder import compute_vwap


def test_vwap_constant_price_equals_price():
    df = pd.DataFrame({
        "high": [100.0] * 5,
        "low": [100.0] * 5,
        "close": [100.0] * 5,
        "volume": [1000, 2000, 1500, 3000, 2500],
    })
    vwap = compute_vwap(df)
    assert (vwap == 100.0).all()


def test_vwap_weighted_correctly():
    df = pd.DataFrame({
        "high": [100.0, 110.0, 90.0],
        "low":  [100.0, 110.0, 90.0],
        "close":[100.0, 110.0, 90.0],
        "volume": [100, 200, 100],
    })
    vwap = compute_vwap(df)
    assert vwap.iloc[0] == pytest.approx(100.0)
    assert vwap.iloc[1] == pytest.approx(32000.0 / 300.0)
    assert vwap.iloc[2] == pytest.approx(41000.0 / 400.0)


def test_vwap_zero_volume_returns_nan():
    df = pd.DataFrame({
        "high": [100.0, 110.0],
        "low":  [100.0, 110.0],
        "close":[100.0, 110.0],
        "volume": [0, 0],
    })
    vwap = compute_vwap(df)
    assert vwap.isna().all()


from equity_trading.src.data.feature_builder import (
    compute_volume_ratio,
    compute_momentum_reversal,
    compute_sma,
)


def test_volume_ratio_against_recent_average():
    volume = pd.Series([100] * 20 + [150])
    ratio = compute_volume_ratio(volume, period=20)
    assert ratio.iloc[-1] == pytest.approx(1.5)


def test_volume_ratio_first_period_is_nan():
    volume = pd.Series([100] * 25)
    ratio = compute_volume_ratio(volume, period=20)
    assert ratio.iloc[:19].isna().all()


def test_momentum_reversal_detects_negative_to_positive():
    prices = pd.Series([100.0, 99.5, 99.0, 98.5, 99.0, 99.5, 100.0])
    flag = compute_momentum_reversal(prices, lookback=3)
    assert flag.iloc[-1] is True or flag.iloc[-1] == 1


def test_momentum_reversal_constant_prices_no_reversal():
    prices = pd.Series([100.0] * 10)
    flag = compute_momentum_reversal(prices, lookback=3)
    assert flag.iloc[-1] is False or flag.iloc[-1] == 0


def test_sma_basic():
    prices = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    sma = compute_sma(prices, period=3)
    assert sma.iloc[2] == pytest.approx(2.0)
    assert sma.iloc[4] == pytest.approx(4.0)
    assert sma.iloc[:2].isna().all()
