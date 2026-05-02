"""Gate 3: sample size — too few holdout trades = no statistical power."""
from __future__ import annotations

import pandas as pd

from equity_trading.src.validation.gates.base import GateResult, Status


def run_sample_size_gate(
    holdout_trades: pd.DataFrame,
    min_holdout_trades: int,
) -> GateResult:
    n = len(holdout_trades)
    if n < min_holdout_trades:
        status = Status.FAIL
        summary = f"n={n} < min={min_holdout_trades}: insufficient sample"
    elif n < min_holdout_trades * 1.5:
        status = Status.WARN
        summary = f"n={n} just above min={min_holdout_trades}: borderline power"
    else:
        status = Status.PASS
        summary = f"n={n} >= 1.5*min={int(min_holdout_trades*1.5)}: adequate"
    detail = (
        f"### Gate 3: Sample size {status.icon}\n\n"
        f"- holdout trades: **{n}**\n"
        f"- threshold: **{min_holdout_trades}** (FAIL below, WARN below 1.5x)\n"
        f"- {summary}\n"
    )
    return GateResult(name="sample_size", status=status, summary=summary,
                       detail_md=detail, metrics={"n": n, "min": min_holdout_trades})
