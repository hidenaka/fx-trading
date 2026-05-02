"""Gate 2: tail-risk — single-trade, portfolio DD, rolling 30d."""
from __future__ import annotations

import pandas as pd

from equity_trading.src.validation.gates.base import GateResult, Status


def _max_drawdown_pct(equity: pd.Series) -> float:
    running_max = equity.cummax()
    dd = (equity - running_max) / running_max
    return float(abs(dd.min() * 100)) if len(dd) > 0 else 0.0


def _max_rolling_loss_pct(eq_df: pd.DataFrame, window_days: int) -> float:
    """Worst (peak - trough) % within any rolling window of length window_days."""
    if len(eq_df) < 2:
        return 0.0
    eq = eq_df.set_index("ts")["equity"]
    eq = eq.sort_index()
    worst = 0.0
    for i, ts in enumerate(eq.index):
        end = ts + pd.Timedelta(days=window_days)
        window = eq[(eq.index >= ts) & (eq.index <= end)]
        if len(window) < 2:
            continue
        peak = window.iloc[0]
        trough = window.min()
        loss = (peak - trough) / peak * 100 if peak > 0 else 0.0
        worst = max(worst, loss)
    return float(worst)


def _catastrophic_stop_worst(trades: pd.DataFrame, cap_pct: float = 5.0) -> float:
    """If a 5% hard stop were applied, what's the worst trade pnl_pct?"""
    if len(trades) == 0:
        return 0.0
    capped = trades["pnl_pct"].apply(lambda p: max(p, -cap_pct / 100))
    return float(capped.min() * 100)


def run_tail_risk_gate(
    *,
    equity_curve: pd.DataFrame,
    trades: pd.DataFrame,
    max_single_trade_loss_pct: float,
    max_portfolio_dd_pct: float,
    max_rolling_30d_loss_pct: float,
) -> GateResult:
    worst_trade_pct = float(trades["pnl_pct"].min() * 100) if len(trades) > 0 else 0.0
    portfolio_dd_pct = _max_drawdown_pct(equity_curve["equity"])
    rolling_30d_loss_pct = _max_rolling_loss_pct(equity_curve, window_days=30)
    cat_stop_worst = _catastrophic_stop_worst(trades, cap_pct=5.0)

    failures: list[str] = []
    warnings: list[str] = []

    if abs(worst_trade_pct) > max_single_trade_loss_pct:
        failures.append(
            f"worst single trade {worst_trade_pct:.2f}% exceeds limit -{max_single_trade_loss_pct:.1f}%"
        )
    if portfolio_dd_pct > max_portfolio_dd_pct:
        failures.append(
            f"portfolio drawdown {portfolio_dd_pct:.2f}% exceeds limit {max_portfolio_dd_pct:.1f}%"
        )
    if rolling_30d_loss_pct > max_rolling_30d_loss_pct:
        warnings.append(
            f"30-day rolling loss {rolling_30d_loss_pct:.2f}% exceeds {max_rolling_30d_loss_pct:.1f}%"
        )

    if failures:
        status = Status.FAIL
        summary = "; ".join(failures)
    elif warnings:
        status = Status.WARN
        summary = "; ".join(warnings)
    else:
        status = Status.PASS
        summary = (
            f"worst trade {worst_trade_pct:.2f}%, MaxDD {portfolio_dd_pct:.2f}%, "
            f"30d rolling {rolling_30d_loss_pct:.2f}% — all within limits"
        )

    detail = (
        f"### Gate 2: Tail risk {status.icon}\n\n"
        f"- worst single trade: **{worst_trade_pct:.2f}%** (limit -{max_single_trade_loss_pct:.1f}%)\n"
        f"- portfolio MaxDD: **{portfolio_dd_pct:.2f}%** (limit {max_portfolio_dd_pct:.1f}%)\n"
        f"- 30-day rolling loss: **{rolling_30d_loss_pct:.2f}%** (limit {max_rolling_30d_loss_pct:.1f}%)\n"
        f"\n#### Catastrophic stop simulation (-5% cap on every trade)\n"
        f"- worst trade if cap were applied: **{cat_stop_worst:.2f}%**\n"
        f"- This is informational only. To apply, add a `catastrophic_stop_pct: 5.0` "
        f"override in the variant config and re-validate.\n"
    )
    return GateResult(name="tail_risk", status=status, summary=summary, detail_md=detail,
                       metrics={
                           "worst_trade_pct": worst_trade_pct,
                           "portfolio_dd_pct": portfolio_dd_pct,
                           "rolling_30d_loss_pct": rolling_30d_loss_pct,
                           "catastrophic_stop_worst_pct": cat_stop_worst,
                       })
