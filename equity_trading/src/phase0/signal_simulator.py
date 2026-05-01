"""Phase 0：シグナル発火頻度・勝率を簡易シミュレートする閾値スイープ."""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np
import pandas as pd

from equity_trading.src.data.feature_builder import (
    compute_rsi,
    compute_bollinger_bands,
    compute_vwap,
    compute_volume_ratio,
    compute_momentum_reversal,
    compute_sma,
)


# 仕様書 Strategy Logic セクション準拠の初期重み
DEFAULT_WEIGHTS = {
    "rsi": 0.30,
    "bb": 0.25,
    "vwap": 0.25,
    "volume": 0.10,
    "momentum": 0.10,
}


def _compute_combined_score(bars: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """5シグナルの統合スコアを各バーで計算."""
    rsi = compute_rsi(bars["close"], period=14)
    rsi_score = ((30.0 - rsi) / 30.0).clip(lower=0.0, upper=1.0)

    upper, middle, lower = compute_bollinger_bands(bars["close"], period=20, num_std=2.0)
    sigma = (upper - middle) / 2.0
    bb_score = ((lower - bars["close"]) / sigma).clip(lower=0.0, upper=1.0).fillna(0)

    vwap = compute_vwap(bars)
    vwap_dev = ((vwap - bars["close"]) / bars["close"]).clip(lower=0.0, upper=1.0).fillna(0)

    vol_ratio = compute_volume_ratio(bars["volume"], period=20)
    vol_score = ((vol_ratio / 2.0).clip(lower=0.0, upper=1.0)).fillna(0)
    vol_score = vol_score.where(vol_ratio >= 1.5, 0.0)

    mom_rev = compute_momentum_reversal(bars["close"], lookback=3)
    mom_score = mom_rev.astype(float).fillna(0.0)

    combined = (
        weights["rsi"] * rsi_score.fillna(0)
        + weights["bb"] * bb_score
        + weights["vwap"] * vwap_dev
        + weights["volume"] * vol_score
        + weights["momentum"] * mom_score
    )
    return combined


def simulate_one_threshold(
    bars_5min: pd.DataFrame,
    daily: pd.DataFrame,
    threshold: float,
    atr_pct: float,
    stop_multiplier: float = 1.5,
    target_multiplier: float = 2.4,
    weights: dict[str, float] | None = None,
    cost_pct: float = 0.10,
) -> dict[str, float]:
    """1 つの閾値で簡易バックテスト.

    Returns:
        {'trade_count', 'win_count', 'win_rate', 'avg_pnl_pct'}
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    sma200 = compute_sma(daily["close"], period=200)
    daily_above_ma = (daily["close"] > sma200).reindex(
        bars_5min.index, method="pad"
    ).fillna(False)

    score = _compute_combined_score(bars_5min, weights)

    entry_signal = (score >= threshold) & daily_above_ma

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
            elif i - entry_idx > 78:
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


def sweep_thresholds(
    bars_5min: pd.DataFrame,
    daily: pd.DataFrame,
    thresholds: Sequence[float],
    atr_pct: float,
    stop_multiplier: float = 1.5,
    target_multiplier: float = 2.4,
    weights: dict[str, float] | None = None,
    cost_pct: float = 0.10,
) -> pd.DataFrame:
    """複数の閾値をスイープして結果を DataFrame で返す."""
    rows: list[dict] = []
    for th in thresholds:
        s = simulate_one_threshold(
            bars_5min=bars_5min,
            daily=daily,
            threshold=th,
            atr_pct=atr_pct,
            stop_multiplier=stop_multiplier,
            target_multiplier=target_multiplier,
            weights=weights,
            cost_pct=cost_pct,
        )
        s["threshold"] = th
        rows.append(s)
    return pd.DataFrame(rows)[
        ["threshold", "trade_count", "win_count", "win_rate", "avg_pnl_pct"]
    ]
