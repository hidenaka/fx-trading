"""Portfolio runner: consumes a VariantConfig + EvaluationContext, returns
(summary, trades, equity_curve). Re-uses simulate_strategy from phase0.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from equity_trading.src.phase0.atr_analyzer import analyze_atr_distribution
from equity_trading.src.phase0.strategy_simulator import simulate_strategy
from equity_trading.src.validation.config import VariantConfig
from equity_trading.src.validation.data import EvaluationContext


def _collect_trades(cfg: VariantConfig, ctx: EvaluationContext) -> pd.DataFrame:
    out: list[pd.DataFrame] = []
    holdout_start = pd.Timestamp(cfg.gates["oos"]["holdout_start"], tz="UTC")
    for entry in cfg.strategies:
        cls = cfg.resolve_strategy_class(entry["class"])
        for symbol in entry["symbols"]:
            bars_5min = ctx.load_holdout_bars(symbol, timeframe_minutes=5)
            daily = ctx.load_holdout_bars(symbol, timeframe_minutes=1440)
            atr = analyze_atr_distribution(bars_5min, period=14)["median_pct"]
            params = dict(entry["params"])
            params["_daily"] = daily
            cost = params.pop("cost_pct", 0.10)
            _, trades = simulate_strategy(
                strategy=cls(), bars_5min=bars_5min, daily=daily, atr_pct=atr,
                params=params, cost_pct=cost, return_trades=True,
            )
            if len(trades) > 0:
                trades = trades.copy()
                trades["symbol"] = symbol
                trades["strategy_label"] = f"{cls.__name__}_{symbol}"
                out.append(trades)
    if not out:
        return pd.DataFrame(columns=["entry_ts", "exit_ts", "pnl_pct", "symbol", "strategy_label"])
    df = pd.concat(out, ignore_index=True)
    df["entry_ts"] = pd.to_datetime(df["entry_ts"], utc=True)
    df["exit_ts"] = pd.to_datetime(df["exit_ts"], utc=True)
    df = df[df["entry_ts"] >= holdout_start]
    df = df.drop_duplicates(subset=["symbol", "entry_ts"], keep="first")
    return df.sort_values("entry_ts").reset_index(drop=True)


def _simulate_portfolio(
    trades: pd.DataFrame, starting_equity: float,
    position_size_pct: float, max_concurrent: int,
) -> tuple[dict, pd.DataFrame]:
    if len(trades) == 0:
        return {"annualized_pct": 0.0, "max_dd_pct": 0.0, "sharpe": 0.0,
                "final_equity": starting_equity}, pd.DataFrame(columns=["ts", "equity"])
    equity = starting_equity
    open_pos: list[dict] = []
    eq_curve = [(trades["entry_ts"].iloc[0] - pd.Timedelta(seconds=1), equity)]
    for _, t in trades.iterrows():
        still = []
        for p in open_pos:
            if p["exit_ts"] <= t["entry_ts"]:
                equity += p["dollars"] * p["pnl_pct"]
                eq_curve.append((p["exit_ts"], equity))
            else:
                still.append(p)
        open_pos[:] = still
        if len(open_pos) >= max_concurrent or any(p["symbol"] == t["symbol"] for p in open_pos):
            continue
        open_pos.append({"symbol": t["symbol"], "exit_ts": t["exit_ts"],
                          "dollars": equity * position_size_pct, "pnl_pct": t["pnl_pct"]})
    final_close = trades["exit_ts"].max() + pd.Timedelta(seconds=1)
    for p in open_pos:
        equity += p["dollars"] * p["pnl_pct"]
        eq_curve.append((p["exit_ts"], equity))
    eq_df = pd.DataFrame(eq_curve, columns=["ts", "equity"]).sort_values("ts").reset_index(drop=True)
    eq_df = eq_df.drop_duplicates("ts", keep="last")

    rmax = eq_df["equity"].cummax()
    dd = (eq_df["equity"] - rmax) / rmax
    max_dd = float(abs(dd.min() * 100)) if len(dd) > 0 else 0.0

    days = (eq_df["ts"].iloc[-1] - eq_df["ts"].iloc[0]).total_seconds() / 86400
    yrs = max(days / 365.25, 1e-9)
    ann = (math.pow(equity / starting_equity, 1 / yrs) - 1) * 100

    daily_rets = trades["pnl_pct"].to_numpy()
    sharpe = (daily_rets.mean() / daily_rets.std() * math.sqrt(252)) if daily_rets.std() > 0 else 0.0

    summary = {"annualized_pct": ann, "max_dd_pct": -max_dd, "sharpe": float(sharpe),
                "final_equity": equity}
    return summary, eq_df


def run_holdout_simulation(
    cfg: VariantConfig, ctx: EvaluationContext,
) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    trades = _collect_trades(cfg, ctx)
    summary, equity_curve = _simulate_portfolio(
        trades=trades,
        starting_equity=cfg.portfolio["starting_equity_usd"],
        position_size_pct=cfg.portfolio["position_size_pct"],
        max_concurrent=cfg.portfolio["max_concurrent"],
    )
    return summary, trades, equity_curve


from equity_trading.src.validation import internal_split as _internal_split
from equity_trading.src.validation.internal_split import VALID2_START


def _collect_trades_from_split(
    cfg: VariantConfig,
    root,
    partition: str,
    *,
    vix_daily: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """partition: 'train2' or 'valid2'. Reads from train/ via internal_split.
    Filters trades whose entry_ts falls outside the partition window so
    warmup-period signals are not counted. vix_daily, if provided, is
    injected into each strategy's params as '_vix_daily' (consumed by
    strategies with vix_halve_threshold set)."""
    if partition == "train2":
        load_bars = _internal_split.load_train2_bars
        window_start = pd.Timestamp("2019-05-01", tz="UTC")
    elif partition == "valid2":
        load_bars = _internal_split.load_valid2_bars
        window_start = pd.Timestamp(VALID2_START, tz="UTC")
    else:
        raise ValueError(f"Unknown partition: {partition!r}")

    out: list[pd.DataFrame] = []
    for entry in cfg.strategies:
        cls = cfg.resolve_strategy_class(entry["class"])
        for symbol in entry["symbols"]:
            bars_5min = load_bars(root, symbol, timeframe_minutes=5)
            daily = load_bars(root, symbol, timeframe_minutes=1440)
            atr = analyze_atr_distribution(bars_5min, period=14)["median_pct"] if len(bars_5min) > 0 else 0.0
            params = dict(entry["params"])
            params["_daily"] = daily
            if vix_daily is not None:
                params["_vix_daily"] = vix_daily
            cost = params.pop("cost_pct", 0.10)
            cat_stop = params.pop("catastrophic_stop_pct", None)
            _, trades = simulate_strategy(
                strategy=cls(), bars_5min=bars_5min, daily=daily, atr_pct=atr,
                params=params, cost_pct=cost,
                catastrophic_stop_pct=cat_stop, return_trades=True,
            )
            if len(trades) > 0:
                trades = trades.copy()
                trades["symbol"] = symbol
                trades["strategy_label"] = f"{cls.__name__}_{symbol}"
                out.append(trades)
    if not out:
        return pd.DataFrame(columns=["entry_ts", "exit_ts", "pnl_pct", "symbol", "strategy_label"])
    df = pd.concat(out, ignore_index=True)
    df["entry_ts"] = pd.to_datetime(df["entry_ts"], utc=True)
    df["exit_ts"] = pd.to_datetime(df["exit_ts"], utc=True)
    df = df[df["entry_ts"] >= window_start]
    df = df.drop_duplicates(subset=["symbol", "entry_ts"], keep="first")
    return df.sort_values("entry_ts").reset_index(drop=True)
