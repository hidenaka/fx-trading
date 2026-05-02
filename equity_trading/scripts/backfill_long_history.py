"""Backfill 5+ years of historical bars for our 5 ETFs.

Tries to extend the cache from 2019-05-01 to 2024-05-01 (5 additional years
beyond the existing 2024-2026 window). Alpaca's IEX free feed serves IEX-only
data (subset of consolidated tape) — sufficient for backtesting validation.

Usage:
    python3 equity_trading/scripts/backfill_long_history.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd

from equity_trading.src.broker.alpaca_client import AlpacaClient
from equity_trading.src.config import load_config
from equity_trading.src.data.price_fetcher import PriceFetcher


# 5 years before existing cache; existing covers 2024-05-01 to 2026-05-01
EXTRA_START = datetime(2019, 5, 1, tzinfo=timezone.utc)
EXISTING_START = datetime(2024, 5, 1, tzinfo=timezone.utc)
EXISTING_END = datetime(2026, 5, 1, tzinfo=timezone.utc)
SYMBOLS = ["SPY", "QQQ", "IWM", "DIA", "XLK"]


def fetch_in_chunks(fetcher: PriceFetcher, symbol: str, start: datetime, end: datetime,
                   timeframe_minutes: int, chunk_days: int = 365) -> pd.DataFrame:
    """Fetch data in 1-year chunks to avoid API timeouts; concat results."""
    chunks: list[pd.DataFrame] = []
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=chunk_days), end)
        try:
            df = fetcher.fetch(symbol=symbol, start=cursor, end=chunk_end,
                               timeframe_minutes=timeframe_minutes)
            chunks.append(df)
            print(f"  [{symbol} {timeframe_minutes}m] {cursor.date()} → {chunk_end.date()}: {len(df)} bars")
        except Exception as e:
            print(f"  [{symbol} {timeframe_minutes}m] {cursor.date()} ERROR: {type(e).__name__}: {e}")
        cursor = chunk_end
    if not chunks:
        return pd.DataFrame()
    return pd.concat(chunks).sort_index()


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    cache_dir = project_root / "data" / "prices"
    env_path = project_root / ".env"
    cfg = load_config(env_path=env_path if env_path.exists() else None)
    broker = AlpacaClient(api_key=cfg.alpaca_api_key,
                         secret_key=cfg.alpaca_secret_key,
                         base_url=cfg.alpaca_base_url)
    fetcher = PriceFetcher(broker=broker, cache_dir=cache_dir)

    print(f"Backfilling {EXTRA_START.date()} → {EXISTING_START.date()} (5 yr) and "
          f"merging with existing {EXISTING_START.date()} → {EXISTING_END.date()}")

    for sym in SYMBOLS:
        for tf in (5, 1440):
            print(f"\n=== {sym} {tf}min ===")
            extra = fetch_in_chunks(fetcher, sym, EXTRA_START, EXISTING_START, tf)
            existing = fetcher.fetch(sym, EXISTING_START, EXISTING_END, tf)
            if len(extra) == 0:
                print(f"  no extra data fetched, keeping existing only")
                continue
            combined = pd.concat([extra, existing]).sort_index()
            combined = combined[~combined.index.duplicated(keep="first")]
            tf_label = f"{tf}min" if tf < 1440 else "1day"
            out_path = cache_dir / f"{sym}_{tf_label}_{EXTRA_START.strftime('%Y-%m-%dT%H%M')}_{EXISTING_END.strftime('%Y-%m-%dT%H%M')}.parquet"
            combined.to_parquet(out_path)
            print(f"  ✓ saved combined {len(combined)} bars to {out_path.name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
