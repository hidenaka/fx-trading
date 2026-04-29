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

@patch("src.runner.polling_runner.OandaClient")
def test_runner_uses_multiple_strategies(mock_client_class):
    mock_config = MagicMock()
    mock_config.currency_pair = "USD_JPY"
    mock_config.risk_per_trade = 0.01
    mock_config.api_token = "test"
    mock_config.account_id = "acc"
    mock_config.environment = "practice"
    mock_config.slack_webhook_url = None

    runner = PollingRunner(config=mock_config, strategies=["ma_macd", "ma_cross"])
    assert len(runner.strategies) == 2

@patch("src.runner.polling_runner.OandaClient")
def test_runner_aggregates_signals(mock_client_class):
    mock_config = MagicMock()
    mock_config.currency_pair = "USD_JPY"
    mock_config.risk_per_trade = 0.01
    mock_config.api_token = "test"
    mock_config.account_id = "acc"
    mock_config.environment = "practice"
    mock_config.slack_webhook_url = None

    runner = PollingRunner(config=mock_config, strategies=["ma_macd"])
    # Mock strategy signals
    import pandas as pd
    df = pd.DataFrame({
        "datetime": [pd.Timestamp("2024-01-01")],
        "signal": [1],
    })
    runner.strategies[0].generate_signals = MagicMock(return_value=df)

    signal = runner._aggregate_signals(df)
    assert signal == 1

def test_runner_processes_multiple_pairs():
    from unittest.mock import MagicMock, patch
    mock_config = MagicMock()
    mock_config.currency_pairs = ["USD_JPY", "EUR_USD"]
    mock_config.risk_per_trade = 0.01
    mock_config.api_token = "test"
    mock_config.account_id = "acc"
    mock_config.environment = "practice"
    mock_config.slack_webhook_url = None
    
    with patch("src.runner.polling_runner.OandaClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.get_multiple_prices.return_value = {
            "USD_JPY": {"bid": 145.0, "ask": 145.02},
            "EUR_USD": {"bid": 1.085, "ask": 1.0852},
        }
        mock_client.get_open_positions.return_value = []
        mock_client_class.return_value = mock_client
        
        runner = PollingRunner(config=mock_config)
        results = runner.run_all_pairs()
        assert len(results) == 2
        assert "USD_JPY" in results
        assert "EUR_USD" in results
