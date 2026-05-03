"""Gate 4: stress_test — train-data window slicing.

Runs the variant + baseline against hardcoded historical stress windows
(e.g. COVID 2020, 2022 hike cycle) using train data only, and FAILs if
the variant's worst trade or MaxDD exceeds the per-window limits or if
variant DD exceeds 1.3x baseline DD.

Opt-in via `gates.stress_test.enabled: true` in variant config.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from equity_trading.src.phase0.atr_analyzer import analyze_atr_distribution
from equity_trading.src.phase0.strategy_simulator import simulate_strategy
from equity_trading.src.validation.data import load_train_bars
from equity_trading.src.validation.gates.base import GateResult, Status

if TYPE_CHECKING:
    from equity_trading.src.validation.config import VariantConfig


def run_stress_test_gate_from_summaries(
    windows: list[dict],
    variant_summaries: list[dict],
    baseline_summaries: list[dict],
) -> GateResult:
    """Pure-summary gate. Each window dict requires `name`,
    `max_dd_limit_pct`, `worst_trade_limit_pct`. Each summary requires
    `annualized_pct`, `max_dd_pct`, `worst_trade_pct`."""
    if not windows:
        return GateResult(
            name="stress_test", status=Status.WARN,
            summary="no windows configured",
            detail_md="### Gate 4: Stress test ⚠️\n\nno windows configured\n",
        )
    failures: list[str] = []
    rows: list[str] = []
    for w, v, b in zip(windows, variant_summaries, baseline_summaries):
        v_dd = abs(v["max_dd_pct"])
        b_dd = abs(b["max_dd_pct"])
        v_worst = abs(v["worst_trade_pct"])
        ok = True
        if v_dd > w["max_dd_limit_pct"]:
            failures.append(f"{w['name']}: MaxDD {v_dd:.2f}% > limit {w['max_dd_limit_pct']:.1f}%")
            ok = False
        if v_worst > w["worst_trade_limit_pct"]:
            failures.append(f"{w['name']}: worst trade {v_worst:.2f}% > limit {w['worst_trade_limit_pct']:.1f}%")
            ok = False
        if v_dd > b_dd * 1.3:
            failures.append(f"{w['name']}: variant DD {v_dd:.2f}% > 1.3x baseline {b_dd:.2f}%")
            ok = False
        rows.append(
            f"| {w['name']} | {v['annualized_pct']:+.2f}% | -{v_dd:.2f}% | -{b_dd:.2f}% | "
            f"-{v_worst:.2f}% | {'✅' if ok else '❌'} |"
        )
    status = Status.FAIL if failures else Status.PASS
    summary = "; ".join(failures) if failures else f"{len(windows)} stress windows passed"
    detail = (
        f"### Gate 4: Stress test {status.icon}\n\n"
        f"| window | variant ann | variant DD | baseline DD | worst trade | result |\n"
        f"|---|---:|---:|---:|---:|:---:|\n"
        + "\n".join(rows) + "\n\n" + summary + "\n"
    )
    return GateResult(name="stress_test", status=status, summary=summary,
                       detail_md=detail, metrics={"failures": len(failures)})


def _simulate_window(cfg: "VariantConfig", train_root: Path, window: dict) -> dict:
    """Simulate one variant on one stress window using train data."""
    start = pd.Timestamp(window["start"], tz="UTC")
    end = pd.Timestamp(window["end"], tz="UTC")
    daily_warmup_start = start - pd.Timedelta(days=365)
    all_pnl: list[float] = []
    n_trades = 0
    for entry in cfg.strategies:
        cls = cfg.resolve_strategy_class(entry["class"])
        for symbol in entry["symbols"]:
            bars_5min = load_train_bars(train_root, symbol, timeframe_minutes=5)
            daily = load_train_bars(train_root, symbol, timeframe_minutes=1440)
            bars_window = bars_5min.loc[start:end]
            daily_window = daily.loc[daily_warmup_start:end]
            if len(bars_window) == 0 or len(daily_window) == 0:
                continue
            atr = analyze_atr_distribution(bars_window, period=14)["median_pct"]
            params = dict(entry["params"])
            params["_daily"] = daily_window
            cost = params.pop("cost_pct", 0.10)
            cat_stop = params.pop("catastrophic_stop_pct", None)
            _, trades = simulate_strategy(
                strategy=cls(), bars_5min=bars_window, daily=daily_window, atr_pct=atr,
                params=params, cost_pct=cost,
                catastrophic_stop_pct=cat_stop, return_trades=True,
            )
            all_pnl.extend(trades["pnl_pct"].tolist())
            n_trades += len(trades)
    if not all_pnl:
        return {"annualized_pct": 0.0, "max_dd_pct": 0.0, "sharpe": 0.0,
                 "final_equity": 100000.0, "worst_trade_pct": 0.0, "trade_count": 0}
    equity = 100000.0
    eq_curve = [equity]
    size_pct = cfg.portfolio["position_size_pct"]
    for p in all_pnl:
        equity *= (1 + p * size_pct)
        eq_curve.append(equity)
    eq_series = pd.Series(eq_curve)
    rmax = eq_series.cummax()
    dd = float(((eq_series - rmax) / rmax * 100).min())
    days = max((end - start).days, 1)
    yrs = max(days / 365.25, 1e-9)
    ann = ((equity / 100000.0) ** (1 / yrs) - 1) * 100
    return {"annualized_pct": ann, "max_dd_pct": dd, "sharpe": 0.0,
             "final_equity": equity,
             "worst_trade_pct": min(all_pnl) * 100,
             "trade_count": n_trades}


def run_stress_test_gate(
    *,
    cfg: "VariantConfig",
    baseline_cfg: "VariantConfig",
    train_root: Path,
    stress_windows: list[dict],
) -> GateResult:
    if not stress_windows:
        return run_stress_test_gate_from_summaries([], [], [])
    v_summaries = [_simulate_window(cfg, train_root, w) for w in stress_windows]
    b_summaries = [_simulate_window(baseline_cfg, train_root, w) for w in stress_windows]
    return run_stress_test_gate_from_summaries(stress_windows, v_summaries, b_summaries)
