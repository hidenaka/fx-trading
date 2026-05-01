"""価格データの取得とローカルキャッシュ（Parquet形式）."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from equity_trading.src.broker.alpaca_client import AlpacaClient


class PriceFetcher:
    """ブローカーから過去価格を取得し、Parquet にキャッシュ."""

    def __init__(self, broker: AlpacaClient, cache_dir: Path | str) -> None:
        self.broker = broker
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe_minutes: int,
    ) -> pd.DataFrame:
        """過去バーを取得.

        ローカルキャッシュ（Parquet）に同条件のファイルがあれば優先利用、
        なければブローカー API を叩いて取得＆保存。
        """
        cache_path = self._cache_key(symbol, start, end, timeframe_minutes)
        if cache_path.exists():
            return pd.read_parquet(cache_path)

        df = self.broker.get_historical_bars(
            symbol=symbol,
            start=start,
            end=end,
            timeframe_minutes=timeframe_minutes,
        )
        df.to_parquet(cache_path)
        return df

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
