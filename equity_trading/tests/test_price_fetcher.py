from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from equity_trading.src.data.price_fetcher import PriceFetcher


def _make_bars(n: int = 3) -> pd.DataFrame:
    """Bars timestamped during US regular trading hours so the default RTH filter keeps them."""
    return pd.DataFrame(
        {
            "open": [100.0 + i for i in range(n)],
            "high": [101.0 + i for i in range(n)],
            "low": [99.0 + i for i in range(n)],
            "close": [100.5 + i for i in range(n)],
            "volume": [10000 + 1000 * i for i in range(n)],
        },
        # 14:30 UTC on a Tuesday = 9:30 ET (during EST winter); regular open.
        index=pd.date_range("2024-01-02 14:30", periods=n, freq="5min", tz="UTC"),
    )


def test_fetcher_loads_from_cache_when_exists(tmp_path):
    cache_dir = tmp_path / "prices"
    cache_dir.mkdir()
    df = _make_bars()
    cache_name = "SPY_5min_2024-01-02T1430_2024-01-02T1445.parquet"
    cache_path = cache_dir / cache_name
    df.to_parquet(cache_path)
    expected = pd.read_parquet(cache_path)

    broker = MagicMock()
    fetcher = PriceFetcher(broker=broker, cache_dir=cache_dir)
    out = fetcher.fetch(
        symbol="SPY",
        start=datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc),
        end=datetime(2024, 1, 2, 14, 45, tzinfo=timezone.utc),
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
        start=datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc),
        end=datetime(2024, 1, 2, 14, 45, tzinfo=timezone.utc),
        timeframe_minutes=5,
    )

    # The fetcher returns the broker's DataFrame as-is on cache miss (filter applied below)
    pd.testing.assert_frame_equal(out, bars)
    broker.get_historical_bars.assert_called_once()
    cache_files = list(cache_dir.glob("SPY_5min_*.parquet"))
    assert len(cache_files) == 1


def test_fetcher_filters_pre_and_after_hours_by_default(tmp_path):
    """Pre-market (4:00-9:25 ET) and after-hours (16:00+ ET) bars are dropped."""
    cache_dir = tmp_path / "prices"
    cache_dir.mkdir()

    # Build bars across pre-market, RTH, and after-hours
    times_utc = [
        "2024-01-02 09:00",  # 4:00 ET pre-market — DROP
        "2024-01-02 14:30",  # 9:30 ET regular open — KEEP
        "2024-01-02 18:00",  # 13:00 ET RTH — KEEP
        "2024-01-02 21:00",  # 16:00 ET after close — DROP (>= close)
        "2024-01-02 21:30",  # 16:30 ET after-hours — DROP
    ]
    bars = pd.DataFrame(
        {"open": [100.0]*5, "high": [101.0]*5, "low": [99.0]*5,
         "close": [100.5]*5, "volume": [10000]*5},
        index=pd.DatetimeIndex(times_utc, tz="UTC"),
    )
    broker = MagicMock()
    broker.get_historical_bars.return_value = bars
    fetcher = PriceFetcher(broker=broker, cache_dir=cache_dir)
    out = fetcher.fetch(
        symbol="SPY",
        start=datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc),
        end=datetime(2024, 1, 3, 0, 0, tzinfo=timezone.utc),
        timeframe_minutes=5,
    )
    # Only 9:30 ET and 13:00 ET RTH bars survive
    assert len(out) == 2
    assert out.index[0].tz_convert("America/New_York").hour == 9
    assert out.index[1].tz_convert("America/New_York").hour == 13


def test_fetcher_can_disable_rth_filter(tmp_path):
    """Setting regular_hours_only=False keeps all bars (for diagnostics)."""
    cache_dir = tmp_path / "prices"
    cache_dir.mkdir()
    times_utc = ["2024-01-02 09:00", "2024-01-02 14:30", "2024-01-02 21:30"]
    bars = pd.DataFrame(
        {"open": [100.0]*3, "high": [101.0]*3, "low": [99.0]*3,
         "close": [100.5]*3, "volume": [10000]*3},
        index=pd.DatetimeIndex(times_utc, tz="UTC"),
    )
    broker = MagicMock()
    broker.get_historical_bars.return_value = bars
    fetcher = PriceFetcher(broker=broker, cache_dir=cache_dir)
    out = fetcher.fetch(
        symbol="SPY",
        start=datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc),
        end=datetime(2024, 1, 3, 0, 0, tzinfo=timezone.utc),
        timeframe_minutes=5,
        regular_hours_only=False,
    )
    assert len(out) == 3


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
