"""分析駆動戦略（mean_reversion + 時間帯/SPY地合いフィルタ）.

診断レポートの結果を反映した戦略：
- threshold 0.30（mean_reversion より緩めて頻度を上げる）
- NY 11-12時除外（ランチ時間帯はWR 0%）
- SPY 同日寄り比上昇のときのみ許可（forward-only）
- 200d MA トレンドフィルター（mean_reversion 由来）
- 当日下落フィルタは入れない（分析で逆に勝率高かった）
"""
from __future__ import annotations

import pandas as pd

from equity_trading.src.strategy.base import TradingStrategy
from equity_trading.src.strategy.strategies.mean_reversion import MeanReversionStrategy


class AnalysisDrivenReversionStrategy(TradingStrategy):
    name = "analysis_driven_reversion"

    def __init__(self) -> None:
        self._base = MeanReversionStrategy()

    def compute_entry_signal(
        self,
        bars_5min: pd.DataFrame,
        daily: pd.DataFrame,
        atr_pct: float,
        params: dict,
    ) -> pd.Series:
        # 既定値：閾値 0.30
        local_params = dict(params)
        local_params.setdefault("threshold", 0.30)

        base_signal = self._base.compute_entry_signal(bars_5min, daily, atr_pct, local_params)

        block_hours = set(params.get("block_lunch_hours", [11, 12]))
        ny_hours = pd.Series(
            bars_5min.index.tz_convert("America/New_York").hour,
            index=bars_5min.index,
        )
        ok_hours = ~ny_hours.isin(block_hours)

        spy_5min = params.get("_spy_5min")
        require_spy_up = bool(params.get("require_spy_up", True))
        if require_spy_up and spy_5min is not None:
            ok_spy = self._spy_up_intraday(bars_5min.index, spy_5min)
        else:
            ok_spy = pd.Series(True, index=bars_5min.index)

        signal = base_signal & ok_hours & ok_spy
        return signal.astype(bool)

    @staticmethod
    def _spy_up_intraday(target_index: pd.DatetimeIndex, spy_bars: pd.DataFrame) -> pd.Series:
        """各 target バー時点で SPY が同日寄り比プラスかを返す（forward-only）.

        Args:
            target_index: 評価対象のタイムスタンプ列（tz-aware）
            spy_bars: SPY 5min OHLCV（'open', 'close' 必須）

        Returns:
            target_index と同じ長さの bool Series。
            SPY の最新 close（pad 方式で過去側のみ参照）が同日寄り値より上なら True。
        """
        spy_ny_date = pd.Series(
            spy_bars.index.tz_convert("America/New_York").date,
            index=spy_bars.index,
        )
        spy_first_open = spy_bars.groupby(spy_ny_date)["open"].transform("first")
        spy_change = (spy_bars["close"] - spy_first_open) / spy_first_open
        # reindex with pad → 過去のみ参照、forward-only
        spy_change_at_target = spy_change.reindex(target_index, method="pad")
        return (spy_change_at_target > 0).fillna(False)
