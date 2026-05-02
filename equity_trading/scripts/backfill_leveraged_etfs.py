"""Backfill 7 years of 5-min and daily bars for 3x leveraged ETFs and inverse ETFs.

Symbols:
  TQQQ — 3x QQQ (Nasdaq 100)
  UPRO — 3x SPY (S&P 500)
  TNA  — 3x IWM (Russell 2000 small caps)
  TECL — 3x XLK (US tech sector)
  SQQQ — -3x QQQ (inverse, for short-side via long position)
  UDOW — 3x DIA (Dow 30)
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


PERIOD_START = datetime(2019, 5, 1, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 5, 1, tzinfo=timezone.utc)
SYMBOLS = ["TQQQ", "UPRO", "TNA", "TECL", "SQQQ", "UDOW"]


def fetch_in_chunks(fetcher, symbol, start, end, tf, chunk_days=365) -> pd.DataFrame:
    chunks = []
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=chunk_days), end)
        try:
            df = fetcher.fetch(symbol=symbol, start=cursor, end=chunk_end,
                               timeframe_minutes=tf, regular_hours_only=False)
            chunks.append(df)
            print(f"  [{symbol} {tf}m] {cursor.date()}→{chunk_end.date()}: {len(df)} bars")
        except Exception as e:
            print(f"  [{symbol} {tf}m] {cursor.date()} ERROR: {type(e).__name__}: {e}")
        cursor = chunk_end
    if not chunks:
        return pd.DataFrame()
    return pd.concat(chunks).sort_index()


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    cache_dir = project_root / "data" / "prices"
    cfg = load_config(env_path=project_root / ".env")
    broker = AlpacaClient(api_key=cfg.alpaca_api_key, secret_key=cfg.alpaca_secret_key,
                         base_url=cfg.alpaca_base_url)
    fetcher = PriceFetcher(broker=broker, cache_dir=cache_dir)

    print(f"Backfilling {SYMBOLS} for {PERIOD_START.date()}→{PERIOD_END.date()}")

    for sym in SYMBOLS:
        for tf in (5, 1440):
            print(f"\n=== {sym} {tf}min ===")
            df = fetch_in_chunks(fetcher, sym, PERIOD_START, PERIOD_END, tf)
            if len(df) == 0:
                print(f"  no data fetched for {sym} {tf}min — skipping save")
                continue
            df = df[~df.index.duplicated(keep="first")]
            tf_label = f"{tf}min" if tf < 1440 else "1day"
            out_path = cache_dir / f"{sym}_{tf_label}_{PERIOD_START.strftime('%Y-%m-%dT%H%M')}_{PERIOD_END.strftime('%Y-%m-%dT%H%M')}.parquet"
            df.to_parquet(out_path)
            print(f"  ✓ saved combined {len(df)} bars to {out_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
