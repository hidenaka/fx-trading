"""勝敗要因分析の Markdown レポート."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def generate_analysis_report(
    analyses: dict[tuple[str, str], dict],
    output_path: Path | str,
    period_start: str,
    period_end: str,
) -> None:
    """Write a Markdown diagnostic report for one or more (strategy, symbol) analyses."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# Phase 0 Trade-Level Diagnostic Report")
    lines.append("")
    lines.append(f"**Period:** {period_start} 〜 {period_end}")
    lines.append("")
    lines.append("各戦略×ETFの個別取引について、退場理由・時間帯・地合い別に勝敗を集計。")
    lines.append("")

    for (strategy, symbol), a in analyses.items():
        lines.append(f"## {strategy} × {symbol}")
        lines.append("")
        wr_str = f"{a['win_rate']:.3f}" if pd.notna(a["win_rate"]) else "n/a"
        lines.append(
            f"- Trades: **{a['n_trades']}**, Wins: **{a['n_wins']}**, WR: **{wr_str}**, "
            f"Avg P&L: **{a['avg_pnl_pct']:.4f}%**, Total P&L: **{a['total_pnl_pct']:.3f}%**"
        )
        lines.append("")

        # Exit breakdown
        lines.append("### 退場理由 (Exit Type Breakdown)")
        lines.append("")
        lines.append("| Exit | Count | Avg P&L (%) |")
        lines.append("|------|-------|-------------|")
        for ex in ["stop", "target", "time"]:
            n = a["exit_breakdown"].get(ex, 0)
            apx = a["avg_pnl_by_exit_type"].get(ex, float("nan"))
            apx_str = f"{apx:.4f}" if pd.notna(apx) else "n/a"
            lines.append(f"| {ex} | {n} | {apx_str} |")
        lines.append("")

        # Hour of day
        lines.append("### 時間帯別（NY時刻）/ Hour of Day")
        lines.append("")
        if len(a["wr_by_hour_of_day"]) == 0:
            lines.append("(no trades)")
        else:
            lines.append("| Hour | Trades | Wins | WR | Avg P&L (%) |")
            lines.append("|------|--------|------|------|------|")
            for _, r in a["wr_by_hour_of_day"].iterrows():
                lines.append(
                    f"| {int(r['hour'])} | {int(r['n_trades'])} | {int(r['n_wins'])} | "
                    f"{r['win_rate']:.3f} | {r['avg_pnl_pct']:.4f} |"
                )
        lines.append("")

        # Day-open change buckets
        lines.append("### 当日下落・上昇率（始値からのエントリー時点）")
        lines.append("")
        if len(a["wr_by_day_open_change"]) == 0:
            lines.append("(no trades)")
        else:
            lines.append("| Bucket | Trades | WR | Avg P&L (%) |")
            lines.append("|--------|--------|------|------|")
            for _, r in a["wr_by_day_open_change"].iterrows():
                lines.append(
                    f"| {r['bucket']} | {int(r['n_trades'])} | {r['win_rate']:.3f} | {r['avg_pnl_pct']:.4f} |"
                )
        lines.append("")

        # SPY regime (optional)
        if "wr_by_spy_regime" in a:
            lines.append("### SPY 地合い (Market Regime)")
            lines.append("")
            if len(a["wr_by_spy_regime"]) == 0:
                lines.append("(no trades)")
            else:
                lines.append("| Regime | Trades | WR | Avg P&L (%) |")
                lines.append("|--------|--------|------|------|")
                for _, r in a["wr_by_spy_regime"].iterrows():
                    lines.append(
                        f"| {r['regime']} | {int(r['n_trades'])} | {r['win_rate']:.3f} | {r['avg_pnl_pct']:.4f} |"
                    )
            lines.append("")

        # Holding time
        lines.append("### 保有時間別 (Holding Time)")
        lines.append("")
        if len(a["wr_by_holding_bars"]) == 0:
            lines.append("(no trades)")
        else:
            lines.append("| Bars Held | Trades | WR | Avg P&L (%) |")
            lines.append("|-----------|--------|------|------|")
            for _, r in a["wr_by_holding_bars"].iterrows():
                lines.append(
                    f"| {r['bucket']} | {int(r['n_trades'])} | {r['win_rate']:.3f} | {r['avg_pnl_pct']:.4f} |"
                )
        lines.append("")

    # Cross-strategy patterns section
    lines.append("## 横断パターン (Cross-strategy Patterns)")
    lines.append("")
    if not analyses:
        lines.append("(no analyses)")
    else:
        # Stop-exit concentration: losers that are dominated by stop exits
        rows = []
        for (s, sym), a in analyses.items():
            n = a["n_trades"]
            stops = a["exit_breakdown"]["stop"]
            stop_frac = stops / n if n else float("nan")
            rows.append((s, sym, n, stops, stop_frac))

        lines.append("### 退場理由 stop の比率（高い＝損切で叩かれている）")
        lines.append("")
        lines.append("| Strategy | Symbol | Trades | Stops | Stop % |")
        lines.append("|----------|--------|--------|-------|--------|")
        for s, sym, n, st, sf in sorted(rows, key=lambda r: -(r[4] if pd.notna(r[4]) else -1)):
            sf_str = f"{sf * 100:.1f}%" if pd.notna(sf) else "n/a"
            lines.append(f"| {s} | {sym} | {n} | {st} | {sf_str} |")
        lines.append("")

        # Hour-of-day WR gap between best and worst strategy
        lines.append("### 時間帯別 WR の戦略間ギャップ")
        lines.append("")
        # Collect per-hour WR for each strategy
        hour_data: dict[int, list[float]] = {}
        for (s, sym), a in analyses.items():
            hod = a["wr_by_hour_of_day"]
            if len(hod) == 0:
                continue
            for _, r in hod.iterrows():
                h = int(r["hour"])
                hour_data.setdefault(h, []).append(float(r["win_rate"]))

        gap_rows = []
        for h, wrs in sorted(hour_data.items()):
            if len(wrs) >= 2:
                gap_rows.append((h, max(wrs) - min(wrs), max(wrs), min(wrs)))

        if gap_rows:
            lines.append("| Hour | WR Gap | Best WR | Worst WR |")
            lines.append("|------|--------|---------|----------|")
            for h, gap, best, worst in sorted(gap_rows, key=lambda r: -r[1]):
                lines.append(f"| {h} | {gap:.3f} | {best:.3f} | {worst:.3f} |")
        else:
            lines.append("(insufficient data for cross-strategy hour comparison)")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
