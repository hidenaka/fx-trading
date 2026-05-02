"""平均回帰戦略（マルチシグナル合致）."""
from __future__ import annotations

import pandas as pd

from equity_trading.src.data.feature_builder import (
    compute_bollinger_bands,
    compute_momentum_reversal,
    compute_rsi,
    compute_sma,
    compute_volume_ratio,
    compute_vwap,
)
from equity_trading.src.strategy.base import TradingStrategy


DEFAULT_WEIGHTS = {
    "rsi": 0.30,
    "bb": 0.25,
    "vwap": 0.25,
    "volume": 0.10,
    "momentum": 0.10,
}


class MeanReversionStrategy(TradingStrategy):
    """RSI/BB/VWAP/出来高/勢い反転 の合致スコアでエントリー判定."""

    name = "mean_reversion"

    def compute_entry_signal(
        self,
        bars_5min: pd.DataFrame,
        daily: pd.DataFrame,
        atr_pct: float,
        params: dict,
    ) -> pd.Series:
        threshold = float(params.get("threshold", 0.6))
        weights = params.get("weights", DEFAULT_WEIGHTS)

        score = self.compute_combined_score(bars_5min, weights)

        # トレンドフィルター
        sma200 = compute_sma(daily["close"], period=200)
        daily_above_ma = (daily["close"] > sma200).reindex(
            bars_5min.index, method="pad"
        ).fillna(False)

        signal = (score >= threshold) & daily_above_ma
        return signal.astype(bool)

    def compute_combined_score(self, bars: pd.DataFrame, weights: dict) -> pd.Series:
        rsi = compute_rsi(bars["close"], period=14)
        rsi_score = ((30.0 - rsi) / 30.0).clip(lower=0.0, upper=1.0)

        upper, middle, lower = compute_bollinger_bands(bars["close"], period=20, num_std=2.0)
        sigma = (upper - middle) / 2.0
        bb_score = ((lower - bars["close"]) / sigma).clip(lower=0.0, upper=1.0).fillna(0)

        vwap = compute_vwap(bars)
        vwap_dev = ((vwap - bars["close"]) / bars["close"]).clip(lower=0.0, upper=1.0).fillna(0)

        vol_ratio = compute_volume_ratio(bars["volume"], period=20)
        vol_score = (vol_ratio / 2.0).clip(lower=0.0, upper=1.0).fillna(0)
        vol_score = vol_score.where(vol_ratio >= 1.5, 0.0)

        mom_rev = compute_momentum_reversal(bars["close"], lookback=3)
        mom_score = mom_rev.astype(float).fillna(0.0)

        return (
            weights["rsi"] * rsi_score.fillna(0)
            + weights["bb"] * bb_score
            + weights["vwap"] * vwap_dev
            + weights["volume"] * vol_score
            + weights["momentum"] * mom_score
        )
