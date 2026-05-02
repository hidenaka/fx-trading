"""Tail-risk gate: per-trade loss + portfolio MaxDD + rolling 30d."""
from __future__ import annotations

import pandas as pd

from equity_trading.src.validation.gates.base import Status
from equity_trading.src.validation.gates.tail_risk import run_tail_risk_gate


def _equity_curve(values: list[float], start_date: str = "2024-06-01") -> pd.DataFrame:
    ts = pd.date_range(start_date, periods=len(values), freq="1D", tz="UTC")
    return pd.DataFrame({"ts": ts, "equity": values})


def _trades(pnls: list[float]) -> pd.DataFrame:
    ts = pd.date_range("2024-06-01", periods=len(pnls), freq="1D", tz="UTC")
    return pd.DataFrame({
        "entry_ts": ts, "exit_ts": ts + pd.Timedelta(hours=2),
        "pnl_pct": pnls, "symbol": ["TECL"] * len(pnls),
    })


def test_tail_risk_pass_when_all_within_thresholds():
    eq = _equity_curve([100_000, 101_000, 100_500, 102_000])
    trades = _trades([0.01, -0.005, 0.015])
    res = run_tail_risk_gate(
        equity_curve=eq, trades=trades,
        max_single_trade_loss_pct=5.0,
        max_portfolio_dd_pct=20.0,
        max_rolling_30d_loss_pct=10.0,
    )
    assert res.status == Status.PASS


def test_tail_risk_fail_on_single_trade_loss():
    eq = _equity_curve([100_000, 95_000])
    trades = _trades([0.01, -0.06])
    res = run_tail_risk_gate(
        equity_curve=eq, trades=trades,
        max_single_trade_loss_pct=5.0,
        max_portfolio_dd_pct=20.0,
        max_rolling_30d_loss_pct=10.0,
    )
    assert res.status == Status.FAIL
    assert "single trade" in res.summary.lower() or "trade" in res.summary.lower()


def test_tail_risk_fail_on_portfolio_dd():
    eq = _equity_curve([100_000, 78_000])
    trades = _trades([-0.04])
    res = run_tail_risk_gate(
        equity_curve=eq, trades=trades,
        max_single_trade_loss_pct=5.0,
        max_portfolio_dd_pct=20.0,
        max_rolling_30d_loss_pct=10.0,
    )
    assert res.status == Status.FAIL
    assert "drawdown" in res.summary.lower() or "dd" in res.summary.lower()


def test_tail_risk_warn_on_rolling_30d():
    days = 60
    values = [100_000.0] * days
    for i in range(15, 30):
        values[i] = 88_000
    eq = _equity_curve(values)
    res = run_tail_risk_gate(
        equity_curve=eq, trades=_trades([0.0]),
        max_single_trade_loss_pct=5.0,
        max_portfolio_dd_pct=20.0,
        max_rolling_30d_loss_pct=10.0,
    )
    assert res.status == Status.WARN


def test_tail_risk_reports_catastrophic_stop_simulation():
    eq = _equity_curve([100_000, 90_000])
    trades = _trades([-0.10])
    res = run_tail_risk_gate(
        equity_curve=eq, trades=trades,
        max_single_trade_loss_pct=5.0,
        max_portfolio_dd_pct=20.0,
        max_rolling_30d_loss_pct=10.0,
    )
    assert "catastrophic" in res.detail_md.lower() or "5%" in res.detail_md
    assert res.metrics.get("catastrophic_stop_worst_pct") is not None
