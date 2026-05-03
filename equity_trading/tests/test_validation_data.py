"""EvaluationContext access tests."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from equity_trading.src.validation.data import (
    EvaluationContext,
    HoldoutAccessError,
    load_train_bars,
)


def _write_parquet(path: Path, ts_start: str, n: int = 10) -> None:
    ts = pd.date_range(ts_start, periods=n, freq="5min", tz="UTC")
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1}, index=ts)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)


def _setup_data_root(tmp_path: Path) -> Path:
    root = tmp_path / "prices"
    _write_parquet(root / "train" / "TECL_5min.parquet", "2023-01-01")
    _write_parquet(root / "holdout" / "TECL_5min.parquet", "2025-01-01")
    return root


def test_load_train_bars_reads_train_partition(tmp_path):
    root = _setup_data_root(tmp_path)
    df = load_train_bars(root, "TECL", timeframe_minutes=5)
    assert len(df) == 10
    assert df.index[0].year == 2023


def test_evaluation_context_can_load_holdout(tmp_path):
    root = _setup_data_root(tmp_path)
    log_path = tmp_path / "holdout_access.jsonl"
    with EvaluationContext(
        root=root, variant_id="v_test", reason="gate:oos",
        access_log_path=log_path,
    ) as ctx:
        df = ctx.load_holdout_bars("TECL", timeframe_minutes=5)
    assert len(df) == 10
    assert df.index[0].year == 2025
    # access logged
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["variant_id"] == "v_test"
    assert record["reason"] == "gate:oos"
    assert record["symbol"] == "TECL"
    assert record["timeframe_minutes"] == 5


def test_holdout_access_outside_evaluation_context_raises(tmp_path):
    root = _setup_data_root(tmp_path)
    with pytest.raises(HoldoutAccessError):
        load_train_bars(root, "TECL", timeframe_minutes=5, partition="holdout")


def test_evaluation_context_appends_to_access_log(tmp_path):
    root = _setup_data_root(tmp_path)
    log_path = tmp_path / "log.jsonl"
    log_path.write_text(json.dumps({"variant_id": "old", "reason": "x", "symbol": "Y", "timeframe_minutes": 5, "ts_utc": "old"}) + "\n")
    with EvaluationContext(root=root, variant_id="v", reason="r", access_log_path=log_path) as ctx:
        ctx.load_holdout_bars("TECL", timeframe_minutes=5)
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 2  # appended, did not overwrite


def _write_daily_parquet(path: Path, ts_start: str, n: int) -> None:
    ts = pd.date_range(ts_start, periods=n, freq="1D", tz="UTC")
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1}, index=ts)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)


def test_load_holdout_daily_prepends_warmup(tmp_path):
    root = tmp_path / "prices"
    # train: 300 daily bars ending 2024-04-30
    _write_daily_parquet(root / "train" / "TECL_1440min.parquet", "2023-07-06", n=300)
    # holdout: 100 daily bars starting 2024-05-01
    _write_daily_parquet(root / "holdout" / "TECL_1440min.parquet", "2024-05-01", n=100)
    log_path = tmp_path / "holdout_access.jsonl"
    with EvaluationContext(root=root, variant_id="v", reason="gate:oos",
                           access_log_path=log_path) as ctx:
        df = ctx.load_holdout_bars("TECL", timeframe_minutes=1440)
    # 250 warmup + 100 holdout = 350 (no duplicates expected)
    assert len(df) == 350
    # First row is 250 days before holdout start
    assert df.index[0] == pd.Timestamp("2023-08-25", tz="UTC")
    # Last row is the last holdout day
    assert df.index[-1] == pd.Timestamp("2024-08-08", tz="UTC")
    # Access log records the warmup
    record = json.loads(log_path.read_text().strip().splitlines()[0])
    assert record["source"] == "holdout+warmup"
    assert record["warmup_rows"] == 250


def test_load_holdout_5min_unchanged_by_warmup(tmp_path):
    root = _setup_data_root(tmp_path)  # existing helper
    log_path = tmp_path / "holdout_access.jsonl"
    with EvaluationContext(root=root, variant_id="v", reason="gate:oos",
                           access_log_path=log_path) as ctx:
        df = ctx.load_holdout_bars("TECL", timeframe_minutes=5)
    assert len(df) == 10  # original holdout count, no warmup
    record = json.loads(log_path.read_text().strip().splitlines()[0])
    assert record["source"] == "holdout"
    assert "warmup_rows" not in record
