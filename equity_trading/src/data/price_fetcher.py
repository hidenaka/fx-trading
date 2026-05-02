"""価格データの取得とローカルキャッシュ（Parquet形式）.

Critical: cached parquet files include pre-market and after-hours bars
(roughly 192 bars/day vs the regular-hours 78 bars). Strategies that key
off "first bar of day" or specific bar positions must operate on
regular-trading-hours-only data, otherwise bar 0 is 4:00 ET pre-market.

The fetch method takes `regular_hours_only` (default True) to filter
post-fetch. Set to False only for diagnostic comparisons.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from equity_trading.src.broker.alpaca_client import AlpacaClient


def filter_regular_hours(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only US regular trading hours bars (9:30-16:00 ET, 78 bars/day at 5min)."""
    if df is None or len(df) == 0 or df.index.tz is None:
        return df
    ny = df.index.tz_convert("America/New_York")
    minutes_since_open = (ny.hour * 60 + ny.minute) - (9 * 60 + 30)
    mask = (minutes_since_open >= 0) & (minutes_since_open < 6 * 60 + 30)
    return df[mask]


class PriceFetcher:
    """ブローカーから過去価格を取得し、Parquet にキャッシュ."""

    def __init__(
        self,
        broker: AlpacaClient,
        cache_dir: Path | str,
        *,
        partition: str = "full",
    ) -> None:
        self.broker = broker
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.partition = partition

    def fetch(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe_minutes: int,
        regular_hours_only: bool = True,
    ) -> pd.DataFrame:
        """過去バーを取得.

        ローカルキャッシュ（Parquet）に同条件のファイルがあれば優先利用、
        なければブローカー API を叩いて取得＆保存。

        partition が "train", "holdout", または "full" に設定されている場合、
        cache_dir/{partition}/{symbol}_{tf}min.parquet から読み込む。
        パーティションファイルが存在する場合は Alpaca へのフォールバックをスキップ。

        Args:
            regular_hours_only: True (default) で 9:30-16:00 ET の bars に絞る。
                pre-market/after-hours は流動性が低く、ブラケット注文が機能しないため、
                バックテストとライブの両方で RTH-only に統一する。
        """
        # Check for partitioned parquet file first
        partitioned_path = self._partitioned_path(symbol, timeframe_minutes)
        if partitioned_path.exists():
            df = pd.read_parquet(partitioned_path)
            # Filter to the requested [start, end) window
            df = df.loc[(df.index >= start) & (df.index < end)]
            # Partitioned data is pre-processed; skip RTH filtering to avoid
            # accidentally dropping data the caller intended to include.
            return df
        # Legacy flat-cache path
        cache_path = self._cache_key(symbol, start, end, timeframe_minutes)
        if cache_path.exists():
            df = pd.read_parquet(cache_path)
        else:
            df = self.broker.get_historical_bars(
                symbol=symbol,
                start=start,
                end=end,
                timeframe_minutes=timeframe_minutes,
            )
            df.to_parquet(cache_path)
        if regular_hours_only and timeframe_minutes < 1440:
            df = filter_regular_hours(df)
        return df

    def _partitioned_path(self, symbol: str, timeframe_minutes: int) -> Path:
        """Return the partition-aware parquet path: cache_dir/{partition}/{symbol}_{tf}min.parquet."""
        tf_label = f"{timeframe_minutes}min" if timeframe_minutes < 1440 else "1day"
        return self.cache_dir / self.partition / f"{symbol}_{tf_label}.parquet"

    def _cache_key(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe_minutes: int,
    ) -> Path:
        tf_label = f"{timeframe_minutes}min" if timeframe_minutes < 1440 else "1day"
        start_label = start.strftime("%Y-%m-%dT%H%M")
        end_label = end.strftime("%Y-%m-%dT%H%M")
        return self.cache_dir / f"{symbol}_{tf_label}_{start_label}_{end_label}.parquet"
