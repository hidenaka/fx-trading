from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from equity_trading.src.data.price_fetcher import PriceFetcher


def _make_bars(n: int = 3) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [100.0 + i for i in range(n)],
            "high": [101.0 + i for i in range(n)],
            "low": [99.0 + i for i in range(n)],
            "close": [100.5 + i for i in range(n)],
            "volume": [10000 + 1000 * i for i in range(n)],
        },
        index=pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC"),
    )


def test_fetcher_loads_from_cache_when_exists(tmp_path):
    cache_dir = tmp_path / "prices"
    cache_dir.mkdir()
    df = _make_bars()
    # 実装の cache_key 命名規則に合わせる: SPY_5min_2024-01-01T0000_2024-01-01T0015.parquet
    cache_name = "SPY_5min_2024-01-01T0000_2024-01-01T0015.parquet"
    cache_path = cache_dir / cache_name
    df.to_parquet(cache_path)
    expected = pd.read_parquet(cache_path)

    broker = MagicMock()
    fetcher = PriceFetcher(broker=broker, cache_dir=cache_dir)
    out = fetcher.fetch(
        symbol="SPY",
        start=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
        end=datetime(2024, 1, 1, 0, 15, tzinfo=timezone.utc),
        timeframe_minutes=5,
    )

    pd.testing.assert_frame_equal(out, expected)
    broker.get_historical_bars.assert_not_called()


def test_fetcher_calls_broker_when_cache_missing(tmp_path):
    cache_dir = tmp_path / "prices"
    cache_dir.mkdir()
    bars = _make_bars()

    broker = MagicMock()
    broker.get_historical_bars.return_value = bars

    fetcher = PriceFetcher(broker=broker, cache_dir=cache_dir)
    out = fetcher.fetch(
        symbol="SPY",
        start=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
        end=datetime(2024, 1, 1, 0, 15, tzinfo=timezone.utc),
        timeframe_minutes=5,
    )

    # The fetcher returns the broker's DataFrame as-is on cache miss
    pd.testing.assert_frame_equal(out, bars)
    broker.get_historical_bars.assert_called_once()
    cache_files = list(cache_dir.glob("SPY_5min_*.parquet"))
    assert len(cache_files) == 1


def test_fetcher_keys_by_symbol_and_timeframe(tmp_path):
    cache_dir = tmp_path / "prices"
    cache_dir.mkdir()
    bars = _make_bars()

    broker = MagicMock()
    broker.get_historical_bars.return_value = bars

    fetcher = PriceFetcher(broker=broker, cache_dir=cache_dir)
    fetcher.fetch(
        symbol="QQQ",
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 1, 0, 15, tzinfo=timezone.utc),
        timeframe_minutes=1,
    )
    cache_files = sorted(p.name for p in cache_dir.glob("*.parquet"))
    assert any("QQQ_1min" in name for name in cache_files)
