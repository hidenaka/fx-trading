"""Phase 0：キャリブレーション結果の Markdown レポート生成."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def generate_calibration_report(
    atr_results: dict[str, dict[str, float]],
    sweep_results: dict[str, pd.DataFrame],
    output_path: Path | str,
    period_start: str,
    period_end: str,
) -> None:
    """ATR と閾値スイープの結果を Markdown レポートに書き出す.

    Args:
        atr_results: {symbol: {'median_pct', 'mean_pct', 'p25_pct', 'p75_pct'}}
        sweep_results: {symbol: DataFrame(threshold, trade_count, win_rate, avg_pnl_pct, ...)}
        output_path: 出力ファイルパス
        period_start, period_end: データ期間（表示用）
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# Phase 0 Calibration Report")
    lines.append("")
    lines.append(f"**Period:** {period_start} 〜 {period_end}")
    lines.append("")
    lines.append("## ETF別 ATR(14, 5min) 分布（価格対比 %）")
    lines.append("")
    lines.append("| ETF | Median | Mean | P25 | P75 | 推奨損切(×1.5) | 推奨利確(×2.4) |")
    lines.append("|-----|--------|------|-----|-----|---------------|----------------|")
    for sym, atr in atr_results.items():
        med = atr["median_pct"]
        lines.append(
            f"| {sym} | {med:.3f}% | {atr['mean_pct']:.3f}% | "
            f"{atr['p25_pct']:.3f}% | {atr['p75_pct']:.3f}% | "
            f"{med*1.5:.3f}% | {med*2.4:.3f}% |"
        )
    lines.append("")

    lines.append("## ETF別 統合スコア閾値スイープ結果")
    for sym, df in sweep_results.items():
        lines.append("")
        lines.append(f"### {sym}")
        lines.append("")
        lines.append("| Threshold | Trades | Wins | Win Rate | Avg P&L | Expected (P&L×Count) |")
        lines.append("|-----------|--------|------|----------|---------|----------------------|")
        for _, row in df.iterrows():
            ev = row["avg_pnl_pct"] * row["trade_count"]
            lines.append(
                f"| {row['threshold']:.2f} | {int(row['trade_count'])} | "
                f"{int(row['win_count'])} | {row['win_rate']:.3f} | "
                f"{row['avg_pnl_pct']:.3f}% | {ev:.2f} |"
            )
        df_valid = df[df["trade_count"] > 0].copy()
        if len(df_valid) > 0:
            df_valid["expected"] = df_valid["avg_pnl_pct"] * df_valid["trade_count"]
            best = df_valid.loc[df_valid["expected"].idxmax()]
            lines.append("")
            lines.append(
                f"**推奨閾値（期待値最大）:** {best['threshold']:.2f}"
                f" — Win Rate {best['win_rate']:.3f}, Trades {int(best['trade_count'])}"
            )

    lines.append("")
    lines.append("## 次のステップ")
    lines.append("")
    lines.append("1. このレポートを人間がレビュー")
    lines.append("2. 推奨閾値・推奨ATR乗数を `phase0/recommended_config.json` に書き出す")
    lines.append("3. その値を `equity_trading/data/trades.sqlite` の `parameters` テーブルに投入")
    lines.append("4. Plan 2 の実装に進む")

    output_path.write_text("\n".join(lines), encoding="utf-8")
