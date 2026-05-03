"""Compute and print correlation matrices for the 5 leveraged ETFs in our universe.

Used to populate static figures in equity_trading/docs/risk_disclosure.md.
Reads train/*_5min.parquet and train/*_1440min.parquet.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SYMBOLS = ["TECL", "TQQQ", "TNA", "UPRO", "UDOW"]


def _load_returns(timeframe_minutes: int) -> pd.DataFrame:
    cols = {}
    for s in SYMBOLS:
        path = ROOT / "data" / "prices" / "train" / f"{s}_{timeframe_minutes}min.parquet"
        df = pd.read_parquet(path)
        cols[s] = df["close"].pct_change().dropna()
    return pd.DataFrame(cols).dropna()


def _print_md_corr(label: str, corr: pd.DataFrame) -> None:
    print(f"\n## {label}\n")
    print("|   | " + " | ".join(corr.columns) + " |")
    print("|---|" + "|".join(["---:"] * len(corr.columns)) + "|")
    for s in corr.index:
        row = "| " + s + " | " + " | ".join(f"{corr.loc[s, t]:.2f}" for t in corr.columns) + " |"
        print(row)


def main() -> int:
    daily = _load_returns(1440)
    bars = _load_returns(5)
    _print_md_corr("Daily-return correlation (train)", daily.corr())
    _print_md_corr("5min-return correlation (train)", bars.corr())
    return 0


if __name__ == "__main__":
    sys.exit(main())
