"""候補シグナル + 特徴量抽出（ML 学習用データセット生成）."""
from __future__ import annotations

import bisect
from dataclasses import dataclass

import numpy as np
import pandas as pd

from equity_trading.src.data.feature_builder import (
    compute_bollinger_bands,
    compute_rsi,
    compute_sma,
    compute_volume_ratio,
    compute_vwap,
)
from equity_trading.src.strategy.strategies.gap_fill import GapFillStrategy
from equity_trading.src.strategy.strategies.mean_reversion import (
    DEFAULT_WEIGHTS as MR_WEIGHTS,
    MeanReversionStrategy,
)
from equity_trading.src.strategy.strategies.vwap_scalp import VWAPScalpStrategy


SUPPORTED_STRATEGIES = {"gap_fill", "mean_reversion", "vwap_scalp"}


@dataclass(frozen=True)
class CandidateSignal:
    """One candidate entry point with computed features (no outcome yet)."""

    timestamp: pd.Timestamp
    symbol: str
    strategy_name: str
    features: dict
    bar_index: int


def generate_candidates(
    bars_5min: pd.DataFrame,
    daily: pd.DataFrame,
    spy_5min: pd.DataFrame | None,
    symbol: str,
    strategy_name: str,
    relaxed_params: dict,
) -> list[CandidateSignal]:
    """For one (symbol, strategy), generate candidates by running the strategy
    with RELAXED params, then for each True bar collect features.

    Forward-only: features at signal time use only bars up to and including that time.
    """
    if strategy_name not in SUPPORTED_STRATEGIES:
        raise ValueError(
            f"Unsupported strategy_name: {strategy_name!r}. "
            f"Supported: {SUPPORTED_STRATEGIES}"
        )

    if len(bars_5min) < 30 or len(daily) < 30:
        return []

    # Run the strategy with relaxed params to get signal series
    if strategy_name == "gap_fill":
        strategy = GapFillStrategy()
    elif strategy_name == "mean_reversion":
        strategy = MeanReversionStrategy()
    else:
        strategy = VWAPScalpStrategy()

    signal_series = strategy.compute_entry_signal(
        bars_5min, daily, atr_pct=0.10, params=relaxed_params,
    )

    # Pre-compute all feature arrays across the full bars frame
    feature_arrays = _precompute_feature_arrays(
        bars_5min, daily, spy_5min, strategy_name, relaxed_params,
    )

    # gap_fill is an at-open strategy — only valid during market hours (9:00-9:59 NY)
    ny_hours_arr = bars_5min.index.tz_convert("America/New_York").hour

    candidates: list[CandidateSignal] = []
    signal_arr = signal_series.to_numpy()
    for i, fired in enumerate(signal_arr):
        if not fired:
            continue
        # gap_fill signals must be during market open hour (9 AM NY)
        if strategy_name == "gap_fill" and ny_hours_arr[i] != 9:
            continue
        feat = {}
        for k, arr in feature_arrays.items():
            v = arr[i]
            feat[k] = float(v) if not pd.isna(v) else float("nan")
        candidates.append(CandidateSignal(
            timestamp=bars_5min.index[i],
            symbol=symbol,
            strategy_name=strategy_name,
            features=feat,
            bar_index=i,
        ))

    return candidates


def _precompute_feature_arrays(
    bars: pd.DataFrame,
    daily: pd.DataFrame,
    spy_5min: pd.DataFrame | None,
    strategy_name: str,
    relaxed_params: dict,
) -> dict:
    n = len(bars)

    # NY timezone index
    ny_idx = bars.index.tz_convert("America/New_York")
    ny_hour = ny_idx.hour.to_numpy().astype(float)
    day_of_week = ny_idx.day_of_week.to_numpy().astype(float)

    # RSI
    rsi = compute_rsi(bars["close"], period=14).to_numpy().astype(float)

    # Bollinger Bands %B
    bb_upper, bb_middle, bb_lower = compute_bollinger_bands(bars["close"], period=20, num_std=2.0)
    bb_band_width = (bb_upper - bb_lower)
    bb_band_width_safe = bb_band_width.where(bb_band_width > 0, np.nan)
    bb_pct_b = ((bars["close"] - bb_lower) / bb_band_width_safe).to_numpy().astype(float)

    # VWAP deviation (consistent with how strategies compute it)
    vwap = compute_vwap(bars).to_numpy().astype(float)
    close_arr = bars["close"].to_numpy().astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        vwap_dev = np.where(close_arr > 0, (vwap - close_arr) / close_arr, np.nan)

    # Volume ratio
    volume_ratio = compute_volume_ratio(bars["volume"], period=20).to_numpy().astype(float)

    # Per-day intraday stats
    ny_date_arr = ny_idx.date  # numpy array of date objects
    ny_date_series = pd.Series(ny_date_arr, index=bars.index)
    first_open_per_day = bars.groupby(ny_date_series)["open"].transform("first").to_numpy().astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        intraday_change = np.where(
            first_open_per_day > 0,
            (close_arr - first_open_per_day) / first_open_per_day,
            np.nan,
        )

    # Gap pct: today_open vs prev daily close
    sorted_dates, sorted_closes = _sorted_daily_lists(daily)
    gap_pct = np.array([
        _safe_gap(d, first_open_per_day[i], sorted_dates, sorted_closes)
        for i, d in enumerate(ny_date_arr)
    ])

    # Daily features (use prev day to avoid lookahead)
    if daily.index.tz is not None:
        daily_ny_dates = list(daily.index.tz_convert("America/New_York").date)
    else:
        daily_ny_dates = list(daily.index.date)
    daily_closes = daily["close"].to_numpy().astype(float)
    daily_sma200 = compute_sma(daily["close"], period=200).to_numpy().astype(float)

    daily_ma_distance = np.full(n, np.nan)
    daily_5d_return = np.full(n, np.nan)
    daily_20d_return = np.full(n, np.nan)

    sorted_daily_dates = sorted(daily_ny_dates)
    for i, d in enumerate(ny_date_arr):
        prev_idx = bisect.bisect_left(sorted_daily_dates, d) - 1
        if prev_idx >= 0:
            pc = daily_closes[prev_idx]
            ps = daily_sma200[prev_idx]
            if not np.isnan(ps) and ps > 0:
                daily_ma_distance[i] = (pc - ps) / ps
            if prev_idx >= 5:
                p5 = daily_closes[prev_idx - 5]
                if p5 > 0:
                    daily_5d_return[i] = (pc - p5) / p5
            if prev_idx >= 20:
                p20 = daily_closes[prev_idx - 20]
                if p20 > 0:
                    daily_20d_return[i] = (pc - p20) / p20

    # ATR ratio (5min short-term / longer-term vol regime)
    high = bars["high"].to_numpy().astype(float)
    low = bars["low"].to_numpy().astype(float)
    prev_close_shifted = np.empty_like(close_arr)
    prev_close_shifted[0] = close_arr[0]
    prev_close_shifted[1:] = close_arr[:-1]
    tr = np.maximum.reduce([
        high - low,
        np.abs(high - prev_close_shifted),
        np.abs(low - prev_close_shifted),
    ])
    tr_series = pd.Series(tr)
    atr_14 = tr_series.rolling(14).mean().to_numpy().astype(float)
    atr_78 = tr_series.rolling(78).mean().to_numpy().astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        atr_ratio = np.where(atr_78 > 0, atr_14 / atr_78, np.nan)

    # SPY intraday (forward-only pad)
    if spy_5min is not None and len(spy_5min) > 0:
        spy_ny_date = pd.Series(
            spy_5min.index.tz_convert("America/New_York").date,
            index=spy_5min.index,
        )
        spy_first_open = spy_5min.groupby(spy_ny_date)["open"].transform("first")
        spy_close = spy_5min["close"]
        with np.errstate(invalid="ignore", divide="ignore"):
            spy_change = (spy_close - spy_first_open) / spy_first_open
        spy_intraday_at_target = (
            spy_change.reindex(bars.index, method="pad").fillna(0.0).to_numpy().astype(float)
        )
    else:
        spy_intraday_at_target = np.zeros(n)

    # Bars since open today
    bars_since_open = bars.groupby(ny_date_series).cumcount().to_numpy().astype(float)

    # Score value (strategy-specific continuous score)
    if strategy_name == "mean_reversion":
        mr = MeanReversionStrategy()
        score_series = mr.compute_combined_score(bars, MR_WEIGHTS)
        score_value = score_series.to_numpy().astype(float)
    elif strategy_name == "gap_fill":
        score_value = np.abs(gap_pct)
    elif strategy_name == "vwap_scalp":
        # Use vwap_dev as the score (how far below VWAP, clipped positive)
        score_value = np.clip(vwap_dev, 0.0, None)
    else:
        score_value = np.zeros(n)

    return {
        "ny_hour": ny_hour,
        "day_of_week": day_of_week,
        "rsi_14": rsi,
        "bb_pct_b": bb_pct_b,
        "vwap_dev": vwap_dev,
        "volume_ratio": volume_ratio,
        "intraday_change": intraday_change,
        "gap_pct": gap_pct,
        "daily_ma_distance": daily_ma_distance,
        "daily_5d_return": daily_5d_return,
        "daily_20d_return": daily_20d_return,
        "atr_ratio_5min": atr_ratio,
        "spy_intraday": spy_intraday_at_target,
        "bars_since_open": bars_since_open,
        "score_value": score_value,
    }


def _sorted_daily_lists(daily: pd.DataFrame) -> tuple[list, list]:
    """Return (sorted_dates, sorted_closes) lists for binary-search lookup."""
    if daily.index.tz is not None:
        dates = list(daily.index.tz_convert("America/New_York").date)
    else:
        dates = list(daily.index.date)
    closes = list(daily["close"].values.astype(float))
    pairs = sorted(zip(dates, closes), key=lambda p: p[0])
    return [p[0] for p in pairs], [p[1] for p in pairs]


def _safe_gap(
    today_date,
    today_open: float,
    sorted_dates: list,
    sorted_closes: list,
) -> float:
    """Compute (today_open - prev_close) / prev_close with binary search. No lookahead."""
    idx = bisect.bisect_left(sorted_dates, today_date) - 1
    if idx < 0:
        return float("nan")
    pc = sorted_closes[idx]
    if pc <= 0 or np.isnan(today_open):
        return float("nan")
    return (today_open - pc) / pc
