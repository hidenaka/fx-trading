"""Real-data ML pipeline driver: candidate → label → walk-forward → filtered comparison."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

from equity_trading.src.ml.candidate_dataset import generate_candidates
from equity_trading.src.ml.outcome_labeler import label_candidates
from equity_trading.src.ml.walk_forward import walk_forward_splits
from equity_trading.src.phase0.strategy_simulator import simulate_strategy
from equity_trading.src.strategy.strategies.gap_fill import GapFillStrategy
from equity_trading.src.strategy.strategies.mean_reversion import MeanReversionStrategy


ENTRIES = [
    ("SPY", "gap_fill",
     {"gap_threshold": 0.0015, "stop_extension": 0.005},
     {"gap_threshold": 0.003,  "stop_extension": 0.005}),
    ("QQQ", "gap_fill",
     {"gap_threshold": 0.0025, "stop_extension": 0.005},
     {"gap_threshold": 0.005,  "stop_extension": 0.005}),
    ("IWM", "gap_fill",
     {"gap_threshold": 0.005,  "stop_extension": 0.010},
     {"gap_threshold": 0.010,  "stop_extension": 0.010}),
    ("XLK", "gap_fill",
     {"gap_threshold": 0.0025, "stop_extension": 0.005},
     {"gap_threshold": 0.005,  "stop_extension": 0.005}),
    ("XLK", "mean_reversion",
     {"threshold": 0.20},
     {"threshold": 0.40}),
]

FEATURE_NAMES = [
    "ny_hour", "day_of_week", "rsi_14", "bb_pct_b", "vwap_dev",
    "volume_ratio", "intraday_change", "gap_pct", "daily_ma_distance",
    "daily_5d_return", "daily_20d_return", "atr_ratio_5min",
    "spy_intraday", "bars_since_open", "score_value",
]

ATR_PCT = {"SPY": 0.061, "QQQ": 0.083, "IWM": 0.096, "XLK": 0.129}


def _load_cached_bars(cache_dir: Path, symbol: str, timeframe: str,
                      start: datetime, end: datetime) -> pd.DataFrame:
    s = start.strftime("%Y-%m-%dT%H%M")
    e = end.strftime("%Y-%m-%dT%H%M")
    path = cache_dir / f"{symbol}_{timeframe}_{s}_{e}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Cached file missing: {path}")
    return pd.read_parquet(path)


def _strict_baseline(strategy_name, symbol, bars_5min, daily, strict_params, atr_pct):
    """Run simulator with strict params to get baseline trades."""
    if strategy_name == "gap_fill":
        s = GapFillStrategy()
    else:
        s = MeanReversionStrategy()
    params = dict(strict_params)
    if strategy_name == "gap_fill":
        params["_daily"] = daily
    summary, trades = simulate_strategy(
        strategy=s, bars_5min=bars_5min, daily=daily, atr_pct=atr_pct,
        params=params, return_trades=True,
    )
    return summary, trades


def _aggregate_filtered(labeled, oof_preds, threshold):
    kept = [lc for lc, p in zip(labeled, oof_preds)
            if not np.isnan(p) and p >= threshold]
    if not kept:
        return {"n": 0, "wr": float("nan"), "total_pnl_pct": 0.0,
                "avg_pnl_pct": float("nan")}
    n = len(kept)
    wins = sum(1 for lc in kept if lc.win)
    pnls_pct = np.array([lc.pnl_pct * 100 for lc in kept])
    return {
        "n": n,
        "wr": wins / n,
        "total_pnl_pct": float(pnls_pct.sum()),
        "avg_pnl_pct": float(pnls_pct.mean()),
    }


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    cache_dir = project_root / "data" / "prices"
    output_dir = project_root / "phase0"
    output_dir.mkdir(parents=True, exist_ok=True)

    period_start = datetime(2024, 5, 1, tzinfo=timezone.utc)
    period_end = datetime(2026, 5, 1, tzinfo=timezone.utc)

    spy_5min = _load_cached_bars(cache_dir, "SPY", "5min", period_start, period_end)

    rows_for_report: list[dict] = []
    all_oof: list[dict] = []

    for symbol, strategy_name, loose_params, strict_params in ENTRIES:
        print(f"\n=== {symbol} {strategy_name} ===")
        bars = _load_cached_bars(cache_dir, symbol, "5min", period_start, period_end)
        daily = _load_cached_bars(cache_dir, symbol, "1day", period_start, period_end)
        atr = ATR_PCT[symbol]

        # 1) Strict baseline
        strict_summary, strict_trades = _strict_baseline(
            strategy_name, symbol, bars, daily, strict_params, atr,
        )
        print(f"  strict: n={strict_summary['trade_count']} "
              f"wr={strict_summary.get('win_rate', 'nan')} "
              f"avg={strict_summary.get('avg_pnl_pct', 'nan')}")

        # 2) Loose candidates
        candidates = generate_candidates(
            bars_5min=bars, daily=daily, spy_5min=spy_5min,
            symbol=symbol, strategy_name=strategy_name,
            relaxed_params=loose_params,
        )
        labeled = label_candidates(
            candidates=candidates, bars_5min=bars, daily=daily,
            atr_pct=atr, base_params=loose_params,
        )
        n_loose = len(labeled)
        wr_loose = float(np.mean([lc.win for lc in labeled])) if labeled else float("nan")
        total_pnl_loose_pct = float(sum(lc.pnl_pct * 100 for lc in labeled))
        print(f"  loose: n={n_loose} wr={wr_loose:.3f} total_pnl={total_pnl_loose_pct:.2f}%")

        if n_loose < 60:
            print(f"  [skip ML]: {n_loose} labeled candidates is below 60-sample threshold for ML training")
            strict_n = strict_summary["trade_count"]
            strict_wr = strict_summary.get("win_rate", float("nan"))
            strict_avg = strict_summary.get("avg_pnl_pct", float("nan"))
            if isinstance(strict_avg, float) and np.isnan(strict_avg):
                strict_total_pnl = 0.0
            else:
                strict_total_pnl = strict_avg * strict_n

            rows_for_report.append({
                "symbol": symbol, "strategy": strategy_name,
                "strict_n": strict_n,
                "strict_wr": strict_wr,
                "strict_total_pnl_pct": strict_total_pnl,
                "loose_n": n_loose, "loose_wr": wr_loose,
                "loose_total_pnl_pct": total_pnl_loose_pct,
                "ml_p50_n": 0, "ml_p50_wr": float("nan"), "ml_p50_total_pnl_pct": 0.0,
                "ml_p60_n": 0, "ml_p60_wr": float("nan"), "ml_p60_total_pnl_pct": 0.0,
                "ml_p70_n": 0, "ml_p70_wr": float("nan"), "ml_p70_total_pnl_pct": 0.0,
                "n_folds": 0, "mean_auc": float("nan"),
            })
            continue

        # 3) Walk-forward
        timestamps = [lc.signal.timestamp for lc in labeled]
        splits = walk_forward_splits(
            timestamps=timestamps,
            train_window_days=180, test_window_days=30,
            step_days=30, purge_gap_days=1,
        )
        print(f"  splits: {len(splits)}")

        oof_preds = np.full(len(labeled), np.nan)
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.metrics import roc_auc_score
        aucs = []
        for split in splits:
            if len(split.train_indices) < 30 or len(split.test_indices) < 10:
                continue
            X_train = np.array([
                [labeled[i].signal.features.get(fn, 0.0) for fn in FEATURE_NAMES]
                for i in split.train_indices
            ], dtype=float)
            X_train = np.nan_to_num(X_train, nan=0.0)
            y_train = np.array([labeled[i].win for i in split.train_indices], dtype=int)
            if len(np.unique(y_train)) < 2:
                continue
            X_test = np.array([
                [labeled[i].signal.features.get(fn, 0.0) for fn in FEATURE_NAMES]
                for i in split.test_indices
            ], dtype=float)
            X_test = np.nan_to_num(X_test, nan=0.0)
            y_test = np.array([labeled[i].win for i in split.test_indices], dtype=int)

            model = GradientBoostingClassifier(
                n_estimators=50, max_depth=3, learning_rate=0.05, random_state=42,
            )
            model.fit(X_train, y_train)
            p = model.predict_proba(X_test)[:, 1]
            for ti, pi in zip(split.test_indices, p):
                oof_preds[ti] = pi
            try:
                aucs.append(float(roc_auc_score(y_test, p)))
            except ValueError:
                pass

        mean_auc = float(np.mean(aucs)) if aucs else float("nan")
        print(f"  mean AUC: {mean_auc:.3f}")

        # 4) Apply filter at multiple thresholds
        ml50 = _aggregate_filtered(labeled, oof_preds, 0.50)
        ml60 = _aggregate_filtered(labeled, oof_preds, 0.60)
        ml70 = _aggregate_filtered(labeled, oof_preds, 0.70)
        print(f"  p>=0.50: n={ml50['n']} wr={ml50['wr']:.3f} ev={ml50['total_pnl_pct']:.2f}")
        print(f"  p>=0.60: n={ml60['n']} wr={ml60['wr']:.3f} ev={ml60['total_pnl_pct']:.2f}")
        print(f"  p>=0.70: n={ml70['n']} wr={ml70['wr']:.3f} ev={ml70['total_pnl_pct']:.2f}")

        # 5) Save oof
        for lc, p in zip(labeled, oof_preds):
            all_oof.append({
                "symbol": symbol, "strategy": strategy_name,
                "timestamp": lc.signal.timestamp,
                "win": lc.win, "pnl_pct": lc.pnl_pct,
                "p_win_oof": p,
            })

        strict_n = strict_summary["trade_count"]
        strict_wr = strict_summary.get("win_rate", float("nan"))
        strict_avg = strict_summary.get("avg_pnl_pct", float("nan"))
        if isinstance(strict_avg, float) and np.isnan(strict_avg):
            strict_total_pnl = 0.0
        else:
            strict_total_pnl = strict_avg * strict_n

        rows_for_report.append({
            "symbol": symbol, "strategy": strategy_name,
            "strict_n": strict_n,
            "strict_wr": strict_wr,
            "strict_total_pnl_pct": strict_total_pnl,
            "loose_n": n_loose, "loose_wr": wr_loose,
            "loose_total_pnl_pct": total_pnl_loose_pct,
            "ml_p50_n": ml50["n"], "ml_p50_wr": ml50["wr"], "ml_p50_total_pnl_pct": ml50["total_pnl_pct"],
            "ml_p60_n": ml60["n"], "ml_p60_wr": ml60["wr"], "ml_p60_total_pnl_pct": ml60["total_pnl_pct"],
            "ml_p70_n": ml70["n"], "ml_p70_wr": ml70["wr"], "ml_p70_total_pnl_pct": ml70["total_pnl_pct"],
            "n_folds": len(splits), "mean_auc": mean_auc,
        })

    # Save oof predictions
    if all_oof:
        oof_df = pd.DataFrame(all_oof)
        oof_path = output_dir / "ml_oof_predictions.parquet"
        oof_df.to_parquet(oof_path)
        print(f"\n[saved] {oof_path}")

    # Build markdown report
    lines = []
    lines.append("# ML Phase 0 Evaluation Report")
    lines.append("")
    lines.append(f"**Period:** 2024-05-01 to 2026-05-01 (cached parquet)")
    lines.append(f"**Method:** Walk-forward (180d train / 30d test / 1d purge / 30d step), GBM (depth=3, lr=0.05, n_est=50)")
    lines.append("")
    lines.append("## ETF x Strategy Results")
    lines.append("")
    lines.append("| Symbol | Strategy | Strict n / WR / EV | Loose n / WR / EV | ML p>=0.5 n / WR / EV | ML p>=0.6 | ML p>=0.7 | AUC |")
    lines.append("|--------|----------|--------------------|--------------------|----------------------|----------|----------|-----|")

    def fmt(n, wr, ev):
        wr_s = f"{wr:.3f}" if not (isinstance(wr, float) and np.isnan(wr)) else "n/a"
        return f"{n}/{wr_s}/{ev:+.2f}"

    for r in rows_for_report:
        auc_s = f"{r['mean_auc']:.3f}" if not (isinstance(r['mean_auc'], float) and np.isnan(r['mean_auc'])) else "n/a"
        lines.append(
            f"| {r['symbol']} | {r['strategy']} | "
            f"{fmt(r['strict_n'], r['strict_wr'], r['strict_total_pnl_pct'])} | "
            f"{fmt(r['loose_n'], r['loose_wr'], r['loose_total_pnl_pct'])} | "
            f"{fmt(r['ml_p50_n'], r['ml_p50_wr'], r['ml_p50_total_pnl_pct'])} | "
            f"{fmt(r['ml_p60_n'], r['ml_p60_wr'], r['ml_p60_total_pnl_pct'])} | "
            f"{fmt(r['ml_p70_n'], r['ml_p70_wr'], r['ml_p70_total_pnl_pct'])} | "
            f"{auc_s} |"
        )
    lines.append("")

    # Aggregate row
    total_strict_ev = sum(r["strict_total_pnl_pct"] for r in rows_for_report)
    total_p50_ev = sum(r["ml_p50_total_pnl_pct"] for r in rows_for_report)
    total_p60_ev = sum(r["ml_p60_total_pnl_pct"] for r in rows_for_report)
    total_p70_ev = sum(r["ml_p70_total_pnl_pct"] for r in rows_for_report)
    lines.append("## Aggregate (5 ensembles total)")
    lines.append("")
    lines.append(f"- Strict baseline total EV: **{total_strict_ev:+.2f}%**")
    lines.append(f"- ML filter p>=0.50 total EV: **{total_p50_ev:+.2f}%**")
    lines.append(f"- ML filter p>=0.60 total EV: **{total_p60_ev:+.2f}%**")
    lines.append(f"- ML filter p>=0.70 total EV: **{total_p70_ev:+.2f}%**")
    lines.append("")

    # Verdict
    best_ml = max(total_p50_ev, total_p60_ev, total_p70_ev)
    if best_ml > total_strict_ev:
        lines.append(f"**Verdict:** ML filter improved aggregate EV ({total_strict_ev:+.2f} -> {best_ml:+.2f}). Worth deeper investigation in ML7.")
    else:
        lines.append(f"**Verdict:** ML filter did NOT beat strict baseline ({total_strict_ev:+.2f} vs best ML {best_ml:+.2f}). Hand-crafted thresholds were already near-optimal.")
    lines.append("")

    report_path = output_dir / "ml_evaluation_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[saved] {report_path}")
    print(f"\nVerdict: strict={total_strict_ev:+.2f}, best_ml={best_ml:+.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
