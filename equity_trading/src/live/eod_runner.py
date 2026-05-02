"""End-of-day runner: close open positions, write daily P&L summary."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def run_eod(
    db_path: Path | str,
    broker,
    fetcher,
    now_utc: datetime | None = None,
) -> dict:
    """Force-close any open positions and compute daily summary.

    Returns: {"positions_closed": int, "errors": list[str], "summary_md": str}
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
               VALUES ('eod', ?, 'running')""",
            (started_at,),
        )
        run_id = cur.lastrowid
        conn.commit()

    try:
        # Find all open positions
        with sqlite3.connect(db_path) as conn:
            open_rows = conn.execute(
                """SELECT id, symbol, entry_price, entry_qty FROM positions
                   WHERE status = 'open'"""
            ).fetchall()

        for pid, symbol, entry_price, entry_qty in open_rows:
            try:
                # Estimate exit price = latest 5min bar's close
                bars = fetcher.fetch(
                    symbol=symbol,
                    start=now_utc - timedelta(minutes=15),
                    end=now_utc,
                    timeframe_minutes=5,
                )
                exit_price = float(bars["close"].iloc[-1]) if len(bars) > 0 else float(entry_price)

                # Submit close at market
                broker.close_position(symbol)

                pnl_pct = (exit_price - entry_price) / entry_price
                realized_pnl_usd = (exit_price - entry_price) * entry_qty

                with sqlite3.connect(db_path) as conn:
                    conn.execute(
                        """UPDATE positions
                           SET exit_ts_utc=?, exit_price=?, exit_type='time',
                               pnl_pct=?, realized_pnl_usd=?, status='closed'
                           WHERE id=?""",
                        (now_utc.isoformat(), exit_price, pnl_pct, realized_pnl_usd, pid),
                    )
                    conn.commit()
                positions_closed += 1
            except Exception as e:
                errors.append(f"{symbol}: {type(e).__name__}: {e}")

        # Compute daily summary
        from zoneinfo import ZoneInfo
        ny_date = now_utc.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

        account = broker.get_account()
        ending_equity = float(account.get("equity", 0.0))

        with sqlite3.connect(db_path) as conn:
            # Today's realized P&L = sum of positions closed today
            cur = conn.execute(
                """SELECT
                   COALESCE(SUM(realized_pnl_usd), 0.0) AS rpnl,
                   COUNT(*) AS n_exits
                   FROM positions
                   WHERE status='closed' AND DATE(exit_ts_utc) = ?""",
                (now_utc.strftime("%Y-%m-%d"),),
            )
            r_row = cur.fetchone()
            realized_pnl = float(r_row[0])
            n_exits_today = int(r_row[1])

            cur = conn.execute(
                """SELECT COUNT(*) FROM positions
                   WHERE DATE(entry_ts_utc) = ?""",
                (now_utc.strftime("%Y-%m-%d"),),
            )
            n_entries_today = int(cur.fetchone()[0])

            starting_equity = ending_equity - realized_pnl
            daily_return_pct = (realized_pnl / starting_equity * 100.0) if starting_equity > 0 else 0.0

            conn.execute(
                """INSERT OR REPLACE INTO daily_pnl
                   (trade_date, starting_equity_usd, ending_equity_usd, realized_pnl_usd,
                    daily_return_pct, circuit_breaker_triggered, n_entries, n_exits)
                   VALUES (?, ?, ?, ?, ?, 0, ?, ?)""",
                (ny_date, starting_equity, ending_equity, realized_pnl,
                 daily_return_pct, n_entries_today, n_exits_today),
            )
            conn.commit()

        # Markdown summary (returned, not saved to disk by default)
        summary_md = (
            f"# EOD Summary — {ny_date}\n\n"
            f"- Positions closed: **{positions_closed}**\n"
            f"- Realized P&L: **${realized_pnl:.2f}** ({daily_return_pct:+.3f}%)\n"
            f"- Ending equity: **${ending_equity:.2f}**\n"
            f"- Entries today: {n_entries_today}, Exits today: {n_exits_today}\n"
        )
        if errors:
            summary_md += "\n## Errors\n\n" + "\n".join(f"- {e}" for e in errors) + "\n"

        finished_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """UPDATE bot_runs SET finished_at_utc=?, status='success',
                   exits_placed=? WHERE id=?""",
                (finished_at, positions_closed, run_id),
            )
            conn.commit()

        return {
            "positions_closed": positions_closed,
            "errors": errors,
            "summary_md": summary_md,
        }

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
