from datetime import datetime, timezone

import pandas as pd
import pytest

from equity_trading.src.ml.walk_forward import WalkForwardSplit, walk_forward_splits


def _ts_list(start_iso: str, end_iso: str, freq_min: int = 60) -> list[pd.Timestamp]:
    """Generate hourly timestamps from start to end (UTC)."""
    return list(pd.date_range(start_iso, end_iso, freq=f"{freq_min}min", tz="UTC"))


def test_walk_forward_split_dataclass_is_frozen():
    s = WalkForwardSplit(
        fold_id=0,
        train_start=pd.Timestamp("2024-01-01", tz="UTC"),
        train_end=pd.Timestamp("2024-07-01", tz="UTC"),
        test_start=pd.Timestamp("2024-07-02", tz="UTC"),
        test_end=pd.Timestamp("2024-08-01", tz="UTC"),
        train_indices=[0, 1, 2],
        test_indices=[3, 4],
    )
    with pytest.raises((AttributeError, ValueError)):
        s.fold_id = 1  # type: ignore


def test_walk_forward_basic_2_year_range():
    """2-year range with default 180-day train, 30-day test, 30-day step."""
    ts = _ts_list("2024-01-01", "2026-01-01", freq_min=60 * 24)  # daily
    splits = walk_forward_splits(
        timestamps=ts,
        train_window_days=180, test_window_days=30, step_days=30, purge_gap_days=1,
    )
    # Expect ~24 folds: (2*365 - 180 - 1 - 30) / 30 ≈ 18+ folds
    assert len(splits) >= 10
    # Each fold has non-empty train and test
    for s in splits:
        assert len(s.train_indices) > 0
        assert len(s.test_indices) > 0


def test_walk_forward_test_strictly_after_train():
    """Every test timestamp must be > every train timestamp."""
    ts = _ts_list("2024-01-01", "2026-01-01", freq_min=60 * 24)
    splits = walk_forward_splits(timestamps=ts)
    for s in splits:
        train_max = max(ts[i] for i in s.train_indices)
        test_min = min(ts[i] for i in s.test_indices)
        assert train_max < test_min, f"leakage in fold {s.fold_id}: train_max={train_max} test_min={test_min}"


def test_walk_forward_purge_gap_respected():
    """purge_gap_days=2 → at least 2 days between train_end and test_start."""
    ts = _ts_list("2024-01-01", "2026-01-01", freq_min=60 * 24)
    splits = walk_forward_splits(
        timestamps=ts,
        train_window_days=180, test_window_days=30, step_days=30, purge_gap_days=2,
    )
    for s in splits:
        gap = (s.test_start - s.train_end).total_seconds() / 86400
        assert gap >= 2 - 0.01  # allow small rounding


def test_walk_forward_steps_forward_correctly():
    ts = _ts_list("2024-01-01", "2026-01-01", freq_min=60 * 24)
    splits = walk_forward_splits(
        timestamps=ts,
        train_window_days=180, test_window_days=30, step_days=30, purge_gap_days=1,
    )
    # Adjacent folds: train_start[i+1] - train_start[i] == step_days
    for a, b in zip(splits, splits[1:]):
        gap_days = (b.train_start - a.train_start).total_seconds() / 86400
        assert abs(gap_days - 30) < 0.5


def test_walk_forward_too_few_timestamps_returns_empty():
    """If timestamps span less than train+test window, return empty."""
    ts = _ts_list("2024-01-01", "2024-02-01", freq_min=60 * 24)
    splits = walk_forward_splits(
        timestamps=ts,
        train_window_days=180, test_window_days=30,
    )
    assert splits == []


def test_walk_forward_unsorted_input_handled():
    """Function should work even if timestamps are not pre-sorted (or document the requirement).
    For now, assume sorted. Test with sorted input only, but no ordering bug."""
    ts = _ts_list("2024-01-01", "2026-01-01", freq_min=60 * 24)
    splits = walk_forward_splits(timestamps=ts)
    assert all(s.train_start <= s.train_end for s in splits)
    assert all(s.test_start <= s.test_end for s in splits)
