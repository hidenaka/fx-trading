import sqlite3
from pathlib import Path

import pytest

from equity_trading.src.state.migrations import init_database


def test_init_database_creates_parameters_table(tmp_path):
    db_path = tmp_path / "test.sqlite"
    init_database(db_path)

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='parameters'"
        )
        rows = cur.fetchall()
    assert len(rows) == 1


def test_init_database_creates_parameter_history_table(tmp_path):
    db_path = tmp_path / "test.sqlite"
    init_database(db_path)

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='parameter_history'"
        )
        rows = cur.fetchall()
    assert len(rows) == 1


def test_init_database_enables_wal_mode(tmp_path):
    db_path = tmp_path / "test.sqlite"
    init_database(db_path)

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("PRAGMA journal_mode")
        mode = cur.fetchone()[0]
    assert mode.lower() == "wal"


def test_init_database_idempotent(tmp_path):
    db_path = tmp_path / "test.sqlite"
    init_database(db_path)
    init_database(db_path)

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("SELECT count(*) FROM parameters")
        count = cur.fetchone()[0]
    assert count == 0


def test_init_database_creates_positions_table(tmp_path):
    db_path = tmp_path / "trades.sqlite"
    init_database(db_path)
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("PRAGMA table_info(positions)")
        cols = {row[1] for row in cur}
    expected = {
        "id", "symbol", "strategy_name", "entry_ts_utc", "entry_price",
        "entry_qty", "stop_price", "target_price",
        "alpaca_entry_order_id", "alpaca_stop_order_id", "alpaca_target_order_id",
        "exit_ts_utc", "exit_price", "exit_type",
        "pnl_pct", "realized_pnl_usd", "status",
    }
    assert expected.issubset(cols), f"Missing columns: {expected - cols}"


def test_init_database_creates_bot_runs_table(tmp_path):
    db_path = tmp_path / "trades.sqlite"
    init_database(db_path)
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("PRAGMA table_info(bot_runs)")
        cols = {row[1] for row in cur}
    expected = {
        "id", "run_type", "started_at_utc", "finished_at_utc",
        "status", "error_message", "entries_placed", "exits_placed",
    }
    assert expected.issubset(cols)


def test_init_database_creates_daily_pnl_table(tmp_path):
    db_path = tmp_path / "trades.sqlite"
    init_database(db_path)
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("PRAGMA table_info(daily_pnl)")
        cols = {row[1] for row in cur}
    expected = {
        "trade_date", "starting_equity_usd", "ending_equity_usd",
        "realized_pnl_usd", "daily_return_pct", "circuit_breaker_triggered",
        "n_entries", "n_exits",
    }
    assert expected.issubset(cols)


def test_positions_default_status_is_open(tmp_path):
    db_path = tmp_path / "trades.sqlite"
    init_database(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO positions (symbol, strategy_name, entry_ts_utc, entry_price,
                entry_qty, stop_price, target_price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("XLK", "gap_fill", "2026-05-02T13:30:00Z", 250.0, 10, 245.0, 252.0),
        )
        conn.commit()
        row = conn.execute("SELECT status FROM positions").fetchone()
    assert row[0] == "open"


def test_init_database_idempotent_plan2(tmp_path):
    """Running init_database twice on same path is safe."""
    db_path = tmp_path / "trades.sqlite"
    init_database(db_path)
    init_database(db_path)  # second call should not error
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        names = {row[0] for row in cur}
    assert "positions" in names
    assert "parameters" in names  # original Phase 0 table still there
