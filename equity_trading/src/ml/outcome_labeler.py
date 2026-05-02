"""候補シグナルに勝敗ラベルを付与."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from equity_trading.src.ml.candidate_dataset import CandidateSignal
from equity_trading.src.phase0.strategy_simulator import simulate_single_trade
from equity_trading.src.strategy.strategies.gap_fill import GapFillStrategy
from equity_trading.src.strategy.strategies.mean_reversion import MeanReversionStrategy
from equity_trading.src.strategy.strategies.vwap_scalp import VWAPScalpStrategy


_STRATEGY_REGISTRY = {
    "gap_fill": GapFillStrategy,
    "mean_reversion": MeanReversionStrategy,
    "vwap_scalp": VWAPScalpStrategy,
}


@dataclass(frozen=True)
class LabeledCandidate:
    """A CandidateSignal plus its simulated outcome."""

    signal: CandidateSignal
    win: bool          # pnl_pct > 0
    pnl_pct: float     # fraction (e.g. -0.00192 = -0.192%)
    exit_type: str     # 'stop', 'target', 'time'
    bars_held: int


def label_candidates(
    candidates: list[CandidateSignal],
    bars_5min: pd.DataFrame,
    daily: pd.DataFrame,
    atr_pct: float,
    base_params: dict,
    spy_5min: pd.DataFrame | None = None,
) -> list[LabeledCandidate]:
    """For each candidate, simulate the trade outcome using its strategy's
    compute_exit_levels, then label win/loss + P&L.

    Args:
        candidates: CandidateSignal のリスト（ML1 の出力）
        bars_5min: 5分足 OHLCV
        daily: 日足 OHLCV
        atr_pct: ETF の ATR 中央値（%）
        base_params: エグジット計算に使う標準パラメータ
        spy_5min: SPY の5分足（現在未使用、将来の拡張用）

    Returns:
        LabeledCandidate のリスト（シミュレート不可のものはスキップ）
    """
    if not candidates:
        return []

    labeled: list[LabeledCandidate] = []
    strategy_cache: dict[str, object] = {}

    for cand in candidates:
        cls = _STRATEGY_REGISTRY.get(cand.strategy_name)
        if cls is None:
            continue
        if cand.strategy_name not in strategy_cache:
            strategy_cache[cand.strategy_name] = cls()
        strategy = strategy_cache[cand.strategy_name]

        params = dict(base_params)
        if cand.strategy_name == "gap_fill":
            params["_daily"] = daily

        trade = simulate_single_trade(
            strategy=strategy,
            bars_5min=bars_5min,
            entry_signal_idx=cand.bar_index,
            atr_pct=atr_pct,
            params=params,
        )
        if trade is None:
            continue

        labeled.append(LabeledCandidate(
            signal=cand,
            win=bool(trade["pnl_pct"] > 0),
            pnl_pct=float(trade["pnl_pct"]),
            exit_type=str(trade["exit_type"]),
            bars_held=int(trade["bars_held"]),
        ))

    return labeled
