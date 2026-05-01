"""テクニカル指標の純粋関数群（pandas ベース）."""
from __future__ import annotations

import pandas as pd


def compute_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index を計算.

    Args:
        prices: 終値の時系列
        period: 計算期間（典型値 14）

    Returns:
        RSI 値（0〜100）の時系列。最初の period-1 本は NaN。
    """
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    # Wilder's smoothing（指数移動平均、α = 1/period）
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = rsi.where(avg_loss != 0, 100.0)
    rsi = rsi.where(~((avg_gain == 0) & (avg_loss == 0)), pd.NA)
    return rsi
