"""Walk-forward time-series CV splits."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pandas as pd


@dataclass(frozen=True)
class WalkForwardSplit:
    fold_id: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    train_indices: list[int]
    test_indices: list[int]


def walk_forward_splits(
    timestamps: list[pd.Timestamp],
    train_window_days: int = 180,
    test_window_days: int = 30,
    step_days: int = 30,
    purge_gap_days: int = 1,
) -> list[WalkForwardSplit]:
    if not timestamps:
        return []

    sorted_ts = sorted(timestamps)
    overall_start = sorted_ts[0]
    overall_end = sorted_ts[-1]

    train_window = timedelta(days=train_window_days)
    test_window = timedelta(days=test_window_days)
    purge = timedelta(days=purge_gap_days)
    step = timedelta(days=step_days)

    folds: list[WalkForwardSplit] = []
    fold_id = 0
    train_start = overall_start

    while True:
        train_end = train_start + train_window
        test_start = train_end + purge
        test_end = test_start + test_window

        if test_end > overall_end + timedelta(seconds=1):
            break

        train_indices = [
            i for i, t in enumerate(timestamps)
            if train_start <= t < train_end
        ]
        test_indices = [
            i for i, t in enumerate(timestamps)
            if test_start <= t < test_end
        ]

        if train_indices and test_indices:
            folds.append(WalkForwardSplit(
                fold_id=fold_id,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                train_indices=train_indices,
                test_indices=test_indices,
            ))
            fold_id += 1

        train_start = train_start + step

    return folds
