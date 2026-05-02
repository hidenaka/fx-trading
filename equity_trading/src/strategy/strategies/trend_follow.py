"""トレンドフォロー戦略（200d MA + 直近高値ブレイク + RSI>50）."""
from __future__ import annotations

import pandas as pd

from equity_trading.src.data.feature_builder import compute_rsi, compute_sma
from equity_trading.src.strategy.base import TradingStrategy


class TrendFollowStrategy(TradingStrategy):
    """200d MA 上 + 直近 N 本高値更新 + RSI > 50 で買い."""

    name = "trend_follow"

    def compute_entry_signal(
        self,
        bars_5min: pd.DataFrame,
        daily: pd.DataFrame,
        atr_pct: float,
        params: dict,
    ) -> pd.Series:
        breakout_period = int(params.get("breakout_period", 20))
        rsi_threshold = float(params.get("rsi_threshold", 50.0))

        sma200 = compute_sma(daily["close"], period=200)
        daily_above_ma = (daily["close"] > sma200).reindex(
            bars_5min.index, method="pad"
        ).fillna(False)

        rolling_max = bars_5min["high"].rolling(window=breakout_period).max()
        breakout = bars_5min["high"] >= rolling_max

        rsi = compute_rsi(bars_5min["close"], period=14)
        rsi_strong = rsi > rsi_threshold

        signal = daily_above_ma & breakout & rsi_strong.fillna(False)
        return signal.astype(bool)
