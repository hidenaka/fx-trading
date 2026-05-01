from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from equity_trading.src.phase0.data_collector import collect_phase0_data


def _make_bars(n: int = 3) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [100.0] * n,
            "high": [101.0] * n,
            "low": [99.0] * n,
            "close": [100.5] * n,
            "volume": [10000] * n,
        },
        index=pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC"),
    )


def test_collect_calls_fetcher_for_each_etf_and_timeframe(tmp_path):
    fetcher = MagicMock()
    fetcher.fetch.return_value = _make_bars()

    result = collect_phase0_data(
        fetcher=fetcher,
        symbols=["SPY", "QQQ"],
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 31, tzinfo=timezone.utc),
        timeframes=[5, 1440],
    )

    assert fetcher.fetch.call_count == 4
    assert ("SPY", 5) in result
    assert ("SPY", 1440) in result
    assert ("QQQ", 5) in result
    assert ("QQQ", 1440) in result


def test_collect_returns_dataframes_keyed_by_symbol_timeframe():
    fetcher = MagicMock()
    fetcher.fetch.return_value = _make_bars()

    result = collect_phase0_data(
        fetcher=fetcher,
        symbols=["SPY"],
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 2, tzinfo=timezone.utc),
        timeframes=[5],
    )
    assert isinstance(result[("SPY", 5)], pd.DataFrame)
    assert len(result[("SPY", 5)]) == 3
