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
        conn.commit()
