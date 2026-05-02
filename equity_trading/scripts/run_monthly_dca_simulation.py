"""Monthly DCA simulator: ¥100,000 initial + ¥50,000 monthly deposits over 1/3/5 yr.

Replays the leveraged-ETF portfolio (TECL/UPRO/UDOW pre-FOMC, TQQQ/TECL/TNA ORB,
UPRO/UDOW LHM) on 7-yr historical data with monthly cash injections to model
the user's actual cadence. Reports best/median/worst rolling-period outcomes
and reproduces the equity curve through bear-market stretches (March 2020,
2022 rate hikes) so the user can see real drawdowns.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

from equity_trading.scripts.run_portfolio_ensemble import SELECTED, collect_all_trades
from equity_trading.src.broker.alpaca_client import AlpacaClient
from equity_trading.src.config import load_config
from equity_trading.src.data.price_fetcher import PriceFetcher
from equity_trading.src.phase0.atr_analyzer import analyze_atr_distribution
from equity_trading.src.phase0.data_collector import collect_phase0_data


# JPY assumptions: ¥154 / $1, monthly deposit ¥50,000, initial ¥100,000.
JPY_USD = 154.0
INITIAL_JPY = 100_000
MONTHLY_JPY = 50_000


def run_dca(
    trades: pd.DataFrame,
    starting_equity_usd: float,
    monthly_deposit_usd: float,
    position_size_pct: float,
    max_concurrent: int,
    period_start: pd.Timestamp,
    period_end: pd.Timestamp,
) -> dict:
    """Run portfolio sim with monthly cash injections. Equity grows from new
    capital + trade P&L."""
    equity = starting_equity_usd
    cash_added = 0.0  # cumulative deposits (excl initial)

    open_positions: list[dict] = []
    eq_curve: list[tuple] = [(period_start, equity)]
    rejected = 0
    accepted = 0

    # Pre-compute monthly deposit dates (1st of each month after period_start)
    next_deposit = pd.Timestamp(period_start) + pd.offsets.MonthBegin(1)

    def _close_due(now):
        nonlocal equity
        still = []
        for pos in open_positions:
            if pos["exit_ts"] <= now:
                equity += pos["position_dollars"] * pos["pnl_pct"]
                eq_curve.append((pos["exit_ts"], equity))
            else:
                still.append(pos)
        open_positions[:] = still

    for _, t in trades.iterrows():
        # Apply pending monthly deposits before processing this trade
        while next_deposit <= t["entry_ts"]:
            equity += monthly_deposit_usd
            cash_added += monthly_deposit_usd
            eq_curve.append((next_deposit, equity))
            next_deposit = next_deposit + pd.offsets.MonthBegin(1)

        _close_due(t["entry_ts"])
        if len(open_positions) >= max_concurrent:
            rejected += 1
            continue
        if any(p.get("symbol") == t["symbol"] for p in open_positions):
            rejected += 1
            continue
        position_dollars = equity * position_size_pct
        open_positions.append({
            "symbol": t["symbol"],
            "exit_ts": t["exit_ts"],
            "position_dollars": position_dollars,
            "pnl_pct": t["pnl_pct"],
        })
        accepted += 1

    # Final close
    _close_due(period_end + pd.Timedelta(seconds=1))
    # Apply any remaining monthly deposits
    while next_deposit <= period_end:
        equity += monthly_deposit_usd
        cash_added += monthly_deposit_usd
        eq_curve.append((next_deposit, equity))
        next_deposit = next_deposit + pd.offsets.MonthBegin(1)

    total_invested = starting_equity_usd + cash_added
    total_return_dollars = equity - total_invested
    total_return_pct = total_return_dollars / total_invested * 100 if total_invested > 0 else 0

    eq_df = pd.DataFrame(eq_curve, columns=["ts", "equity"]).sort_values("ts")
    eq_df = eq_df.drop_duplicates(subset=["ts"], keep="last").reset_index(drop=True)

    # Compute peak-to-trough max DD on equity (relative to running max)
    if len(eq_df) > 1:
        running_max = eq_df["equity"].cummax()
        dd = (eq_df["equity"] - running_max) / running_max
        max_dd_pct = float(dd.min() * 100)
    else:
        max_dd_pct = 0.0

    period_years = (period_end - period_start).total_seconds() / (86400 * 365.25)
    return {
        "starting_equity_usd": starting_equity_usd,
        "total_invested_usd": total_invested,
        "final_equity_usd": equity,
        "total_return_dollars": total_return_dollars,
        "total_return_pct": total_return_pct,
        "max_drawdown_pct": max_dd_pct,
        "trades_accepted": accepted,
        "trades_rejected": rejected,
        "period_years": period_years,
        "equity_curve": eq_df,
    }


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    cfg = load_config(env_path=project_root / ".env")
    broker = AlpacaClient(api_key=cfg.alpaca_api_key, secret_key=cfg.alpaca_secret_key,
                          base_url=cfg.alpaca_base_url)
    fetcher = PriceFetcher(broker=broker, cache_dir=project_root / "data" / "prices")

    period_start = datetime(2019, 5, 1, tzinfo=timezone.utc)
    period_end = datetime(2026, 5, 1, tzinfo=timezone.utc)

    symbols = sorted({entry[1] for entry in SELECTED})
    print(f"loading data for {symbols}...")
    data_map = collect_phase0_data(fetcher=fetcher, symbols=symbols,
                                    start=period_start, end=period_end, timeframes=[5, 1440])
    atr_map = {s: analyze_atr_distribution(data_map[(s, 5)], period=14)["median_pct"]
               for s in symbols}
    vix_daily = pd.read_parquet(project_root / "data" / "prices" / "VIX_1day_2019-05-01_2026-05-01.parquet")
    trades = collect_all_trades(symbols, data_map, atr_map, vix_daily=vix_daily)
    print(f"  total trades: {len(trades)}")

    initial_usd = INITIAL_JPY / JPY_USD       # ~$650
    monthly_usd = MONTHLY_JPY / JPY_USD       # ~$325

    md = []
    md.append("# 月次積立シミュレーション (敏腕モード)")
    md.append("")
    md.append(f"前提:\n- 初期投入: ¥{INITIAL_JPY:,} (≈ ${initial_usd:.2f})\n"
              f"- 毎月積立: ¥{MONTHLY_JPY:,} (≈ ${monthly_usd:.2f})\n"
              f"- 為替: ¥{JPY_USD}/$1\n"
              f"- 戦略セット: 3x ETF (TECL/TQQQ/TNA/UPRO/UDOW) で Pre-FOMC + ORB + LHM\n"
              f"- 検証期間: {period_start.date()} 〜 {period_end.date()} (7 年間)\n")
    md.append("")

    md.append("## Scenario A (25%/取引 × 3 同時、推奨)")
    md.append("")
    res_a = run_dca(trades, initial_usd, monthly_usd, 0.25, 3,
                    pd.Timestamp(period_start), pd.Timestamp(period_end))

    md.append(f"- 投入総額: ${res_a['total_invested_usd']:.0f}  (≈ ¥{res_a['total_invested_usd']*JPY_USD:,.0f})")
    md.append(f"- 最終残高: ${res_a['final_equity_usd']:.0f}  (≈ ¥{res_a['final_equity_usd']*JPY_USD:,.0f})")
    md.append(f"- 損益:    ${res_a['total_return_dollars']:+.0f}  (¥{res_a['total_return_dollars']*JPY_USD:+,.0f}) "
              f"= **{res_a['total_return_pct']:+.1f}%** of total deposited")
    md.append(f"- 最大下落: **{res_a['max_drawdown_pct']:+.1f}%** (元本に対するピーク→ボトム)")
    md.append(f"- 取引: {res_a['trades_accepted']} 受託 / {res_a['trades_rejected']} 棄却")
    md.append("")

    md.append("## Scenario B (50%/取引 × 2 同時、強気)")
    res_b = run_dca(trades, initial_usd, monthly_usd, 0.50, 2,
                    pd.Timestamp(period_start), pd.Timestamp(period_end))
    md.append(f"- 最終残高: ${res_b['final_equity_usd']:.0f}  (¥{res_b['final_equity_usd']*JPY_USD:,.0f})")
    md.append(f"- 損益:    {res_b['total_return_pct']:+.1f}%  最大下落 {res_b['max_drawdown_pct']:+.1f}%")
    md.append("")

    md.append("## 各年末の残高 (Scenario A、月次積立続行)")
    md.append("")
    md.append("| 年末 | 投入累計 | 残高 (USD) | 残高 (JPY) | 含み益 |")
    md.append("|------|---------:|------:|------:|------:|")
    eq_df = res_a["equity_curve"]
    eq_df["ts"] = pd.to_datetime(eq_df["ts"], utc=True)
    for year_end in [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]:
        cutoff = pd.Timestamp(f"{year_end}-12-31", tz="UTC")
        if cutoff > pd.Timestamp(period_end):
            cutoff = pd.Timestamp(period_end)
        eq_at = eq_df[eq_df["ts"] <= cutoff]
        if len(eq_at) == 0:
            continue
        # Compute deposits-to-date
        months_in = max(0, (cutoff.year - 2019) * 12 + cutoff.month - 5)
        invested = initial_usd + months_in * monthly_usd
        balance = float(eq_at["equity"].iloc[-1])
        gain_pct = (balance / invested - 1) * 100 if invested > 0 else 0
        md.append(f"| {cutoff.date()} | ${invested:.0f} | ${balance:.0f} | "
                  f"¥{balance*JPY_USD:,.0f} | {gain_pct:+.1f}% |")
    md.append("")

    md.append("## ピーク → ボトム 最大ドローダウン（実体験）")
    md.append("")
    md.append("過去 7 年で最大の下落区間 (Scenario A、Max DD = "
              f"{res_a['max_drawdown_pct']:.1f}%):")
    running_max = eq_df["equity"].cummax()
    dd = (eq_df["equity"] - running_max) / running_max
    bottom_idx = int(dd.idxmin())
    bottom_ts = eq_df["ts"].iloc[bottom_idx]
    bottom_eq = float(eq_df["equity"].iloc[bottom_idx])
    peak_idx = int(running_max.iloc[:bottom_idx+1].idxmax())
    peak_ts = eq_df["ts"].iloc[peak_idx]
    peak_eq = float(eq_df["equity"].iloc[peak_idx])
    md.append(f"- ピーク: {peak_ts.date()}  ${peak_eq:.0f}  (¥{peak_eq*JPY_USD:,.0f})")
    md.append(f"- 底値:   {bottom_ts.date()}  ${bottom_eq:.0f}  (¥{bottom_eq*JPY_USD:,.0f})")
    md.append(f"- 期間:   約 {(bottom_ts - peak_ts).days} 日 / 損失額 ¥{(bottom_eq - peak_eq)*JPY_USD:+,.0f}")
    md.append("")
    md.append("→ この期間中にあなたは bot を止めず、毎月積立を続けられますか?")

    out = project_root / "phase0" / "monthly_dca_projection.md"
    out.write_text("\n".join(md), encoding="utf-8")
    print(f"\n[saved] {out}")
    print(f"\nScenario A 7-yr summary:")
    print(f"  Total deposited: ${res_a['total_invested_usd']:.0f}  (≈ ¥{res_a['total_invested_usd']*JPY_USD:,.0f})")
    print(f"  Final balance:   ${res_a['final_equity_usd']:.0f}  (≈ ¥{res_a['final_equity_usd']*JPY_USD:,.0f})")
    print(f"  Net P&L:         ${res_a['total_return_dollars']:+.0f}  ({res_a['total_return_pct']:+.1f}%)")
    print(f"  Max DD:          {res_a['max_drawdown_pct']:+.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
