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

from src.portfolio.portfolio_manager import PortfolioManager

def test_manager_generates_signal_from_multiple_strategies():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=50, freq="h"),
        "high": [150 + i * 0.1 for i in range(50)],
        "low": [150 + i * 0.1 - 0.5 for i in range(50)],
        "close": [150 + i * 0.1 for i in range(50)],
    })
    manager = PortfolioManager()
    result = manager.generate_signal(df)
    assert "signal" in result
    assert result["signal"] in [-1, 0, 1]

def test_manager_aggregates_signals_with_confidence():
    # Mock: 2 buy, 1 sell, 1 neutral -> should be buy (majority)
    manager = PortfolioManager(confidence_threshold=2)
    signals = {"ma_macd": 1, "ma_cross": 1, "dow_theory": -1, "stochastic": 0}
    result = manager._aggregate_signals(signals)
    assert result == 1

def test_manager_skips_when_no_clear_signal():
    manager = PortfolioManager(confidence_threshold=3)
    signals = {"ma_macd": 1, "ma_cross": -1, "dow_theory": 1, "stochastic": -1}
    result = manager._aggregate_signals(signals)
    assert result == 0

from src.portfolio.rebalancer import Rebalancer

def test_rebalancer_calculates_weights():
    performance = {
        "ma_macd": {"return": 0.15, "sharpe": 1.2},
        "ma_cross": {"return": 0.20, "sharpe": 1.5},
        "dow_theory": {"return": 0.05, "sharpe": 0.8},
    }
    reb = Rebalancer()
    weights = reb.calculate_weights(performance)
    assert abs(sum(weights.values()) - 1.0) < 0.01
    assert weights["ma_cross"] > weights["dow_theory"]  # Better performance gets more weight

def test_rebalancer_skips_broken_strategies():
    performance = {
        "ma_macd": {"return": 0.15, "sharpe": 1.2},
        "broken": {"return": -0.30, "sharpe": -0.5},
    }
    reb = Rebalancer(min_sharpe=0.0)
    weights = reb.calculate_weights(performance)
    assert "broken" not in weights or weights["broken"] == 0.0
