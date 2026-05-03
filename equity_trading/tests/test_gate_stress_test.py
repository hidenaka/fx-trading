"""Stress test gate."""
from __future__ import annotations

import pandas as pd
import pytest

from equity_trading.src.validation.gates.base import Status


def _summary(ann, dd, worst, n=50):
    return {"annualized_pct": ann, "max_dd_pct": dd,
             "sharpe": 0.0, "final_equity": 100000.0,
             "worst_trade_pct": worst, "trade_count": n}


def test_stress_gate_pass_when_all_windows_within_limits():
    from equity_trading.src.validation.gates.stress_test import (
        run_stress_test_gate_from_summaries,
    )
    windows = [
        {"name": "w1", "max_dd_limit_pct": 30.0, "worst_trade_limit_pct": 7.0},
        {"name": "w2", "max_dd_limit_pct": 25.0, "worst_trade_limit_pct": 5.0},
    ]
    variant = [_summary(-5.0, -22.0, -4.5), _summary(-2.0, -18.0, -4.0)]
    baseline = [_summary(-5.0, -20.0, -4.5), _summary(-2.0, -17.0, -4.0)]
    result = run_stress_test_gate_from_summaries(windows, variant, baseline)
    assert result.status == Status.PASS


def test_stress_gate_fail_when_dd_exceeds_window_limit():
    from equity_trading.src.validation.gates.stress_test import (
        run_stress_test_gate_from_summaries,
    )
    windows = [{"name": "w1", "max_dd_limit_pct": 25.0, "worst_trade_limit_pct": 7.0}]
    variant = [_summary(-10.0, -40.0, -4.5)]
    baseline = [_summary(-5.0, -20.0, -4.5)]
    result = run_stress_test_gate_from_summaries(windows, variant, baseline)
    assert result.status == Status.FAIL
    assert "w1" in result.summary


def test_stress_gate_fail_when_variant_dd_excessive_vs_baseline():
    from equity_trading.src.validation.gates.stress_test import (
        run_stress_test_gate_from_summaries,
    )
    windows = [{"name": "w1", "max_dd_limit_pct": 50.0, "worst_trade_limit_pct": 50.0}]
    variant = [_summary(-5.0, -30.0, -4.0)]
    baseline = [_summary(-5.0, -20.0, -4.0)]  # 30 > 1.3*20
    result = run_stress_test_gate_from_summaries(windows, variant, baseline)
    assert result.status == Status.FAIL


def test_stress_gate_warn_when_no_windows_configured():
    from equity_trading.src.validation.gates.stress_test import (
        run_stress_test_gate_from_summaries,
    )
    result = run_stress_test_gate_from_summaries([], [], [])
    assert result.status == Status.WARN
    assert "no windows" in result.summary.lower()


def test_stress_gate_fail_when_worst_trade_exceeds_limit():
    from equity_trading.src.validation.gates.stress_test import (
        run_stress_test_gate_from_summaries,
    )
    windows = [{"name": "w1", "max_dd_limit_pct": 50.0, "worst_trade_limit_pct": 5.0}]
    variant = [_summary(-2.0, -10.0, -7.5)]
    baseline = [_summary(-2.0, -10.0, -4.0)]
    result = run_stress_test_gate_from_summaries(windows, variant, baseline)
    assert result.status == Status.FAIL
    assert "worst" in result.summary.lower()
