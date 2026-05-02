"""Intraday mean_reversion runner. Runs every 5 minutes during market hours."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from equity_trading.src.live.position_manager import check_capacity
from equity_trading.src.live.signal_evaluator import evaluate_live_signal
from equity_trading.src.strategy.strategies.mean_reversion import MeanReversionStrategy


XLK_PARAMS = {"threshold": 0.40}
XLK_ATR_PCT = 0.129  # Phase 0 calibrated median


def run_intraday(
    db_path: Path | str,
    broker,
    fetcher,
    now_utc: datetime | None = None,
) -> dict:
    """Run the 5-min intraday mean_reversion check on XLK.

    Returns: {"entries_placed": int, "errors": list[str]}
    """
    db_path = Path(db_path)
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    started_at = now_utc.isoformat()
    entries_placed = 0
    errors: list[str] = []

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO bot_runs (run_type, started_at_utc, status)
               VALUES ('intraday', ?, 'running')""",
            (started_at,),
        )
        run_id = cur.lastrowid
        conn.commit()

    try:
        strategy = MeanReversionStrategy()
        symbol = "XLK"

        try:
            # Fetch enough 5min bars for indicator warmup (RSI 14, BB 20, vol 20, etc.) — 100 bars is plenty
            bars_5min = fetcher.fetch(
                symbol=symbol,
                start=now_utc - timedelta(hours=10),
                end=now_utc,
                timeframe_minutes=5,
            )
            daily = fetcher.fetch(
                symbol=symbol,
                start=now_utc - timedelta(days=400),
                end=now_utc,
                timeframe_minutes=1440,
            )
            if len(bars_5min) < 30 or len(daily) < 200:
                errors.append(
                    f"{symbol}: insufficient bars ({len(bars_5min)} 5min, {len(daily)} daily)"
                )
            else:
                signal = evaluate_live_signal(
                    strategy=strategy,
                    bars_5min=bars_5min,
                    daily=daily,
                    atr_pct=XLK_ATR_PCT,
                    params=XLK_PARAMS,
                    bar_index=-1,
                )
                if signal.should_enter:
                    account = broker.get_account()
                    cap = check_capacity(
                        symbol=symbol,
                        reference_price=signal.entry_reference_price,
                        db_path=db_path,
                        alpaca_account=account,
                    )
                    if cap.allowed:
                        ids = broker.submit_bracket_buy(
                            symbol=symbol,
                            qty=cap.suggested_qty,
                            stop_price=signal.stop_price,
                            target_price=signal.target_price,
                        )
                        with sqlite3.connect(db_path) as conn:
                            conn.execute(
                                """INSERT INTO positions (symbol, strategy_name, entry_ts_utc,
                                   entry_price, entry_qty, stop_price, target_price,
                                   alpaca_entry_order_id, status)
                                   VALUES (?, 'mean_reversion', ?, ?, ?, ?, ?, ?, 'open')""",
                                (
                                    symbol,
                                    now_utc.isoformat(),
                                    signal.entry_reference_price,
                                    cap.suggested_qty,
                                    signal.stop_price,
                                    signal.target_price,
                                    ids.get("entry_order_id"),
                                ),
                            )
                            conn.commit()
                        entries_placed += 1
        except Exception as e:
            errors.append(f"{symbol}: {type(e).__name__}: {e}")

        finished_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """UPDATE bot_runs SET finished_at_utc = ?, status = 'success',
                   entries_placed = ? WHERE id = ?""",
                (finished_at, entries_placed, run_id),
            )
            conn.commit()
        return {"entries_placed": entries_placed, "errors": errors}

    except Exception as e:
        finished_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """UPDATE bot_runs SET finished_at_utc = ?, status = 'error',
                   error_message = ? WHERE id = ?""",
                (finished_at, str(e), run_id),
            )
            conn.commit()
        raise
