"""SQLite スキーマ管理（手書きマイグレーション）.

Phase 0 では parameters と parameter_history のみ作成する。
Plan 2/3 で他テーブル（trades, signal_weights など）を追加する。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_PHASE0 = [
    """
    CREATE TABLE IF NOT EXISTS parameters (
        scope TEXT NOT NULL,
        key TEXT NOT NULL,
        value_json TEXT NOT NULL,
        updated_at_utc TIMESTAMP NOT NULL,
        source TEXT NOT NULL,
        PRIMARY KEY (scope, key)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS parameter_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scope TEXT NOT NULL,
        key TEXT NOT NULL,
        old_value TEXT,
        new_value TEXT,
        changed_at_utc TIMESTAMP NOT NULL
    );
    """,
]


SCHEMA_PLAN2 = [
    """
    CREATE TABLE IF NOT EXISTS positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        strategy_name TEXT NOT NULL,
        entry_ts_utc TIMESTAMP NOT NULL,
        entry_price REAL NOT NULL,
        entry_qty INTEGER NOT NULL,
        stop_price REAL NOT NULL,
        target_price REAL NOT NULL,
        alpaca_entry_order_id TEXT,
        alpaca_stop_order_id TEXT,
        alpaca_target_order_id TEXT,
        exit_ts_utc TIMESTAMP,
        exit_price REAL,
        exit_type TEXT,
        pnl_pct REAL,
        realized_pnl_usd REAL,
        status TEXT NOT NULL DEFAULT 'open'
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS bot_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_type TEXT NOT NULL,
        started_at_utc TIMESTAMP NOT NULL,
        finished_at_utc TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'running',
        error_message TEXT,
        entries_placed INTEGER NOT NULL DEFAULT 0,
        exits_placed INTEGER NOT NULL DEFAULT 0
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS daily_pnl (
        trade_date TEXT PRIMARY KEY,
        starting_equity_usd REAL NOT NULL,
        ending_equity_usd REAL NOT NULL,
        realized_pnl_usd REAL NOT NULL,
        daily_return_pct REAL NOT NULL,
        circuit_breaker_triggered INTEGER NOT NULL DEFAULT 0,
        n_entries INTEGER NOT NULL DEFAULT 0,
        n_exits INTEGER NOT NULL DEFAULT 0
    );
    """,
]


def init_database(db_path: Path | str) -> None:
    """SQLite を初期化する。WALモード有効化＆Phase 0スキーマ作成."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
        for ddl in SCHEMA_PHASE0:
            conn.execute(ddl)
        for ddl in SCHEMA_PLAN2:
            conn.execute(ddl)
        conn.commit()
