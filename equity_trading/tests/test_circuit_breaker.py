import sqlite3
from datetime import datetime, timezone

import pytest

from equity_trading.src.live.circuit_breaker import CircuitState, check_circuit
from equity_trading.src.state.migrations import init_database


def _seed_closed_position(db_path, realized_pnl, exit_ts="2026-05-04T19:00:00Z"):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """INSERT INTO positions (symbol, strategy_name, entry_ts_utc, entry_price,
               entry_qty, stop_price, target_price, exit_ts_utc, exit_price,
               exit_type, pnl_pct, realized_pnl_usd, status)
               VALUES ('XLK', 'mean_reversion', '2026-05-04T14:00:00Z', 250.0, 10,
               245.0, 252.0, ?, 0.0, 'time', ?, ?, 'closed')""",
            (exit_ts, realized_pnl / 2500.0, realized_pnl),
        )
        conn.commit()


def _account(equity=10000.0):
    return {"account_number": "T", "status": "ACTIVE", "currency": "USD",
            "cash": equity, "equity": equity, "buying_power": equity * 4,
            "pattern_day_trader": False}


def test_circuit_not_halted_when_no_losses(tmp_path):
    db = tmp_path / "trades.sqlite"
    init_database(db)
    state = check_circuit(
        db_path=db, alpaca_account=_account(),
        now_utc=datetime(2026, 5, 4, 19, 0, tzinfo=timezone.utc),
    )
    assert state.halted is False
    assert state.today_realized_pnl_usd == 0.0


def test_circuit_not_halted_at_minus_1_pct(tmp_path):
    db = tmp_path / "trades.sqlite"
    init_database(db)
    _seed_closed_position(db, realized_pnl=-100.0)  # -$100 on $10k = -1%
    state = check_circuit(
        db_path=db, alpaca_account=_account(),
        now_utc=datetime(2026, 5, 4, 19, 0, tzinfo=timezone.utc),
    )
    assert state.halted is False
    assert state.daily_dd_pct == pytest.approx(-1.0, abs=0.01)


def test_circuit_halted_at_minus_2_pct(tmp_path):
    db = tmp_path / "trades.sqlite"
    init_database(db)
    _seed_closed_position(db, realized_pnl=-200.0)  # -$200 on $10k = -2%
    state = check_circuit(
        db_path=db, alpaca_account=_account(),
        now_utc=datetime(2026, 5, 4, 19, 0, tzinfo=timezone.utc),
    )
    assert state.halted is True
    assert "circuit" in state.reason.lower() or "halt" in state.reason.lower() or "drawdown" in state.reason.lower()


def test_circuit_halted_at_minus_3_pct(tmp_path):
    db = tmp_path / "trades.sqlite"
    init_database(db)
    _seed_closed_position(db, realized_pnl=-300.0)
    state = check_circuit(
        db_path=db, alpaca_account=_account(),
        now_utc=datetime(2026, 5, 4, 19, 0, tzinfo=timezone.utc),
    )
    assert state.halted is True


def test_circuit_only_counts_today(tmp_path):
    """A loss on a previous day should NOT trigger today's halt."""
    db = tmp_path / "trades.sqlite"
    init_database(db)
    _seed_closed_position(db, realized_pnl=-300.0, exit_ts="2026-05-01T19:00:00Z")
    state = check_circuit(
        db_path=db, alpaca_account=_account(),
        now_utc=datetime(2026, 5, 4, 19, 0, tzinfo=timezone.utc),
    )
    assert state.halted is False


def test_circuit_state_dataclass_is_frozen():
    s = CircuitState(halted=False, reason="ok", today_realized_pnl_usd=0.0,
                     daily_dd_pct=0.0, threshold_pct=-2.0)
    with pytest.raises((AttributeError, ValueError)):
        s.halted = True  # type: ignore
