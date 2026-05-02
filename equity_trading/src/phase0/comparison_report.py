"""5戦略の比較レポート（Markdown）."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def generate_comparison_report(
    results: dict[str, pd.DataFrame],
    atr_results: dict[str, dict[str, float]],
    output_path: Path | str,
    period_start: str,
    period_end: str,
) -> None:
    """5戦略の検証結果を比較レポートに整形.

    Args:
        results: {strategy_name: DataFrame(strategy, symbol, params, trade_count, win_rate, avg_pnl_pct)}
        atr_results: {symbol: {'median_pct', ...}}
        output_path: 出力ファイルパス
        period_start, period_end: データ期間
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# Phase 0 Multi-Strategy Comparison Report")
    lines.append("")
    lines.append(f"**Period:** {period_start} 〜 {period_end}")
    lines.append("")

    # ATR
    lines.append("## ETF別 ATR(14, 5min) 中央値（価格対比 %）")
    lines.append("")
    lines.append("| ETF | Median |")
    lines.append("|-----|--------|")
    for sym, atr in atr_results.items():
        lines.append(f"| {sym} | {atr['median_pct']:.3f}% |")
    lines.append("")

    # Per-strategy detail tables + per-strategy best
    best_per_strategy: list[dict] = []
    for strategy_name, df in results.items():
        lines.append(f"## 戦略: {strategy_name}")
        lines.append("")
        lines.append("| Symbol | Params | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |")
        lines.append("|--------|--------|--------|------|----------|---------|----------------------|")

        df_copy = df.copy()
        df_copy["expected"] = df_copy["avg_pnl_pct"] * df_copy["trade_count"]

        for _, row in df_copy.iterrows():
            wr = row["win_rate"]
            wr_str = f"{wr:.3f}" if pd.notna(wr) else "nan"
            pnl = row["avg_pnl_pct"]
            pnl_str = f"{pnl:.3f}%" if pd.notna(pnl) else "nan%"
            ev = row["expected"]
            ev_str = f"{ev:.2f}" if pd.notna(ev) else "nan"
            lines.append(
                f"| {row['symbol']} | `{row['params']}` | "
                f"{int(row['trade_count'])} | {int(row['win_count'])} | "
                f"{wr_str} | {pnl_str} | {ev_str} |"
            )

        df_valid = df_copy[df_copy["trade_count"] > 0].copy()
        if len(df_valid) > 0:
            best = df_valid.loc[df_valid["expected"].idxmax()]
            lines.append("")
            lines.append(
                f"**Best for {strategy_name}:** {best['symbol']} / `{best['params']}` "
                f"→ EV {best['expected']:.2f} (WR {best['win_rate']:.3f}, Trades {int(best['trade_count'])})"
            )
            best_per_strategy.append({
                "strategy": strategy_name,
                "symbol": best["symbol"],
                "params": best["params"],
                "expected": best["expected"],
                "win_rate": best["win_rate"],
                "trade_count": int(best["trade_count"]),
            })
        lines.append("")

    # Cross-strategy ranking
    lines.append("## 横断比較：戦略別ベスト")
    lines.append("")
    lines.append("| Rank | Strategy | Symbol | Params | EV | Win Rate | Trades |")
    lines.append("|------|----------|--------|--------|-----|----------|--------|")
    sorted_best = sorted(best_per_strategy, key=lambda d: d["expected"], reverse=True)
    for rank, b in enumerate(sorted_best, start=1):
        lines.append(
            f"| {rank} | {b['strategy']} | {b['symbol']} | `{b['params']}` | "
            f"{b['expected']:.2f} | {b['win_rate']:.3f} | {b['trade_count']} |"
        )
    lines.append("")

    if sorted_best:
        winner = sorted_best[0]
        lines.append(f"## 推奨：**{winner['strategy']}** （{winner['symbol']}、EV {winner['expected']:.2f}）")
        lines.append("")

    lines.append("## 次のステップ")
    lines.append("")
    lines.append("1. このレポートを人間がレビュー、最良戦略を確認")
    lines.append("2. 推奨戦略を Plan 2 の本実装の対象とする")
    lines.append("3. 必要に応じて、上位2戦略をアンサンブル運用も検討")

    output_path.write_text("\n".join(lines), encoding="utf-8")
