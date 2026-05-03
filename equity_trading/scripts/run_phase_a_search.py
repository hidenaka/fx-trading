"""Phase A variant search.

Reads configs/phase_a/*.yaml, simulates each on internal valid2
(2022-01-01 → 2024-04-30), applies the four-axis threshold from spec §1,
and writes a markdown report ranking the candidates by ann return.

This script reads ONLY train data via internal_split. It must not
read holdout — a guard test (test_search_does_not_read_holdout) enforces this.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from equity_trading.src.validation.config import load_variant_config
from equity_trading.src.validation.runner import (
    _collect_trades_from_split,
    _simulate_portfolio,
)


def _eval_threshold(summary: dict, worst_trade_pct: float) -> list[str]:
    fails: list[str] = []
    if summary["annualized_pct"] < -3.0:
        fails.append("ann")
    if abs(summary["max_dd_pct"]) > 20.0:
        fails.append("MaxDD")
    if abs(worst_trade_pct) > 5.0:
        fails.append("worst")
    if summary["sharpe"] < -0.3:
        fails.append("Sharpe")
    return fails


def _render_md(rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append("# Phase A search — internal valid (2022-01-01 → 2024-04-30)\n")
    lines.append("**Threshold (Q2 A)**: ann ≥ -3%/yr, MaxDD ≤ 20%, "
                  "worst trade ≤ 5%, Sharpe ≥ -0.3\n")
    lines.append("| variant | ann | MaxDD | worst | Sharpe | n trades | passes? |")
    lines.append("|---|---:|---:|---:|---:|---:|:---:|")
    for r in rows:
        passes = "✅" if not r["fails"] else "❌ " + "/".join(r["fails"])
        lines.append(
            f"| {r['variant_id']} | {r['ann']:+.2f}% | {r['dd']:+.2f}% | "
            f"{r['worst']:+.2f}% | {r['sharpe']:+.2f} | {r['n']} | {passes} |"
        )
    lines.append("")
    passing = [r for r in rows if not r["fails"]]
    if not passing:
        lines.append("## No candidate passes")
        lines.append("")
        lines.append("Phase A step 1 (6 candidates) yielded no passing variant. "
                      "Escalate to step 2 (12 candidates) by adding `target_mult ∈ {1.0, 1.5}` "
                      "to the search dimensions, or to step 3 (24 candidates, +daily_halt_pct), "
                      "or to Phase B (new strategies / universe) per "
                      "`docs/superpowers/specs/2026-05-04-strategy-rethink-design.md` §8.")
    else:
        winner = max(passing, key=lambda r: r["ann"])
        lines.append(f"## Top by ann return (passing only): **{winner['variant_id']}** "
                      f"({winner['ann']:+.2f}%/yr)")
        lines.append("")
        lines.append("→ Run holdout test:")
        lines.append("```")
        lines.append("python3 -m equity_trading.src.validation \\")
        lines.append(f"    --variant equity_trading/configs/phase_a/"
                      f"{winner['variant_id'].replace('orb_default_v0_', 'v0_')}.yaml \\")
        lines.append("    --baseline equity_trading/configs/orb_default_v0.yaml \\")
        lines.append("    --output equity_trading/phase0/validation/"
                      f"<date>_phase_a_winner_holdout.md")
        lines.append("```")
    return "\n".join(lines) + "\n"


def run_search(*, configs_dir: Path, data_root: Path, output: Path,
                vix_daily: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for cfg_path in sorted(Path(configs_dir).glob("*.yaml")):
        cfg = load_variant_config(cfg_path)
        trades = _collect_trades_from_split(cfg, data_root, "valid2", vix_daily=vix_daily)
        summary, _eq, _accepted = _simulate_portfolio_safe(
            trades, starting_equity=cfg.portfolio["starting_equity_usd"],
            position_size_pct=cfg.portfolio["position_size_pct"],
            max_concurrent=cfg.portfolio["max_concurrent"],
        )
        worst = float(trades["pnl_pct"].min() * 100) if len(trades) > 0 else 0.0
        fails = _eval_threshold(summary, worst)
        rows.append({
            "variant_id": cfg.variant_id,
            "ann": summary["annualized_pct"],
            "dd": summary["max_dd_pct"],
            "worst": worst,
            "sharpe": summary["sharpe"],
            "n": len(trades),
            "fails": fails,
        })
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(_render_md(rows))
    return rows


def _simulate_portfolio_safe(trades, starting_equity, position_size_pct, max_concurrent):
    """Wrapper that tolerates either the existing 2-tuple or a future 3-tuple
    return shape from runner._simulate_portfolio."""
    result = _simulate_portfolio(
        trades=trades, starting_equity=starting_equity,
        position_size_pct=position_size_pct, max_concurrent=max_concurrent,
    )
    if len(result) == 2:
        summary, eq = result
        return summary, eq, pd.DataFrame()
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--configs-dir", type=Path,
                    default=Path("equity_trading/configs/phase_a"))
    p.add_argument("--data-root", type=Path,
                    default=Path("equity_trading/data/prices"))
    p.add_argument("--output", type=Path, required=True)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    vix_path = args.data_root / "VIX_1day_2019-05-01_2026-05-01.parquet"
    vix_daily = pd.read_parquet(vix_path) if vix_path.exists() else pd.DataFrame(
        {"close": []}, index=pd.DatetimeIndex([], tz="UTC"))
    run_search(configs_dir=args.configs_dir, data_root=args.data_root,
                output=args.output, vix_daily=vix_daily)
    print(f"[saved] {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
