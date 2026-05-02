"""Intraday Momentum (Heston-Korajczyk-Sadka 2014).

Hypothesis: the first 30-minute return on broad-index ETFs predicts the
direction of the last 30-minute return on the same trading day.

Reference: Heston / Korajczyk / Sadka, "Intraday Patterns in the Cross-Section
of Stock Returns" (J. Finance 2010); follow-up "Intraday Momentum: The First
Half-Hour Return Predicts the Last Half-Hour Return" (2014).

Long-only adaptation: if first_30m_return > threshold, enter at the bar
indicated by `entry_bar_pos` (signal-bar; entry fills next bar's close), hold
for `_max_hold_bars` bars (default 5 = ~25 min, last 30 min of session).
"""
from __future__ import annotations

import pandas as pd

from equity_trading.src.strategy.base import TradingStrategy


class IntradayMomentumStrategy(TradingStrategy):
    name = "intraday_momentum"

    def compute_entry_signal(
        self,
        bars_5min: pd.DataFrame,
        daily: pd.DataFrame,
        atr_pct: float,
        params: dict,
    ) -> pd.Series:
        threshold = float(params.get("threshold", 0.001))
        entry_bar_pos = int(params.get("entry_bar_pos", 71))
        first_30m_bars = int(params.get("first_30m_bars", 6))

        ny_date = pd.Series(
            bars_5min.index.tz_convert("America/New_York").date,
            index=bars_5min.index,
        )
        bar_pos = bars_5min.groupby(ny_date).cumcount()

        first_open = bars_5min.groupby(ny_date)["open"].transform("first")

        def _close_at_bar(s: pd.Series) -> float:
            if len(s) >= first_30m_bars:
                return float(s.iloc[first_30m_bars - 1])
            return float("nan")

        first_30m_close = bars_5min.groupby(ny_date)["close"].transform(_close_at_bar)
        first_30m_return = (first_30m_close - first_open) / first_open

        is_bullish = (first_30m_return > threshold).fillna(False)
        is_signal_bar = (bar_pos == entry_bar_pos)
        signal = is_bullish & is_signal_bar
        return signal.astype(bool)

    def compute_exit_levels(
        self,
        bars_5min: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        atr_pct: float,
        params: dict,
    ) -> tuple[float, float]:
        """HKS holds for a fixed window with no tactical stops in the original spec.

        We keep wide ATR-multiples (configurable via stop_atr_mult / target_atr_mult)
        so time-exit dominates while still capping catastrophic moves.
        """
        stop_mult = float(params.get("stop_atr_mult", 8.0))
        target_mult = float(params.get("target_atr_mult", 16.0))
        stop_pct = atr_pct * stop_mult / 100.0
        target_pct = atr_pct * target_mult / 100.0
        return entry_price * (1.0 - stop_pct), entry_price * (1.0 + target_pct)
