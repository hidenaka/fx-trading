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
