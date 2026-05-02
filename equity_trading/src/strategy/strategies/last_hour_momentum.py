"""Last-Hour Momentum: prior day's last 30-min return predicts today's open.

Hypothesis (Quantified Strategies, others): if SPY/QQQ closed strongly in
the last 30 min of the previous session, today opens with continued buying
pressure. Long-only adaptation: if yesterday's bars 71..77 showed a
positive return, enter at today's bar 0 close (~9:35 ET) and exit by EOD.
"""
from __future__ import annotations

import pandas as pd

from equity_trading.src.strategy.base import TradingStrategy


class LastHourMomentumStrategy(TradingStrategy):
    name = "last_hour_momentum"

    def compute_entry_signal(
        self,
        bars_5min: pd.DataFrame,
        daily: pd.DataFrame,
        atr_pct: float,
        params: dict,
    ) -> pd.Series:
        threshold = float(params.get("threshold", 0.001))
        last_hour_start_bar = int(params.get("last_hour_start_bar", 72))  # bar 72 = 15:30 ET
        last_hour_end_bar = int(params.get("last_hour_end_bar", 77))      # bar 77 = 15:55 ET (close=16:00)

        ny_date = pd.Series(
            bars_5min.index.tz_convert("America/New_York").date,
            index=bars_5min.index,
        )

        # Per-day last-30-min return: close[bar 77] / close[bar 72] - 1
        def _last_30m_return(group: pd.DataFrame) -> float:
            if len(group) <= last_hour_end_bar:
                return float("nan")
            start_close = float(group["close"].iloc[last_hour_start_bar])
            end_close = float(group["close"].iloc[last_hour_end_bar])
            if start_close <= 0:
                return float("nan")
            return (end_close - start_close) / start_close

        per_day_lh = bars_5min.groupby(ny_date).apply(_last_30m_return)
        # Map prior day's last-30m return onto each row of today
        unique_dates = sorted(set(ny_date.tolist()))
        prev_lh_by_date: dict = {}
        for i, d in enumerate(unique_dates):
            if i > 0:
                prev_d = unique_dates[i - 1]
                prev_lh_by_date[d] = per_day_lh.get(prev_d, float("nan"))
            else:
                prev_lh_by_date[d] = float("nan")
        prev_lh_per_bar = ny_date.map(prev_lh_by_date)

        bar_pos = bars_5min.groupby(ny_date).cumcount()

        # Signal at bar 0 (today's first RTH bar = 9:30 ET); fill at bar 1 close.
        is_signal_bar = bar_pos == 0
        is_bullish_yesterday = (prev_lh_per_bar > threshold).fillna(False)
        signal = is_signal_bar & is_bullish_yesterday
        return signal.astype(bool)

    def compute_exit_levels(
        self,
        bars_5min: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        atr_pct: float,
        params: dict,
    ) -> tuple[float, float]:
        """Wide ±3% emergency stops; rely on time exit."""
        return entry_price * 0.97, entry_price * 1.03
