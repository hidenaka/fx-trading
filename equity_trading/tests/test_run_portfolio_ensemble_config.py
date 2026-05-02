"""run_portfolio_ensemble retrofit: SELECTED replaced by config-driven loader."""
from __future__ import annotations

from pathlib import Path

from equity_trading.scripts.run_portfolio_ensemble import selected_from_config


def _seed_yaml(p: Path) -> Path:
    p.write_text("""
variant_id: legacy_orb_lhm
description: legacy
strategies:
  - class: OpeningRangeBreakoutStrategy
    symbols: [TECL, TQQQ]
    params: {or_window_bars: 12, stop_mult: 0.0, target_mult: 1.0, cost_pct: 0.10}
  - class: LastHourMomentumStrategy
    symbols: [UPRO]
    params: {threshold: 0.003, _max_hold_bars: 60, cost_pct: 0.10}
portfolio: {position_size_pct: 0.25, max_concurrent: 3, starting_equity_usd: 100000}
gates:
  oos: {holdout_start: "2024-05-01", holdout_end: "2026-05-01", min_outperformance_pct: 0.0}
  tail_risk: {max_single_trade_loss_pct: 5.0, max_portfolio_dd_pct: 20.0, max_rolling_30d_loss_pct: 10.0}
  sample_size: {min_holdout_trades: 30}
""")
    return p


def test_selected_from_config_returns_5_tuples(tmp_path):
    sel = selected_from_config(_seed_yaml(tmp_path / "c.yaml"))
    assert len(sel) == 3  # 2 ORB + 1 LHM
    for entry in sel:
        assert len(entry) == 5  # (cls, sym, params, label, cost)
    cls0, sym0, params0, label0, cost0 = sel[0]
    from equity_trading.src.strategy.strategies.opening_range_breakout import OpeningRangeBreakoutStrategy
    assert cls0 is OpeningRangeBreakoutStrategy
    assert sym0 == "TECL"
    assert params0["or_window_bars"] == 12
    assert label0 == "OpeningRangeBreakoutStrategy_TECL"
    assert cost0 == 0.10
