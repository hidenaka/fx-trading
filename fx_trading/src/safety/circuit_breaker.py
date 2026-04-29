import datetime
from typing import Optional
from src.monitoring.slack import SlackNotifier

class CircuitBreaker:
    def __init__(self, max_daily_loss_pct: float = 5.0,
                 trading_start_hour: int = 7, trading_end_hour: int = 6,
                 initial_capital: float = 1_000_000,
                 slack_webhook_url: str = None):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.trading_start_hour = trading_start_hour
        self.trading_end_hour = trading_end_hour
        self.initial_capital = initial_capital
        self.daily_pnl = 0.0
        self.last_recorded_date: Optional[datetime.date] = None

        if slack_webhook_url:
            self.slack = SlackNotifier(slack_webhook_url)
        else:
            self.slack = None

    def record_pnl(self, pnl: float, now: Optional[datetime.datetime] = None):
        if now is None:
            now = datetime.datetime.now()
        today = now.date()
        if self.last_recorded_date != today:
            self.daily_pnl = 0.0
            self.last_recorded_date = today
        self.daily_pnl += pnl

    def is_trading_allowed(self, now: Optional[datetime.datetime] = None) -> bool:
        if now is None:
            now = datetime.datetime.now()
        
        # Check trading hours
        weekday = now.weekday()
        hour = now.hour
        
        # Saturday (5) after end hour or Sunday (6) before start hour = no trading
        if weekday == 5 and hour >= self.trading_end_hour:
            return False
        if weekday == 6 and hour < self.trading_start_hour:
            return False
        
        # Check daily loss limit
        if self.last_recorded_date == now.date():
            loss_pct = abs(self.daily_pnl) / self.initial_capital * 100
            if loss_pct >= self.max_daily_loss_pct:
                if self.slack:
                    self.slack.notify_circuit_breaker(self.daily_pnl, self.max_daily_loss_pct)
                return False
        
        return True
