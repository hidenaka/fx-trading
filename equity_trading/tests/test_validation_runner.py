"""Portfolio runner that consumes variant config + EvaluationContext."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from equity_trading.src.validation.config import load_variant_config
from equity_trading.src.validation.data import EvaluationContext
from equity_trading.src.validation.runner import run_holdout_simulation


def _seed_data(root: Path) -> None:
    for sym in ["TECL"]:
        for tf in [5, 1440]:
            ts = pd.date_range("2024-05-02 14:30", "2026-05-01 21:00", freq=f"{tf}min", tz="UTC")
            df = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5,
                                "volume": 1000}, index=ts)
            (root / "holdout").mkdir(parents=True, exist_ok=True)
            df.to_parquet(root / "holdout" / f"{sym}_{tf}min.parquet")


def _seed_variant(path: Path) -> Path:
    body = """
variant_id: t
description: ""
strategies:
  - class: OpeningRangeBreakoutStrategy
    symbols: [TECL]
    params:
      or_window_bars: 12
      stop_mult: 0.0
      target_mult: 1.0
      cost_pct: 0.10
portfolio:
  position_size_pct: 0.25
  max_concurrent: 3
  starting_equity_usd: 100000
gates:
  oos: {holdout_start: "2024-05-01", holdout_end: "2026-05-01", min_outperformance_pct: 0.0}
  tail_risk: {max_single_trade_loss_pct: 5.0, max_portfolio_dd_pct: 20.0, max_rolling_30d_loss_pct: 10.0}
  sample_size: {min_holdout_trades: 30}
"""
    path.write_text(body)
    return path


def test_run_holdout_simulation_returns_summary_trades_equity(tmp_path):
    _seed_data(tmp_path)
    cfg = load_variant_config(_seed_variant(tmp_path / "v.yaml"))
    with EvaluationContext(root=tmp_path, variant_id="t", reason="test") as ctx:
        summary, trades, equity = run_holdout_simulation(cfg, ctx)
    assert "annualized_pct" in summary
    assert "max_dd_pct" in summary
    assert "sharpe" in summary
    assert isinstance(trades, pd.DataFrame)
    assert isinstance(equity, pd.DataFrame)
    assert "ts" in equity.columns and "equity" in equity.columns
