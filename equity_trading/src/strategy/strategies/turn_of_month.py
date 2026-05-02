"""Turn-of-Month Drift Strategy (Lakonishok-Smidt 1988, McConnell-Xu 2008).

Hypothesis: equity returns are concentrated on the last trading day of a
month plus the first 3 trading days of the next month, averaging
+10–20 bps/day vs ~0 elsewhere. The effect has weakened post-2015
but persists in some windows.

Long-only adaptation: at the start of each TOM day (signal at bar 0,
fill at bar 1, ~9:35 ET), hold to near close (~15:45 ET).
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from equity_trading.src.strategy.base import TradingStrategy


class TurnOfMonthStrategy(TradingStrategy):
    name = "turn_of_month"

    def compute_entry_signal(
        self,
        bars_5min: pd.DataFrame,
        daily: pd.DataFrame,
        atr_pct: float,
        params: dict,
    ) -> pd.Series:
        entry_bar_pos = int(params.get("entry_bar_pos", 0))

        ny_date = pd.Series(
            bars_5min.index.tz_convert("America/New_York").date,
            index=bars_5min.index,
        )
        bar_pos = bars_5min.groupby(ny_date).cumcount()

        unique_dates = sorted(set(ny_date.tolist()))
        tom_set: set[dt.date] = set()
        for i, d in enumerate(unique_dates):
            # Last trading day of month: next available trading day is in a different month.
            if i + 1 < len(unique_dates) and unique_dates[i + 1].month != d.month:
                tom_set.add(d)
                # First 3 trading days of the next month
                for j in range(1, 4):
                    if i + j < len(unique_dates):
                        tom_set.add(unique_dates[i + j])

        is_tom = ny_date.isin(tom_set)
        is_signal_bar = (bar_pos == entry_bar_pos)
        signal = is_tom & is_signal_bar
        return signal.astype(bool)

    def compute_exit_levels(
        self,
        bars_5min: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        atr_pct: float,
        params: dict,
    ) -> tuple[float, float]:
        """Wide ±3% emergency stops; rely on time exit for intraday hold."""
        return entry_price * 0.97, entry_price * 1.03
