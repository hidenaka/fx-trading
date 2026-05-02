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

    Returns:
        {'trade_count', 'win_count', 'win_rate', 'avg_pnl_pct'}
    """
    if params is None:
        params = {}

    entry_signal = strategy.compute_entry_signal(bars_5min, daily, atr_pct, params)

    stop_pct = atr_pct * stop_multiplier / 100.0
    target_pct = atr_pct * target_multiplier / 100.0

    closes = bars_5min["close"].values
    n = len(closes)
    trades: list[float] = []
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
                trades.append(-stop_pct - cost_pct / 100.0)
                in_position = False
            elif current >= target_price:
                trades.append(target_pct - cost_pct / 100.0)
                in_position = False
            elif i - entry_idx >= max_hold_bars:
                pnl_pct = (current - entry_price) / entry_price - cost_pct / 100.0
                trades.append(pnl_pct)
                in_position = False

    trade_count = len(trades)
    if trade_count == 0:
        return {
            "trade_count": 0,
            "win_count": 0,
            "win_rate": float("nan"),
            "avg_pnl_pct": float("nan"),
        }

    wins = sum(1 for t in trades if t > 0)
    return {
        "trade_count": trade_count,
        "win_count": wins,
        "win_rate": wins / trade_count,
        "avg_pnl_pct": float(np.mean(trades) * 100.0),
    }
