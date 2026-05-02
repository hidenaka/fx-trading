"""P2: Univariate pattern discovery from labeled candidate dataset."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd


CONTINUOUS_FEATURES = [
    "rsi_14", "bb_pct_b", "vwap_dev", "volume_ratio", "intraday_change",
    "gap_pct", "daily_ma_distance", "daily_5d_return", "daily_20d_return",
    "atr_ratio_5min", "spy_intraday", "score_value",
]
CATEGORICAL_FEATURES = ["ny_hour", "day_of_week", "bars_since_open"]
N_BINS_CONTINUOUS = 10  # deciles


def _bucket_continuous(values: pd.Series, n: int = N_BINS_CONTINUOUS) -> tuple[pd.Series, list]:
    """Quantile-based bucketing. Returns (bucket_label_series, list_of_edges)."""
    # Use train-only quantiles to avoid lookahead in test
    valid = values.dropna()
    if len(valid) < n * 5:
        return pd.Series(["all"] * len(values), index=values.index), []
    edges = list(valid.quantile(np.linspace(0, 1, n + 1)).unique())
    if len(edges) < 3:
        return pd.Series(["all"] * len(values), index=values.index), edges
    labels = [f"q{i+1}" for i in range(len(edges) - 1)]
    bucket = pd.cut(values, bins=edges, labels=labels, include_lowest=True)
    return bucket.astype(str), edges


def _stats(df: pd.DataFrame) -> dict:
    if len(df) == 0:
        return {"n": 0, "wr": float("nan"), "avg_pnl_pct": float("nan")}
    return {
        "n": int(len(df)),
        "wr": float(df["win"].mean()),
        "avg_pnl_pct": float(df["pnl_pct"].mean() * 100),
    }


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    dataset_path = project_root / "phase0" / "pattern_discovery_dataset.parquet"
    out_dir = project_root / "phase0"

    df = pd.read_parquet(dataset_path)
    print(f"loaded {len(df)} rows")

    train_df = df[df["split"] == "train"]
    test_df = df[df["split"] == "test"]

    rows = []
    md_lines = []
    md_lines.append("# P2: Univariate Pattern Discovery")
    md_lines.append("")
    md_lines.append(f"**Total samples:** {len(df)} (train: {len(train_df)}, test: {len(test_df)})")
    md_lines.append("")

    # Per-strategy baseline
    md_lines.append("## Baseline WR by strategy/split")
    md_lines.append("")
    md_lines.append("| Strategy | Train n | Train WR | Test n | Test WR |")
    md_lines.append("|----------|---------|----------|--------|---------|")
    for strat in sorted(df["strategy"].unique()):
        tr = train_df[train_df["strategy"] == strat]
        te = test_df[test_df["strategy"] == strat]
        tr_wr = tr["win"].mean() if len(tr) > 0 else float("nan")
        te_wr = te["win"].mean() if len(te) > 0 else float("nan")
        md_lines.append(f"| {strat} | {len(tr)} | {tr_wr:.3f} | {len(te)} | {te_wr:.3f} |")
    md_lines.append("")

    for strategy in sorted(df["strategy"].unique()):
        s_df = df[df["strategy"] == strategy]
        s_train = train_df[train_df["strategy"] == strategy]
        s_test = test_df[test_df["strategy"] == strategy]

        if len(s_train) < 100 or len(s_test) < 50:
            md_lines.append(f"## {strategy}")
            md_lines.append("")
            md_lines.append(f"_Skipped — insufficient samples (train={len(s_train)}, test={len(s_test)})_")
            md_lines.append("")
            continue

        md_lines.append(f"## {strategy}")
        md_lines.append("")

        for feature in CONTINUOUS_FEATURES + CATEGORICAL_FEATURES:
            if feature not in s_df.columns:
                continue

            # Bucket using train-only quantiles to keep test out-of-sample
            if feature in CONTINUOUS_FEATURES:
                edges = list(s_train[feature].dropna().quantile(np.linspace(0, 1, N_BINS_CONTINUOUS + 1)).unique())
                if len(edges) < 3:
                    continue
                labels = [f"q{i+1}" for i in range(len(edges) - 1)]
                # apply to combined
                s_df_bk = s_df.copy()
                s_df_bk["_bucket"] = pd.cut(
                    s_df_bk[feature], bins=edges, labels=labels, include_lowest=True
                ).astype(str)
            else:
                s_df_bk = s_df.copy()
                s_df_bk["_bucket"] = s_df_bk[feature].astype(int).astype(str)

            tr_bk = s_df_bk[s_df_bk["split"] == "train"]
            te_bk = s_df_bk[s_df_bk["split"] == "test"]

            buckets = sorted(s_df_bk["_bucket"].unique())
            for b in buckets:
                if b == "nan" or b == "NaT":
                    continue
                tr_b = tr_bk[tr_bk["_bucket"] == b]
                te_b = te_bk[te_bk["_bucket"] == b]
                tr_s = _stats(tr_b)
                te_s = _stats(te_b)
                row = {
                    "strategy": strategy,
                    "feature": feature,
                    "bucket": b,
                    "train_n": tr_s["n"],
                    "train_wr": tr_s["wr"],
                    "train_avg_pnl_pct": tr_s["avg_pnl_pct"],
                    "test_n": te_s["n"],
                    "test_wr": te_s["wr"],
                    "test_avg_pnl_pct": te_s["avg_pnl_pct"],
                }
                # robust criterion
                row["robust"] = (
                    tr_s["n"] >= 20 and te_s["n"] >= 20
                    and tr_s["wr"] >= 0.65 and te_s["wr"] >= 0.65
                    and tr_s["avg_pnl_pct"] > 0 and te_s["avg_pnl_pct"] > 0
                )
                rows.append(row)

        # Per-strategy: feature-level robust patterns
        strat_rows = [r for r in rows if r["strategy"] == strategy and r["robust"]]
        if strat_rows:
            md_lines.append(f"### Robust patterns for {strategy}")
            md_lines.append("")
            md_lines.append("| Feature | Bucket | Train n | Train WR | Train Avg P&L | Test n | Test WR | Test Avg P&L |")
            md_lines.append("|---------|--------|---------|----------|---------------|--------|---------|--------------|")
            for r in sorted(strat_rows, key=lambda r: -min(r["train_wr"], r["test_wr"])):
                md_lines.append(
                    f"| {r['feature']} | {r['bucket']} | {r['train_n']} | {r['train_wr']:.3f} | "
                    f"{r['train_avg_pnl_pct']:+.3f}% | {r['test_n']} | {r['test_wr']:.3f} | "
                    f"{r['test_avg_pnl_pct']:+.3f}% |"
                )
            md_lines.append("")
        else:
            md_lines.append(f"_No robust patterns found for {strategy}._")
            md_lines.append("")

    # Save full bucket table
    table = pd.DataFrame(rows)
    table_path = out_dir / "p2_pattern_table.parquet"
    table.to_parquet(table_path)
    print(f"[saved] {table_path}")

    # Top patterns across all strategies
    robust = table[table["robust"]].copy()
    robust["score"] = robust.apply(
        lambda r: min(r["train_wr"], r["test_wr"]) * min(r["train_n"], r["test_n"]), axis=1,
    )
    md_lines.append("## Top robust patterns across all strategies (by WR×n)")
    md_lines.append("")
    if len(robust) == 0:
        md_lines.append("_No patterns met the robustness criteria (train and test WR ≥ 0.65, n ≥ 20)._")
    else:
        md_lines.append("| Strategy | Feature | Bucket | Train (n / WR / P&L) | Test (n / WR / P&L) | Score |")
        md_lines.append("|----------|---------|--------|----------------------|---------------------|-------|")
        top = robust.sort_values("score", ascending=False).head(30)
        for _, r in top.iterrows():
            md_lines.append(
                f"| {r['strategy']} | {r['feature']} | {r['bucket']} | "
                f"{r['train_n']} / {r['train_wr']:.3f} / {r['train_avg_pnl_pct']:+.3f}% | "
                f"{r['test_n']} / {r['test_wr']:.3f} / {r['test_avg_pnl_pct']:+.3f}% | "
                f"{r['score']:.1f} |"
            )
    md_lines.append("")

    # Interpretation section (heuristic)
    md_lines.append("## Interpretation")
    md_lines.append("")
    if len(robust) > 0:
        # which features show up most
        feat_counts = robust["feature"].value_counts().head(5)
        md_lines.append("### Most-frequently-robust features:")
        for feat, n in feat_counts.items():
            md_lines.append(f"- {feat} ({n} robust buckets)")
    else:
        md_lines.append("No single feature provided robust filtering. Move to bivariate (P3).")
    md_lines.append("")

    md_path = out_dir / "p2_univariate_patterns.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"[saved] {md_path}")
    print(f"\nFound {len(robust)} robust univariate patterns")
    return 0


if __name__ == "__main__":
    sys.exit(main())
