import pytest
from unittest.mock import patch, MagicMock
from src.notifications.slack_notifier import SlackNotifier

def test_notifier_sends_trade_message():
    with patch("src.notifications.slack_notifier.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        notifier.notify_trade("USD_JPY", "BUY", 1000, 145.5)
        mock_post.assert_called_once()
        args = mock_post.call_args
        assert "USD_JPY" in args[1]["json"]["text"]

def test_notifier_sends_error_message():
    with patch("src.notifications.slack_notifier.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        notifier.notify_error("API connection failed")
        args = mock_post.call_args
        assert "ERROR" in args[1]["json"]["text"]

def test_notifier_skips_if_no_url():
    with patch("src.notifications.slack_notifier.requests.post") as mock_post:
        notifier = SlackNotifier(webhook_url=None)
        notifier.notify_trade("USD_JPY", "BUY", 1000, 145.5)
        mock_post.assert_not_called()

def test_notifier_handles_failure_gracefully():
    with patch("src.notifications.slack_notifier.requests.post") as mock_post:
        mock_post.return_value.status_code = 500
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        # Should not raise
        notifier.notify_trade("USD_JPY", "BUY", 1000, 145.5)
