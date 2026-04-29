import os
import tempfile
from unittest.mock import patch, MagicMock
from src.monitoring.logger import TradeLogger

def test_logger_creates_log_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "trades.log")
        logger = TradeLogger(log_file=log_file)
        logger.log_trade("USD_JPY", "BUY", 1000, 150.0)
        assert os.path.exists(log_file)
        with open(log_file) as f:
            content = f.read()
        assert "USD_JPY" in content
        assert "BUY" in content

def test_logger_logs_error():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "errors.log")
        logger = TradeLogger(log_file=log_file)
        logger.log_error("API connection failed")
        with open(log_file) as f:
            content = f.read()
        assert "ERROR" in content
        assert "API connection failed" in content

def test_logger_calls_slack_on_trade():
    with patch("src.monitoring.logger.SlackNotifier") as mock_slack_class:
        mock_slack = MagicMock()
        mock_slack_class.return_value = mock_slack
        logger = TradeLogger(log_file="/tmp/test_trades.log", slack_webhook_url="https://test")
        logger.log_trade("USD_JPY", "BUY", 1000, 145.5)
        mock_slack.notify_trade.assert_called_once()

def test_logger_skips_slack_if_no_url():
    with patch("src.monitoring.logger.SlackNotifier") as mock_slack_class:
        logger = TradeLogger(log_file="/tmp/test_trades.log")
        logger.log_trade("USD_JPY", "BUY", 1000, 145.5)
        mock_slack_class.assert_not_called()
