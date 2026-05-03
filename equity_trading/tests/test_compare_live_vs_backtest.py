"""Live vs backtest comparison."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest


def _write_synthetic_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE positions (
            id INTEGER PRIMARY KEY,
            entry_ts TEXT, exit_ts TEXT,
            symbol TEXT, strategy TEXT,
            entry_price REAL, exit_price REAL,
            realized_pnl_usd REAL
        )
    """)
    rows = []
    # 35 ORB×TECL trades, WR ~0.55, avg ~ +0.18%
    for i in range(35):
        win = (i % 20) < 11
        pnl_pct = 0.0030 if win else -0.0015
        rows.append((
            "2026-05-15 14:30:00",
            "2026-05-15 15:30:00",
            "TECL", "OpeningRangeBreakoutStrategy",
            100.0, 100.0 * (1 + pnl_pct), pnl_pct * 25000.0,
        ))
    conn.executemany(
        "INSERT INTO positions(entry_ts, exit_ts, symbol, strategy, entry_price, exit_price, realized_pnl_usd) VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def test_compare_live_vs_backtest_produces_within_expectation(tmp_path):
    from equity_trading.scripts.compare_live_vs_backtest import compare
    db = tmp_path / "trades.sqlite"
    _write_synthetic_db(db)
    expected = {("OpeningRangeBreakoutStrategy", "TECL"): {"wr": 0.54, "avg_pnl_pct": 0.0022}}
    rows = compare(db_path=db, since="2026-05-14", expected=expected, seed=42)
    assert len(rows) == 1
    r = rows[0]
    assert r["strategy"] == "OpeningRangeBreakoutStrategy"
    assert r["symbol"] == "TECL"
    assert r["n"] == 35
    assert r["decision"] in {"WITHIN_EXPECTATION", "DIVERGENCE_AVG", "DIVERGENCE_WR"}


def test_compare_marks_insufficient_sample(tmp_path):
    from equity_trading.scripts.compare_live_vs_backtest import compare
    db = tmp_path / "trades.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE positions (id INTEGER PRIMARY KEY, "
        "entry_ts TEXT, exit_ts TEXT, symbol TEXT, strategy TEXT, "
        "entry_price REAL, exit_price REAL, realized_pnl_usd REAL)"
    )
    conn.executemany(
        "INSERT INTO positions(entry_ts, exit_ts, symbol, strategy, entry_price, exit_price, realized_pnl_usd) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [("2026-05-15", "2026-05-15", "TECL", "OpeningRangeBreakoutStrategy",
          100.0, 101.0, 250.0)] * 5,
    )
    conn.commit()
    conn.close()
    expected = {("OpeningRangeBreakoutStrategy", "TECL"): {"wr": 0.54, "avg_pnl_pct": 0.0022}}
    rows = compare(db_path=db, since="2026-05-14", expected=expected, seed=42)
    assert rows[0]["decision"] == "INSUFFICIENT_SAMPLE"
    assert rows[0]["n"] == 5


def test_compare_bootstrap_reproducible_with_seed(tmp_path):
    from equity_trading.scripts.compare_live_vs_backtest import compare
    db = tmp_path / "trades.sqlite"
    _write_synthetic_db(db)
    expected = {("OpeningRangeBreakoutStrategy", "TECL"): {"wr": 0.54, "avg_pnl_pct": 0.0022}}
    a = compare(db_path=db, since="2026-05-14", expected=expected, seed=42)
    b = compare(db_path=db, since="2026-05-14", expected=expected, seed=42)
    assert a[0]["wr_ci"] == b[0]["wr_ci"]
    assert a[0]["avg_pnl_pct_ci"] == b[0]["avg_pnl_pct_ci"]


def test_compare_marks_unexpected_pair(tmp_path):
    """A live trade whose (strategy, symbol) is absent from the variant
    config should be flagged UNEXPECTED_PAIR."""
    from equity_trading.scripts.compare_live_vs_backtest import compare
    db = tmp_path / "trades.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE positions (id INTEGER PRIMARY KEY, "
        "entry_ts TEXT, exit_ts TEXT, symbol TEXT, strategy TEXT, "
        "entry_price REAL, exit_price REAL, realized_pnl_usd REAL)"
    )
    conn.execute(
        "INSERT INTO positions(entry_ts, exit_ts, symbol, strategy, entry_price, exit_price, realized_pnl_usd) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("2026-05-15", "2026-05-15", "ZZZZ", "WeirdStrategy", 100.0, 101.0, 250.0),
    )
    conn.commit()
    conn.close()
    rows = compare(db_path=db, since="2026-05-14", expected={}, seed=42)
    assert rows[0]["decision"] == "UNEXPECTED_PAIR"


def test_compare_zero_n_pair_marked_insufficient(tmp_path):
    """A pair in expected but with n=0 in SQLite → INSUFFICIENT_SAMPLE n=0."""
    from equity_trading.scripts.compare_live_vs_backtest import compare
    db = tmp_path / "trades.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE positions (id INTEGER PRIMARY KEY, "
        "entry_ts TEXT, exit_ts TEXT, symbol TEXT, strategy TEXT, "
        "entry_price REAL, exit_price REAL, realized_pnl_usd REAL)"
    )
    conn.commit()
    conn.close()
    expected = {("OpeningRangeBreakoutStrategy", "TECL"): {"wr": 0.54, "avg_pnl_pct": 0.0022}}
    rows = compare(db_path=db, since="2026-05-14", expected=expected, seed=42)
    assert rows[0]["decision"] == "INSUFFICIENT_SAMPLE"
    assert rows[0]["n"] == 0
