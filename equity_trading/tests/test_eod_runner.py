import sqlite3
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pandas as pd
import pytest

from equity_trading.src.live.eod_runner import run_eod
from equity_trading.src.state.migrations import init_database


def _seed_open_position(db_path, symbol="XLK", entry_price=250.0, entry_qty=10):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """INSERT INTO positions (symbol, strategy_name, entry_ts_utc, entry_price,
               entry_qty, stop_price, target_price, status)
               VALUES (?, 'mean_reversion', '2026-05-04T14:00:00Z', ?, ?, ?, ?, 'open')""",
            (symbol, entry_price, entry_qty, entry_price * 0.998, entry_price * 1.003),
        )
        conn.commit()


def _account(equity=10010.0):
    return {"account_number": "T", "status": "ACTIVE", "currency": "USD",
            "cash": equity, "equity": equity, "buying_power": equity * 4,
            "pattern_day_trader": False}


def test_eod_runner_closes_open_positions(tmp_path):
    db = tmp_path / "trades.sqlite"
    init_database(db)
    _seed_open_position(db, symbol="XLK", entry_price=250.0, entry_qty=10)

    fetcher = MagicMock()
    # Latest bar close = 251.0 → exit price estimate
    fetcher.fetch.return_value = pd.DataFrame(
        {"open": [251.0], "high": [251.1], "low": [250.9], "close": [251.0], "volume": [10000]},
        index=pd.date_range("2026-05-04 19:55", periods=1, freq="5min", tz="UTC"),
    )

    broker = MagicMock()
    broker.get_account.return_value = _account()
    broker.close_position.return_value = {"order_id": "close-1", "qty": "10"}

    summary = run_eod(
        db_path=db,
        broker=broker,
        fetcher=fetcher,
        now_utc=datetime(2026, 5, 4, 19, 55, tzinfo=timezone.utc),
    )
    assert summary["positions_closed"] == 1
    broker.close_position.assert_called_once_with("XLK")

    # Position row updated
    with sqlite3.connect(db) as conn:
        row = conn.execute(
            """SELECT status, exit_price, exit_type, pnl_pct, realized_pnl_usd
               FROM positions WHERE symbol='XLK'"""
        ).fetchone()
    assert row[0] == "closed"
    assert row[1] == pytest.approx(251.0)
    assert row[2] == "time"
    # pnl_pct = (251 - 250) / 250 = 0.004 (in fraction)
    assert row[3] == pytest.approx(0.004, abs=1e-6)
    # realized_pnl_usd = (251 - 250) * 10 = 10.0
    assert row[4] == pytest.approx(10.0, abs=0.01)


def test_eod_runner_writes_daily_pnl(tmp_path):
    db = tmp_path / "trades.sqlite"
    init_database(db)
    _seed_open_position(db, "XLK", 250.0, 10)

    fetcher = MagicMock()
    fetcher.fetch.return_value = pd.DataFrame(
        {"open": [251.0], "high": [251.1], "low": [250.9], "close": [251.0], "volume": [10000]},
        index=pd.date_range("2026-05-04 19:55", periods=1, freq="5min", tz="UTC"),
    )

    broker = MagicMock()
    broker.get_account.return_value = _account()
    broker.close_position.return_value = {"order_id": "x", "qty": "10"}

    run_eod(db_path=db, broker=broker, fetcher=fetcher,
            now_utc=datetime(2026, 5, 4, 19, 55, tzinfo=timezone.utc))

    with sqlite3.connect(db) as conn:
        row = conn.execute(
            """SELECT trade_date, realized_pnl_usd, n_entries, n_exits FROM daily_pnl"""
        ).fetchone()
    # NY date for UTC 2026-05-04 19:55 = NY 2026-05-04 15:55
    assert row[0] == "2026-05-04"
    assert row[1] == pytest.approx(10.0)
    # n_exits should be 1 (we just exited the XLK position)
    assert row[3] == 1


def test_eod_runner_with_no_open_positions(tmp_path):
    db = tmp_path / "trades.sqlite"
    init_database(db)

    fetcher = MagicMock()
    broker = MagicMock()
    broker.get_account.return_value = _account()

    summary = run_eod(db_path=db, broker=broker, fetcher=fetcher,
                     now_utc=datetime(2026, 5, 4, 19, 55, tzinfo=timezone.utc))
    assert summary["positions_closed"] == 0
    broker.close_position.assert_not_called()
    # daily_pnl row still written
    with sqlite3.connect(db) as conn:
        rows = conn.execute("SELECT * FROM daily_pnl").fetchall()
    assert len(rows) == 1


def test_eod_runner_logs_bot_run(tmp_path):
    db = tmp_path / "trades.sqlite"
    init_database(db)

    fetcher = MagicMock()
    broker = MagicMock()
    broker.get_account.return_value = _account()

    run_eod(db_path=db, broker=broker, fetcher=fetcher,
            now_utc=datetime(2026, 5, 4, 19, 55, tzinfo=timezone.utc))

    with sqlite3.connect(db) as conn:
        rows = conn.execute("SELECT run_type, status FROM bot_runs").fetchall()
    assert rows == [("eod", "success")]
