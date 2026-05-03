"""Risk profile computations for validation reports.

Surfaces concentration risk in the holdout: per-symbol P&L contribution,
pairwise pnl-pct correlation, and simultaneous-position stress overlap.
"""
from __future__ import annotations

import pandas as pd


def compute_symbol_contribution(trades: pd.DataFrame) -> pd.DataFrame:
    """Group accepted trades by symbol; return n / gross $ / % of total / avg %."""
    if len(trades) == 0:
        return pd.DataFrame(columns=["symbol", "trades", "gross_pnl_dollars",
                                       "pct_of_total", "avg_pnl_pct"])
    df = trades.copy()
    df["pnl_dollars"] = df["pnl_pct"] * df["position_dollars"]
    grouped = df.groupby("symbol").agg(
        trades=("pnl_pct", "size"),
        gross_pnl_dollars=("pnl_dollars", "sum"),
        avg_pnl_pct=("pnl_pct", "mean"),
    ).reset_index()
    total = grouped["gross_pnl_dollars"].abs().sum()
    grouped["pct_of_total"] = (grouped["gross_pnl_dollars"].abs() / total * 100) if total > 0 else 0.0
    return grouped


def compute_pairwise_correlation(trades: pd.DataFrame) -> pd.DataFrame:
    """Pivot trades to (date x symbol) -> daily pnl, return Pearson corr matrix."""
    if len(trades) == 0:
        return pd.DataFrame()
    df = trades.copy()
    df["date"] = df["entry_ts"].dt.date
    pivoted = df.pivot_table(index="date", columns="symbol", values="pnl_pct",
                              aggfunc="mean", fill_value=0.0)
    return pivoted.corr()


def compute_stress_overlap(trades: pd.DataFrame, min_concurrent: int = 3) -> dict:
    """Count windows where >= min_concurrent positions were open simultaneously."""
    if len(trades) == 0:
        return {"overlap_windows": 0, "all_losing_windows": 0}
    events = []
    for _, t in trades.iterrows():
        events.append((t["entry_ts"], +1, t["pnl_pct"]))
        events.append((t["exit_ts"], -1, t["pnl_pct"]))
    events.sort(key=lambda e: (e[0], -e[1]))
    open_count = 0
    current_pnls: list[float] = []
    overlap_windows = 0
    all_losing_windows = 0
    in_overlap = False
    for ts, delta, pnl in events:
        if delta == +1:
            open_count += 1
            current_pnls.append(pnl)
            if open_count >= min_concurrent and not in_overlap:
                in_overlap = True
                overlap_windows += 1
                if all(p < 0 for p in current_pnls):
                    all_losing_windows += 1
        else:
            open_count -= 1
            if pnl in current_pnls:
                current_pnls.remove(pnl)
            if open_count < min_concurrent:
                in_overlap = False
    return {"overlap_windows": overlap_windows, "all_losing_windows": all_losing_windows}


def render_risk_profile_md(trades: pd.DataFrame) -> str:
    """Render the full Risk profile section as markdown."""
    parts: list[str] = ["## Risk profile\n"]
    contrib = compute_symbol_contribution(trades)
    parts.append("### Symbol contribution to P&L (holdout)\n")
    if len(contrib) == 0:
        parts.append("(no trades)\n")
    else:
        parts.append("| symbol | trades | gross P&L $ | % of total | avg P&L % |")
        parts.append("|---|---:|---:|---:|---:|")
        for _, r in contrib.iterrows():
            parts.append(
                f"| {r['symbol']} | {int(r['trades'])} | "
                f"${r['gross_pnl_dollars']:+,.0f} | "
                f"{r['pct_of_total']:.1f}% | "
                f"{r['avg_pnl_pct']*100:+.2f}% |"
            )
    parts.append("")
    corr = compute_pairwise_correlation(trades)
    parts.append("### Pairwise daily-return correlation\n")
    if corr.empty:
        parts.append("(no trades)\n")
    else:
        symbols = list(corr.columns)
        header = "|   | " + " | ".join(symbols) + " |"
        sep = "|---|" + "|".join(["---:"] * len(symbols)) + "|"
        parts.append(header)
        parts.append(sep)
        for s in symbols:
            row = "| " + s + " | " + " | ".join(f"{corr.loc[s, t]:.2f}" for t in symbols) + " |"
            parts.append(row)
    parts.append("")
    overlap = compute_stress_overlap(trades, min_concurrent=3)
    parts.append("### Stress overlap\n")
    parts.append(f"- Windows with >=3 positions open simultaneously: **{overlap['overlap_windows']}**")
    parts.append(f"- Of those, windows where all open positions were losing: "
                  f"**{overlap['all_losing_windows']}**")
    parts.append("")
    return "\n".join(parts)
