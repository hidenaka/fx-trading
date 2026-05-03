"""Markdown report writer."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from equity_trading.src.validation.gates.base import GateResult, Status
from equity_trading.src.validation.report import (
    Headline,
    derive_headline,
    write_validation_report,
)


def _g(name: str, status: Status, summary: str = "ok", detail: str = "") -> GateResult:
    return GateResult(name=name, status=status, summary=summary,
                       detail_md=detail or f"### {name} {status.icon}\n\n{summary}")


def test_derive_headline_approve_when_all_pass():
    gates = [_g("oos", Status.PASS), _g("tail_risk", Status.PASS), _g("sample_size", Status.PASS)]
    assert derive_headline(gates) == Headline.APPROVE


def test_derive_headline_review_when_any_warn():
    gates = [_g("oos", Status.PASS), _g("tail_risk", Status.WARN), _g("sample_size", Status.PASS)]
    assert derive_headline(gates) == Headline.REVIEW


def test_derive_headline_reject_when_required_fail():
    gates = [_g("oos", Status.FAIL), _g("tail_risk", Status.PASS), _g("sample_size", Status.PASS)]
    assert derive_headline(gates) == Headline.REJECT


def test_write_validation_report(tmp_path):
    gates = [
        _g("oos", Status.PASS, "variant beats baseline"),
        _g("tail_risk", Status.WARN, "30d rolling 12%"),
        _g("sample_size", Status.PASS, "n=120"),
    ]
    out = tmp_path / "report.md"
    write_validation_report(
        path=out,
        variant_id="orb_tight_v2_1",
        baseline_id="orb_default_v0",
        gates=gates,
        git_sha="abc123",
        manifest_hash="def456",
        holdout_window=("2024-05-01", "2026-05-01"),
        generated_at=datetime(2026, 5, 3, 14, 32, tzinfo=timezone.utc),
    )
    text = out.read_text()
    assert "orb_tight_v2_1" in text
    assert "orb_default_v0" in text
    assert "abc123" in text
    assert "REVIEW" in text
    assert "OOS" in text or "oos" in text
    assert "tail_risk" in text or "Tail" in text


def test_report_appends_risk_profile_section(tmp_path):
    from equity_trading.src.validation.report import write_validation_report
    from equity_trading.src.validation.gates.base import GateResult, Status
    import pandas as pd
    from datetime import datetime, timezone

    trades = pd.DataFrame({
        "entry_ts": pd.to_datetime(["2024-06-01", "2024-06-02"], utc=True),
        "exit_ts":  pd.to_datetime(["2024-06-01 16:00", "2024-06-02 16:00"], utc=True),
        "symbol":   ["TECL", "TQQQ"],
        "pnl_pct":  [0.01, -0.01],
        "position_dollars": [25000, 25000],
    })
    gates = [GateResult(name="oos", status=Status.PASS, summary="ok",
                         detail_md="### Gate 1\n"),
              GateResult(name="tail_risk", status=Status.PASS, summary="ok",
                         detail_md="### Gate 2\n"),
              GateResult(name="sample_size", status=Status.PASS, summary="ok",
                         detail_md="### Gate 3\n")]
    out = tmp_path / "r.md"
    write_validation_report(
        path=out, variant_id="v", baseline_id="b", gates=gates,
        git_sha="abc", manifest_hash="m",
        holdout_window=("2024-05-01", "2026-05-01"),
        generated_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
        variant_trades=trades,
    )
    text = out.read_text()
    assert "## Risk profile" in text
    assert "TECL" in text
