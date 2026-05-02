"""ライブ実行用シグナル評価器."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from equity_trading.src.strategy.base import TradingStrategy


@dataclass(frozen=True)
class LiveSignal:
    """エントリー判定結果."""

    should_enter: bool
    stop_price: float | None
    target_price: float | None
    entry_reference_price: float | None


def evaluate_live_signal(
    strategy: TradingStrategy,
    bars_5min: pd.DataFrame,
    daily: pd.DataFrame,
    atr_pct: float,
    params: dict,
    bar_index: int = -1,
) -> LiveSignal:
    """戦略を1回実行して bar_index 時点でのエントリー判定を返す.

    Args:
        bar_index: 評価する bar のインデックス。-1 = 最新、0 = 最初（gap_fill 用）
    """
    signal_series = strategy.compute_entry_signal(bars_5min, daily, atr_pct, params)
    should_enter = bool(signal_series.iloc[bar_index])
    if not should_enter:
        return LiveSignal(False, None, None, None)

    # Resolve negative index to absolute for compute_exit_levels
    abs_index = bar_index if bar_index >= 0 else len(bars_5min) + bar_index
    entry_ref = float(bars_5min["close"].iloc[bar_index])

    stop_price, target_price = strategy.compute_exit_levels(
        bars_5min=bars_5min,
        entry_idx=abs_index,
        entry_price=entry_ref,
        atr_pct=atr_pct,
        params=params,
    )
    return LiveSignal(
        should_enter=True,
        stop_price=float(stop_price),
        target_price=float(target_price),
        entry_reference_price=entry_ref,
    )
