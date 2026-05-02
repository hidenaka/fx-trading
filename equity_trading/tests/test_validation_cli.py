"""CLI entry point smoke test."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from equity_trading.src.validation import cli


def _seed_variant_yaml(path: Path, variant_id: str) -> Path:
    body = f"""
variant_id: {variant_id}
description: cli test
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
    path.write_text(body)
    return path


def test_cli_parses_args_and_loads_configs(tmp_path):
    v = _seed_variant_yaml(tmp_path / "v.yaml", "test_v1")
    b = _seed_variant_yaml(tmp_path / "b.yaml", "test_b0")
    args = cli.parse_args(["--variant", str(v), "--baseline", str(b),
                            "--output", str(tmp_path / "out.md"),
                            "--data-root", str(tmp_path / "fake_data")])
    assert args.variant == v
    assert args.baseline == b


def test_cli_main_returns_nonzero_when_data_missing(tmp_path):
    v = _seed_variant_yaml(tmp_path / "v.yaml", "test_v1")
    b = _seed_variant_yaml(tmp_path / "b.yaml", "test_b0")
    rc = cli.main([
        "--variant", str(v), "--baseline", str(b),
        "--output", str(tmp_path / "out.md"),
        "--data-root", str(tmp_path / "no_data"),
    ])
    assert rc != 0  # data missing → fail
