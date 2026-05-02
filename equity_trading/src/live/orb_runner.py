"""Opening Range Breakout (ORB) runner — 敏腕モード edition.

Runs every 5 minutes after the 60-min OR window (10:30 ET → 15:50 ET).
For each leveraged ETF (TECL/TQQQ/TNA), checks whether the latest bar's
close has broken above the day's opening range high. If so, places a
bracket buy and inserts the position.

Validated edge (7-yr RTH backtest, post-fix simulator):
  - TECL (3x XLK): WR 0.543, EV +108.38 (n=486)
  - TQQQ (3x QQQ): WR 0.565, EV +76.96 (n=531)
  - TNA  (3x IWM): WR 0.534, EV +62.06 (n=369)
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from equity_trading.src.live.circuit_breaker import check_circuit
from equity_trading.src.live.position_manager import check_capacity
from equity_trading.src.live.signal_evaluator import evaluate_live_signal
from equity_trading.src.strategy.strategies.opening_range_breakout import OpeningRangeBreakoutStrategy


ORB_SYMBOLS_AND_ATR: dict[str, float] = {
    # ATR % medians from 7-yr cache; used by signal_evaluator default exit logic.
    "TECL": 0.40,
    "TQQQ": 0.34,
    "TNA":  0.40,
}
ORB_PARAMS = {"or_window_bars": 12}  # 60-min opening range


def run_orb(
    db_path: Path | str,
    broker,
    fetcher,
    now_utc: datetime | None = None,
) -> dict:
    """Run a single ORB sweep. Place at most one entry per symbol per call."""
    db_path = Path(db_path)
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    started_at = now_utc.isoformat()
    entries_placed = 0
    errors: list[str] = []

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO bot_runs (run_type, started_at_utc, status)
               VALUES ('orb', ?, 'running')""",
            (started_at,),
        )
        run_id = cur.lastrowid
        conn.commit()

    try:
        strategy = OpeningRangeBreakoutStrategy()
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

        for symbol, atr_pct in ORB_SYMBOLS_AND_ATR.items():
            try:
                bars_5min = fetcher.fetch(
                    symbol=symbol, start=now_utc - timedelta(hours=10),
                    end=now_utc, timeframe_minutes=5,
                )
                daily = fetcher.fetch(
                    symbol=symbol, start=now_utc - timedelta(days=400),
                    end=now_utc, timeframe_minutes=1440,
                )
                if len(bars_5min) < 30 or len(daily) < 200:
                    errors.append(f"{symbol}: insufficient bars ({len(bars_5min)} 5min, {len(daily)} daily)")
                    continue

                signal = evaluate_live_signal(
                    strategy=strategy, bars_5min=bars_5min, daily=daily,
                    atr_pct=atr_pct, params=ORB_PARAMS, bar_index=-1,
                )
                if not signal.should_enter:
                    continue

                cap = check_capacity(
                    symbol=symbol, reference_price=signal.entry_reference_price,
                    db_path=db_path, alpaca_account=account,
                )
                if not cap.allowed:
                    continue

                ids = broker.submit_bracket_buy(
                    symbol=symbol, qty=cap.suggested_qty,
                    stop_price=signal.stop_price, target_price=signal.target_price,
                )
                with sqlite3.connect(db_path) as conn:
                    conn.execute(
                        """INSERT INTO positions (symbol, strategy_name, entry_ts_utc,
                           entry_price, entry_qty, stop_price, target_price,
                           alpaca_entry_order_id, status)
                           VALUES (?, 'opening_range_breakout', ?, ?, ?, ?, ?, ?, 'open')""",
                        (symbol, now_utc.isoformat(), signal.entry_reference_price,
                         cap.suggested_qty, signal.stop_price, signal.target_price,
                         ids.get("entry_order_id")),
                    )
                    conn.commit()
                entries_placed += 1
            except Exception as e:
                errors.append(f"{symbol}: {type(e).__name__}: {e}")

        finished_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """UPDATE bot_runs SET finished_at_utc=?, status='success',
                   entries_placed=? WHERE id=?""",
                (finished_at, entries_placed, run_id),
            )
            conn.commit()
        return {"entries_placed": entries_placed, "errors": errors}

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
