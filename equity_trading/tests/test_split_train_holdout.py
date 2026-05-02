"""Test the partition script splits parquet by date correctly."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest


def _make_full_parquet(root: Path, symbol: str, tf: int) -> None:
    src = root / "full"
    src.mkdir(parents=True, exist_ok=True)
    ts = pd.date_range("2023-01-01", "2025-12-31", freq=f"{tf}min", tz="UTC")
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1}, index=ts)
    df.to_parquet(src / f"{symbol}_{tf}min.parquet")


def test_split_creates_train_and_holdout_partitions(tmp_path):
    _make_full_parquet(tmp_path, "TECL", 5)
    _make_full_parquet(tmp_path, "TECL", 1440)

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from equity_trading.scripts.split_train_holdout import split_partitions

    split_partitions(data_root=tmp_path, holdout_cutoff="2024-05-01",
                     symbols=["TECL"], timeframes=[5, 1440])

    train_5 = pd.read_parquet(tmp_path / "train" / "TECL_5min.parquet")
    holdout_5 = pd.read_parquet(tmp_path / "holdout" / "TECL_5min.parquet")
    assert train_5.index.max() < pd.Timestamp("2024-05-01", tz="UTC")
    assert holdout_5.index.min() >= pd.Timestamp("2024-05-01", tz="UTC")
    assert len(train_5) + len(holdout_5) > 0
    # manifest written
    assert (tmp_path / "manifest.json").exists()
