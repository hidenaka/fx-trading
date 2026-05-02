"""End-to-end: load both configs, run validate CLI on real holdout data."""
from __future__ import annotations

from pathlib import Path

import pytest

from equity_trading.src.validation import cli

REPO = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO / "equity_trading" / "data" / "prices"
HOLDOUT_DIR = DATA_ROOT / "holdout"


@pytest.mark.skipif(not HOLDOUT_DIR.exists(), reason="holdout data not yet partitioned")
def test_e2e_orb_v2_1_vs_v0(tmp_path):
    out = tmp_path / "report.md"
    rc = cli.main([
        "--variant", str(REPO / "equity_trading/configs/orb_tight_v2_1.yaml"),
        "--baseline", str(REPO / "equity_trading/configs/orb_default_v0.yaml"),
        "--output", str(out),
        "--data-root", str(DATA_ROOT),
    ])
    assert rc == 0
    text = out.read_text()
    assert any(h in text for h in ["APPROVE", "REVIEW", "REJECT"])
    for gate in ["OOS", "Tail", "Sample"]:
        assert gate in text or gate.lower() in text
