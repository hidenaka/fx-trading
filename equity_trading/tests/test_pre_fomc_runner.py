"""Tests for pre_fomc_runner (entry on pre-FOMC day) and fomc_closer (exit on FOMC day)."""
import datetime as dt
import sqlite3
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pandas as pd

from equity_trading.src.live.pre_fomc_runner import run_pre_fomc, run_fomc_close
from equity_trading.src.state.migrations import init_database


def _account(equity: float = 10000.0) -> dict:
    return {"account_number": "T", "status": "ACTIVE", "currency": "USD",
            "cash": equity, "equity": equity, "buying_power": equity * 4,
            "pattern_day_trader": False}


def _bar(price: float, when: pd.Timestamp) -> pd.DataFrame:
    return pd.DataFrame(
        {"open": [price], "high": [price + 0.05], "low": [price - 0.05],
         "close": [price], "volume": [10000]},
        index=pd.DatetimeIndex([when], tz="UTC"),
    )


# === pre_fomc_runner ===


def test_no_entry_on_non_pre_fomc_day(tmp_path):
    """If today is NOT the trading day before an FOMC announcement, no entry."""
    db = tmp_path / "trades.sqlite"
    init_database(db)
    fetcher = MagicMock()
    broker = MagicMock()
    broker.get_account.return_value = _account()

    # 2026-05-15 — not a pre-FOMC day
    summary = run_pre_fomc(
        symbol="XLK", db_path=db, broker=broker, fetcher=fetcher,
        now_utc=datetime(2026, 5, 15, 16, 30, tzinfo=timezone.utc),
        fomc_dates=[dt.date(2026, 6, 17)],  # next FOMC far away
    )
    assert summary["entries_placed"] == 0
    broker.submit_bracket_buy.assert_not_called()


def test_entry_placed_on_pre_fomc_day(tmp_path):
    """Today is the trading day immediately before an FOMC announcement → place XLK long."""
    db = tmp_path / "trades.sqlite"
    init_database(db)

    fetcher = MagicMock()
    fetcher.fetch.return_value = _bar(price=200.0,
                                      when=pd.Timestamp("2026-05-06 16:30", tz="UTC"))

    broker = MagicMock()
    broker.get_account.return_value = _account()
    broker.submit_bracket_buy.return_value = {"entry_order_id": "ord-001"}

    # 2026-05-06 = pre-FOMC for 2026-05-07 announcement
    summary = run_pre_fomc(
        symbol="XLK", db_path=db, broker=broker, fetcher=fetcher,
        now_utc=datetime(2026, 5, 6, 16, 30, tzinfo=timezone.utc),  # 12:30 ET in EDT
        fomc_dates=[dt.date(2026, 5, 7)],
    )
    assert summary["entries_placed"] == 1
    broker.submit_bracket_buy.assert_called_once()

    # Position should have hold_overnight=1
    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            """SELECT symbol, strategy_name, status, hold_overnight FROM positions"""
        ).fetchall()
    assert len(rows) == 1
    assert rows[0] == ("XLK", "pre_fomc_drift", "open", 1)


def test_pre_fomc_skips_when_capacity_full(tmp_path):
    """3 open positions → pre-FOMC entry rejected."""
    db = tmp_path / "trades.sqlite"
    init_database(db)

    with sqlite3.connect(db) as conn:
        for sym in ("AAPL", "MSFT", "GOOG"):
            conn.execute(
                """INSERT INTO positions (symbol, strategy_name, entry_ts_utc,
                   entry_price, entry_qty, stop_price, target_price, status)
                   VALUES (?, 'gap_fill', '2026-05-06T13:30:00Z', 100.0, 5,
                           99.0, 102.0, 'open')""",
                (sym,),
            )
        conn.commit()

    fetcher = MagicMock()
    fetcher.fetch.return_value = _bar(200.0, pd.Timestamp("2026-05-06 16:30", tz="UTC"))
    broker = MagicMock()
    broker.get_account.return_value = _account()

    summary = run_pre_fomc(
        symbol="XLK", db_path=db, broker=broker, fetcher=fetcher,
        now_utc=datetime(2026, 5, 6, 16, 30, tzinfo=timezone.utc),
        fomc_dates=[dt.date(2026, 5, 7)],
    )
    assert summary["entries_placed"] == 0


def test_pre_fomc_halts_on_circuit_break(tmp_path):
    """Circuit-breaker halt blocks pre-FOMC entry."""
    db = tmp_path / "trades.sqlite"
    init_database(db)
    # Seed loss large enough to trip the breaker
    with sqlite3.connect(db) as conn:
        conn.execute(
            """INSERT INTO positions (symbol, strategy_name, entry_ts_utc,
               entry_price, entry_qty, stop_price, target_price, exit_ts_utc,
               exit_price, exit_type, pnl_pct, realized_pnl_usd, status)
               VALUES ('SPY', 'gap_fill', '2026-05-06T13:30:00Z', 100.0, 25,
                       99.0, 102.0, '2026-05-06T15:00:00Z', 88.0, 'stop',
                       -0.12, -300.0, 'closed')""",
        )
        conn.commit()

    fetcher = MagicMock()
    fetcher.fetch.return_value = _bar(200.0, pd.Timestamp("2026-05-06 16:30", tz="UTC"))
    broker = MagicMock()
    broker.get_account.return_value = _account()

    summary = run_pre_fomc(
        symbol="XLK", db_path=db, broker=broker, fetcher=fetcher,
        now_utc=datetime(2026, 5, 6, 16, 30, tzinfo=timezone.utc),
        fomc_dates=[dt.date(2026, 5, 7)],
    )
    assert summary.get("halted") is True
    broker.submit_bracket_buy.assert_not_called()


# === fomc_closer ===


def test_fomc_closer_closes_hold_overnight_positions(tmp_path):
    """run_fomc_close should close all positions with hold_overnight=1."""
    db = tmp_path / "trades.sqlite"
    init_database(db)
    with sqlite3.connect(db) as conn:
        # Two positions: one pre-FOMC (hold_overnight=1), one normal gap_fill
        conn.execute(
            """INSERT INTO positions (symbol, strategy_name, entry_ts_utc,
               entry_price, entry_qty, stop_price, target_price, status, hold_overnight)
               VALUES ('XLK', 'pre_fomc_drift', '2026-05-06T16:30:00Z', 200.0, 5,
                       190.0, 210.0, 'open', 1)""",
        )
        conn.execute(
            """INSERT INTO positions (symbol, strategy_name, entry_ts_utc,
               entry_price, entry_qty, stop_price, target_price, status, hold_overnight)
               VALUES ('SPY', 'gap_fill', '2026-05-07T13:30:00Z', 100.0, 25,
                       99.0, 102.0, 'open', 0)""",
        )
        conn.commit()

    fetcher = MagicMock()
    fetcher.fetch.return_value = _bar(202.0, pd.Timestamp("2026-05-07 17:55", tz="UTC"))
    broker = MagicMock()
    broker.get_account.return_value = _account()
    broker.close_position = MagicMock()

    summary = run_fomc_close(
        db_path=db, broker=broker, fetcher=fetcher,
        now_utc=datetime(2026, 5, 7, 17, 55, tzinfo=timezone.utc),  # 13:55 ET
    )
    assert summary["positions_closed"] == 1
    broker.close_position.assert_called_once_with("XLK")

    # The pre_fomc position is now closed; gap_fill is still open.
    with sqlite3.connect(db) as conn:
        statuses = dict(conn.execute(
            "SELECT symbol, status FROM positions"
        ).fetchall())
    assert statuses["XLK"] == "closed"
    assert statuses["SPY"] == "open"


def test_fomc_closer_no_positions(tmp_path):
    """No hold_overnight positions → closer is a no-op."""
    db = tmp_path / "trades.sqlite"
    init_database(db)
    fetcher = MagicMock()
    broker = MagicMock()
    summary = run_fomc_close(
        db_path=db, broker=broker, fetcher=fetcher,
        now_utc=datetime(2026, 5, 7, 17, 55, tzinfo=timezone.utc),
    )
    assert summary["positions_closed"] == 0
    broker.close_position.assert_not_called()
