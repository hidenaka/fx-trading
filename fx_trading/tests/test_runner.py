from unittest.mock import MagicMock, patch
from src.runner.polling_runner import PollingRunner

def test_runner_constructs_with_dependencies():
    mock_config = MagicMock()
    mock_config.currency_pair = "USD_JPY"
    mock_config.risk_per_trade = 0.01
    runner = PollingRunner(config=mock_config)
    assert runner.config.currency_pair == "USD_JPY"

@patch("src.runner.polling_runner.OandaClient")
def test_runner_checks_circuit_breaker(mock_client_class):
    mock_config = MagicMock()
    mock_config.currency_pair = "USD_JPY"
    mock_config.risk_per_trade = 0.01
    mock_config.api_token = "test"
    mock_config.account_id = "acc"
    mock_config.environment = "practice"
    
    runner = PollingRunner(config=mock_config)
    # Mock circuit breaker to block trading
    runner.circuit_breaker.is_trading_allowed = MagicMock(return_value=False)
    result = runner.run_cycle()
    assert result is False

@patch("src.runner.polling_runner.OandaClient")
def test_runner_fetches_price(mock_client_class):
    mock_config = MagicMock()
    mock_config.currency_pair = "USD_JPY"
    mock_config.risk_per_trade = 0.01
    mock_config.api_token = "test"
    mock_config.account_id = "acc"
    mock_config.environment = "practice"
    
    mock_client = MagicMock()
    mock_client.get_current_price.return_value = {"bid": 145.0, "ask": 145.02}
    mock_client.get_open_positions.return_value = []
    mock_client_class.return_value = mock_client
    
    runner = PollingRunner(config=mock_config)
    runner.run_cycle()
    mock_client.get_current_price.assert_called_once_with("USD_JPY")
