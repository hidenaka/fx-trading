"""OOS gate: variant must beat baseline on holdout."""
from __future__ import annotations

import pandas as pd

from equity_trading.src.validation.gates.base import Status
from equity_trading.src.validation.gates.oos import run_oos_gate


def _result(ann_pct: float, dd_pct: float, sharpe: float) -> dict:
    return {"annualized_pct": ann_pct, "max_dd_pct": dd_pct, "sharpe": sharpe}


def test_oos_pass_when_variant_beats_baseline():
    res = run_oos_gate(
        variant_holdout=_result(15.0, -10.0, 1.2),
        baseline_holdout=_result(8.0, -12.0, 0.8),
        min_outperformance_pct=0.0,
    )
    assert res.status == Status.PASS
    assert "15.0" in res.summary or "15.00" in res.summary


def test_oos_fail_when_variant_underperforms():
    res = run_oos_gate(
        variant_holdout=_result(5.0, -10.0, 0.5),
        baseline_holdout=_result(8.0, -12.0, 0.8),
        min_outperformance_pct=0.0,
    )
    assert res.status == Status.FAIL


def test_oos_fail_when_variant_dd_120pct_worse_than_baseline():
    res = run_oos_gate(
        variant_holdout=_result(20.0, -25.0, 1.5),
        baseline_holdout=_result(15.0, -18.0, 1.0),
        min_outperformance_pct=0.0,
    )
    assert res.status == Status.FAIL
    assert "drawdown" in res.summary.lower() or "dd" in res.summary.lower()


def test_oos_warn_when_returns_better_but_sharpe_worse():
    res = run_oos_gate(
        variant_holdout=_result(20.0, -10.0, 0.7),
        baseline_holdout=_result(15.0, -10.0, 1.0),
        min_outperformance_pct=0.0,
    )
    assert res.status == Status.WARN
