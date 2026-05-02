"""Pre-FOMC Drift Strategy (Lucca-Moench 2015 / J.Finance).

Hypothesis: in the 24 hours preceding scheduled FOMC announcements, broad-
index US equity ETFs drift up by ~+49 bps on average. The effect is well-
documented from 1994-2011 and weakened post-2015 but is not zero.

Long-only adaptation: at the start of the trading day immediately before the
announcement (signal fires at bar 0, entry fills at bar 1, ~9:35 ET), hold
into the FOMC day until just before the 14:00 ET announcement.

In our 5-min bar model, that is approximately:
  - Pre-FOMC day: bars 1..77 (entry at bar 1, ~9:35 ET; bar 77 close ~16:00 ET)
  - FOMC day:    bars 0..52 (~9:30..14:00 ET)
Time-exit at ~bar 53 of FOMC day = bar (77 - 1) + 53 = 129 from entry → max_hold_bars=129.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from equity_trading.src.strategy.base import TradingStrategy


class PreFOMCDriftStrategy(TradingStrategy):
    name = "pre_fomc_drift"

    # FOMC announcement dates (the second day of each meeting; statement ~14:00 ET).
    # Source: Federal Reserve official meeting calendar.
    DEFAULT_FOMC_DATES: list[dt.date] = [
        # 2019
        dt.date(2019, 5, 1), dt.date(2019, 6, 19), dt.date(2019, 7, 31),
        dt.date(2019, 9, 18), dt.date(2019, 10, 30), dt.date(2019, 12, 11),
        # 2020
        dt.date(2020, 1, 29), dt.date(2020, 3, 3), dt.date(2020, 3, 15),
        dt.date(2020, 3, 18), dt.date(2020, 4, 29), dt.date(2020, 6, 10),
        dt.date(2020, 7, 29), dt.date(2020, 9, 16), dt.date(2020, 11, 5),
        dt.date(2020, 12, 16),
        # 2021
        dt.date(2021, 1, 27), dt.date(2021, 3, 17), dt.date(2021, 4, 28),
        dt.date(2021, 6, 16), dt.date(2021, 7, 28), dt.date(2021, 9, 22),
        dt.date(2021, 11, 3), dt.date(2021, 12, 15),
        # 2022
        dt.date(2022, 1, 26), dt.date(2022, 3, 16), dt.date(2022, 5, 4),
        dt.date(2022, 6, 15), dt.date(2022, 7, 27), dt.date(2022, 9, 21),
        dt.date(2022, 11, 2), dt.date(2022, 12, 14),
        # 2023
        dt.date(2023, 2, 1), dt.date(2023, 3, 22), dt.date(2023, 5, 3),
        dt.date(2023, 6, 14), dt.date(2023, 7, 26), dt.date(2023, 9, 20),
        dt.date(2023, 11, 1), dt.date(2023, 12, 13),
        # 2024
        dt.date(2024, 1, 31), dt.date(2024, 3, 20), dt.date(2024, 5, 1),
        dt.date(2024, 6, 12), dt.date(2024, 7, 31), dt.date(2024, 9, 18),
        dt.date(2024, 11, 7), dt.date(2024, 12, 18),
        # 2025
        dt.date(2025, 1, 29), dt.date(2025, 3, 19), dt.date(2025, 5, 7),
        dt.date(2025, 6, 18), dt.date(2025, 7, 30), dt.date(2025, 9, 17),
        dt.date(2025, 10, 29), dt.date(2025, 12, 10),
        # 2026
        dt.date(2026, 1, 28), dt.date(2026, 3, 18), dt.date(2026, 4, 29),
    ]

    def compute_entry_signal(
        self,
        bars_5min: pd.DataFrame,
        daily: pd.DataFrame,
        atr_pct: float,
        params: dict,
    ) -> pd.Series:
        fomc_dates = params.get("fomc_dates", self.DEFAULT_FOMC_DATES)
        entry_bar_pos = int(params.get("entry_bar_pos", 0))
        vix_min = params.get("vix_min")  # if set, only fire when prev-day VIX close > vix_min
        vix_daily = params.get("_vix_daily")  # DataFrame with daily VIX (index = UTC ts)

        ny_date = pd.Series(
            bars_5min.index.tz_convert("America/New_York").date,
            index=bars_5min.index,
        )
        bar_pos = bars_5min.groupby(ny_date).cumcount()

        unique_dates = sorted(set(ny_date.tolist()))
        date_idx = {d: i for i, d in enumerate(unique_dates)}
        pre_fomc_set: set[dt.date] = set()
        for fomc in fomc_dates:
            if fomc in date_idx and date_idx[fomc] > 0:
                pre_fomc_set.add(unique_dates[date_idx[fomc] - 1])

        is_pre_fomc = ny_date.isin(pre_fomc_set)
        is_signal_bar = (bar_pos == entry_bar_pos)
        signal = is_pre_fomc & is_signal_bar

        if vix_min is not None and vix_daily is not None and len(vix_daily) > 0:
            # Compute prev-day VIX close for each row's NY date (no lookahead).
            vix_dates = list(vix_daily.index.tz_convert("America/New_York").date) \
                if vix_daily.index.tz is not None else list(vix_daily.index.date)
            vix_closes = vix_daily["close"].to_numpy()
            import bisect
            vix_prev_by_date: dict[dt.date, float] = {}
            for d in unique_dates:
                idx = bisect.bisect_left(vix_dates, d)
                if idx > 0:
                    vix_prev_by_date[d] = float(vix_closes[idx - 1])
                else:
                    vix_prev_by_date[d] = float("nan")
            vix_per_bar = ny_date.map(vix_prev_by_date)
            vix_ok = (vix_per_bar > float(vix_min)).fillna(False)
            signal = signal & vix_ok

        return signal.astype(bool)

    def compute_exit_levels(
        self,
        bars_5min: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        atr_pct: float,
        params: dict,
    ) -> tuple[float, float]:
        """Wide ±5% emergency stops; rely on time exit to capture the 24-h drift."""
        return entry_price * 0.95, entry_price * 1.05
