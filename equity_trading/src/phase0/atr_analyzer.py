"""Phase 0：ETF別 ATR(14, 5min) の中央値・分布を測定."""
from __future__ import annotations

import pandas as pd


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """ATR (Average True Range) を計算.

    True Range = max(high-low, |high-prev_close|, |low-prev_close|)
    ATR = TRのWilder's smoothing（指数移動平均、α=1/period）

    Args:
        df: high/low/close カラムを持つ DataFrame
        period: 平滑化期間

    Returns:
        ATR の絶対値時系列。最初の period-1 本は NaN。
    """
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    return atr


def analyze_atr_distribution(df: pd.DataFrame, period: int = 14) -> dict[str, float]:
    """ATR分布の要約統計（価格対比%）を返す.

    Returns:
        {
            'median_pct': float,  # ATR中央値 / 平均価格 * 100
            'mean_pct': float,
            'p25_pct': float,
            'p75_pct': float,
        }
    """
    atr = compute_atr(df, period=period).dropna()
    avg_price = df["close"].mean()
    pct = (atr / avg_price) * 100.0

    return {
        "median_pct": float(pct.median()),
        "mean_pct": float(pct.mean()),
        "p25_pct": float(pct.quantile(0.25)),
        "p75_pct": float(pct.quantile(0.75)),
    }
