"""Morning gap_fill runner. Runs once at ~9:31 ET each trading day."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

from equity_trading.src.live.position_manager import check_capacity
from equity_trading.src.live.signal_evaluator import evaluate_live_signal
from equity_trading.src.strategy.strategies.gap_fill import GapFillStrategy


GAP_FILL_PARAMS_PER_SYMBOL: dict[str, dict] = {
    "SPY": {"gap_threshold": 0.003, "stop_extension": 0.005},
    "QQQ": {"gap_threshold": 0.005, "stop_extension": 0.005},
    "IWM": {"gap_threshold": 0.010, "stop_extension": 0.010},
    "XLK": {"gap_threshold": 0.005, "stop_extension": 0.005},
}

DEFAULT_ATR_PCT = 0.10  # placeholder — gap_fill doesn't use ATR for exits


def run_morning(
    symbols: Sequence[str],
    db_path: Path | str,
    broker,
    fetcher,
    now_utc: datetime | None = None,
) -> dict:
    """Run the morning gap_fill check for each symbol.

    Returns: {"entries_placed": int, "errors": list[str]}
    """
    db_path = Path(db_path)
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    started_at = now_utc.isoformat()
    entries_placed = 0
    errors: list[str] = []

    # Open bot_runs row
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO bot_runs (run_type, started_at_utc, status)
               VALUES ('morning', ?, 'running')""",
            (started_at,),
        )
        run_id = cur.lastrowid
        conn.commit()

    try:
        strategy = GapFillStrategy()
        account = broker.get_account()

        for symbol in symbols:
            try:
                # Fetch today's first 5min bar (just 1 row)
                # Window: now-15min to now is enough to have today's first bar
                bar_start = now_utc - timedelta(hours=2)
                bars_5min = fetcher.fetch(
                    symbol=symbol, start=bar_start, end=now_utc, timeframe_minutes=5,
                )
                # Only keep first bar of today's NY date
                if len(bars_5min) == 0:
                    continue
                bars_5min = bars_5min.iloc[[0]]

                daily = fetcher.fetch(
                    symbol=symbol,
                    start=now_utc - timedelta(days=400),
                    end=now_utc,
                    timeframe_minutes=1440,
                )
                if len(daily) < 200:
                    errors.append(f"{symbol}: insufficient daily bars ({len(daily)})")
                    continue

                params = dict(GAP_FILL_PARAMS_PER_SYMBOL.get(symbol, {}))
                # Inject _daily for compute_exit_levels
                params["_daily"] = daily

                signal = evaluate_live_signal(
                    strategy=strategy,
                    bars_5min=bars_5min,
                    daily=daily,
                    atr_pct=DEFAULT_ATR_PCT,
                    params=params,
                    bar_index=0,
                )
                if not signal.should_enter:
                    continue

                # Capacity check
                cap = check_capacity(
                    symbol=symbol,
                    reference_price=signal.entry_reference_price,
                    db_path=db_path,
                    alpaca_account=account,
                )
                if not cap.allowed:
                    continue

                # Submit bracket
                ids = broker.submit_bracket_buy(
                    symbol=symbol,
                    qty=cap.suggested_qty,
                    stop_price=signal.stop_price,
                    target_price=signal.target_price,
                )

                # Insert position row
                with sqlite3.connect(db_path) as conn:
                    conn.execute(
                        """INSERT INTO positions (symbol, strategy_name, entry_ts_utc,
                           entry_price, entry_qty, stop_price, target_price,
                           alpaca_entry_order_id, status)
                           VALUES (?, 'gap_fill', ?, ?, ?, ?, ?, ?, 'open')""",
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
