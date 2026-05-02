"""P4: gap_fill winners vs losers deep dive with new features."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
from scipy import stats


def _load(cache_dir: Path, symbol: str, tf: str, start, end) -> pd.DataFrame:
    s = start.strftime("%Y-%m-%dT%H%M")
    e = end.strftime("%Y-%m-%dT%H%M")
    return pd.read_parquet(cache_dir / f"{symbol}_{tf}_{s}_{e}.parquet")


def _new_features_for_row(row, daily_by_symbol, spy_daily, xlk_daily) -> dict:
    """Compute 9 new features for one gap_fill candidate."""
    ts = pd.Timestamp(row["timestamp"])
    ny_date = ts.tz_convert("America/New_York").date()
    symbol = row["symbol"]

    daily = daily_by_symbol.get(symbol)
    if daily is None:
        return {k: np.nan for k in [
            "consecutive_down_days", "prev_day_change", "prev_2d_change",
            "gap_size_relative_to_atr", "is_monday", "is_friday", "day_of_month",
            "vix_proxy", "spy_5d_change", "xlk_relative_strength",
        ]}

    import bisect
    # daily index in NY tz
    if daily.index.tz is not None:
        ddates = list(daily.index.tz_convert("America/New_York").date)
    else:
        ddates = list(daily.index.date)
    closes = daily["close"].to_numpy()
    opens = daily["open"].to_numpy() if "open" in daily.columns else closes

    # Find prev daily index
    prev_idx = bisect.bisect_left(ddates, ny_date) - 1

    out = {}
    if prev_idx < 1:
        out.update({k: np.nan for k in [
            "consecutive_down_days", "prev_day_change", "prev_2d_change",
            "gap_size_relative_to_atr", "is_monday", "is_friday", "day_of_month",
            "vix_proxy", "spy_5d_change", "xlk_relative_strength",
        ]})
        return out

    # consecutive down days: count k such that close[prev_idx-i] < open[prev_idx-i] for i=0..k-1
    cdc = 0
    j = prev_idx
    while j >= 0 and closes[j] < opens[j]:
        cdc += 1
        j -= 1
    out["consecutive_down_days"] = float(cdc)

    # prev day change
    if prev_idx >= 1:
        out["prev_day_change"] = float((closes[prev_idx] - closes[prev_idx - 1]) / closes[prev_idx - 1])
    else:
        out["prev_day_change"] = float("nan")

    # prev 2d
    if prev_idx >= 2:
        out["prev_2d_change"] = float((closes[prev_idx] - closes[prev_idx - 2]) / closes[prev_idx - 2])
    else:
        out["prev_2d_change"] = float("nan")

    # daily ATR (14d) -> price-relative
    atr_14 = pd.Series(closes).diff().abs().rolling(14).mean()
    if prev_idx >= 14:
        atr_pct = atr_14.iloc[prev_idx] / closes[prev_idx]
    else:
        atr_pct = np.nan
    gap = float(row.get("gap_pct", np.nan))
    if not np.isnan(atr_pct) and atr_pct > 0:
        out["gap_size_relative_to_atr"] = gap / atr_pct
    else:
        out["gap_size_relative_to_atr"] = np.nan

    # day of week
    dow = ts.tz_convert("America/New_York").day_of_week
    out["is_monday"] = float(dow == 0)
    out["is_friday"] = float(dow == 4)
    out["day_of_month"] = float(ts.tz_convert("America/New_York").day)

    # VIX proxy = SPY 14d daily ATR / SPY price
    spy_dates = list(spy_daily.index.tz_convert("America/New_York").date) if spy_daily.index.tz is not None else list(spy_daily.index.date)
    spy_idx = bisect.bisect_left(spy_dates, ny_date) - 1
    if spy_idx >= 14:
        spy_close = spy_daily["close"].iloc[spy_idx]
        spy_atr14 = spy_daily["close"].diff().abs().rolling(14).mean().iloc[spy_idx]
        out["vix_proxy"] = float(spy_atr14 / spy_close) if spy_close > 0 else float("nan")
    else:
        out["vix_proxy"] = float("nan")

    # SPY 5d change
    if spy_idx >= 5:
        out["spy_5d_change"] = float((spy_daily["close"].iloc[spy_idx] - spy_daily["close"].iloc[spy_idx - 5]) / spy_daily["close"].iloc[spy_idx - 5])
    else:
        out["spy_5d_change"] = float("nan")

    # XLK relative strength = XLK 5d change - SPY 5d change
    xlk_dates = list(xlk_daily.index.tz_convert("America/New_York").date) if xlk_daily.index.tz is not None else list(xlk_daily.index.date)
    xlk_idx = bisect.bisect_left(xlk_dates, ny_date) - 1
    if xlk_idx >= 5 and not np.isnan(out.get("spy_5d_change", float("nan"))):
        xlk_5d = (xlk_daily["close"].iloc[xlk_idx] - xlk_daily["close"].iloc[xlk_idx - 5]) / xlk_daily["close"].iloc[xlk_idx - 5]
        out["xlk_relative_strength"] = float(xlk_5d - out["spy_5d_change"])
    else:
        out["xlk_relative_strength"] = float("nan")

    return out


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    dataset_path = project_root / "phase0" / "pattern_discovery_dataset.parquet"
    cache_dir = project_root / "data" / "prices"
    out_dir = project_root / "phase0"

    period_start = datetime(2024, 5, 1, tzinfo=timezone.utc)
    period_end = datetime(2026, 5, 1, tzinfo=timezone.utc)

    df = pd.read_parquet(dataset_path)
    gf = df[df["strategy"] == "gap_fill"].copy().reset_index(drop=True)
    print(f"gap_fill candidates: {len(gf)}")
    print(f"  WR: {gf['win'].mean():.3f}")
    print(f"  avg P&L: {gf['pnl_pct'].mean()*100:+.3f}%")

    # Load all daily bars + SPY/XLK daily for new features
    daily_by_symbol: dict = {}
    for sym in ["SPY", "QQQ", "IWM", "DIA", "XLK"]:
        try:
            daily_by_symbol[sym] = _load(cache_dir, sym, "1day", period_start, period_end)
        except FileNotFoundError:
            print(f"WARNING: daily file for {sym} not found, skipping")

    spy_daily = daily_by_symbol["SPY"]
    xlk_daily = daily_by_symbol["XLK"]

    # Compute new features
    new_feats_rows = []
    for _, row in gf.iterrows():
        new_feats_rows.append(_new_features_for_row(row, daily_by_symbol, spy_daily, xlk_daily))
    new_feats_df = pd.DataFrame(new_feats_rows)
    gf_aug = pd.concat([gf.reset_index(drop=True), new_feats_df], axis=1)
    print(f"augmented with {new_feats_df.shape[1]} new features")

    OLD_FEATS = [
        "rsi_14", "bb_pct_b", "vwap_dev", "volume_ratio", "intraday_change",
        "gap_pct", "daily_ma_distance", "daily_5d_return", "daily_20d_return",
        "atr_ratio_5min", "spy_intraday", "score_value", "ny_hour", "day_of_week",
    ]
    NEW_FEATS = list(new_feats_df.columns)
    ALL_FEATS = OLD_FEATS + NEW_FEATS

    # For each feature, top quartile vs bottom quartile WR comparison
    rows = []
    for feat in ALL_FEATS:
        if feat not in gf_aug.columns:
            continue
        vals = gf_aug[feat].dropna()
        if len(vals) < 50:
            continue
        q1 = vals.quantile(0.25)
        q3 = vals.quantile(0.75)
        bot = gf_aug[gf_aug[feat] <= q1]
        top = gf_aug[gf_aug[feat] >= q3]
        if len(bot) < 15 or len(top) < 15:
            continue
        bot_wr = bot["win"].mean()
        top_wr = top["win"].mean()
        bot_pnl = bot["pnl_pct"].mean() * 100
        top_pnl = top["pnl_pct"].mean() * 100
        # Mann-Whitney U on the 0/1 win label
        try:
            u_stat, pval = stats.mannwhitneyu(top["win"], bot["win"], alternative="two-sided")
        except Exception:
            pval = 1.0
        rows.append({
            "feature": feat,
            "n_top": len(top), "top_wr": top_wr, "top_pnl_pct": top_pnl,
            "n_bot": len(bot), "bot_wr": bot_wr, "bot_pnl_pct": bot_pnl,
            "wr_diff": top_wr - bot_wr,
            "pnl_diff": top_pnl - bot_pnl,
            "p_value": float(pval),
        })
    table = pd.DataFrame(rows)
    table["abs_wr_diff"] = table["wr_diff"].abs()
    table = table.sort_values("abs_wr_diff", ascending=False)

    # Report
    md = []
    md.append("# P4: gap_fill Winners vs Losers Deep Dive")
    md.append("")
    md.append(f"**Sample:** {len(gf)} gap_fill candidates (all 5 ETFs × 3 thresholds)")
    md.append(f"**Baseline WR:** {gf['win'].mean():.3f}, baseline P&L: {gf['pnl_pct'].mean()*100:+.3f}%")
    md.append("")
    md.append("Each feature's top quartile (q4) vs bottom quartile (q1) WR difference. Larger absolute difference = more discriminative.")
    md.append("")

    md.append("## Top 10 most-discriminating features (by |WR top − WR bot|)")
    md.append("")
    md.append("| Feature | n_bot / WR_bot / P&L_bot | n_top / WR_top / P&L_top | WR diff | P&L diff | p-value |")
    md.append("|---------|---------------------------|---------------------------|---------|----------|---------|")
    for _, r in table.head(10).iterrows():
        md.append(
            f"| {r['feature']} | "
            f"{r['n_bot']} / {r['bot_wr']:.3f} / {r['bot_pnl_pct']:+.3f}% | "
            f"{r['n_top']} / {r['top_wr']:.3f} / {r['top_pnl_pct']:+.3f}% | "
            f"{r['wr_diff']:+.3f} | {r['pnl_diff']:+.3f}% | {r['p_value']:.3f} |"
        )
    md.append("")

    # Top 3 detailed quintile breakdown
    md.append("## Top 3 features — quintile breakdown")
    md.append("")
    for feat in table.head(3)["feature"].tolist():
        vals = gf_aug[feat].dropna()
        edges = list(vals.quantile([0, 0.2, 0.4, 0.6, 0.8, 1.0]).unique())
        if len(edges) < 3:
            continue
        labels = [f"q{i+1}" for i in range(len(edges) - 1)]
        gf_aug[f"_bk_{feat}"] = pd.cut(gf_aug[feat], bins=edges, labels=labels, include_lowest=True).astype(str)
        md.append(f"### {feat}")
        md.append("")
        md.append("| Quintile | Range | n | WR | Avg P&L |")
        md.append("|----------|-------|---|-----|---------|")
        for lbl in labels:
            sub = gf_aug[gf_aug[f"_bk_{feat}"] == lbl]
            if len(sub) == 0:
                continue
            md.append(
                f"| {lbl} | — | {len(sub)} | {sub['win'].mean():.3f} | {sub['pnl_pct'].mean()*100:+.3f}% |"
            )
        md.append("")

    # Honest verdict
    sig = table[(table["abs_wr_diff"] > 0.1) & (table["p_value"] < 0.10)]
    md.append("## Verdict")
    md.append("")
    md.append(f"Features with |WR diff| > 0.10 AND p < 0.10: **{len(sig)}**")
    md.append("")
    if len(sig) == 0:
        md.append("**No new feature provides statistically significant gap_fill winner-vs-loser separation.**")
        md.append("")
        md.append("This is consistent with the broader finding: at the per-trade decision level, the available features (price action + simple regime indicators) do not predict gap_fill outcomes beyond the baseline 60% WR. The gap_fill edge appears to come from selecting the LARGE GAP DAYS THEMSELVES (gap_pct threshold) rather than any further conditioning.")
    else:
        md.append("Statistically significant features:")
        md.append("")
        for _, r in sig.iterrows():
            md.append(
                f"- `{r['feature']}`: top q WR {r['top_wr']:.3f} vs bot q WR {r['bot_wr']:.3f} (diff {r['wr_diff']:+.3f}, p={r['p_value']:.3f})"
            )

    md_path = out_dir / "p4_gap_fill_deep_dive.md"
    md_path.write_text("\n".join(md), encoding="utf-8")
    print(f"[saved] {md_path}")
    print(f"  features with |WR diff|>0.1 AND p<0.10: {len(sig)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
