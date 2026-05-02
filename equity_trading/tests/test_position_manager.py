import sqlite3
from pathlib import Path

import pytest

from equity_trading.src.live.position_manager import CapacityCheck, check_capacity
from equity_trading.src.state.migrations import init_database


def _seed_open_position(db_path: Path, symbol: str = "SPY"):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO positions (symbol, strategy_name, entry_ts_utc, entry_price,
                entry_qty, stop_price, target_price, status)
            VALUES (?, 'gap_fill', '2026-05-02T13:30:00Z', 100.0, 5, 99.0, 102.0, 'open')
            """,
            (symbol,),
        )
        conn.commit()


def _account(equity: float = 10000.0) -> dict:
    return {
        "account_number": "TEST",
        "status": "ACTIVE",
        "currency": "USD",
        "cash": equity,
        "equity": equity,
        "buying_power": equity * 4,
        "pattern_day_trader": False,
    }


def test_check_capacity_allows_when_no_positions(tmp_path):
    db = tmp_path / "trades.sqlite"
    init_database(db)
    result = check_capacity(
        symbol="XLK", reference_price=250.0,
        db_path=db, alpaca_account=_account(equity=10000.0),
    )
    assert result.allowed is True
    # 25% of $10k = $2500, capped at $2500 → buy 10 shares at $250
    assert result.suggested_qty == 10
    assert result.capital_to_deploy_usd == pytest.approx(2500.0)


def test_check_capacity_caps_at_2500_when_account_large(tmp_path):
    db = tmp_path / "trades.sqlite"
    init_database(db)
    result = check_capacity(
        symbol="XLK", reference_price=250.0,
        db_path=db, alpaca_account=_account(equity=100000.0),
    )
    # 25% of $100k = $25k, but cap is $2500 → only 10 shares
    assert result.allowed is True
    assert result.suggested_qty == 10
    assert result.capital_to_deploy_usd == pytest.approx(2500.0)


def test_check_capacity_denies_when_max_concurrent_open(tmp_path):
    db = tmp_path / "trades.sqlite"
    init_database(db)
    _seed_open_position(db, "SPY")
    _seed_open_position(db, "QQQ")
    _seed_open_position(db, "IWM")
    result = check_capacity(
        symbol="XLK", reference_price=250.0,
        db_path=db, alpaca_account=_account(),
    )
    assert result.allowed is False
    assert "concurrent" in result.reason.lower() or "max" in result.reason.lower()


def test_check_capacity_denies_duplicate_symbol(tmp_path):
    db = tmp_path / "trades.sqlite"
    init_database(db)
    _seed_open_position(db, "XLK")
    result = check_capacity(
        symbol="XLK", reference_price=250.0,
        db_path=db, alpaca_account=_account(),
    )
    assert result.allowed is False
    assert "already" in result.reason.lower() or "duplicate" in result.reason.lower()


def test_check_capacity_allows_different_symbol_when_one_open(tmp_path):
    db = tmp_path / "trades.sqlite"
    init_database(db)
    _seed_open_position(db, "SPY")
    result = check_capacity(
        symbol="XLK", reference_price=250.0,
        db_path=db, alpaca_account=_account(),
    )
    assert result.allowed is True


def test_check_capacity_denies_when_share_price_exceeds_allocation(tmp_path):
    db = tmp_path / "trades.sqlite"
    init_database(db)
    # $2500 allocation, $3000 share price → can't afford 1 share
    result = check_capacity(
        symbol="EXPENSIVE", reference_price=3000.0,
        db_path=db, alpaca_account=_account(),
    )
    assert result.allowed is False
    assert "insufficient" in result.reason.lower() or "afford" in result.reason.lower()


def test_check_capacity_ignores_closed_positions(tmp_path):
    """Closed positions don't count toward max_concurrent or duplicate."""
    db = tmp_path / "trades.sqlite"
    init_database(db)
    with sqlite3.connect(db) as conn:
        # Insert 3 closed positions
        for sym in ("SPY", "QQQ", "XLK"):
            conn.execute(
                """
                INSERT INTO positions (symbol, strategy_name, entry_ts_utc, entry_price,
                    entry_qty, stop_price, target_price, status)
                VALUES (?, 'gap_fill', '2026-05-02T13:30:00Z', 100.0, 5, 99.0, 102.0, 'closed')
                """,
                (sym,),
            )
        conn.commit()
    result = check_capacity(
        symbol="XLK", reference_price=250.0,
        db_path=db, alpaca_account=_account(),
    )
    assert result.allowed is True


def test_capacity_check_dataclass_is_frozen():
    c = CapacityCheck(allowed=True, reason="", suggested_qty=10, capital_to_deploy_usd=2500.0)
    with pytest.raises((AttributeError, ValueError)):
        c.allowed = False  # type: ignore
