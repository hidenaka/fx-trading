"""Variant config loader tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from equity_trading.src.validation.config import VariantConfig, load_variant_config


REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_config(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "v.yaml"
    p.write_text(body)
    return p


def test_load_minimal_config(tmp_path):
    body = """
variant_id: test_v0
description: minimal
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
  oos:
    holdout_start: "2024-05-01"
    holdout_end: "2026-05-01"
    min_outperformance_pct: 0.0
  tail_risk:
    max_single_trade_loss_pct: 5.0
    max_portfolio_dd_pct: 20.0
    max_rolling_30d_loss_pct: 10.0
  sample_size:
    min_holdout_trades: 30
"""
    p = _write_config(tmp_path, body)
    cfg = load_variant_config(p)
    assert cfg.variant_id == "test_v0"
    assert cfg.strategies[0]["class"] == "OpeningRangeBreakoutStrategy"
    assert cfg.strategies[0]["symbols"] == ["TECL"]
    assert cfg.gates["oos"]["holdout_start"] == "2024-05-01"
    assert cfg.gates["sample_size"]["min_holdout_trades"] == 30


def test_load_rejects_missing_variant_id(tmp_path):
    body = """
description: missing variant_id
strategies: []
portfolio:
  position_size_pct: 0.25
  max_concurrent: 3
  starting_equity_usd: 100000
gates: {}
"""
    p = _write_config(tmp_path, body)
    with pytest.raises(ValueError, match="variant_id"):
        load_variant_config(p)


def test_load_rejects_unknown_strategy_class(tmp_path):
    body = """
variant_id: bad
description: ""
strategies:
  - class: NonExistentStrategy
    symbols: [TECL]
    params: {}
portfolio:
  position_size_pct: 0.25
  max_concurrent: 3
  starting_equity_usd: 100000
gates:
  oos: {holdout_start: "2024-05-01", holdout_end: "2026-05-01", min_outperformance_pct: 0.0}
  tail_risk: {max_single_trade_loss_pct: 5.0, max_portfolio_dd_pct: 20.0, max_rolling_30d_loss_pct: 10.0}
  sample_size: {min_holdout_trades: 30}
"""
    p = _write_config(tmp_path, body)
    with pytest.raises(ValueError, match="NonExistentStrategy"):
        load_variant_config(p)


def test_load_rejects_strategies_being_none(tmp_path):
    body = """
variant_id: v
description: ""
strategies:
portfolio:
  position_size_pct: 0.25
  max_concurrent: 3
  starting_equity_usd: 100000
gates:
  oos: {holdout_start: "2024-05-01", holdout_end: "2026-05-01", min_outperformance_pct: 0.0}
  tail_risk: {max_single_trade_loss_pct: 5.0, max_portfolio_dd_pct: 20.0, max_rolling_30d_loss_pct: 10.0}
  sample_size: {min_holdout_trades: 30}
"""
    p = _write_config(tmp_path, body)
    with pytest.raises(ValueError, match="strategies"):
        load_variant_config(p)


def test_resolve_strategy_class_returns_real_class(tmp_path):
    body = """
variant_id: test
description: ""
strategies:
  - class: OpeningRangeBreakoutStrategy
    symbols: [TECL]
    params: {or_window_bars: 12, stop_mult: 0.0, target_mult: 1.0, cost_pct: 0.10}
portfolio: {position_size_pct: 0.25, max_concurrent: 3, starting_equity_usd: 100000}
gates:
  oos: {holdout_start: "2024-05-01", holdout_end: "2026-05-01", min_outperformance_pct: 0.0}
  tail_risk: {max_single_trade_loss_pct: 5.0, max_portfolio_dd_pct: 20.0, max_rolling_30d_loss_pct: 10.0}
  sample_size: {min_holdout_trades: 30}
"""
    p = _write_config(tmp_path, body)
    cfg = load_variant_config(p)
    klass = cfg.resolve_strategy_class(cfg.strategies[0]["class"])
    from equity_trading.src.strategy.strategies.opening_range_breakout import OpeningRangeBreakoutStrategy
    assert klass is OpeningRangeBreakoutStrategy


def test_load_rejects_missing_oos_holdout_start(tmp_path):
    body = """
variant_id: t
description: ""
strategies:
  - class: OpeningRangeBreakoutStrategy
    symbols: [TECL]
    params: {}
portfolio:
  position_size_pct: 0.25
  max_concurrent: 3
  starting_equity_usd: 100000
gates:
  oos: { holdout_end: "2026-05-01", min_outperformance_pct: 0.0 }
  tail_risk: { max_single_trade_loss_pct: 5.0, max_portfolio_dd_pct: 20.0, max_rolling_30d_loss_pct: 10.0 }
  sample_size: { min_holdout_trades: 30 }
"""
    p = _write_config(tmp_path, body)
    with pytest.raises(ValueError, match="gates.oos missing required keys.*holdout_start"):
        load_variant_config(p)


def test_load_rejects_missing_tail_risk_dd(tmp_path):
    body = """
variant_id: t
description: ""
strategies:
  - class: OpeningRangeBreakoutStrategy
    symbols: [TECL]
    params: {}
portfolio:
  position_size_pct: 0.25
  max_concurrent: 3
  starting_equity_usd: 100000
gates:
  oos: { holdout_start: "2024-05-01", holdout_end: "2026-05-01", min_outperformance_pct: 0.0 }
  tail_risk: { max_single_trade_loss_pct: 5.0, max_rolling_30d_loss_pct: 10.0 }
  sample_size: { min_holdout_trades: 30 }
"""
    p = _write_config(tmp_path, body)
    with pytest.raises(ValueError, match="gates.tail_risk missing required keys.*max_portfolio_dd_pct"):
        load_variant_config(p)


def test_load_rejects_non_mapping_gate_block(tmp_path):
    body = """
variant_id: t
description: ""
strategies:
  - class: OpeningRangeBreakoutStrategy
    symbols: [TECL]
    params: {}
portfolio:
  position_size_pct: 0.25
  max_concurrent: 3
  starting_equity_usd: 100000
gates:
  oos: "not a dict"
  tail_risk: { max_single_trade_loss_pct: 5.0, max_portfolio_dd_pct: 20.0, max_rolling_30d_loss_pct: 10.0 }
  sample_size: { min_holdout_trades: 30 }
"""
    p = _write_config(tmp_path, body)
    with pytest.raises(ValueError, match="gates.oos must be a mapping"):
        load_variant_config(p)
