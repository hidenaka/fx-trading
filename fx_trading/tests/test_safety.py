import datetime
from unittest.mock import patch, MagicMock
from src.safety.circuit_breaker import CircuitBreaker

def test_trading_hours_allows_trading():
    cb = CircuitBreaker(max_daily_loss_pct=5.0, trading_start_hour=7, trading_end_hour=23)
    # Mock current time to be within trading hours
    now = datetime.datetime(2024, 1, 2, 12, 0)  # Tuesday noon
    assert cb.is_trading_allowed(now) is True

def test_trading_hours_rejects_sunday_early():
    cb = CircuitBreaker(max_daily_loss_pct=5.0, trading_start_hour=7, trading_end_hour=23)
    now = datetime.datetime(2024, 1, 7, 5, 0)  # Sunday 5am
    assert cb.is_trading_allowed(now) is False

def test_daily_loss_limit_blocks_trading():
    cb = CircuitBreaker(max_daily_loss_pct=5.0, trading_start_hour=7, trading_end_hour=23)
    now = datetime.datetime(2024, 1, 2, 12, 0)
    cb.record_pnl(-60000, now=now)  # 6% loss on 1M capital
    assert cb.is_trading_allowed(now) is False

def test_daily_loss_resets_next_day():
    cb = CircuitBreaker(max_daily_loss_pct=5.0, trading_start_hour=7, trading_end_hour=23)
    today = datetime.datetime(2024, 1, 2, 12, 0)
    cb.record_pnl(-60000, now=today)
    # Next day
    next_day = datetime.datetime(2024, 1, 3, 12, 0)
    assert cb.is_trading_allowed(next_day) is True

def test_circuit_breaker_notifies_slack():
    with patch("src.safety.circuit_breaker.SlackNotifier") as mock_slack_class:
        mock_slack = MagicMock()
        mock_slack_class.return_value = mock_slack
        cb = CircuitBreaker(max_daily_loss_pct=5.0, slack_webhook_url="https://test")
        cb.record_pnl(-60000)
        cb.is_trading_allowed()
        mock_slack.notify_circuit_breaker.assert_called_once()


def test_consecutive_losses_block_trading():
    cb = CircuitBreaker(
        max_daily_loss_pct=99.0,  # disable daily-loss path
        max_drawdown_pct=99.0,    # disable drawdown path
        max_consecutive_losses=3,
        trading_start_hour=0, trading_end_hour=24,
    )
    now = datetime.datetime(2024, 1, 2, 12, 0)
    for _ in range(3):
        cb.record_pnl(-100, now=now)
    assert cb.is_trading_allowed(now) is False


def test_consecutive_losses_reset_on_win():
    cb = CircuitBreaker(
        max_daily_loss_pct=99.0,
        max_drawdown_pct=99.0,
        max_consecutive_losses=3,
        trading_start_hour=0, trading_end_hour=24,
    )
    now = datetime.datetime(2024, 1, 2, 12, 0)
    cb.record_pnl(-100, now=now)
    cb.record_pnl(-100, now=now)
    cb.record_pnl(+50, now=now)  # win resets the streak
    cb.record_pnl(-100, now=now)
    assert cb.consecutive_losses == 1
    assert cb.is_trading_allowed(now) is True


def test_drawdown_blocks_trading_after_peak():
    cb = CircuitBreaker(
        max_daily_loss_pct=99.0,
        max_drawdown_pct=10.0,
        max_consecutive_losses=99,
        initial_capital=1_000_000,
        trading_start_hour=0, trading_end_hour=24,
    )
    now = datetime.datetime(2024, 1, 2, 12, 0)
    # Equity climbs to 1.2M (new peak), then drops to 1.05M = 12.5% drawdown.
    cb.record_pnl(+200_000, now=now)
    assert cb.equity_peak == 1_200_000
    cb.record_pnl(-150_000, now=now)
    assert cb.current_drawdown_pct() > 10.0
    assert cb.is_trading_allowed(now) is False


def test_drawdown_below_threshold_allows_trading():
    cb = CircuitBreaker(
        max_daily_loss_pct=99.0,
        max_drawdown_pct=15.0,
        max_consecutive_losses=99,
        initial_capital=1_000_000,
        trading_start_hour=0, trading_end_hour=24,
    )
    now = datetime.datetime(2024, 1, 2, 12, 0)
    cb.record_pnl(+100_000, now=now)
    cb.record_pnl(-50_000, now=now)  # ~4.5% drawdown from peak 1.1M
    assert cb.is_trading_allowed(now) is True


def test_reset_consecutive_losses():
    cb = CircuitBreaker(
        max_daily_loss_pct=99.0,
        max_drawdown_pct=99.0,
        max_consecutive_losses=3,
        trading_start_hour=0, trading_end_hour=24,
    )
    now = datetime.datetime(2024, 1, 2, 12, 0)
    for _ in range(3):
        cb.record_pnl(-100, now=now)
    assert cb.is_trading_allowed(now) is False
    cb.reset_consecutive_losses()
    assert cb.is_trading_allowed(now) is True
