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
        # Task 1 contract: load_holdout_bars(1440) reads warmup from train/.
        # Seed a year of synthetic train daily data so the warmup tail is non-empty.
        train_ts = pd.date_range("2023-05-01", "2024-04-30", freq="1D", tz="UTC")
        train_df = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5,
                                  "volume": 1000}, index=train_ts)
        (root / "train").mkdir(parents=True, exist_ok=True)
        train_df.to_parquet(root / "train" / f"{sym}_1440min.parquet")


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


def test_collect_trades_excludes_warmup_period_signals(tmp_path):
    """Synthetic trades whose entry_ts < holdout_start must be dropped."""
    from equity_trading.src.validation.runner import _collect_trades
    from equity_trading.src.validation.config import VariantConfig
    from equity_trading.src.validation.data import EvaluationContext
    import pandas as pd

    # We craft a fake _collect_trades input by monkeypatching simulate_strategy
    # to return synthetic trades, half before holdout_start and half after.
    import equity_trading.src.validation.runner as R

    holdout_start = pd.Timestamp("2024-05-01", tz="UTC")
    fake_trades_df = pd.DataFrame({
        "entry_ts": [holdout_start - pd.Timedelta(days=30),
                      holdout_start + pd.Timedelta(days=1),
                      holdout_start + pd.Timedelta(days=10)],
        "exit_ts":  [holdout_start - pd.Timedelta(days=29),
                      holdout_start + pd.Timedelta(days=1, hours=1),
                      holdout_start + pd.Timedelta(days=10, hours=1)],
        "entry_price": [100.0, 100.0, 100.0],
        "exit_price":  [101.0, 101.0, 101.0],
        "exit_type":   ["target", "target", "target"],
        "bars_held":   [12, 12, 12],
        "pnl_pct":     [0.01, 0.01, 0.01],
    })

    def _fake_simulate(**kwargs):
        return ({}, fake_trades_df)

    cfg = VariantConfig(
        variant_id="v_test", description="",
        strategies=[{"class": "OpeningRangeBreakoutStrategy", "symbols": ["TECL"], "params": {}}],
        portfolio={"position_size_pct": 0.25, "max_concurrent": 3,
                    "starting_equity_usd": 100000},
        gates={"oos": {"holdout_start": "2024-05-01", "holdout_end": "2026-05-01",
                       "min_outperformance_pct": 0.0},
                "tail_risk": {"max_single_trade_loss_pct": 5.0,
                               "max_portfolio_dd_pct": 20.0,
                               "max_rolling_30d_loss_pct": 10.0},
                "sample_size": {"min_holdout_trades": 30}},
    )

    class FakeCtx:
        def load_holdout_bars(self, symbol, timeframe_minutes):
            return pd.DataFrame()  # unused

    monkey = pytest.MonkeyPatch()
    monkey.setattr(R, "simulate_strategy", _fake_simulate)
    monkey.setattr(R, "analyze_atr_distribution", lambda b, period=14: {"median_pct": 0.2})
    try:
        result = _collect_trades(cfg, FakeCtx())
    finally:
        monkey.undo()

    assert len(result) == 2  # only the two trades on/after holdout_start
    assert (result["entry_ts"] >= holdout_start).all()
