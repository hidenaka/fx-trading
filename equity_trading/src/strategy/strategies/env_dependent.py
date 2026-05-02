"""環境依存リバージョン戦略（MeanReversion + 時間帯/当日下落率フィルター）."""
from __future__ import annotations

import pandas as pd

from equity_trading.src.strategy.base import TradingStrategy
from equity_trading.src.strategy.strategies.mean_reversion import MeanReversionStrategy


class EnvDependentReversionStrategy(TradingStrategy):
    """MeanReversion に以下のフィルターを追加：
    - 米国市場オープン後30分以内は禁止
    - 米国市場クローズ前30分以内は禁止
    - 当日累計下落率 > 1% なら禁止（パニック相場除外）
    """

    name = "env_dependent_reversion"

    def __init__(self) -> None:
        self._base = MeanReversionStrategy()

    def compute_entry_signal(
        self,
        bars_5min: pd.DataFrame,
        daily: pd.DataFrame,
        atr_pct: float,
        params: dict,
    ) -> pd.Series:
        base_signal = self._base.compute_entry_signal(bars_5min, daily, atr_pct, params)
        ok_env = self._compute_env_filter(bars_5min)
        return (base_signal & ok_env).astype(bool)

    @staticmethod
    def _compute_env_filter(bars: pd.DataFrame) -> pd.Series:
        """各バーで環境条件を満たすか判定."""
        idx = bars.index

        # 各バーが属する米東時間の日付（DST境界も自動考慮）
        date_only = pd.Index(idx.tz_convert("America/New_York").date)
        date_series = pd.Series(date_only, index=idx)

        # 各バーの「同日内最初のバー時刻」「最後のバー時刻」を計算
        first_per_day = idx.to_series().groupby(date_series).transform("min")
        last_per_day = idx.to_series().groupby(date_series).transform("max")

        elapsed_minutes = (idx - pd.DatetimeIndex(first_per_day)).total_seconds() / 60.0
        until_close = (pd.DatetimeIndex(last_per_day) - idx).total_seconds() / 60.0

        ok_after_open = pd.Series(elapsed_minutes >= 30, index=idx)
        ok_before_close = pd.Series(until_close >= 30, index=idx)

        # 当日下落率 > 1% を除外（始値からの下落率）
        first_open = bars.groupby(date_series)["open"].transform("first")
        intraday_change = (bars["close"] - first_open) / first_open
        ok_no_panic = intraday_change > -0.01

        return ok_after_open & ok_before_close & ok_no_panic
