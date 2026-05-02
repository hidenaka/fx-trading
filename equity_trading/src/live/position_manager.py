"""ポジション容量・資金配分マネージャ."""
from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CapacityCheck:
    allowed: bool
    reason: str
    suggested_qty: int
    capital_to_deploy_usd: float


def check_capacity(
    symbol: str,
    reference_price: float,
    db_path: Path | str,
    alpaca_account: dict,
    max_concurrent: int = 3,
    per_trade_pct: float = 0.25,
    per_trade_cap_usd: float = 2500.0,
) -> CapacityCheck:
    """エントリー可否と推奨株数を返す."""
    db_path = Path(db_path)
    with sqlite3.connect(db_path) as conn:
        # Same symbol already open?
        cur = conn.execute(
            "SELECT COUNT(*) FROM positions WHERE symbol = ? AND status = 'open'",
            (symbol,),
        )
        if cur.fetchone()[0] > 0:
            return CapacityCheck(
                allowed=False,
                reason=f"{symbol} already has an open position",
                suggested_qty=0,
                capital_to_deploy_usd=0.0,
            )

        # Max concurrent?
        cur = conn.execute("SELECT COUNT(*) FROM positions WHERE status = 'open'")
        n_open = cur.fetchone()[0]
        if n_open >= max_concurrent:
            return CapacityCheck(
                allowed=False,
                reason=f"max concurrent ({max_concurrent}) positions already open",
                suggested_qty=0,
                capital_to_deploy_usd=0.0,
            )

    equity = float(alpaca_account.get("equity", 0.0))
    capital_to_deploy = min(equity * per_trade_pct, per_trade_cap_usd)
    suggested_qty = math.floor(capital_to_deploy / reference_price)

    if suggested_qty < 1:
        return CapacityCheck(
            allowed=False,
            reason=f"insufficient capital: ${capital_to_deploy:.2f} can't afford 1 share at ${reference_price:.2f}",
            suggested_qty=0,
            capital_to_deploy_usd=capital_to_deploy,
        )

    return CapacityCheck(
        allowed=True,
        reason="ok",
        suggested_qty=suggested_qty,
        capital_to_deploy_usd=capital_to_deploy,
    )
