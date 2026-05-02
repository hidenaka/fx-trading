"""マルチタイムフレーム合致戦略（5min + 15min + 1h RSI 過売り合致）."""
from __future__ import annotations

import pandas as pd

from equity_trading.src.data.feature_builder import compute_rsi, compute_sma
from equity_trading.src.strategy.base import TradingStrategy


class MultiTimeframeStrategy(TradingStrategy):
    """5min RSI<30 かつ 15min RSI<35 かつ 1h RSI<40 の合致でエントリー."""

    name = "multi_timeframe"

    def compute_entry_signal(
        self,
        bars_5min: pd.DataFrame,
        daily: pd.DataFrame,
        atr_pct: float,
        params: dict,
    ) -> pd.Series:
        rsi_5_th = float(params.get("rsi_5min_threshold", 30.0))
        rsi_15_th = float(params.get("rsi_15min_threshold", 35.0))
        rsi_60_th = float(params.get("rsi_60min_threshold", 40.0))

        sma200 = compute_sma(daily["close"], period=200)
        daily_above_ma = (daily["close"] > sma200).reindex(
            bars_5min.index, method="pad"
        ).fillna(False)

        rsi_5 = compute_rsi(bars_5min["close"], period=14)
        cond_5 = (rsi_5 < rsi_5_th).fillna(False)

        # 15min RSI（5min を 3本ずつまとめる）— shift(1) to prevent look-ahead
        bars_15 = bars_5min["close"].resample("15min").last().dropna()
        rsi_15 = compute_rsi(bars_15, period=14).shift(1)
        cond_15_5min = (rsi_15 < rsi_15_th).reindex(bars_5min.index, method="pad").fillna(False)

        bars_60 = bars_5min["close"].resample("60min").last().dropna()
        rsi_60 = compute_rsi(bars_60, period=14).shift(1)
        cond_60_5min = (rsi_60 < rsi_60_th).reindex(bars_5min.index, method="pad").fillna(False)

        signal = daily_above_ma & cond_5 & cond_15_5min & cond_60_5min
        return signal.astype(bool)
