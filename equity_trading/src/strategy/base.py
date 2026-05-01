"""戦略の共通インターフェース."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


class TradingStrategy(ABC):
    """全戦略が実装する共通インターフェース.

    Subclass attributes:
        name: 戦略の一意な識別子（例 'mean_reversion', 'trend_follow'）

    Subclass methods:
        compute_entry_signal: エントリーシグナル時系列を返す（True=エントリー）
    """

    name: str = ""

    @abstractmethod
    def compute_entry_signal(
        self,
        bars_5min: pd.DataFrame,
        daily: pd.DataFrame,
        atr_pct: float,
        params: dict,
    ) -> pd.Series:
        """エントリーシグナルを計算.

        Args:
            bars_5min: 5分足 OHLCV
            daily: 日足 OHLCV（200d MA トレンドフィルター用）
            atr_pct: ETFのATR中央値（%）。利用するかは戦略次第
            params: 戦略固有のパラメータ辞書

        Returns:
            bool型のSeries（True=エントリー、False=何もしない）
        """
        ...


@dataclass(frozen=True)
class StrategyResult:
    """1戦略 × 1ETF × 1閾値の検証結果."""

    strategy_name: str
    symbol: str
    threshold: float          # 戦略によっては意味なし（その場合 0.0）
    trade_count: int
    win_count: int
    win_rate: float
    avg_pnl_pct: float

    @property
    def expected_value(self) -> float:
        """期待値 = 取引数 × 平均損益."""
        return self.trade_count * self.avg_pnl_pct
