"""Gate 1: out-of-sample — variant must beat baseline on holdout."""
from __future__ import annotations

from equity_trading.src.validation.gates.base import GateResult, Status


def run_oos_gate(
    *,
    variant_holdout: dict,
    baseline_holdout: dict,
    min_outperformance_pct: float,
) -> GateResult:
    v_ann = variant_holdout["annualized_pct"]
    b_ann = baseline_holdout["annualized_pct"]
    v_dd = abs(variant_holdout["max_dd_pct"])
    b_dd = abs(baseline_holdout["max_dd_pct"])
    v_sharpe = variant_holdout["sharpe"]
    b_sharpe = baseline_holdout["sharpe"]

    fails: list[str] = []
    warns: list[str] = []

    return_diff = v_ann - b_ann
    if return_diff < min_outperformance_pct:
        fails.append(
            f"variant ann {v_ann:.2f}% < baseline ann {b_ann:.2f}% + threshold {min_outperformance_pct:.2f}%"
        )
    if v_dd > b_dd * 1.2:
        fails.append(
            f"variant drawdown {v_dd:.2f}% > 1.2x baseline DD {b_dd:.2f}% (excessive risk)"
        )
    if not fails and v_sharpe < b_sharpe:
        warns.append(
            f"variant Sharpe {v_sharpe:.2f} < baseline Sharpe {b_sharpe:.2f} "
            f"(returns up but risk-adjusted worse)"
        )

    if fails:
        status = Status.FAIL
        summary = "; ".join(fails)
    elif warns:
        status = Status.WARN
        summary = "; ".join(warns)
    else:
        status = Status.PASS
        summary = (
            f"variant ann {v_ann:.2f}% vs baseline {b_ann:.2f}% "
            f"(+{return_diff:.2f}pp), Sharpe {v_sharpe:.2f} vs {b_sharpe:.2f}"
        )

    detail = (
        f"### Gate 1: OOS holdout {status.icon}\n\n"
        f"| metric | variant | baseline | diff |\n"
        f"|---|---:|---:|---:|\n"
        f"| Annual return | {v_ann:+.2f}% | {b_ann:+.2f}% | {return_diff:+.2f}pp |\n"
        f"| Max drawdown | -{v_dd:.2f}% | -{b_dd:.2f}% | {-v_dd-(-b_dd):+.2f}pp |\n"
        f"| Sharpe | {v_sharpe:.2f} | {b_sharpe:.2f} | {v_sharpe-b_sharpe:+.2f} |\n"
        f"\n{summary}\n"
    )
    return GateResult(name="oos", status=status, summary=summary, detail_md=detail,
                       metrics={
                           "variant_ann": v_ann, "baseline_ann": b_ann,
                           "variant_dd": v_dd, "baseline_dd": b_dd,
                           "variant_sharpe": v_sharpe, "baseline_sharpe": b_sharpe,
                       })
