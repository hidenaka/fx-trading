"""Intraday mean_reversion runner E2E with mocked broker + fetcher."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from equity_trading.src.live.intraday_runner import run_intraday
from equity_trading.src.state.migrations import init_database


def _make_5min_bars_below_with_signal(n: int = 100) -> pd.DataFrame:
    """Bars where the LATEST bar should produce a strong mean_reversion signal.

    Build a series where: high RSI starting → drop sharply at the end so RSI is low,
    BB lower hit, VWAP above price, etc. We force this by having a long uptrend,
    then a sharp drop in the last 5 bars.
    """
    np.random.seed(42)
    closes = []
    # First 80 bars: uptrending around 100
    for i in range(80):
        closes.append(100.0 + i * 0.05 + np.random.randn() * 0.05)
    # Last 20 bars: sharp drop
    base = closes[-1]
    for i in range(20):
        closes.append(base - (i + 1) * 0.20)
    closes_arr = np.array(closes)
    return pd.DataFrame(
        {
            "open": closes_arr,
            "high": closes_arr + 0.05,
            "low": closes_arr - 0.05,
            "close": closes_arr,
            "volume": [50000] * 80 + [80000] * 20,  # higher volume on the drop
        },
        index=pd.date_range("2026-05-04 14:30", periods=n, freq="5min", tz="UTC"),
    )


def _make_5min_bars_no_signal(n: int = 100) -> pd.DataFrame:
    """Bars with no strong signal (flat price)."""
    closes = np.full(n, 100.0)
    return pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes,
         "volume": [10000] * n},
        index=pd.date_range("2026-05-04 14:30", periods=n, freq="5min", tz="UTC"),
    )


def _daily_above_ma(n: int = 250) -> pd.DataFrame:
    closes = list(np.linspace(80, 120, n))
    return pd.DataFrame(
        {"close": closes},
        index=pd.date_range("2025-08-26", periods=n, freq="1D", tz="UTC"),
    )


def _account(equity: float = 10000.0) -> dict:
    return {"account_number": "T", "status": "ACTIVE", "currency": "USD",
            "cash": equity, "equity": equity, "buying_power": equity * 4,
            "pattern_day_trader": False}


def test_intraday_runner_no_signal_no_orders(tmp_path):
    """Flat price → no mean_reversion signal → no orders."""
    db = tmp_path / "trades.sqlite"
    init_database(db)

    fetcher = MagicMock()
    def fake_fetch(symbol, start, end, timeframe_minutes):
        if timeframe_minutes == 5:
            return _make_5min_bars_no_signal()
        return _daily_above_ma()
    fetcher.fetch.side_effect = fake_fetch

    broker = MagicMock()
    broker.get_account.return_value = _account()

    summary = run_intraday(
        db_path=db,
        broker=broker,
        fetcher=fetcher,
        now_utc=datetime(2026, 5, 4, 18, 0, tzinfo=timezone.utc),
    )
    assert summary["entries_placed"] == 0
    broker.submit_bracket_buy.assert_not_called()


def test_intraday_runner_skips_when_xlk_already_open(tmp_path):
    """If positions has open XLK row → no new entry attempted."""
    import sqlite3

    db = tmp_path / "trades.sqlite"
    init_database(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """INSERT INTO positions (symbol, strategy_name, entry_ts_utc,
               entry_price, entry_qty, stop_price, target_price, status)
               VALUES ('XLK', 'mean_reversion', '2026-05-04T14:00:00Z', 250.0, 10, 245.0, 252.0, 'open')""",
        )
        conn.commit()

    fetcher = MagicMock()
    def fake_fetch(symbol, start, end, timeframe_minutes):
        if timeframe_minutes == 5:
            return _make_5min_bars_below_with_signal()
        return _daily_above_ma()
    fetcher.fetch.side_effect = fake_fetch

    broker = MagicMock()
    broker.get_account.return_value = _account()

    summary = run_intraday(
        db_path=db,
        broker=broker,
        fetcher=fetcher,
        now_utc=datetime(2026, 5, 4, 18, 0, tzinfo=timezone.utc),
    )
    # Even if signal fires, capacity check denies (duplicate XLK)
    assert summary["entries_placed"] == 0
    broker.submit_bracket_buy.assert_not_called()


def test_intraday_runner_logs_bot_run(tmp_path):
    """Each invocation appends a bot_runs row with run_type='intraday'."""
    import sqlite3

    db = tmp_path / "trades.sqlite"
    init_database(db)

    fetcher = MagicMock()
    def fake_fetch(symbol, start, end, timeframe_minutes):
        if timeframe_minutes == 5:
            return _make_5min_bars_no_signal()
        return _daily_above_ma()
    fetcher.fetch.side_effect = fake_fetch

    broker = MagicMock()
    broker.get_account.return_value = _account()

    run_intraday(
        db_path=db,
        broker=broker,
        fetcher=fetcher,
        now_utc=datetime(2026, 5, 4, 18, 0, tzinfo=timezone.utc),
    )

    with sqlite3.connect(db) as conn:
        rows = conn.execute("SELECT run_type, status FROM bot_runs").fetchall()
    assert any(r == ("intraday", "success") for r in rows)
