"""Validation report writer (markdown)."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from equity_trading.src.validation.gates.base import GateResult, Status

if TYPE_CHECKING:
    import pandas as pd

REQUIRED_GATES = {"oos", "tail_risk", "sample_size"}


class Headline(Enum):
    APPROVE = "APPROVE"
    REVIEW = "REVIEW"
    REJECT = "REJECT"

    @property
    def icon(self) -> str:
        return {"APPROVE": "✅", "REVIEW": "⚠️", "REJECT": "❌"}[self.value]


def derive_headline(gates: Iterable[GateResult]) -> Headline:
    gates = list(gates)
    required = [g for g in gates if g.name in REQUIRED_GATES]
    if any(g.status == Status.FAIL for g in required):
        return Headline.REJECT
    if any(g.status == Status.WARN for g in gates):
        return Headline.REVIEW
    return Headline.APPROVE


def write_validation_report(
    *,
    path: Path | str,
    variant_id: str,
    baseline_id: str,
    gates: list[GateResult],
    git_sha: str,
    manifest_hash: str,
    holdout_window: tuple[str, str],
    generated_at: datetime,
    variant_trades: "pd.DataFrame | None" = None,
) -> None:
    headline = derive_headline(gates)
    lines: list[str] = []
    lines.append(f"# Validation Report: {variant_id}\n")
    lines.append(f"- **Variant**: `{variant_id}`")
    lines.append(f"- **Baseline**: `{baseline_id}`")
    lines.append(f"- **Generated**: {generated_at.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"- **Git SHA**: `{git_sha}`")
    lines.append(f"- **Data manifest hash**: `{manifest_hash}`")
    lines.append(f"- **Holdout window**: {holdout_window[0]} → {holdout_window[1]}")
    lines.append("")
    lines.append(f"## Headline: {headline.icon} **{headline.value}**\n")
    for g in gates:
        if g.name in REQUIRED_GATES and g.status == Status.FAIL:
            lines.append(f"- ❌ Required gate `{g.name}` failed: {g.summary}")
        elif g.status == Status.WARN:
            lines.append(f"- ⚠️ `{g.name}`: {g.summary}")
    lines.append("")
    lines.append("## Gate Results\n")
    for g in gates:
        lines.append(g.detail_md)
        lines.append("")
    lines.append("## Reproducibility\n")
    lines.append("```")
    lines.append(f"git checkout {git_sha}")
    lines.append("python3 -m equity_trading.validation.validate \\")
    lines.append(f"    --variant configs/{variant_id}.yaml \\")
    lines.append(f"    --baseline configs/{baseline_id}.yaml")
    lines.append("```")
    lines.append("")
    if variant_trades is not None and len(variant_trades) > 0:
        from equity_trading.src.validation.risk_profile import render_risk_profile_md
        lines.append(render_risk_profile_md(variant_trades))
        lines.append("")
    lines.append("## Decision Log\n")
    lines.append("(Fill in: APPROVED / REJECTED / reasoning)")
    lines.append("")
    Path(path).write_text("\n".join(lines))
