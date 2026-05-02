"""任意の戦略を受け取り、同じ stop/target ロジックでバックテストする.

Exit modeling:
- Long-only.
- Stop hits if bar open <= stop (gap-through, fill at open) or bar low <= stop
  (intra-bar, fill at stop_price). Stop is checked before target (conservative).
- Target hits if bar open >= target (gap-through, fill at open) or bar high >= target
  (intra-bar, fill at target_price).
- Time exit fires at close of bar where (i - entry_idx) == max_hold_bars.
- Entry bar (i == entry_idx) is skipped for exit checks because its low/high
  occurred BEFORE entry fill at close.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from equity_trading.src.strategy.base import TradingStrategy


def _check_exit_at_bar(
    open_p: float,
    high_p: float,
    low_p: float,
    close_p: float,
    stop_price: float,
    target_price: float,
) -> tuple[str, float] | None:
    """Return (exit_type, fill_price) if exit triggers in this bar, else None.

    Conservative: stop wins over target when both sides of bar would trigger.
    Gap-through (open beyond level) fills at open; intra-bar fills at the level.
    """
    # Stop checks first (conservative)
    if open_p <= stop_price:
        return "stop", open_p
    if low_p <= stop_price:
        return "stop", stop_price
    # Then target
    if open_p >= target_price:
        return "target", open_p
    if high_p >= target_price:
        return "target", target_price
    return None


def simulate_strategy(
    strategy: TradingStrategy,
    bars_5min: pd.DataFrame,
    daily: pd.DataFrame,
    atr_pct: float,
    params: dict | None = None,
    stop_multiplier: float = 1.5,
    target_multiplier: float = 2.4,
    cost_pct: float = 0.10,
    max_hold_bars: int = 78,
    return_trades: bool = False,
) -> dict[str, float]:
    """1戦略 × 1ETF でバックテストし、結果を辞書で返す.

    Args:
        strategy: TradingStrategy インスタンス
        bars_5min: 5分足 OHLCV
        daily: 日足 OHLCV
        atr_pct: ETF の ATR 中央値（%）
        params: 戦略固有のパラメータ辞書
        stop_multiplier: 損切り幅 = atr_pct * stop_multiplier （価格対比%）
        target_multiplier: 利確幅 = atr_pct * target_multiplier
        cost_pct: 往復コスト %
        max_hold_bars: 最大保持バー数（時間切れ強制決済）
        return_trades: True の場合 (summary_dict, trades_df) を返す

    Returns:
        {'trade_count', 'win_count', 'win_rate', 'avg_pnl_pct'}
        または return_trades=True の場合 (summary_dict, pd.DataFrame)
    """
    if params is None:
        params = {}

    # Allow per-strategy override of max_hold_bars via params (e.g. EOD-bound strategies).
    if "_max_hold_bars" in params:
        max_hold_bars = int(params["_max_hold_bars"])

    entry_signal = strategy.compute_entry_signal(bars_5min, daily, atr_pct, params)

    opens = bars_5min["open"].to_numpy()
    highs = bars_5min["high"].to_numpy()
    lows = bars_5min["low"].to_numpy()
    closes = bars_5min["close"].to_numpy()
    n = len(closes)
    trade_records: list[dict] = []
    in_position = False
    entry_idx = -1
    entry_price = 0.0
    stop_price = 0.0
    target_price = 0.0

    for i in range(n - 1):
        if not in_position and bool(entry_signal.iloc[i]):
            in_position = True
            entry_idx = i + 1
            if entry_idx >= n:
                break
            entry_price = float(closes[entry_idx])
            merged_params = {**params, "stop_multiplier": stop_multiplier, "target_multiplier": target_multiplier}
            stop_price, target_price = strategy.compute_exit_levels(
                bars_5min, entry_idx, entry_price, atr_pct, merged_params,
            )
        elif in_position and i > entry_idx:
            exit_outcome = _check_exit_at_bar(
                float(opens[i]), float(highs[i]), float(lows[i]), float(closes[i]),
                stop_price, target_price,
            )
            if exit_outcome is not None:
                exit_type, fill_price = exit_outcome
                pnl_fraction = (fill_price - entry_price) / entry_price - cost_pct / 100.0
                trade_records.append({
                    "entry_ts": bars_5min.index[entry_idx],
                    "exit_ts": bars_5min.index[i],
                    "entry_price": entry_price,
                    "exit_price": float(fill_price),
                    "exit_type": exit_type,
                    "bars_held": i - entry_idx,
                    "pnl_pct": pnl_fraction,
                })
                in_position = False
            elif i - entry_idx >= max_hold_bars:
                close_p = float(closes[i])
                pnl_fraction = (close_p - entry_price) / entry_price - cost_pct / 100.0
                trade_records.append({
                    "entry_ts": bars_5min.index[entry_idx],
                    "exit_ts": bars_5min.index[i],
                    "entry_price": entry_price,
                    "exit_price": close_p,
                    "exit_type": "time",
                    "bars_held": i - entry_idx,
                    "pnl_pct": pnl_fraction,
                })
                in_position = False

    trade_count = len(trade_records)
    _trade_cols = ["entry_ts", "exit_ts", "entry_price", "exit_price", "exit_type", "bars_held", "pnl_pct"]

    if trade_count == 0:
        summary = {
            "trade_count": 0,
            "win_count": 0,
            "win_rate": float("nan"),
            "avg_pnl_pct": float("nan"),
        }
        if return_trades:
            return summary, pd.DataFrame(trade_records, columns=_trade_cols)
        return summary

    pnl_values = [r["pnl_pct"] for r in trade_records]
    wins = sum(1 for p in pnl_values if p > 0)
    summary = {
        "trade_count": trade_count,
        "win_count": wins,
        "win_rate": wins / trade_count,
        "avg_pnl_pct": float(np.mean(pnl_values) * 100.0),
    }
    if return_trades:
        return summary, pd.DataFrame(trade_records, columns=_trade_cols)
    return summary


def simulate_single_trade(
    strategy: TradingStrategy,
    bars_5min: pd.DataFrame,
    entry_signal_idx: int,
    atr_pct: float,
    params: dict,
    stop_multiplier: float = 1.5,
    target_multiplier: float = 2.4,
    cost_pct: float = 0.10,
    max_hold_bars: int = 78,
) -> dict | None:
    """Simulate one trade. Returns trade dict or None if not fillable.

    Uses the same realistic low/high/gap exit modeling as simulate_strategy.

    Args:
        strategy: TradingStrategy インスタンス
        bars_5min: 5分足 OHLCV
        entry_signal_idx: シグナルが発火したバーのインデックス
        atr_pct: ETF の ATR 中央値（%）
        params: 戦略固有のパラメータ辞書
        stop_multiplier: 損切り幅 = atr_pct * stop_multiplier
        target_multiplier: 利確幅 = atr_pct * target_multiplier
        cost_pct: 往復コスト %
        max_hold_bars: 最大保持バー数

    Returns:
        dict with entry_ts, exit_ts, entry_price, exit_price, exit_type, bars_held, pnl_pct
        or None if entry can't fill (signal at last bar).
    """
    n = len(bars_5min)
    entry_idx = entry_signal_idx + 1
    if entry_idx >= n:
        return None

    opens = bars_5min["open"].to_numpy()
    highs = bars_5min["high"].to_numpy()
    lows = bars_5min["low"].to_numpy()
    closes = bars_5min["close"].to_numpy()
    entry_price = float(closes[entry_idx])
    merged_params = {**params, "stop_multiplier": stop_multiplier, "target_multiplier": target_multiplier}
    stop_price, target_price = strategy.compute_exit_levels(
        bars_5min=bars_5min,
        entry_idx=entry_idx,
        entry_price=entry_price,
        atr_pct=atr_pct,
        params=merged_params,
    )

    for i in range(entry_idx + 1, n):
        exit_outcome = _check_exit_at_bar(
            float(opens[i]), float(highs[i]), float(lows[i]), float(closes[i]),
            stop_price, target_price,
        )
        if exit_outcome is not None:
            exit_type, fill_price = exit_outcome
            pnl_pct = (fill_price - entry_price) / entry_price - cost_pct / 100.0
            return {
                "entry_ts": bars_5min.index[entry_idx],
                "exit_ts": bars_5min.index[i],
                "entry_price": entry_price,
                "exit_price": float(fill_price),
                "exit_type": exit_type,
                "bars_held": i - entry_idx,
                "pnl_pct": pnl_pct,
            }
        if i - entry_idx >= max_hold_bars:
            close_p = float(closes[i])
            pnl_pct = (close_p - entry_price) / entry_price - cost_pct / 100.0
            return {
                "entry_ts": bars_5min.index[entry_idx],
                "exit_ts": bars_5min.index[i],
                "entry_price": entry_price,
                "exit_price": close_p,
                "exit_type": "time",
                "bars_held": i - entry_idx,
                "pnl_pct": pnl_pct,
            }

    # Reached end of bars without a clean exit
    return None
