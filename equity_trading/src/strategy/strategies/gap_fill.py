"""Gap-Fill 戦略 — ギャップダウン日の寄付き反発を狙う long-only.

- 当日寄付き open vs 前営業日 close で -gap_threshold 以下なら signal at bar 0.
- target = prev close
- stop = today_open × (1 - stop_extension)
- 200d MA フィルター（前日まで使用、ルックアヘッドなし）
"""
from __future__ import annotations

import bisect
import datetime

import pandas as pd

from equity_trading.src.data.feature_builder import compute_sma
from equity_trading.src.strategy.base import TradingStrategy


class GapFillStrategy(TradingStrategy):
    name = "gap_fill"

    def compute_entry_signal(
        self,
        bars_5min: pd.DataFrame,
        daily: pd.DataFrame,
        atr_pct: float,
        params: dict,
    ) -> pd.Series:
        gap_threshold = float(params.get("gap_threshold", 0.005))

        # Per-day NY date and bar position
        ny_date = pd.Series(
            bars_5min.index.tz_convert("America/New_York").date,
            index=bars_5min.index,
        )
        bar_pos = bars_5min.groupby(ny_date).cumcount()

        # First bar of day's open per bar
        first_open_per_day = bars_5min.groupby(ny_date)["open"].transform("first")

        # Build prev-close lookup: for each intraday NY date, find the latest
        # daily bar with date strictly before that intraday date.
        sorted_dates, sorted_closes = self._sorted_daily(daily)
        prev_close_per_bar = ny_date.map(
            lambda d: self._lookup_prev_close(d, sorted_dates, sorted_closes)
        )

        # Gap = (today_open - prev_close) / prev_close
        gap = (first_open_per_day - prev_close_per_bar) / prev_close_per_bar
        is_gap_down = (gap <= -gap_threshold).fillna(False)
        is_first_bar = bar_pos == 0

        # 200d MA filter: previous-day close > previous-day SMA200 (no lookahead)
        sma200 = compute_sma(daily["close"], period=200).shift(1)
        prev_close = daily["close"].shift(1)
        daily_above_ma = (prev_close > sma200).reindex(
            bars_5min.index, method="pad"
        ).fillna(False)

        signal = is_first_bar & is_gap_down & daily_above_ma
        return signal.astype(bool)

    def compute_exit_levels(
        self,
        bars_5min: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        atr_pct: float,
        params: dict,
    ) -> tuple[float, float]:
        stop_extension = float(params.get("stop_extension", 0.005))

        # Locate prev close for the entry's NY date
        entry_ts = bars_5min.index[entry_idx]
        entry_ny_date = entry_ts.tz_convert("America/New_York").date()

        # `_daily` may be passed via params for tests; in the runner, the strategy
        # has access via the `daily` argument of compute_entry_signal but NOT here.
        # Workaround: callers (simulator) inject `_daily` through params.
        daily = params.get("_daily")
        if daily is None:
            # Fallback: use today_open and a fixed extension only (no prev_close known)
            today_open = float(bars_5min["open"].iloc[entry_idx])
            return today_open * (1 - stop_extension), today_open  # degenerate; should not happen in production

        sorted_dates, sorted_closes = self._sorted_daily(daily)
        prev_close = self._lookup_prev_close(entry_ny_date, sorted_dates, sorted_closes)
        if prev_close is None:
            prev_close = entry_price

        # today_open: first bar of the entry's NY date
        ny_dates = bars_5min.index.tz_convert("America/New_York").date
        same_day_mask = pd.Series(ny_dates == entry_ny_date, index=bars_5min.index)
        same_day_bars = bars_5min[same_day_mask]
        today_open = float(same_day_bars["open"].iloc[0])

        stop_price = today_open * (1.0 - stop_extension)
        target_price = float(prev_close)
        return stop_price, target_price

    @staticmethod
    def _sorted_daily(daily: pd.DataFrame) -> tuple[list, list]:
        """Return sorted (dates, closes) lists for binary-search lookup."""
        if daily.index.tz is not None:
            dates = list(daily.index.tz_convert("America/New_York").date)
        else:
            dates = list(daily.index.date)
        closes = list(daily["close"].values)
        pairs = sorted(zip(dates, closes), key=lambda p: p[0])
        sorted_dates = [p[0] for p in pairs]
        sorted_closes = [p[1] for p in pairs]
        return sorted_dates, sorted_closes

    @staticmethod
    def _lookup_prev_close(
        intraday_date: datetime.date,
        sorted_dates: list,
        sorted_closes: list,
    ):
        """Return the close of the latest daily bar with date < intraday_date."""
        # bisect_left gives insertion point for intraday_date;
        # the element just before that is the last date < intraday_date.
        idx = bisect.bisect_left(sorted_dates, intraday_date)
        if idx == 0:
            return None
        return sorted_closes[idx - 1]
