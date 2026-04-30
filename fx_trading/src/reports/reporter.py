import math
from typing import List, Dict
import pandas as pd
from src.engine.backtest import Trade


class ReportGenerator:
    # Annualization assumes ~252 trading days; adjust if you change resampling.
    TRADING_DAYS_PER_YEAR = 252

    def __init__(self, initial_capital: float = 1_000_000, risk_free_rate: float = 0.0):
        self.initial_capital = initial_capital
        self.risk_free_rate = risk_free_rate

    def generate(self, trades: List[Trade]) -> Dict:
        total_trades = len(trades)
        if total_trades == 0:
            return self._empty_report()

        wins = [t.pnl for t in trades if t.pnl is not None and t.pnl > 0]
        losses = [t.pnl for t in trades if t.pnl is not None and t.pnl < 0]
        total_pnl = sum(t.pnl for t in trades if t.pnl is not None)
        win_rate = len(wins) / total_trades

        gross_profit = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss != 0 else float("inf")

        max_dd_pct, max_dd_abs = self._max_drawdown(trades)
        sharpe = self._sharpe_ratio(trades)
        sortino = self._sortino_ratio(trades)
        avg_hold_hours = self._avg_holding_hours(trades)

        return {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_pnl": total_pnl,
            "max_drawdown_pct": max_dd_pct,
            "max_drawdown_abs": max_dd_abs,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "avg_holding_hours": avg_hold_hours,
        }

    def _empty_report(self) -> Dict:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "total_pnl": 0.0,
            "max_drawdown_pct": 0.0,
            "max_drawdown_abs": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "avg_holding_hours": 0.0,
        }

    def _equity_curve(self, trades: List[Trade]) -> List[float]:
        # Cumulative equity from initial_capital, in trade-close order.
        ordered = sorted(
            (t for t in trades if t.exit_time is not None and t.pnl is not None),
            key=lambda t: t.exit_time,
        )
        equity = self.initial_capital
        curve = [equity]
        for t in ordered:
            equity += t.pnl
            curve.append(equity)
        return curve

    def _max_drawdown(self, trades: List[Trade]):
        curve = self._equity_curve(trades)
        if len(curve) < 2:
            return 0.0, 0.0
        peak = curve[0]
        max_dd_abs = 0.0
        max_dd_pct = 0.0
        for value in curve:
            if value > peak:
                peak = value
            dd_abs = peak - value
            dd_pct = dd_abs / peak * 100 if peak > 0 else 0.0
            if dd_abs > max_dd_abs:
                max_dd_abs = dd_abs
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
        return max_dd_pct, max_dd_abs

    def _daily_returns(self, trades: List[Trade]) -> pd.Series:
        # Bucket each trade's PnL by exit-day and convert to a daily return
        # series anchored at initial_capital. Days with no trades return 0.
        rows = [
            (t.exit_time.normalize(), t.pnl)
            for t in trades
            if t.exit_time is not None and t.pnl is not None
        ]
        if not rows:
            return pd.Series(dtype=float)
        df = pd.DataFrame(rows, columns=["date", "pnl"])
        daily_pnl = df.groupby("date")["pnl"].sum().sort_index()
        full_range = pd.date_range(daily_pnl.index.min(), daily_pnl.index.max(), freq="D")
        daily_pnl = daily_pnl.reindex(full_range, fill_value=0.0)
        return daily_pnl / self.initial_capital

    def _sharpe_ratio(self, trades: List[Trade]) -> float:
        returns = self._daily_returns(trades)
        if len(returns) < 2:
            return 0.0
        excess = returns - (self.risk_free_rate / self.TRADING_DAYS_PER_YEAR)
        std = excess.std(ddof=1)
        if std == 0 or math.isnan(std):
            return 0.0
        return float(excess.mean() / std * math.sqrt(self.TRADING_DAYS_PER_YEAR))

    def _sortino_ratio(self, trades: List[Trade]) -> float:
        returns = self._daily_returns(trades)
        if len(returns) < 2:
            return 0.0
        excess = returns - (self.risk_free_rate / self.TRADING_DAYS_PER_YEAR)
        downside = excess[excess < 0]
        if len(downside) == 0:
            return 0.0
        downside_std = downside.std(ddof=1)
        if downside_std == 0 or math.isnan(downside_std):
            return 0.0
        return float(excess.mean() / downside_std * math.sqrt(self.TRADING_DAYS_PER_YEAR))

    def _avg_holding_hours(self, trades: List[Trade]) -> float:
        durations = [
            (t.exit_time - t.entry_time).total_seconds() / 3600.0
            for t in trades
            if t.exit_time is not None and t.entry_time is not None
        ]
        if not durations:
            return 0.0
        return sum(durations) / len(durations)
