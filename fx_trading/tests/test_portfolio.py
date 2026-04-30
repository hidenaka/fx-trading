import pandas as pd
import numpy as np
from src.portfolio.market_regime import MarketRegimeDetector

def test_detects_trending_market():
    # Strong uptrend data
    df = pd.DataFrame({
        "high": [150 + i * 0.5 + np.random.rand() * 0.2 for i in range(30)],
        "low": [150 + i * 0.5 - np.random.rand() * 0.2 for i in range(30)],
        "close": [150 + i * 0.5 for i in range(30)],
    })
    detector = MarketRegimeDetector(lookback=14)
    regime = detector.detect(df)
    assert regime == "trending"

def test_detects_ranging_market():
    # Sideways data
    df = pd.DataFrame({
        "high": [150 + np.sin(i) * 0.5 for i in range(30)],
        "low": [150 - np.sin(i) * 0.5 for i in range(30)],
        "close": [150 + np.sin(i) * 0.3 for i in range(30)],
    })
    detector = MarketRegimeDetector(lookback=14)
    regime = detector.detect(df)
    assert regime == "ranging"

def test_returns_neutral_for_insufficient_data():
    df = pd.DataFrame({
        "high": [150.0] * 5,
        "low": [149.0] * 5,
        "close": [149.5] * 5,
    })
    detector = MarketRegimeDetector(lookback=14)
    regime = detector.detect(df)
    assert regime == "neutral"

from src.portfolio.strategy_selector import StrategySelector

def test_selector_returns_trend_strategies():
    selector = StrategySelector()
    strategies = selector.select("trending")
    assert "ma_macd" in strategies
    assert "ma_cross" in strategies
    assert "dow_theory" in strategies
    assert "stochastic" not in strategies

def test_selector_returns_ranging_strategies():
    selector = StrategySelector()
    strategies = selector.select("ranging")
    assert "stochastic" in strategies
    assert "ml_strategy" in strategies
    assert "ma_macd" not in strategies

def test_selector_returns_default_for_neutral():
    selector = StrategySelector()
    strategies = selector.select("neutral")
    assert len(strategies) >= 2

from src.portfolio.position_sizer import PositionSizer

def test_kelly_criterion_calculates_fraction():
    sizer = PositionSizer()
    # win_rate=0.6, avg_win=2, avg_loss=1
    kelly = sizer.kelly_fraction(win_rate=0.6, avg_win=2.0, avg_loss=1.0)
    # f* = (bp - q) / b = (0.6*2 - 0.4) / 2 = 0.4
    assert kelly == 0.4

def test_half_kelly_is_used_by_default():
    sizer = PositionSizer()
    kelly = sizer.kelly_fraction(win_rate=0.6, avg_win=2.0, avg_loss=1.0)
    half_kelly = sizer.calculate_lot(capital=100000, entry_price=150.0, stop_loss=149.0, win_rate=0.6, avg_win=2.0, avg_loss=1.0)
    # Risk amount with half-kelly
    expected_risk = 100000 * 0.4 * 0.5  # half kelly
    price_diff = 1.0
    expected_lot = expected_risk / price_diff
    assert half_kelly == expected_lot

def test_volatility_target_adjusts_size():
    sizer = PositionSizer(volatility_target=0.05)
    # High volatility reduces position size
    lot_normal = sizer.calculate_lot(capital=100000, entry_price=150.0, stop_loss=149.0, win_rate=0.6, avg_win=2.0, avg_loss=1.0, current_volatility=0.02)
    lot_high_vol = sizer.calculate_lot(capital=100000, entry_price=150.0, stop_loss=149.0, win_rate=0.6, avg_win=2.0, avg_loss=1.0, current_volatility=0.10)
    assert lot_high_vol < lot_normal
