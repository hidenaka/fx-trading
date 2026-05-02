"""End-to-end daily cycle: morning → intraday × 2 → eod.

All Alpaca + fetcher calls are mocked. Verifies SQLite state and runner
return values at each step.
"""
import sqlite3
from datetime import datetime, timezone
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

from equity_trading.src.live.eod_runner import run_eod
from equity_trading.src.live.intraday_runner import run_intraday
from equity_trading.src.live.morning_runner import run_morning
from equity_trading.src.state.migrations import init_database


def _gap_down_first_bar(open_price: float, when: str = "2026-05-04 13:30") -> pd.DataFrame:
    """Single 5min bar at NY 09:30 with given open price."""
    return pd.DataFrame(
        {"open": [open_price], "high": [open_price + 0.05], "low": [open_price - 0.05],
         "close": [open_price], "volume": [10000]},
        index=pd.date_range(when, periods=1, freq="5min", tz="UTC"),
    )


def _daily_with_prev_close(prev_close: float, n: int = 250) -> pd.DataFrame:
    closes = list(np.linspace(prev_close * 0.7, prev_close, n))
    return pd.DataFrame(
        {"close": closes},
        index=pd.date_range("2025-08-26", periods=n, freq="1D", tz="UTC"),
    )


def _xlk_5min_flat(n: int = 100, when: str = "2026-05-04 14:30") -> pd.DataFrame:
    """Flat XLK bars - no mean_reversion signal."""
    closes = np.full(n, 250.0)
    return pd.DataFrame(
        {"open": closes, "high": closes + 0.05, "low": closes - 0.05, "close": closes,
         "volume": [10000] * n},
        index=pd.date_range(when, periods=n, freq="5min", tz="UTC"),
    )


def _xlk_close_now(price: float = 251.0, when: str = "2026-05-04 19:55") -> pd.DataFrame:
    """One-bar fixture for EOD's exit-price lookup."""
    return pd.DataFrame(
        {"open": [price], "high": [price + 0.05], "low": [price - 0.05], "close": [price],
         "volume": [10000]},
        index=pd.date_range(when, periods=1, freq="5min", tz="UTC"),
    )


def _account(equity: float = 10000.0) -> dict:
    return {"account_number": "T", "status": "ACTIVE", "currency": "USD",
            "cash": equity, "equity": equity, "buying_power": equity * 4,
            "pattern_day_trader": False}


def test_full_daily_cycle_morning_intraday_eod(tmp_path):
    db = tmp_path / "trades.sqlite"
    init_database(db)

    broker = MagicMock()
    broker.get_account.return_value = _account()
    broker.submit_bracket_buy.return_value = {
        "entry_order_id": "ord-spy-1", "client_order_id": "cli-1",
    }
    broker.close_position.return_value = {"order_id": "close-1", "qty": "25"}

    # ===== Morning: SPY gap-down 1% =====
    morning_fetcher = MagicMock()
    def morning_fetch(symbol, start, end, timeframe_minutes):
        if symbol == "SPY":
            if timeframe_minutes == 5:
                return _gap_down_first_bar(99.0)
            return _daily_with_prev_close(100.0)
        # Other symbols: no gap → no signal
        if timeframe_minutes == 5:
            return _gap_down_first_bar(100.0)
        return _daily_with_prev_close(100.0)
    morning_fetcher.fetch.side_effect = morning_fetch

    morning_summary = run_morning(
        symbols=["SPY", "QQQ", "IWM", "XLK"],
        db_path=db,
        broker=broker,
        fetcher=morning_fetcher,
        now_utc=datetime(2026, 5, 4, 13, 35, tzinfo=timezone.utc),
    )
    assert morning_summary["entries_placed"] == 1, morning_summary

    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            "SELECT symbol, status FROM positions"
        ).fetchall()
    assert rows == [("SPY", "open")]

    # ===== Intraday #1: XLK no signal (flat) =====
    intraday_fetcher = MagicMock()
    def intraday_fetch(symbol, start, end, timeframe_minutes):
        if timeframe_minutes == 5:
            return _xlk_5min_flat()
        return _daily_with_prev_close(250.0)
    intraday_fetcher.fetch.side_effect = intraday_fetch

    intra1 = run_intraday(
        db_path=db, broker=broker, fetcher=intraday_fetcher,
        now_utc=datetime(2026, 5, 4, 15, 30, tzinfo=timezone.utc),
    )
    assert intra1["entries_placed"] == 0

    # SPY position should still be open
    with sqlite3.connect(db) as conn:
        n_open = conn.execute(
            "SELECT COUNT(*) FROM positions WHERE status='open'"
        ).fetchone()[0]
    assert n_open == 1

    # ===== Intraday #2: XLK no signal (still flat) =====
    intra2 = run_intraday(
        db_path=db, broker=broker, fetcher=intraday_fetcher,
        now_utc=datetime(2026, 5, 4, 16, 0, tzinfo=timezone.utc),
    )
    assert intra2["entries_placed"] == 0

    # ===== EOD: close SPY at $99.50 (small win) =====
    eod_fetcher = MagicMock()
    def eod_fetch(symbol, start, end, timeframe_minutes):
        if symbol == "SPY":
            return _xlk_close_now(price=99.50, when="2026-05-04 19:55")
        return _xlk_close_now(price=250.0, when="2026-05-04 19:55")
    eod_fetcher.fetch.side_effect = eod_fetch

    eod_summary = run_eod(
        db_path=db,
        broker=broker,
        fetcher=eod_fetcher,
        now_utc=datetime(2026, 5, 4, 19, 55, tzinfo=timezone.utc),
    )
    assert eod_summary["positions_closed"] == 1
    broker.close_position.assert_called_with("SPY")

    # ===== Verify final state =====
    with sqlite3.connect(db) as conn:
        # All positions closed
        n_open = conn.execute(
            "SELECT COUNT(*) FROM positions WHERE status='open'"
        ).fetchone()[0]
        assert n_open == 0

        # SPY position has exit info
        spy_row = conn.execute(
            """SELECT exit_type, exit_price, pnl_pct, realized_pnl_usd
               FROM positions WHERE symbol='SPY'"""
        ).fetchone()
        assert spy_row[0] == "time"
        assert abs(spy_row[1] - 99.50) < 0.01
        # Entry was at 99.0, exit at 99.50 → +0.50/99 = +0.00505
        assert abs(spy_row[2] - 0.00505) < 0.001
        # qty was 25 (= 2500/99 floor), realized = 0.50 * 25 = 12.50
        assert abs(spy_row[3] - 12.50) < 0.5

        # daily_pnl row exists
        dp = conn.execute(
            "SELECT trade_date, n_entries, n_exits FROM daily_pnl"
        ).fetchone()
        assert dp[0] == "2026-05-04"
        assert dp[1] == 1  # 1 entry today
        assert dp[2] == 1  # 1 exit today

        # 4 bot_runs rows (1 morning, 2 intraday, 1 eod), all 'success'
        runs = conn.execute(
            "SELECT run_type, status FROM bot_runs ORDER BY id"
        ).fetchall()
        run_types = [r[0] for r in runs]
        statuses = [r[1] for r in runs]
        assert run_types == ["morning", "intraday", "intraday", "eod"]
        assert all(s == "success" for s in statuses), runs
