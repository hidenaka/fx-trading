"""Internal train2/valid2 split for Phase A variant search.

train/ partition spans 2019-05-01 through 2024-04-30. We carve it conceptually:
  train2 = 2019-05-01 → 2021-12-31  (~32 months, exploration / fit)
  valid2 = 2022-01-01 → 2024-04-30  (~28 months, internal validation,
                                      includes 2022 hike cycle)

Daily indicators (200d SMA) need warmup. valid2 reads daily from
(VALID2_START - 365 calendar days) so 200d SMA is non-NaN at VALID2_START.
5-min bars need no warmup (ATR(14) fills in 14 bars).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

TRAIN2_END = "2021-12-31"
VALID2_START = "2022-01-01"
VALID2_END = "2024-04-30"
WARMUP_DAYS_DAILY = 250


def load_train2_bars(root: Path | str, symbol: str, timeframe_minutes: int) -> pd.DataFrame:
    """train2 = train_full[:TRAIN2_END]. Same slicing for 5min and daily."""
    df = _read_train(root, symbol, timeframe_minutes)
    return df.loc[:TRAIN2_END]


def load_valid2_bars(root: Path | str, symbol: str, timeframe_minutes: int) -> pd.DataFrame:
    """valid2 = train_full[VALID2_START:VALID2_END]. Daily prepends 365-day
    calendar warmup so 200d SMA is non-NaN at VALID2_START."""
    df = _read_train(root, symbol, timeframe_minutes)
    if timeframe_minutes == 1440:
        warmup_start = pd.Timestamp(VALID2_START, tz="UTC") - pd.Timedelta(days=365)
        valid2_end = pd.Timestamp(VALID2_END, tz="UTC")
        return df.loc[warmup_start:valid2_end]
    return df.loc[VALID2_START:VALID2_END]


def _read_train(root: Path | str, symbol: str, timeframe_minutes: int) -> pd.DataFrame:
    path = Path(root) / "train" / f"{symbol}_{timeframe_minutes}min.parquet"
    return pd.read_parquet(path)
