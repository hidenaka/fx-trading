"""Morning runner E2E with mocked broker + fetcher."""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

from equity_trading.src.live.morning_runner import run_morning
from equity_trading.src.state.migrations import init_database


def _make_first_bar(open_price: float, when: str = "2026-05-04 13:30") -> pd.DataFrame:
    """One 5min bar — today's first bar (NY 09:30 = UTC 13:30 in summer)."""
    return pd.DataFrame(
        {"open": [open_price], "high": [open_price + 0.05], "low": [open_price - 0.05],
         "close": [open_price], "volume": [10000]},
        index=pd.date_range(when, periods=1, freq="5min", tz="UTC"),
    )


def _make_daily_with_prev_close(prev_close: float, n: int = 250) -> pd.DataFrame:
    """Daily bars with last close = prev_close, generally rising for 200d MA filter."""
    closes = list(np.linspace(prev_close * 0.7, prev_close, n))
    return pd.DataFrame(
        {"close": closes},
        index=pd.date_range("2025-08-26", periods=n, freq="1D", tz="UTC"),
    )


def _account(equity: float = 10000.0) -> dict:
    return {"account_number": "T", "status": "ACTIVE", "currency": "USD",
            "cash": equity, "equity": equity, "buying_power": equity * 4,
            "pattern_day_trader": False}


def test_morning_runner_no_gap_no_orders(tmp_path):
    """Today opens at prev close → no gap → no orders, no positions."""
    db = tmp_path / "trades.sqlite"
    init_database(db)

    fetcher = MagicMock()
    def fake_fetch(symbol, start, end, timeframe_minutes):
        if timeframe_minutes == 5:
            return _make_first_bar(open_price=100.0)
        return _make_daily_with_prev_close(prev_close=100.0)
    fetcher.fetch.side_effect = fake_fetch

    broker = MagicMock()
    broker.get_account.return_value = _account()
    broker.submit_bracket_buy = MagicMock()

    summary = run_morning(
        symbols=["XLK"],
        db_path=db,
        broker=broker,
        fetcher=fetcher,
        now_utc=datetime(2026, 5, 4, 13, 35, tzinfo=timezone.utc),
    )
    assert summary["entries_placed"] == 0
    broker.submit_bracket_buy.assert_not_called()


def test_morning_runner_gap_down_places_bracket(tmp_path):
    """SPY opens 99 vs prev close 100 (1% gap-down) → triggers signal."""
    db = tmp_path / "trades.sqlite"
    init_database(db)

    fetcher = MagicMock()
    def fake_fetch(symbol, start, end, timeframe_minutes):
        if timeframe_minutes == 5:
            return _make_first_bar(open_price=99.0)
        return _make_daily_with_prev_close(prev_close=100.0)
    fetcher.fetch.side_effect = fake_fetch

    broker = MagicMock()
    broker.get_account.return_value = _account()
    broker.submit_bracket_buy.return_value = {
        "entry_order_id": "ord-001", "client_order_id": "cli-001",
    }

    summary = run_morning(
        symbols=["SPY"],
        db_path=db,
        broker=broker,
        fetcher=fetcher,
        now_utc=datetime(2026, 5, 4, 13, 35, tzinfo=timezone.utc),
    )
    assert summary["entries_placed"] == 1
    broker.submit_bracket_buy.assert_called_once()

    call = broker.submit_bracket_buy.call_args
    kwargs = call.kwargs if call.kwargs else {}
    # symbol is SPY
    sym = kwargs.get("symbol") or call.args[0]
    assert sym == "SPY"
    # qty was computed: 25% of $10k = $2500, $2500/$99 = 25 shares
    qty = kwargs.get("qty") or call.args[1]
    assert qty == 25
    # target should be prev_close = 100, stop should be open*0.995 = 99*0.995 = 98.505
    target = kwargs.get("target_price")
    stop = kwargs.get("stop_price")
    if target is None and len(call.args) >= 4:
        stop, target = call.args[2], call.args[3]
    assert abs(target - 100.0) < 0.01
    assert abs(stop - 98.505) < 0.01

    # And a position record was inserted
    import sqlite3
    with sqlite3.connect(db) as conn:
        rows = conn.execute("SELECT symbol, strategy_name, status FROM positions").fetchall()
    assert len(rows) == 1
    assert rows[0] == ("SPY", "gap_fill", "open")


def test_morning_runner_logs_bot_run(tmp_path):
    """Each run inserts a row in bot_runs."""
    db = tmp_path / "trades.sqlite"
    init_database(db)

    fetcher = MagicMock()
    fetcher.fetch.return_value = _make_first_bar(open_price=100.0)
    # Daily has to be returned for the daily call too; reuse via side_effect
    def fake_fetch(symbol, start, end, timeframe_minutes):
        if timeframe_minutes == 5:
            return _make_first_bar(open_price=100.0)
        return _make_daily_with_prev_close(prev_close=100.0)
    fetcher.fetch.side_effect = fake_fetch

    broker = MagicMock()
    broker.get_account.return_value = _account()

    summary = run_morning(
        symbols=["SPY"],
        db_path=db,
        broker=broker,
        fetcher=fetcher,
        now_utc=datetime(2026, 5, 4, 13, 35, tzinfo=timezone.utc),
    )
    import sqlite3
    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            "SELECT run_type, status FROM bot_runs"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0] == ("morning", "success")


def test_morning_runner_skips_when_capacity_full(tmp_path):
    """3 open positions already → new gap_fill signal is skipped."""
    db = tmp_path / "trades.sqlite"
    init_database(db)
    import sqlite3
    with sqlite3.connect(db) as conn:
        for sym in ("AAPL", "MSFT", "GOOG"):
            conn.execute(
                """INSERT INTO positions (symbol, strategy_name, entry_ts_utc,
                   entry_price, entry_qty, stop_price, target_price, status)
                   VALUES (?, 'gap_fill', '2026-05-04T13:30:00Z', 100.0, 5, 99.0, 102.0, 'open')""",
                (sym,),
            )
        conn.commit()

    fetcher = MagicMock()
    def fake_fetch(symbol, start, end, timeframe_minutes):
        if timeframe_minutes == 5:
            return _make_first_bar(open_price=99.0)  # gap-down on SPY
        return _make_daily_with_prev_close(prev_close=100.0)
    fetcher.fetch.side_effect = fake_fetch

    broker = MagicMock()
    broker.get_account.return_value = _account()

    summary = run_morning(
        symbols=["SPY"],
        db_path=db,
        broker=broker,
        fetcher=fetcher,
        now_utc=datetime(2026, 5, 4, 13, 35, tzinfo=timezone.utc),
    )
    assert summary["entries_placed"] == 0
    broker.submit_bracket_buy.assert_not_called()
