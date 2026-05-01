import numpy as np
import pandas as pd

from equity_trading.src.phase0.atr_analyzer import (
    compute_atr,
    analyze_atr_distribution,
)


def _make_5min_bars(n: int) -> pd.DataFrame:
    np.random.seed(42)
    base = 100.0
    closes = base + np.cumsum(np.random.randn(n) * 0.1)
    highs = closes + np.abs(np.random.randn(n) * 0.05)
    lows = closes - np.abs(np.random.randn(n) * 0.05)
    return pd.DataFrame(
        {
            "open": closes,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": [10000] * n,
        },
        index=pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC"),
    )


def test_compute_atr_returns_positive_values():
    df = _make_5min_bars(50)
    atr = compute_atr(df, period=14)
    valid = atr.dropna()
    assert (valid > 0).all()


def test_compute_atr_first_period_is_nan():
    df = _make_5min_bars(50)
    atr = compute_atr(df, period=14)
    assert atr.iloc[:13].isna().all()


def test_analyze_atr_distribution_returns_summary():
    df = _make_5min_bars(100)
    summary = analyze_atr_distribution(df, period=14)
    assert "median_pct" in summary
    assert "mean_pct" in summary
    assert "p25_pct" in summary
    assert "p75_pct" in summary
    assert summary["median_pct"] > 0
