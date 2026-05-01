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
