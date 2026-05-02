"""Portfolio simulator: combines multiple strategy trade lists into a single
$100k-account equity curve with realistic position sizing and overlap handling.

Picks top-EV strategies from comparison_report and simulates the portfolio
chronologically: every entry deploys `position_size_pct` of equity (capped
at `max_concurrent` simultaneous positions). PnL flows to equity. Bootstrap
for 95% CI on annualized return.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

from equity_trading.src.phase0.atr_analyzer import analyze_atr_distribution
from equity_trading.src.phase0.data_collector import collect_phase0_data
from equity_trading.src.phase0.strategy_simulator import simulate_strategy
from equity_trading.src.broker.alpaca_client import AlpacaClient
from equity_trading.src.config import load_config
from equity_trading.src.data.price_fetcher import PriceFetcher
from equity_trading.src.strategy.strategies.gap_fill import GapFillStrategy
from equity_trading.src.strategy.strategies.last_hour_momentum import LastHourMomentumStrategy
from equity_trading.src.strategy.strategies.opening_range_breakout import OpeningRangeBreakoutStrategy
from equity_trading.src.strategy.strategies.overnight_hold import OvernightHoldStrategy
from equity_trading.src.strategy.strategies.pre_fomc import PreFOMCDriftStrategy


# RTH-validated strategies (2019-05–2026-05, 78 bars/day, post-fix low/high stop modeling).
# Per-strategy cost_pct accounts for execution method:
#   - 0.10% (10 bps) for intraday market orders (gap_fill, ORB)
#   - 0.03% (3 bps)  for MOC + MOO auction fills (overnight_hold) — no spread on auctions
#   - 0.10% for pre-FOMC (intraday market orders both legs)
#
# Format: (StrategyClass, symbol, params, label, cost_pct)
SELECTED = [
    # ============= 敏腕モード: 3x leveraged ETFs =============
    # Pre-FOMC drift via 3x ETFs. TECL is the standout (VIX > 22 → WR 70%, avg +1.555%).
    (PreFOMCDriftStrategy,    "TECL", {"entry_bar_pos": 0, "_max_hold_bars": 130, "vix_min": 22}, "pre_fomc_TECL", 0.10),
    (PreFOMCDriftStrategy,    "UPRO", {"entry_bar_pos": 0, "_max_hold_bars": 130}, "pre_fomc_UPRO", 0.10),
    (PreFOMCDriftStrategy,    "UDOW", {"entry_bar_pos": 0, "_max_hold_bars": 130}, "pre_fomc_UDOW", 0.10),
    # ORB 60-min on 3x ETFs (massive EV due to amplified intraday moves)
    (OpeningRangeBreakoutStrategy, "TECL", {"or_window_bars": 12}, "orb_TECL", 0.10),
    (OpeningRangeBreakoutStrategy, "TQQQ", {"or_window_bars": 12}, "orb_TQQQ", 0.10),
    (OpeningRangeBreakoutStrategy, "TNA",  {"or_window_bars": 12}, "orb_TNA",  0.10),
    # Last-hour momentum on UPRO (only leveraged variant where LHM works)
    (LastHourMomentumStrategy, "UPRO", {"threshold": 0.003, "_max_hold_bars": 60}, "lhm_UPRO", 0.10),
    (LastHourMomentumStrategy, "UDOW", {"threshold": 0.003, "_max_hold_bars": 60}, "lhm_UDOW", 0.10),
]


def collect_all_trades(symbols: list[str], data_map, atr_map,
                       vix_daily: pd.DataFrame | None = None) -> pd.DataFrame:
    """Run each selected strategy with its per-strategy cost_pct and collect trades."""
    all_trades: list[pd.DataFrame] = []
    spy_5min = data_map.get(("SPY", 5))
    for entry in SELECTED:
        if len(entry) == 5:
            strat_cls, sym, params, label, cost_pct = entry
        else:
            strat_cls, sym, params, label = entry
            cost_pct = 0.10
        bars = data_map[(sym, 5)]
        daily = data_map[(sym, 1440)]
        atr = atr_map[sym]
        augmented = {**params, "_daily": daily}
        if spy_5min is not None:
            augmented["_spy_5min"] = spy_5min
        if vix_daily is not None:
            augmented["_vix_daily"] = vix_daily
        _, trades = simulate_strategy(
            strategy=strat_cls(),
            bars_5min=bars, daily=daily, atr_pct=atr,
            params=augmented, cost_pct=cost_pct, return_trades=True,
        )
        if len(trades) == 0:
            continue
        trades = trades.copy()
        trades["strategy_label"] = label
        trades["symbol"] = sym
        all_trades.append(trades)
    if not all_trades:
        return pd.DataFrame()
    out = pd.concat(all_trades, ignore_index=True)
    out["entry_ts"] = pd.to_datetime(out["entry_ts"], utc=True)
    out["exit_ts"] = pd.to_datetime(out["exit_ts"], utc=True)
    # Safety net: drop any trades that have identical (symbol, entry_ts) across
    # different strategy_labels — these are duplicates from overlapping subset
    # configurations. Keep the first by sort order. Live position_manager already
    # blocks same-symbol re-entry, so the simulator must mirror that.
    before = len(out)
    out = out.drop_duplicates(subset=["symbol", "entry_ts"], keep="first")
    dropped = before - len(out)
    if dropped > 0:
        print(f"  [dedup] dropped {dropped} duplicate (symbol, entry_ts) rows")
    out = out.sort_values("entry_ts").reset_index(drop=True)
    return out


def simulate_portfolio(
    trades: pd.DataFrame,
    starting_equity: float = 100_000.0,
    position_size_pct: float = 0.25,
    max_concurrent: int = 3,
) -> dict:
    """Process trades chronologically. Deploy `position_size_pct` of CURRENT equity
    on each entry; cap at `max_concurrent` simultaneous positions.

    Returns dict with equity_curve (list of (ts, equity)), and summary stats.
    """
    equity = starting_equity
    open_positions: list[dict] = []  # {exit_ts, position_dollars, pnl_pct}
    equity_curve: list[tuple] = [(trades["entry_ts"].iloc[0] - pd.Timedelta(seconds=1), equity)]
    accepted: list[dict] = []
    rejected_count = 0

    def _close_due_positions(now: pd.Timestamp) -> None:
        nonlocal equity, open_positions
        still_open = []
        for pos in open_positions:
            if pos["exit_ts"] <= now:
                pnl_dollars = pos["position_dollars"] * pos["pnl_pct"]
                equity += pnl_dollars
                equity_curve.append((pos["exit_ts"], equity))
            else:
                still_open.append(pos)
        open_positions = still_open

    for _, t in trades.iterrows():
        _close_due_positions(t["entry_ts"])
        if len(open_positions) >= max_concurrent:
            rejected_count += 1
            continue
        # Mirror live position_manager: block re-entry on a symbol already open.
        if any(p.get("symbol") == t["symbol"] for p in open_positions):
            rejected_count += 1
            continue
        position_dollars = equity * position_size_pct
        open_positions.append({
            "symbol": t["symbol"],
            "exit_ts": t["exit_ts"],
            "position_dollars": position_dollars,
            "pnl_pct": t["pnl_pct"],
        })
        accepted.append({**t.to_dict(), "position_dollars": position_dollars})

    # Close any remaining open positions at their scheduled exit
    final_ts = trades["exit_ts"].max()
    _close_due_positions(final_ts + pd.Timedelta(seconds=1))

    eq_df = pd.DataFrame(equity_curve, columns=["ts", "equity"]).sort_values("ts")
    eq_df = eq_df.drop_duplicates(subset=["ts"], keep="last").reset_index(drop=True)
    accepted_df = pd.DataFrame(accepted)

    if len(eq_df) > 1:
        running_max = eq_df["equity"].cummax()
        drawdown = (eq_df["equity"] - running_max) / running_max
        max_dd_pct = float(drawdown.min() * 100)
    else:
        max_dd_pct = 0.0

    period_days = (eq_df["ts"].iloc[-1] - eq_df["ts"].iloc[0]).total_seconds() / 86400
    period_years = period_days / 365.25
    total_return_pct = (equity / starting_equity - 1) * 100
    annualized_return_pct = (
        ((equity / starting_equity) ** (1 / period_years) - 1) * 100
        if period_years > 0 else 0.0
    )

    return {
        "starting_equity": starting_equity,
        "final_equity": equity,
        "total_return_pct": total_return_pct,
        "annualized_return_pct": annualized_return_pct,
        "max_drawdown_pct": max_dd_pct,
        "period_years": period_years,
        "trade_count_taken": len(accepted_df),
        "trade_count_rejected_capacity": rejected_count,
        "trade_count_total_signals": len(trades),
        "equity_curve": eq_df,
        "accepted_trades": accepted_df,
    }


def bootstrap_annualized_return(
    trades: pd.DataFrame,
    starting_equity: float,
    position_size_pct: float,
    max_concurrent: int,
    n_boot: int = 500,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Bootstrap by resampling trades with replacement (preserving chronological order
    of the resampled set). Returns (mean, 2.5%ile, 97.5%ile) of annualized return.
    """
    rng = np.random.default_rng(seed)
    samples = np.empty(n_boot)
    n = len(trades)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        sub = trades.iloc[idx].sort_values("entry_ts").reset_index(drop=True)
        result = simulate_portfolio(sub, starting_equity, position_size_pct, max_concurrent)
        samples[i] = result["annualized_return_pct"]
    return float(samples.mean()), float(np.percentile(samples, 2.5)), float(np.percentile(samples, 97.5))


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    cache_dir = project_root / "data" / "prices"

    # Use long history (2019-2026 = 7 years) for robust validation
    period_start = datetime(2019, 5, 1, tzinfo=timezone.utc)
    period_end = datetime(2026, 5, 1, tzinfo=timezone.utc)

    env_path = project_root / ".env"
    cfg = load_config(env_path=env_path if env_path.exists() else None)
    broker = AlpacaClient(api_key=cfg.alpaca_api_key,
                         secret_key=cfg.alpaca_secret_key,
                         base_url=cfg.alpaca_base_url)
    fetcher = PriceFetcher(broker=broker, cache_dir=cache_dir)

    # Both base and 3x leveraged ETFs are loaded (敏腕モード)
    symbols = ["SPY", "QQQ", "IWM", "DIA", "XLK",
               "TQQQ", "UPRO", "TNA", "TECL", "UDOW"]
    print(f"loading data for {symbols}...")
    data_map = collect_phase0_data(
        fetcher=fetcher, symbols=symbols, start=period_start, end=period_end,
        timeframes=[5, 1440],
    )
    atr_map = {s: analyze_atr_distribution(data_map[(s, 5)], period=14)["median_pct"]
               for s in symbols}

    vix_daily = pd.read_parquet(project_root / "data" / "prices" / "VIX_1day_2019-05-01_2026-05-01.parquet")
    print(f"loaded VIX: {len(vix_daily)} daily bars")

    print("collecting trades from selected strategies...")
    trades = collect_all_trades(symbols, data_map, atr_map, vix_daily=vix_daily)
    print(f"  total trades: {len(trades)}")
    print(trades.groupby("strategy_label").size())

    md = []
    md.append("# Portfolio Ensemble Backtest")
    md.append("")
    md.append("Combines top post-fix strategies into one $100k account simulation.")
    md.append("")
    md.append("**Selected strategies:**")
    for entry in SELECTED:
        cls, sym, params, label = entry[0], entry[1], entry[2], entry[3]
        cost = entry[4] if len(entry) >= 5 else 0.10
        md.append(f"- {label}: {cls.__name__}({sym}, {params}, cost={cost}%)")
    md.append("")

    if len(trades) == 0:
        print("No trades — aborting.")
        return 1

    # === Scenario 1: Conservative (β-mode in Plan 2.0) ===
    # 25% per position, 3 concurrent max, $2,500 cap was original; here pure 25% sizing.
    print("\n=== Scenario A: 25% per trade, 3 concurrent (Plan 2.0 baseline) ===")
    res_a = simulate_portfolio(trades, 100_000, 0.25, 3)
    boot_a = bootstrap_annualized_return(trades, 100_000, 0.25, 3, n_boot=300)
    print(f"  final equity: ${res_a['final_equity']:,.0f}")
    print(f"  total return: {res_a['total_return_pct']:+.2f}%")
    print(f"  annualized: {res_a['annualized_return_pct']:+.2f}%  (95% CI [{boot_a[1]:+.2f}, {boot_a[2]:+.2f}])")
    print(f"  max DD: {res_a['max_drawdown_pct']:+.2f}%")
    print(f"  trades taken: {res_a['trade_count_taken']} / {res_a['trade_count_total_signals']} "
          f"(rejected at cap: {res_a['trade_count_rejected_capacity']})")

    # === Scenario 2: Aggressive (full sizing) ===
    print("\n=== Scenario B: 50% per trade, 2 concurrent (aggressive) ===")
    res_b = simulate_portfolio(trades, 100_000, 0.50, 2)
    boot_b = bootstrap_annualized_return(trades, 100_000, 0.50, 2, n_boot=300)
    print(f"  final equity: ${res_b['final_equity']:,.0f}")
    print(f"  annualized: {res_b['annualized_return_pct']:+.2f}%  (95% CI [{boot_b[1]:+.2f}, {boot_b[2]:+.2f}])")
    print(f"  max DD: {res_b['max_drawdown_pct']:+.2f}%")

    # === Scenario 3: Full sizing one-at-a-time ===
    print("\n=== Scenario C: 100% per trade, 1 concurrent (max-leverage-no-overlap) ===")
    res_c = simulate_portfolio(trades, 100_000, 1.00, 1)
    boot_c = bootstrap_annualized_return(trades, 100_000, 1.00, 1, n_boot=300)
    print(f"  final equity: ${res_c['final_equity']:,.0f}")
    print(f"  annualized: {res_c['annualized_return_pct']:+.2f}%  (95% CI [{boot_c[1]:+.2f}, {boot_c[2]:+.2f}])")
    print(f"  max DD: {res_c['max_drawdown_pct']:+.2f}%")

    # Markdown output
    md.append("## Results")
    md.append("")
    md.append("| Scenario | Position Size | Max Concurrent | Trades Taken | Final Equity | Annualized Return (mean) | 95% CI | Max DD |")
    md.append("|----------|---------------|----------------|--------------|--------------|--------------------------|--------|--------|")
    for label, res, boot in [
        ("A: Plan 2.0 baseline (25%/pos × 3)", res_a, boot_a),
        ("B: Aggressive (50%/pos × 2)",         res_b, boot_b),
        ("C: Full size, 1 at a time",          res_c, boot_c),
    ]:
        md.append(
            f"| {label} | {res.get('position_size_pct', '')} | | "
            f"{res['trade_count_taken']} / {res['trade_count_total_signals']} | "
            f"${res['final_equity']:,.0f} | {res['annualized_return_pct']:+.2f}% | "
            f"[{boot[1]:+.2f}, {boot[2]:+.2f}]% | {res['max_drawdown_pct']:+.2f}% |"
        )

    md.append("")
    md.append("## Trade Counts by Strategy")
    md.append("")
    md.append("| Strategy | Trades | Avg P&L | Total Contribution |")
    md.append("|----------|--------|---------|--------------------|")
    for lbl, sub in trades.groupby("strategy_label"):
        avg = sub["pnl_pct"].mean() * 100
        total = sub["pnl_pct"].sum() * 100
        md.append(f"| {lbl} | {len(sub)} | {avg:+.3f}% | {total:+.2f}% |")
    md.append("")

    md.append("## Honest Projection")
    md.append("")
    md.append(f"- **Plan 2.0 baseline (Scenario A)**: annualized {res_a['annualized_return_pct']:+.2f}% "
              f"(95% CI [{boot_a[1]:+.2f}, {boot_a[2]:+.2f}]), max DD {res_a['max_drawdown_pct']:+.2f}%")
    md.append(f"- **Aggressive (Scenario B)**: annualized {res_b['annualized_return_pct']:+.2f}% "
              f"(95% CI [{boot_b[1]:+.2f}, {boot_b[2]:+.2f}]), max DD {res_b['max_drawdown_pct']:+.2f}%")
    md.append(f"- **Full-size sequential (Scenario C)**: annualized {res_c['annualized_return_pct']:+.2f}% "
              f"(95% CI [{boot_c[1]:+.2f}, {boot_c[2]:+.2f}]), max DD {res_c['max_drawdown_pct']:+.2f}%")
    md.append("")
    md.append("CIs from 300 bootstrap resamples of the trade list (with replacement).")
    md.append("**Caveat:** the 2-yr window includes a structurally bullish 2025 sub-period; "
              "live performance is likely below the mean estimate.")

    out_path = project_root / "phase0" / "portfolio_ensemble_long.md"
    out_path.write_text("\n".join(md), encoding="utf-8")
    print(f"\n[saved] {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
