"""任意の戦略を受け取り、同じ stop/target ロジックでバックテストする."""
from __future__ import annotations

import numpy as np
import pandas as pd

from equity_trading.src.strategy.base import TradingStrategy


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

    entry_signal = strategy.compute_entry_signal(bars_5min, daily, atr_pct, params)

    stop_pct = atr_pct * stop_multiplier / 100.0
    target_pct = atr_pct * target_multiplier / 100.0

    closes = bars_5min["close"].values
    n = len(closes)
    trade_records: list[dict] = []
    in_position = False
    entry_idx = -1
    entry_price = 0.0

    for i in range(n - 1):
        if not in_position and bool(entry_signal.iloc[i]):
            in_position = True
            entry_idx = i + 1
            if entry_idx >= n:
                break
            entry_price = closes[entry_idx]
        elif in_position:
            current = closes[i]
            stop_price = entry_price * (1 - stop_pct)
            target_price = entry_price * (1 + target_pct)
            if current <= stop_price:
                pnl_fraction = -stop_pct - cost_pct / 100.0
                trade_records.append({
                    "entry_ts": bars_5min.index[entry_idx],
                    "exit_ts": bars_5min.index[i],
                    "entry_price": entry_price,
                    "exit_price": current,
                    "exit_type": "stop",
                    "bars_held": i - entry_idx,
                    "pnl_pct": pnl_fraction,
                })
                in_position = False
            elif current >= target_price:
                pnl_fraction = target_pct - cost_pct / 100.0
                trade_records.append({
                    "entry_ts": bars_5min.index[entry_idx],
                    "exit_ts": bars_5min.index[i],
                    "entry_price": entry_price,
                    "exit_price": current,
                    "exit_type": "target",
                    "bars_held": i - entry_idx,
                    "pnl_pct": pnl_fraction,
                })
                in_position = False
            elif i - entry_idx >= max_hold_bars:
                pnl_fraction = (current - entry_price) / entry_price - cost_pct / 100.0
                trade_records.append({
                    "entry_ts": bars_5min.index[entry_idx],
                    "exit_ts": bars_5min.index[i],
                    "entry_price": entry_price,
                    "exit_price": current,
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
