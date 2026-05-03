"""Opening Range Breakout 戦略.

寄り付き 30 分（or_window_bars = 6）の高値抜けを当日初回のみ取る.
exit はデフォルトで stop=OR_low / target=OR_high+1R (R = OR_high-OR_low).
200d MA フィルターあり.

`stop_mult` / `target_mult` を params で渡せば変更可能。validation framework
で variant 探索する用途。デフォルトの V0 値は 7-yr in-sample の保守選択であり、
holdout 検証を経ない限り別 variant にデフォルトを切り替えてはならない
(2026-05-03: V2.1 = stop_mult=0.25 / target_mult=2.0 は holdout で REJECT 済).
"""
from __future__ import annotations

import pandas as pd

from equity_trading.src.data.feature_builder import compute_sma
from equity_trading.src.strategy.base import TradingStrategy


class OpeningRangeBreakoutStrategy(TradingStrategy):
    name = "opening_range_breakout"

    def compute_entry_signal(
        self,
        bars_5min: pd.DataFrame,
        daily: pd.DataFrame,
        atr_pct: float,
        params: dict,
    ) -> pd.Series:
        or_window = int(params.get("or_window_bars", 6))

        ny_date = pd.Series(
            bars_5min.index.tz_convert("America/New_York").date,
            index=bars_5min.index,
        )
        bar_pos = bars_5min.groupby(ny_date).cumcount()

        # OR_high per day (max of first or_window bars)
        or_high_per_bar = (
            bars_5min["high"]
            .where(bar_pos < or_window)
            .groupby(ny_date)
            .transform(lambda g: g.max())
        )

        after_or = bar_pos >= or_window
        breakout = (bars_5min["high"] > or_high_per_bar) & after_or

        # First breakout per day only
        cum_breakout_today = breakout.groupby(ny_date).cumsum()
        first_breakout = breakout & (cum_breakout_today == 1)

        # 200d MA filter (use prev-day close to avoid lookahead)
        sma200 = compute_sma(daily["close"], period=200).shift(1)
        daily_close_prev = daily["close"].shift(1)
        daily_above_ma = (daily_close_prev > sma200).reindex(
            bars_5min.index, method="pad"
        ).fillna(False)

        signal = first_breakout & daily_above_ma

        vix_halve_threshold = params.get("vix_halve_threshold")
        if vix_halve_threshold is not None and "_vix_daily" in params:
            vix = params["_vix_daily"]
            ny_date = pd.Series(
                bars_5min.index.tz_convert("America/New_York").date,
                index=bars_5min.index,
            )
            vix_dict = {ts.date(): float(c) for ts, c in vix["close"].items()}
            vix_high_mask = ny_date.map(vix_dict).fillna(0) > vix_halve_threshold
            signal = signal & ~vix_high_mask
        return signal.astype(bool)

    def compute_exit_levels(
        self,
        bars_5min: pd.DataFrame,
        entry_idx: int,
        entry_price: float,
        atr_pct: float,
        params: dict,
    ) -> tuple[float, float]:
        or_window = int(params.get("or_window_bars", 6))
        stop_mult = float(params.get("stop_mult", 0.0))     # stop = OR_low + stop_mult*range
        target_mult = float(params.get("target_mult", 1.0))  # target = OR_high + target_mult*range

        # Find which NY date the entry bar is on
        entry_ts = bars_5min.index[entry_idx]
        entry_ny_date = entry_ts.tz_convert("America/New_York").date()

        # Locate that day's OR bars
        ny_dates = bars_5min.index.tz_convert("America/New_York").date
        same_day_mask = pd.Series(ny_dates == entry_ny_date, index=bars_5min.index)
        same_day_bars = bars_5min[same_day_mask]
        or_bars = same_day_bars.iloc[:or_window]

        or_high = float(or_bars["high"].max())
        or_low = float(or_bars["low"].min())
        range_height = or_high - or_low

        stop_price = or_low + stop_mult * range_height
        target_price = or_high + target_mult * range_height
        return stop_price, target_price
