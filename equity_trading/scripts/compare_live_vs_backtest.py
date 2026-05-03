"""Compare live paper-trading results to backtest expectations.

Reads data/trades.sqlite, groups by (strategy, symbol), computes WR and avg pnl%
with bootstrap 95% CI, compares to expected values from train data, and emits
a markdown report with per-row decision tags.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


N_BOOT = 1000
MIN_N = 30


def _bootstrap_ci(values: np.ndarray, stat_fn, n_boot: int, rng: np.random.Generator
                   ) -> tuple[float, float]:
    samples = np.empty(n_boot)
    n = len(values)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        samples[i] = stat_fn(values[idx])
    lo = float(np.quantile(samples, 0.025))
    hi = float(np.quantile(samples, 0.975))
    return lo, hi


def compare(*, db_path: Path | str, since: str,
             expected: dict[tuple[str, str], dict[str, float]],
             seed: int = 42) -> list[dict]:
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        "SELECT entry_ts, exit_ts, symbol, strategy, entry_price, exit_price, "
        "realized_pnl_usd FROM positions WHERE exit_ts >= ?",
        conn, params=[since],
    )
    conn.close()
    rows: list[dict] = []
    rng = np.random.default_rng(seed)
    seen_pairs = set()

    if len(df) > 0:
        df["pnl_pct"] = (df["exit_price"] - df["entry_price"]) / df["entry_price"]
        for (strategy, symbol), grp in df.groupby(["strategy", "symbol"]):
            seen_pairs.add((strategy, symbol))
            n = len(grp)
            wins = (grp["pnl_pct"] > 0).sum()
            wr = wins / n if n > 0 else 0.0
            avg_pnl = grp["pnl_pct"].mean()
            if (strategy, symbol) not in expected:
                rows.append({
                    "strategy": strategy, "symbol": symbol, "n": int(n),
                    "wr": float(wr), "avg_pnl_pct": float(avg_pnl),
                    "wr_ci": (None, None), "avg_pnl_pct_ci": (None, None),
                    "expected_wr": None, "expected_avg_pnl_pct": None,
                    "decision": "UNEXPECTED_PAIR",
                })
                continue
            exp = expected[(strategy, symbol)]
            if n < MIN_N:
                decision = "INSUFFICIENT_SAMPLE"
                wr_ci = (None, None)
                avg_ci = (None, None)
            else:
                pnls = grp["pnl_pct"].to_numpy()
                wr_ci = _bootstrap_ci(pnls, lambda v: float((v > 0).mean()), N_BOOT, rng)
                avg_ci = _bootstrap_ci(pnls, lambda v: float(v.mean()), N_BOOT, rng)
                if avg_ci[1] < exp["avg_pnl_pct"]:
                    decision = "DIVERGENCE_AVG"
                elif abs(wr - exp["wr"]) > 0.10:
                    decision = "DIVERGENCE_WR"
                else:
                    decision = "WITHIN_EXPECTATION"
            rows.append({
                "strategy": strategy, "symbol": symbol, "n": int(n),
                "wr": float(wr), "avg_pnl_pct": float(avg_pnl),
                "wr_ci": wr_ci, "avg_pnl_pct_ci": avg_ci,
                "expected_wr": float(exp["wr"]),
                "expected_avg_pnl_pct": float(exp["avg_pnl_pct"]),
                "decision": decision,
            })

    # Pairs in expected but never traded: flag as INSUFFICIENT_SAMPLE n=0
    for pair in expected:
        if pair not in seen_pairs:
            rows.append({
                "strategy": pair[0], "symbol": pair[1], "n": 0,
                "wr": 0.0, "avg_pnl_pct": 0.0,
                "wr_ci": (None, None), "avg_pnl_pct_ci": (None, None),
                "expected_wr": expected[pair]["wr"],
                "expected_avg_pnl_pct": expected[pair]["avg_pnl_pct"],
                "decision": "INSUFFICIENT_SAMPLE",
            })
    return rows


def render_md(rows: list[dict], variant_id: str, period_label: str, total_n: int) -> str:
    parts = [f"# Live vs Backtest Comparison\n",
              f"**Variant**: {variant_id}  **Period**: {period_label}  **Total live trades**: {total_n}\n",
              "## By strategy x symbol\n",
              "| strat x sym | n | live WR | live avg | expected WR | expected avg | decision |",
              "|---|---:|---:|---:|---:|---:|---|"]
    for r in rows:
        wr_str = f"{r['wr']:.2f}" if r["wr_ci"][0] is None else f"{r['wr']:.2f} [{r['wr_ci'][0]:.2f}, {r['wr_ci'][1]:.2f}]"
        avg_str = f"{r['avg_pnl_pct']*100:+.2f}%" if r["avg_pnl_pct_ci"][0] is None else (
            f"{r['avg_pnl_pct']*100:+.2f}% [{r['avg_pnl_pct_ci'][0]*100:+.2f}, {r['avg_pnl_pct_ci'][1]*100:+.2f}]%"
        )
        exp_wr = f"{r['expected_wr']:.2f}" if r["expected_wr"] is not None else "-"
        exp_avg = f"{r['expected_avg_pnl_pct']*100:+.2f}%" if r["expected_avg_pnl_pct"] is not None else "-"
        parts.append(f"| {r['strategy']} x {r['symbol']} | {r['n']} | {wr_str} | {avg_str} | "
                      f"{exp_wr} | {exp_avg} | {r['decision']} |")
    parts.append("")
    return "\n".join(parts)


def _compute_expected(variant_path: Path, train_root: Path) -> dict[tuple[str, str], dict[str, float]]:
    from equity_trading.src.validation.config import load_variant_config
    from equity_trading.src.validation.data import load_train_bars
    from equity_trading.src.phase0.atr_analyzer import analyze_atr_distribution
    from equity_trading.src.phase0.strategy_simulator import simulate_strategy
    cfg = load_variant_config(variant_path)
    expected = {}
    for entry in cfg.strategies:
        cls = cfg.resolve_strategy_class(entry["class"])
        for symbol in entry["symbols"]:
            bars = load_train_bars(train_root, symbol, timeframe_minutes=5)
            daily = load_train_bars(train_root, symbol, timeframe_minutes=1440)
            atr = analyze_atr_distribution(bars, period=14)["median_pct"]
            params = dict(entry["params"])
            params["_daily"] = daily
            cost = params.pop("cost_pct", 0.10)
            cat_stop = params.pop("catastrophic_stop_pct", None)
            summary, _ = simulate_strategy(
                strategy=cls(), bars_5min=bars, daily=daily, atr_pct=atr,
                params=params, cost_pct=cost,
                catastrophic_stop_pct=cat_stop, return_trades=True,
            )
            wr = summary.get("win_rate", 0.0)
            avg = summary.get("avg_pnl_pct", 0.0) / 100.0  # back to fraction
            expected[(cls.__name__, symbol)] = {"wr": float(wr), "avg_pnl_pct": float(avg)}
    return expected


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--variant", type=Path, required=True)
    p.add_argument("--db", type=Path, default=Path("equity_trading/data/trades.sqlite"))
    p.add_argument("--train-root", type=Path, default=Path("equity_trading/data/prices"))
    p.add_argument("--since", default=None)
    p.add_argument("--output", type=Path, default=None)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args(argv)


def _next_day_str(date_str: str) -> str:
    return (datetime.fromisoformat(date_str) + pd.Timedelta(days=1)).date().isoformat()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    from equity_trading.src.validation.config import load_variant_config
    cfg = load_variant_config(args.variant)
    since = args.since or _next_day_str(cfg.gates["oos"]["holdout_end"])
    expected = _compute_expected(args.variant, args.train_root)
    rows = compare(db_path=args.db, since=since, expected=expected, seed=args.seed)
    total_n = sum(r["n"] for r in rows)
    period = f"{since} -> today"
    md = render_md(rows, cfg.variant_id, period, total_n)
    if args.output is None:
        out = Path("equity_trading/phase0") / f"live_vs_backtest_{datetime.now(timezone.utc).date()}.md"
    else:
        out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md)
    print(f"[saved] {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
