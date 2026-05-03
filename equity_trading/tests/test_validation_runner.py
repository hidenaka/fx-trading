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


def test_collect_trades_from_split_rejects_unknown_partition(tmp_path):
    from equity_trading.src.validation.runner import _collect_trades_from_split
    from equity_trading.src.validation.config import VariantConfig
    cfg = VariantConfig(
        variant_id="t", description="",
        strategies=[{"class": "OpeningRangeBreakoutStrategy", "symbols": ["TECL"], "params": {}}],
        portfolio={"position_size_pct": 0.25, "max_concurrent": 3, "starting_equity_usd": 100000},
        gates={"oos": {"holdout_start": "2024-05-01", "holdout_end": "2026-05-01", "min_outperformance_pct": 0.0},
                "tail_risk": {"max_single_trade_loss_pct": 5.0, "max_portfolio_dd_pct": 20.0, "max_rolling_30d_loss_pct": 10.0},
                "sample_size": {"min_holdout_trades": 30}},
    )
    with pytest.raises(ValueError, match="Unknown partition"):
        _collect_trades_from_split(cfg, tmp_path, "invalid")


def test_collect_trades_from_split_excludes_pre_valid2_signals(monkeypatch, tmp_path):
    """A synthetic trade with entry_ts < VALID2_START must be dropped."""
    import equity_trading.src.validation.runner as R
    from equity_trading.src.validation.config import VariantConfig
    from equity_trading.src.validation.internal_split import VALID2_START

    valid2_start = pd.Timestamp(VALID2_START, tz="UTC")
    fake_trades = pd.DataFrame({
        "entry_ts": [valid2_start - pd.Timedelta(days=30),
                      valid2_start + pd.Timedelta(days=1),
                      valid2_start + pd.Timedelta(days=10)],
        "exit_ts":  [valid2_start - pd.Timedelta(days=29),
                      valid2_start + pd.Timedelta(days=1, hours=1),
                      valid2_start + pd.Timedelta(days=10, hours=1)],
        "entry_price": [100.0, 100.0, 100.0],
        "exit_price":  [101.0, 101.0, 101.0],
        "exit_type":   ["target", "target", "target"],
        "bars_held":   [12, 12, 12],
        "pnl_pct":     [0.01, 0.01, 0.01],
    })
    monkeypatch.setattr(R, "simulate_strategy",
                         lambda **kw: ({}, fake_trades))
    monkeypatch.setattr(R, "analyze_atr_distribution",
                         lambda b, period=14: {"median_pct": 0.2})
    # Stub the internal_split loaders so we don't need parquet files.
    import equity_trading.src.validation.internal_split as IS
    monkeypatch.setattr(IS, "load_valid2_bars", lambda r, s, timeframe_minutes: pd.DataFrame())

    cfg = VariantConfig(
        variant_id="t", description="",
        strategies=[{"class": "OpeningRangeBreakoutStrategy", "symbols": ["TECL"], "params": {}}],
        portfolio={"position_size_pct": 0.25, "max_concurrent": 3, "starting_equity_usd": 100000},
        gates={"oos": {"holdout_start": "2024-05-01", "holdout_end": "2026-05-01", "min_outperformance_pct": 0.0},
                "tail_risk": {"max_single_trade_loss_pct": 5.0, "max_portfolio_dd_pct": 20.0, "max_rolling_30d_loss_pct": 10.0},
                "sample_size": {"min_holdout_trades": 30}},
    )
    result = R._collect_trades_from_split(cfg, tmp_path, "valid2")
    assert len(result) == 2
    assert (result["entry_ts"] >= valid2_start).all()


def test_collect_trades_from_split_injects_vix_daily(monkeypatch, tmp_path):
    """vix_daily kwarg propagates into each strategy's params dict."""
    import equity_trading.src.validation.runner as R
    from equity_trading.src.validation.config import VariantConfig

    captured_params: list[dict] = []

    def _fake_simulate(**kwargs):
        captured_params.append(dict(kwargs["params"]))
        return ({}, pd.DataFrame(columns=["entry_ts", "exit_ts", "pnl_pct"]))

    monkeypatch.setattr(R, "simulate_strategy", _fake_simulate)
    monkeypatch.setattr(R, "analyze_atr_distribution",
                         lambda b, period=14: {"median_pct": 0.2})
    import equity_trading.src.validation.internal_split as IS
    monkeypatch.setattr(IS, "load_valid2_bars", lambda r, s, timeframe_minutes: pd.DataFrame())

    cfg = VariantConfig(
        variant_id="t", description="",
        strategies=[{"class": "OpeningRangeBreakoutStrategy", "symbols": ["TECL"], "params": {}}],
        portfolio={"position_size_pct": 0.25, "max_concurrent": 3, "starting_equity_usd": 100000},
        gates={"oos": {"holdout_start": "2024-05-01", "holdout_end": "2026-05-01", "min_outperformance_pct": 0.0},
                "tail_risk": {"max_single_trade_loss_pct": 5.0, "max_portfolio_dd_pct": 20.0, "max_rolling_30d_loss_pct": 10.0},
                "sample_size": {"min_holdout_trades": 30}},
    )
    fake_vix = pd.DataFrame({"close": [20.0]},
                             index=pd.date_range("2022-01-01", periods=1, freq="1D", tz="UTC"))
    R._collect_trades_from_split(cfg, tmp_path, "valid2", vix_daily=fake_vix)
    assert len(captured_params) == 1
    assert "_vix_daily" in captured_params[0]
    assert captured_params[0]["_vix_daily"] is fake_vix
