"""Internal train2/valid2 split for Phase A variant search."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


def _write_daily(path: Path, start: str, end: str) -> None:
    ts = pd.date_range(start, end, freq="1D", tz="UTC")
    df = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5,
                        "volume": 1000}, index=ts)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)


def _write_5min(path: Path, start: str, end: str) -> None:
    ts = pd.date_range(start, end, freq="5min", tz="UTC")
    df = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5,
                        "volume": 1000}, index=ts)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)


def test_load_train2_daily_ends_at_2021_12_31(tmp_path):
    from equity_trading.src.validation.internal_split import load_train2_bars
    _write_daily(tmp_path / "train" / "TECL_1440min.parquet",
                  "2019-05-01", "2024-04-30")
    df = load_train2_bars(tmp_path, "TECL", timeframe_minutes=1440)
    assert df.index[-1] <= pd.Timestamp("2021-12-31", tz="UTC")
    assert df.index[0] == pd.Timestamp("2019-05-01", tz="UTC")


def test_load_train2_5min_ends_at_2021_12_31(tmp_path):
    from equity_trading.src.validation.internal_split import load_train2_bars
    _write_5min(tmp_path / "train" / "TECL_5min.parquet",
                 "2019-05-01", "2024-04-30")
    df = load_train2_bars(tmp_path, "TECL", timeframe_minutes=5)
    assert df.index[-1] <= pd.Timestamp("2021-12-31 23:59:59", tz="UTC")


def test_load_valid2_daily_prepends_warmup(tmp_path):
    from equity_trading.src.validation.internal_split import load_valid2_bars
    _write_daily(tmp_path / "train" / "TECL_1440min.parquet",
                  "2019-05-01", "2024-04-30")
    df = load_valid2_bars(tmp_path, "TECL", timeframe_minutes=1440)
    # warmup_start = VALID2_START - 365 calendar days = 2021-01-01
    assert df.index[0] <= pd.Timestamp("2021-01-02", tz="UTC")
    assert df.index[0] >= pd.Timestamp("2020-12-31", tz="UTC")
    assert df.index[-1] == pd.Timestamp("2024-04-30", tz="UTC")


def test_load_valid2_5min_no_warmup(tmp_path):
    from equity_trading.src.validation.internal_split import load_valid2_bars
    _write_5min(tmp_path / "train" / "TECL_5min.parquet",
                 "2019-05-01", "2024-04-30")
    df = load_valid2_bars(tmp_path, "TECL", timeframe_minutes=5)
    assert df.index[0] >= pd.Timestamp("2022-01-01", tz="UTC")
    assert df.index[-1] <= pd.Timestamp("2024-04-30 23:59:59", tz="UTC")
