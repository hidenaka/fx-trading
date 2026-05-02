"""Overnight Hold Strategy — buy at the regular-session close, sell at next open.

Hypothesis: most of the long-term equity premium accrues OVERNIGHT, not
during regular hours. Cliff Asness, AQR, and many others document that
SPY's overnight returns from close-to-open average +5-7%/year while its
intraday (open-to-close) returns are roughly flat or slightly negative
since 2000.

Long-only adaptation: at the bar one before the session close (signal at
bar 76, fill at bar 77 close = 16:00 ET), enter long. Time-exit at the
first bar of the next trading day (entry+1 bar = next-day's bar 0 close
≈ 9:35 ET).

Backtest holds ~17.5 hours wall-clock through the overnight window;
live execution would be a market-on-close (MOC) buy and a market-on-open
(MOO) sell — supported by Alpaca paper.
"""
from __future__ import annotations

import pandas as pd

from equity_trading.src.strategy.base import TradingStrategy


class OvernightHoldStrategy(TradingStrategy):
    name = "overnight_hold"

    def compute_entry_signal(
        self,
        bars_5min: pd.DataFrame,
        daily: pd.DataFrame,
        atr_pct: float,
        params: dict,
    ) -> pd.Series:
        # Default RTH bars per day = 78. Bar 77 = 15:55-16:00 ET (close at 16:00).
        # Signal at bar 76 (15:50-15:55 close=15:55) → fill at bar 77 close = 16:00.
        entry_signal_bar = int(params.get("entry_signal_bar", 76))

        ny_date = pd.Series(
            bars_5min.index.tz_convert("America/New_York").date,
            index=bars_5min.index,
        )
        bar_pos = bars_5min.groupby(ny_date).cumcount()
        return (bar_pos == entry_signal_bar).astype(bool)

    def compute_exit_levels(
        self,
        bars_5min: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        atr_pct: float,
        params: dict,
    ) -> tuple[float, float]:
        """Wide ±5% emergency stops; rely on time-exit (1 bar = next-day's first RTH close)."""
        return entry_price * 0.95, entry_price * 1.05
