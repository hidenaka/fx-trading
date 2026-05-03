"""Smoke test for compute_correlation utility."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_compute_correlation_runs_on_train_data():
    """The script should execute without error and emit two markdown tables."""
    repo = Path(__file__).resolve().parents[2]
    env = {**os.environ, "PYTHONPATH": str(repo)}
    result = subprocess.run(
        [sys.executable, str(repo / "equity_trading" / "scripts" / "compute_correlation.py")],
        capture_output=True, text=True, timeout=120, cwd=repo, env=env,
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "Daily-return correlation" in out
    assert "5min-return correlation" in out
    assert "TECL" in out
    assert "UDOW" in out
