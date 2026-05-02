"""Fetch VIX daily close history via yfinance and save to data cache.

VIX is the CBOE volatility index — the "fear gauge". Used as a regime
filter so we trade only when implied volatility is meaningfully high
(VIX prior-day close > threshold).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import yfinance as yf


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    out_path = project_root / "data" / "prices" / "VIX_1day_2019-05-01_2026-05-01.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print("downloading ^VIX from yfinance…")
    df = yf.download("^VIX", start="2019-05-01", end="2026-05-02",
                     progress=False, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = ["open", "high", "low", "close", "volume"]
    df.index = pd.to_datetime(df.index, utc=True)
    df.to_parquet(out_path)
    print(f"  saved {len(df)} VIX daily bars to {out_path.name}")
    print(f"  VIX percentiles: 25th={df['close'].quantile(0.25):.1f} "
          f"50th={df['close'].median():.1f} 75th={df['close'].quantile(0.75):.1f}")
    print(f"  VIX > 18: {(df['close'] > 18).sum()} days, "
          f"VIX > 22: {(df['close'] > 22).sum()} days, "
          f"VIX > 30: {(df['close'] > 30).sum()} days")
    return 0


if __name__ == "__main__":
    sys.exit(main())
