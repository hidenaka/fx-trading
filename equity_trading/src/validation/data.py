"""Train/holdout data access with explicit holdout audit trail.

Train data is freely accessible via load_train_bars. Holdout data is
only readable inside an EvaluationContext, which appends a record to
holdout_access.jsonl on every read. This makes "I accidentally trained
on the holdout" physically impossible from properly written code.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import pandas as pd


class HoldoutAccessError(RuntimeError):
    """Raised when code attempts to read holdout data without EvaluationContext."""


def _parquet_filename(symbol: str, timeframe_minutes: int) -> str:
    return f"{symbol}_{timeframe_minutes}min.parquet"


def load_train_bars(
    root: Path | str,
    symbol: str,
    timeframe_minutes: int,
    partition: Literal["train", "holdout"] = "train",
) -> pd.DataFrame:
    """Load bars from the train partition. partition='holdout' is rejected
    here — use EvaluationContext for that path.
    """
    if partition != "train":
        raise HoldoutAccessError(
            "Direct access to non-train partition is forbidden. "
            "Use EvaluationContext to read holdout data."
        )
    root = Path(root)
    path = root / "train" / _parquet_filename(symbol, timeframe_minutes)
    return pd.read_parquet(path)


class EvaluationContext:
    """Context manager that grants holdout-read permission while logging access.

    For ``timeframe_minutes == 1440``, the returned DataFrame is prefixed with the
    last ``WARMUP_DAYS_DAILY`` train rows so 200-day indicators are non-NaN at
    holdout_start; callers must filter trades by holdout_start
    (see ``runner._collect_trades``).

    Usage:
        with EvaluationContext(root, variant_id, reason="gate:oos") as ctx:
            df = ctx.load_holdout_bars("TECL", timeframe_minutes=5)
    """

    WARMUP_DAYS_DAILY = 250  # 200d SMA + 50-day safety margin

    def __init__(
        self,
        root: Path | str,
        variant_id: str,
        reason: str,
        access_log_path: Path | str | None = None,
    ):
        self.root = Path(root)
        self.variant_id = variant_id
        self.reason = reason
        self.access_log_path = (
            Path(access_log_path) if access_log_path is not None
            else self.root / "holdout_access.jsonl"
        )

    def __enter__(self) -> "EvaluationContext":
        return self

    def __exit__(self, exc_type, exc, tb):
        return False  # don't suppress exceptions

    def load_holdout_bars(self, symbol: str, timeframe_minutes: int) -> pd.DataFrame:
        """Read the symbol's holdout parquet. For 1440min (daily), prepend the last
        WARMUP_DAYS_DAILY rows of the train parquet so long-window indicators are
        warmed; for 5min, return the holdout parquet as-is. Every read is logged
        with source ('holdout' or 'holdout+warmup') and row counts."""
        path_holdout = self.root / "holdout" / _parquet_filename(symbol, timeframe_minutes)
        df_holdout = pd.read_parquet(path_holdout)
        if timeframe_minutes == 1440:
            df_warmup = self._load_warmup_daily(symbol)
            df = pd.concat([df_warmup, df_holdout]).sort_index()
            df = df[~df.index.duplicated(keep="last")]
            self._log_access(symbol, timeframe_minutes,
                              source="holdout+warmup",
                              rows=len(df), warmup_rows=len(df_warmup))
            return df
        self._log_access(symbol, timeframe_minutes,
                          source="holdout", rows=len(df_holdout))
        return df_holdout

    def _load_warmup_daily(self, symbol: str) -> pd.DataFrame:
        path_train = self.root / "train" / _parquet_filename(symbol, 1440)
        df = pd.read_parquet(path_train)
        return df.tail(self.WARMUP_DAYS_DAILY)

    def _log_access(self, symbol: str, timeframe_minutes: int, *,
                     source: str, rows: int, warmup_rows: int | None = None) -> None:
        record = {
            "variant_id": self.variant_id,
            "reason": self.reason,
            "symbol": symbol,
            "timeframe_minutes": timeframe_minutes,
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "rows": rows,
        }
        if warmup_rows is not None:
            record["warmup_rows"] = warmup_rows
        self.access_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.access_log_path.open("a") as f:
            f.write(json.dumps(record) + "\n")
