"""Status enum + GateResult dataclass tests."""
from __future__ import annotations

import pytest

from equity_trading.src.validation.gates.base import GateResult, Status


def test_status_enum_has_three_levels():
    assert Status.PASS.value == "PASS"
    assert Status.WARN.value == "WARN"
    assert Status.FAIL.value == "FAIL"


def test_gate_result_constructs_with_required_fields():
    r = GateResult(
        name="oos",
        status=Status.PASS,
        summary="variant +12.5% vs baseline +8.3%",
        detail_md="### OOS\nfoo bar",
        metrics={"variant_ann": 12.5, "baseline_ann": 8.3},
    )
    assert r.name == "oos"
    assert r.status == Status.PASS
    assert "variant" in r.summary
    assert "###" in r.detail_md
    assert r.metrics["variant_ann"] == 12.5


def test_gate_result_metrics_defaults_to_empty_dict():
    r = GateResult(name="x", status=Status.PASS, summary="ok", detail_md="")
    assert r.metrics == {}


def test_gate_result_status_icon():
    """Each status maps to a markdown icon for the report."""
    assert Status.PASS.icon == "✅"
    assert Status.WARN.icon == "⚠️"
    assert Status.FAIL.icon == "❌"
