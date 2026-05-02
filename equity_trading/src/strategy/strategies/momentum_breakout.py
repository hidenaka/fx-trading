"""モメンタム・ブレイクアウト戦略（直近高値抜け + 出来高急増）."""
from __future__ import annotations

import pandas as pd

from equity_trading.src.data.feature_builder import compute_sma, compute_volume_ratio
from equity_trading.src.strategy.base import TradingStrategy


class MomentumBreakoutStrategy(TradingStrategy):
    """直近 N 本の高値ブレイクと出来高 1.5 倍以上で買い."""

    name = "momentum_breakout"

    def compute_entry_signal(
        self,
        bars_5min: pd.DataFrame,
        daily: pd.DataFrame,
        atr_pct: float,
        params: dict,
    ) -> pd.Series:
        breakout_period = int(params.get("breakout_period", 78))
        volume_multiplier = float(params.get("volume_multiplier", 1.5))

        sma200 = compute_sma(daily["close"], period=200)
        daily_above_ma = (daily["close"] > sma200).reindex(
            bars_5min.index, method="pad"
        ).fillna(False)

        prev_max = bars_5min["high"].shift(1).rolling(window=breakout_period - 1).max()
        breakout = bars_5min["high"] > prev_max

        vol_ratio = compute_volume_ratio(bars_5min["volume"], period=20)
        vol_strong = (vol_ratio >= volume_multiplier).fillna(False)

        signal = daily_above_ma & breakout & vol_strong
        return signal.astype(bool)
