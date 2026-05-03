"""CLI: python3 -m equity_trading.validation.validate \\
        --variant configs/<id>.yaml \\
        --baseline configs/<id>.yaml \\
        --output phase0/validation/<id>.md
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from equity_trading.src.validation.config import load_variant_config
from equity_trading.src.validation.data import EvaluationContext
from equity_trading.src.validation.gates.oos import run_oos_gate
from equity_trading.src.validation.gates.sample_size import run_sample_size_gate
from equity_trading.src.validation.gates.tail_risk import run_tail_risk_gate
from equity_trading.src.validation.manifest import verify_manifest
from equity_trading.src.validation.report import write_validation_report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validation framework")
    p.add_argument("--variant", type=Path, required=True)
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--data-root", type=Path,
                    default=Path("equity_trading/data/prices"))
    return p.parse_args(argv)


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True,
        ).strip()
    except Exception:
        return "unknown"


def _manifest_hash(data_root: Path) -> str:
    mp = data_root / "manifest.json"
    if not mp.exists():
        return "no-manifest"
    import hashlib
    return hashlib.sha256(mp.read_bytes()).hexdigest()[:12]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.data_root.exists():
        print(f"[ERROR] data root not found: {args.data_root}", file=sys.stderr)
        return 2
    try:
        verify_manifest(args.data_root)
    except Exception as exc:
        print(f"[ERROR] manifest verification failed: {exc}", file=sys.stderr)
        return 2

    variant = load_variant_config(args.variant)
    baseline = load_variant_config(args.baseline)

    try:
        from equity_trading.src.validation.runner import run_holdout_simulation
    except ImportError:
        print("[ERROR] portfolio runner not available (Task 12 prerequisite). "
              "Wire equity_trading.src.validation.runner first.", file=sys.stderr)
        return 3

    with EvaluationContext(
        root=args.data_root, variant_id=variant.variant_id,
        reason="cli:validate",
    ) as ctx:
        v_summary, v_trades, v_equity, _ = run_holdout_simulation(variant, ctx)
        b_summary, b_trades, b_equity, _ = run_holdout_simulation(baseline, ctx)

    gates = []
    gates.append(run_oos_gate(
        variant_holdout=v_summary,
        baseline_holdout=b_summary,
        min_outperformance_pct=variant.gates["oos"]["min_outperformance_pct"],
    ))
    gates.append(run_tail_risk_gate(
        equity_curve=v_equity, trades=v_trades,
        max_single_trade_loss_pct=variant.gates["tail_risk"]["max_single_trade_loss_pct"],
        max_portfolio_dd_pct=variant.gates["tail_risk"]["max_portfolio_dd_pct"],
        max_rolling_30d_loss_pct=variant.gates["tail_risk"]["max_rolling_30d_loss_pct"],
    ))
    gates.append(run_sample_size_gate(
        holdout_trades=v_trades,
        min_holdout_trades=variant.gates["sample_size"]["min_holdout_trades"],
    ))

    stress_cfg = variant.gates.get("stress_test", {})
    if stress_cfg.get("enabled"):
        from equity_trading.src.validation.gates.stress_test import run_stress_test_gate
        gates.append(run_stress_test_gate(
            cfg=variant, baseline_cfg=baseline,
            train_root=args.data_root,
            stress_windows=stress_cfg.get("windows", []),
        ))

    write_validation_report(
        path=args.output, variant_id=variant.variant_id, baseline_id=baseline.variant_id,
        gates=gates, git_sha=_git_sha(), manifest_hash=_manifest_hash(args.data_root),
        holdout_window=(variant.gates["oos"]["holdout_start"], variant.gates["oos"]["holdout_end"]),
        generated_at=datetime.now(timezone.utc),
        variant_trades=v_trades,
    )
    print(f"[saved] {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
