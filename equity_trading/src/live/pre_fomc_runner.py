"""Pre-FOMC drift runner.

Two entry points:
- run_pre_fomc: place a long XLK order at ~12:30 ET on the trading day
  immediately preceding an FOMC announcement. Marks the position with
  hold_overnight=1 so the EOD runner skips it.
- run_fomc_close: at ~13:55 ET on the FOMC announcement day, close every
  open position with hold_overnight=1.

Reference: Lucca-Moench (J.Finance 2015) — the 24h preceding FOMC announcements
account for >80% of equity premium 1994-2011. Effect is weaker post-2015 but
7-yr (2019-2026) backtest still shows EV +30.83 (WR 0.649, n=57) on XLK.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Sequence

import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay

from equity_trading.src.live.circuit_breaker import check_circuit
from equity_trading.src.live.position_manager import check_capacity
from equity_trading.src.strategy.strategies.pre_fomc import PreFOMCDriftStrategy


STOP_PCT = 0.05      # ±5% emergency only — backtest holds ~24h with no tactical stops.
TARGET_PCT = 0.05


@lru_cache(maxsize=1)
def _us_business_day() -> CustomBusinessDay:
    """One US business-day offset that excludes federal holidays.

    Cached because constructing it touches the holiday calendar each time.
    """
    return CustomBusinessDay(calendar=USFederalHolidayCalendar())


def _previous_us_trading_day(d: dt.date) -> dt.date:
    """Return the most recent US trading day strictly before `d` (skips weekends + federal holidays)."""
    bday = _us_business_day()
    prev = (pd.Timestamp(d) - bday).date()
    return prev


def _compute_pre_fomc_set(fomc_dates: Sequence[dt.date]) -> set[dt.date]:
    """Compute the set of trading days that are the trading-day-immediately-before each FOMC.

    Skips FOMC dates that fall on weekends (emergency announcements aren't
    tradable in advance with this strategy).
    """
    out: set[dt.date] = set()
    for f in fomc_dates:
        if f.weekday() in (5, 6):
            continue
        out.add(_previous_us_trading_day(f))
    return out


def _is_pre_fomc_day(today: dt.date, fomc_dates: Sequence[dt.date]) -> bool:
    """True if today is the trading day immediately before any FOMC announcement.

    Uses pandas USFederalHolidayCalendar — handles weekends and federal holidays
    correctly (e.g. an FOMC on the Tuesday after MLK Monday yields pre-FOMC on
    the preceding Friday).
    """
    return today in _compute_pre_fomc_set(fomc_dates)


def run_pre_fomc(
    symbol: str,
    db_path: Path | str,
    broker,
    fetcher,
    now_utc: datetime | None = None,
    fomc_dates: Sequence[dt.date] | None = None,
    vix_min: float | None = None,
    vix_daily: "pd.DataFrame | None" = None,  # type: ignore[name-defined]
) -> dict:
    """Place a long position on `symbol` if today is a pre-FOMC trading day.

    If vix_min and vix_daily are provided, only fires when the prior trading
    day's VIX close > vix_min. Backtest shows VIX > 22 → WR 0.700, avg +1.555%
    on TECL pre-FOMC.

    Returns: {"entries_placed": int, "errors": list[str], "halted": bool?}
    """
    db_path = Path(db_path)
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    if fomc_dates is None:
        fomc_dates = PreFOMCDriftStrategy.DEFAULT_FOMC_DATES

    started_at = now_utc.isoformat()
    entries_placed = 0
    errors: list[str] = []

    # Open bot_runs row
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO bot_runs (run_type, started_at_utc, status)
               VALUES ('pre_fomc', ?, 'running')""",
            (started_at,),
        )
        run_id = cur.lastrowid
        conn.commit()

    try:
        from zoneinfo import ZoneInfo
        ny_today = now_utc.astimezone(ZoneInfo("America/New_York")).date()

        if not _is_pre_fomc_day(ny_today, fomc_dates):
            finished_at = datetime.now(timezone.utc).isoformat()
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """UPDATE bot_runs SET finished_at_utc=?, status='success',
                       error_message=?, entries_placed=0 WHERE id=?""",
                    (finished_at, f"not a pre-FOMC day ({ny_today.isoformat()})", run_id),
                )
                conn.commit()
            return {"entries_placed": 0, "errors": [], "halted": False}

        # Optional VIX regime filter: skip if prior trading day's VIX close <= vix_min.
        if vix_min is not None and vix_daily is not None and len(vix_daily) > 0:
            idx = vix_daily.index
            vix_dates = (idx.tz_convert("America/New_York").date
                         if idx.tz is not None else idx.date)
            vix_dates = list(vix_dates)
            prior_close: float | None = None
            for d, c in zip(reversed(vix_dates), reversed(vix_daily["close"].tolist())):
                if d < ny_today:
                    prior_close = float(c)
                    break
            if prior_close is None or prior_close <= float(vix_min):
                reason = (f"VIX prior close {prior_close:.2f} <= {vix_min} (skip)"
                          if prior_close is not None else "VIX prior close unavailable")
                finished_at = datetime.now(timezone.utc).isoformat()
                with sqlite3.connect(db_path) as conn:
                    conn.execute(
                        """UPDATE bot_runs SET finished_at_utc=?, status='success',
                           error_message=?, entries_placed=0 WHERE id=?""",
                        (finished_at, reason, run_id),
                    )
                    conn.commit()
                return {"entries_placed": 0, "errors": [reason], "halted": False}

        account = broker.get_account()
        circuit = check_circuit(db_path=db_path, alpaca_account=account, now_utc=now_utc)
        if circuit.halted:
            finished_at = datetime.now(timezone.utc).isoformat()
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """UPDATE bot_runs SET finished_at_utc=?, status='success',
                       error_message=?, entries_placed=0 WHERE id=?""",
                    (finished_at, circuit.reason, run_id),
                )
                conn.commit()
            return {"entries_placed": 0, "errors": [circuit.reason], "halted": True}

        # Fetch the most recent 5min bar for reference price
        bar_start = now_utc - timedelta(minutes=15)
        bars = fetcher.fetch(symbol=symbol, start=bar_start, end=now_utc, timeframe_minutes=5)
        if len(bars) == 0:
            errors.append(f"{symbol}: no recent 5min bar available")
            finished_at = datetime.now(timezone.utc).isoformat()
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """UPDATE bot_runs SET finished_at_utc=?, status='success',
                       error_message=?, entries_placed=0 WHERE id=?""",
                    (finished_at, "no bar", run_id),
                )
                conn.commit()
            return {"entries_placed": 0, "errors": errors, "halted": False}

        ref_price = float(bars["close"].iloc[-1])
        cap = check_capacity(
            symbol=symbol, reference_price=ref_price,
            db_path=db_path, alpaca_account=account,
        )
        if not cap.allowed:
            finished_at = datetime.now(timezone.utc).isoformat()
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """UPDATE bot_runs SET finished_at_utc=?, status='success',
                       error_message=?, entries_placed=0 WHERE id=?""",
                    (finished_at, cap.reason, run_id),
                )
                conn.commit()
            return {"entries_placed": 0, "errors": [cap.reason], "halted": False}

        stop_price = ref_price * (1 - STOP_PCT)
        target_price = ref_price * (1 + TARGET_PCT)
        ids = broker.submit_bracket_buy(
            symbol=symbol, qty=cap.suggested_qty,
            stop_price=stop_price, target_price=target_price,
        )

        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """INSERT INTO positions (symbol, strategy_name, entry_ts_utc,
                   entry_price, entry_qty, stop_price, target_price,
                   alpaca_entry_order_id, status, hold_overnight)
                   VALUES (?, 'pre_fomc_drift', ?, ?, ?, ?, ?, ?, 'open', 1)""",
                (symbol, now_utc.isoformat(), ref_price, cap.suggested_qty,
                 stop_price, target_price, ids.get("entry_order_id")),
            )
            conn.commit()
        entries_placed = 1

        finished_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """UPDATE bot_runs SET finished_at_utc=?, status='success',
                   entries_placed=? WHERE id=?""",
                (finished_at, entries_placed, run_id),
            )
            conn.commit()
        return {"entries_placed": entries_placed, "errors": errors, "halted": False}

    except Exception as e:
        finished_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """UPDATE bot_runs SET finished_at_utc=?, status='error',
                   error_message=? WHERE id=?""",
                (finished_at, str(e), run_id),
            )
            conn.commit()
        raise


def run_fomc_close(
    db_path: Path | str,
    broker,
    fetcher,
    now_utc: datetime | None = None,
) -> dict:
    """Close all open positions with hold_overnight=1.

    Intended to be triggered ~13:55 ET on FOMC announcement days, before the
    14:00 ET statement releases. The 'fomc_close' bot_run row makes the action
    auditable.
    """
    db_path = Path(db_path)
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    started_at = now_utc.isoformat()
    positions_closed = 0
    errors: list[str] = []

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO bot_runs (run_type, started_at_utc, status)
               VALUES ('fomc_close', ?, 'running')""",
            (started_at,),
        )
        run_id = cur.lastrowid
        conn.commit()

    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                """SELECT id, symbol, entry_price, entry_qty FROM positions
                   WHERE status='open' AND COALESCE(hold_overnight, 0) = 1"""
            ).fetchall()

        for pid, symbol, entry_price, entry_qty in rows:
            try:
                bars = fetcher.fetch(
                    symbol=symbol, start=now_utc - timedelta(minutes=15),
                    end=now_utc, timeframe_minutes=5,
                )
                exit_price = float(bars["close"].iloc[-1]) if len(bars) > 0 else float(entry_price)
                broker.close_position(symbol)
                pnl_pct = (exit_price - entry_price) / entry_price
                realized = (exit_price - entry_price) * entry_qty
                with sqlite3.connect(db_path) as conn:
                    conn.execute(
                        """UPDATE positions
                           SET exit_ts_utc=?, exit_price=?, exit_type='time',
                               pnl_pct=?, realized_pnl_usd=?, status='closed'
                           WHERE id=?""",
                        (now_utc.isoformat(), exit_price, pnl_pct, realized, pid),
                    )
                    conn.commit()
                positions_closed += 1
            except Exception as e:
                errors.append(f"{symbol}: {type(e).__name__}: {e}")

        finished_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """UPDATE bot_runs SET finished_at_utc=?, status='success',
                   exits_placed=? WHERE id=?""",
                (finished_at, positions_closed, run_id),
            )
            conn.commit()
        return {"positions_closed": positions_closed, "errors": errors}

    except Exception as e:
        finished_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """UPDATE bot_runs SET finished_at_utc=?, status='error',
                   error_message=? WHERE id=?""",
                (finished_at, str(e), run_id),
            )
            conn.commit()
        raise
