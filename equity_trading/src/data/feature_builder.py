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


def compute_bollinger_bands(
    prices: pd.Series,
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """ボリンジャーバンドを計算.

    Args:
        prices: 終値の時系列
        period: 移動平均期間
        num_std: バンド幅の標準偏差倍数

    Returns:
        (upper_band, middle_band, lower_band) のタプル
    """
    middle = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std(ddof=0)
    upper = middle + num_std * std
    lower = middle - num_std * std
    return upper, middle, lower


def compute_vwap(df: pd.DataFrame) -> pd.Series:
    """累積VWAPを計算.

    入力DataFrameは high/low/close/volume カラムを持つこと。
    典型価格（high+low+close）/3 を出来高で重み付けして累積平均。
    呼び出し側で「当日分のみ」を渡すことで「当日VWAP」になる。

    Args:
        df: ['high', 'low', 'close', 'volume'] カラムを持つ DataFrame

    Returns:
        累積VWAP の時系列。volume が 0 のときは NaN。
    """
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = typical * df["volume"]
    cum_pv = pv.cumsum()
    cum_v = df["volume"].cumsum()
    vwap = cum_pv / cum_v
    return vwap.where(cum_v > 0, pd.NA)
