"""One-time data partition: split data/prices/full/SYMBOL_*min.parquet
into train/ (ts < cutoff) and holdout/ (ts >= cutoff), then compute manifest.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from equity_trading.src.validation.manifest import compute_manifest


def split_partitions(
    data_root: Path | str,
    holdout_cutoff: str,
    symbols: Sequence[str],
    timeframes: Sequence[int],
) -> None:
    data_root = Path(data_root)
    cutoff = pd.Timestamp(holdout_cutoff, tz="UTC")
    train_dir = data_root / "train"
    holdout_dir = data_root / "holdout"
    train_dir.mkdir(parents=True, exist_ok=True)
    holdout_dir.mkdir(parents=True, exist_ok=True)

    for symbol in symbols:
        for tf in timeframes:
            src = data_root / "full" / f"{symbol}_{tf}min.parquet"
            if not src.exists():
                print(f"[skip] {src} not found")
                continue
            df = pd.read_parquet(src)
            train_df = df[df.index < cutoff]
            holdout_df = df[df.index >= cutoff]
            train_df.to_parquet(train_dir / f"{symbol}_{tf}min.parquet")
            holdout_df.to_parquet(holdout_dir / f"{symbol}_{tf}min.parquet")
            print(f"[ok] {symbol} {tf}min: train n={len(train_df)}, holdout n={len(holdout_df)}")

    m = compute_manifest(data_root, holdout_cutoff=holdout_cutoff)
    m.write(data_root / "manifest.json")
    print(f"[saved] manifest.json with {len(m.file_hashes)} entries")


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    data_root = project_root / "data" / "prices"
    full_dir = data_root / "full"
    if not full_dir.exists():
        print(f"[ERROR] {full_dir} does not exist. Move existing parquet files there first:")
        print(f"  mkdir -p {full_dir}")
        print(f"  mv {data_root}/*.parquet {full_dir}/")
        return 1
    symbols = ["TECL", "TQQQ", "TNA", "UPRO", "UDOW"]
    timeframes = [5, 1440]
    split_partitions(data_root=data_root, holdout_cutoff="2024-05-01",
                     symbols=symbols, timeframes=timeframes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
