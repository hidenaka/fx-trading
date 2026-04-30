import datetime
from typing import Optional
from src.monitoring.slack import SlackNotifier

class CircuitBreaker:
    def __init__(self, max_daily_loss_pct: float = 5.0,
                 trading_start_hour: int = 7, trading_end_hour: int = 6,
                 initial_capital: float = 1_000_000,
                 max_drawdown_pct: float = 15.0,
                 max_consecutive_losses: int = 5,
                 slack_webhook_url: str = None):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.trading_start_hour = trading_start_hour
        self.trading_end_hour = trading_end_hour
        self.initial_capital = initial_capital
        self.max_drawdown_pct = max_drawdown_pct
        self.max_consecutive_losses = max_consecutive_losses

        self.daily_pnl = 0.0
        self.last_recorded_date: Optional[datetime.date] = None

        # Equity / drawdown tracking starts at the initial capital. Peak rises
        # only on new highs; drawdown is measured from peak, not from initial.
        self.equity_peak = initial_capital
        self.current_equity = initial_capital
        self.consecutive_losses = 0

        if slack_webhook_url:
            self.slack = SlackNotifier(slack_webhook_url)
        else:
            self.slack = None

    def record_pnl(self, pnl: float, now: Optional[datetime.datetime] = None):
        # Treats `pnl` as a closed-trade result. Daily PnL, equity, drawdown
        # peak, and consecutive-loss count all derive from this single signal.
        if now is None:
            now = datetime.datetime.now()
        today = now.date()
        if self.last_recorded_date != today:
            self.daily_pnl = 0.0
            self.last_recorded_date = today
        self.daily_pnl += pnl

        self.current_equity += pnl
        if self.current_equity > self.equity_peak:
            self.equity_peak = self.current_equity

        if pnl < 0:
            self.consecutive_losses += 1
        elif pnl > 0:
            self.consecutive_losses = 0

    def current_drawdown_pct(self) -> float:
        if self.equity_peak <= 0:
            return 0.0
        return max(0.0, (self.equity_peak - self.current_equity) / self.equity_peak * 100)

    def reset_consecutive_losses(self):
        self.consecutive_losses = 0

    def is_trading_allowed(self, now: Optional[datetime.datetime] = None) -> bool:
        if now is None:
            now = datetime.datetime.now()

        weekday = now.weekday()
        hour = now.hour
        if weekday == 5 and hour >= self.trading_end_hour:
            return False
        if weekday == 6 and hour < self.trading_start_hour:
            return False

        if self.last_recorded_date == now.date():
            loss_pct = abs(self.daily_pnl) / self.initial_capital * 100
            if self.daily_pnl < 0 and loss_pct >= self.max_daily_loss_pct:
                if self.slack:
                    self.slack.notify_circuit_breaker(self.daily_pnl, self.max_daily_loss_pct)
                return False

        if self.current_drawdown_pct() >= self.max_drawdown_pct:
            if self.slack:
                self.slack.notify_circuit_breaker(
                    self.current_equity - self.equity_peak, self.max_drawdown_pct
                )
            return False

        if self.consecutive_losses >= self.max_consecutive_losses:
            if self.slack:
                self.slack.notify_circuit_breaker(self.daily_pnl, 0)
            return False

        return True
