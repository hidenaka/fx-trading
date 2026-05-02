"""PriceFetcher with partition kwarg routes reads to train/ vs holdout/."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from equity_trading.src.data.price_fetcher import PriceFetcher


class _StubBroker:
    """Avoids hitting Alpaca; returns empty DataFrame on fetch."""
    def fetch_bars(self, *args, **kwargs):
        return pd.DataFrame()


def _seed_partition(tmp_path: Path, partition: str, symbol: str, tf: int) -> None:
    p = tmp_path / partition
    p.mkdir(parents=True, exist_ok=True)
    ts = pd.date_range("2023-01-01", periods=10, freq=f"{tf}min", tz="UTC")
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1}, index=ts)
    df.to_parquet(p / f"{symbol}_{tf}min.parquet")


def test_pricefetcher_partition_train_loads_train_data(tmp_path):
    _seed_partition(tmp_path, "train", "TECL", 5)
    fetcher = PriceFetcher(broker=_StubBroker(), cache_dir=tmp_path, partition="train")
    df = fetcher.fetch(symbol="TECL", start=pd.Timestamp("2023-01-01", tz="UTC"),
                       end=pd.Timestamp("2024-01-01", tz="UTC"), timeframe_minutes=5)
    assert len(df) > 0


def test_pricefetcher_partition_train_does_not_leak_holdout(tmp_path):
    """When partition='train', the fetcher reads from train/ — never from holdout/."""
    _seed_partition(tmp_path, "train", "TECL", 5)
    # Even if a holdout file exists with future-dated data, train mode ignores it
    holdout_dir = tmp_path / "holdout"
    holdout_dir.mkdir(parents=True, exist_ok=True)
    ts = pd.date_range("2025-01-01", periods=10, freq="5min", tz="UTC")
    pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1},
                  index=ts).to_parquet(holdout_dir / "TECL_5min.parquet")
    fetcher = PriceFetcher(broker=_StubBroker(), cache_dir=tmp_path, partition="train")
    df = fetcher.fetch(symbol="TECL", start=pd.Timestamp("2023-01-01", tz="UTC"),
                       end=pd.Timestamp("2026-01-01", tz="UTC"), timeframe_minutes=5)
    # Only train rows (2023) should appear — never holdout (2025)
    assert df.index.max() < pd.Timestamp("2024-05-01", tz="UTC")


def test_pricefetcher_default_partition_is_full_for_back_compat(tmp_path):
    """Default partition='full' means use cache_dir/full/ — preserves existing behavior."""
    flat = tmp_path / "full"
    flat.mkdir(parents=True)
    ts = pd.date_range("2023-01-01", periods=10, freq="5min", tz="UTC")
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1}, index=ts)
    df.to_parquet(flat / "TECL_5min.parquet")
    fetcher = PriceFetcher(broker=_StubBroker(), cache_dir=tmp_path)  # no partition
    df_out = fetcher.fetch(symbol="TECL", start=pd.Timestamp("2023-01-01", tz="UTC"),
                            end=pd.Timestamp("2024-01-01", tz="UTC"), timeframe_minutes=5)
    assert len(df_out) > 0
