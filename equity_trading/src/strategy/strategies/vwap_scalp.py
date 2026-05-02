"""VWAP scalp 戦略 — VWAP 下方乖離リバウンド狙い."""
from __future__ import annotations

import pandas as pd

from equity_trading.src.data.feature_builder import compute_sma, compute_vwap
from equity_trading.src.strategy.base import TradingStrategy


class VWAPScalpStrategy(TradingStrategy):
    """5min VWAP に対する下方乖離が k_entry × atr_pct を超えたらエントリー.

    - VWAP は当該バー時点までの累積出来高加重平均（feature_builder.compute_vwap）
    - 200d MA トレンドフィルター（mean_reversion 等と同じ）
    - exit はデフォルトの ATR スケール
    """

    name = "vwap_scalp"

    def compute_entry_signal(
        self,
        bars_5min: pd.DataFrame,
        daily: pd.DataFrame,
        atr_pct: float,
        params: dict,
    ) -> pd.Series:
        k_entry = float(params.get("k_entry", 1.5))
        threshold_frac = atr_pct * k_entry / 100.0  # fraction (e.g. 0.10% * 1.5 / 100 = 0.0015)

        vwap = compute_vwap(bars_5min)
        deviation = (vwap - bars_5min["close"]) / bars_5min["close"]  # >0 when close below VWAP
        below_vwap_strong = (deviation >= threshold_frac).fillna(False)

        sma200 = compute_sma(daily["close"], period=200)
        daily_above_ma = (daily["close"] > sma200).reindex(
            bars_5min.index, method="pad"
        ).fillna(False)

        signal = below_vwap_strong & daily_above_ma
        return signal.astype(bool)
