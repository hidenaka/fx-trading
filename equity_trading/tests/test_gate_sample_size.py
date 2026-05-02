"""Sample-size gate."""
from __future__ import annotations

import pandas as pd

from equity_trading.src.validation.gates.base import Status
from equity_trading.src.validation.gates.sample_size import run_sample_size_gate


def _trades(n: int) -> pd.DataFrame:
    ts = pd.date_range("2024-06-01", periods=n, freq="1D", tz="UTC")
    return pd.DataFrame({
        "entry_ts": ts,
        "exit_ts": ts + pd.Timedelta(hours=2),
        "pnl_pct": [0.005] * n,
        "symbol": ["TECL"] * n,
    })


def test_sample_size_pass_when_n_well_above_min():
    res = run_sample_size_gate(holdout_trades=_trades(60), min_holdout_trades=30)
    assert res.status == Status.PASS
    assert "60" in res.summary
    assert res.metrics["n"] == 60


def test_sample_size_warn_in_borderline_band():
    res = run_sample_size_gate(holdout_trades=_trades(35), min_holdout_trades=30)
    assert res.status == Status.WARN  # 35 < 30 * 1.5


def test_sample_size_fail_below_minimum():
    res = run_sample_size_gate(holdout_trades=_trades(20), min_holdout_trades=30)
    assert res.status == Status.FAIL
    assert "20" in res.summary
