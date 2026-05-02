"""P1: Generate massive labeled candidate dataset for pattern discovery."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

from equity_trading.src.ml.candidate_dataset import generate_candidates
from equity_trading.src.ml.outcome_labeler import label_candidates


STRATEGY_TIERS = [
    ("gap_fill", [
        ("tight",  {"gap_threshold": 0.005,  "stop_extension": 0.005}),
        ("medium", {"gap_threshold": 0.003,  "stop_extension": 0.005}),
        ("loose",  {"gap_threshold": 0.0015, "stop_extension": 0.005}),
    ]),
    ("mean_reversion", [
        ("tight",  {"threshold": 0.40}),
        ("medium", {"threshold": 0.25}),
        ("loose",  {"threshold": 0.10}),
    ]),
    ("vwap_scalp", [
        ("tight",  {"k_entry": 2.0}),
        ("medium", {"k_entry": 1.0}),
        ("loose",  {"k_entry": 0.5}),
    ]),
]

ATR_PCT = {"SPY": 0.061, "QQQ": 0.083, "IWM": 0.096, "DIA": 0.073, "XLK": 0.129}
SYMBOLS = ["SPY", "QQQ", "IWM", "DIA", "XLK"]
SPLIT_DATE = pd.Timestamp("2025-05-01", tz="UTC")


def _load(cache_dir: Path, symbol: str, tf: str,
          start: datetime, end: datetime) -> pd.DataFrame:
    s = start.strftime("%Y-%m-%dT%H%M")
    e = end.strftime("%Y-%m-%dT%H%M")
    path = cache_dir / f"{symbol}_{tf}_{s}_{e}.parquet"
    return pd.read_parquet(path)


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    cache_dir = project_root / "data" / "prices"
    out_dir = project_root / "phase0"
    out_dir.mkdir(parents=True, exist_ok=True)

    period_start = datetime(2024, 5, 1, tzinfo=timezone.utc)
    period_end = datetime(2026, 5, 1, tzinfo=timezone.utc)
    spy_5min = _load(cache_dir, "SPY", "5min", period_start, period_end)

    rows = []
    total_cfg = len(SYMBOLS) * sum(len(tiers) for _, tiers in STRATEGY_TIERS)
    cfg_done = 0

    for symbol in SYMBOLS:
        bars = _load(cache_dir, symbol, "5min", period_start, period_end)
        daily = _load(cache_dir, symbol, "1day", period_start, period_end)
        atr = ATR_PCT[symbol]

        for strategy_name, tiers in STRATEGY_TIERS:
            for tier_name, tier_params in tiers:
                cfg_done += 1
                cands = generate_candidates(
                    bars_5min=bars, daily=daily, spy_5min=spy_5min,
                    symbol=symbol, strategy_name=strategy_name,
                    relaxed_params=tier_params,
                )
                labeled = label_candidates(
                    candidates=cands, bars_5min=bars, daily=daily,
                    atr_pct=atr, base_params=tier_params,
                )
                print(f"[{cfg_done}/{total_cfg}] {symbol} {strategy_name} "
                      f"{tier_name}: {len(labeled)} labeled")

                for lc in labeled:
                    row = {
                        "timestamp": lc.signal.timestamp,
                        "symbol": symbol,
                        "strategy": strategy_name,
                        "threshold_tier": tier_name,
                        "pnl_pct": lc.pnl_pct,
                        "win": int(lc.win),
                        "exit_type": lc.exit_type,
                        "bars_held": lc.bars_held,
                    }
                    row.update(lc.signal.features)
                    rows.append(row)

    df = pd.DataFrame(rows)
    df["split"] = df["timestamp"].apply(lambda t: "train" if t < SPLIT_DATE else "test")
    print(f"\nTotal labeled candidates: {len(df)}")
    print(f"  train: {(df['split'] == 'train').sum()}")
    print(f"  test:  {(df['split'] == 'test').sum()}")
    print(f"  per-strategy counts:")
    print(df.groupby(["strategy", "split"]).size())

    out_path = out_dir / "pattern_discovery_dataset.parquet"
    df.to_parquet(out_path)
    print(f"\n[saved] {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
