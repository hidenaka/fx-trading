"""日次サーキットブレーカー."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class CircuitState:
    halted: bool
    reason: str
    today_realized_pnl_usd: float
    daily_dd_pct: float
    threshold_pct: float


def check_circuit(
    db_path: Path | str,
    alpaca_account: dict,
    now_utc: datetime,
    daily_dd_threshold_pct: float = -2.0,
) -> CircuitState:
    """Compute today's drawdown and return halt status.

    halted=True if `daily_dd_pct < daily_dd_threshold_pct`.

    `today_realized_pnl_usd` = sum of realized_pnl_usd from positions closed today (NY date).
    `daily_dd_pct` = today_realized_pnl_usd / current_equity * 100.

    (Note: this is a coarse approximation — proper DD would use starting equity
    of the day, not current. For Plan 2.0 MVP it's sufficient.)
    """
    db_path = Path(db_path)
    today_str = now_utc.strftime("%Y-%m-%d")

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """SELECT COALESCE(SUM(realized_pnl_usd), 0.0) FROM positions
               WHERE status = 'closed' AND DATE(exit_ts_utc) = ?""",
            (today_str,),
        )
        realized = float(cur.fetchone()[0])

    equity = float(alpaca_account.get("equity", 0.0))
    if equity <= 0:
        return CircuitState(False, "no equity info", realized, 0.0, daily_dd_threshold_pct)

    daily_dd_pct = realized / equity * 100.0
    halted = daily_dd_pct <= daily_dd_threshold_pct
    if halted:
        reason = (
            f"circuit halted: today's drawdown {daily_dd_pct:.2f}% "
            f"below threshold {daily_dd_threshold_pct:.2f}%"
        )
    else:
        reason = "ok"
    return CircuitState(
        halted=halted,
        reason=reason,
        today_realized_pnl_usd=realized,
        daily_dd_pct=daily_dd_pct,
        threshold_pct=daily_dd_threshold_pct,
    )
