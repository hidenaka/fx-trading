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
    mock_config.initial_capital = 1_000_000
    mock_config.max_daily_loss_pct = 5.0
    mock_config.max_drawdown_pct = 15.0
    mock_config.max_consecutive_losses = 5
    mock_config.trading_start_hour = 0
    mock_config.trading_end_hour = 24

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

@patch("src.runner.polling_runner.OandaClient")
def test_runner_records_realized_pnl_to_circuit_breaker(mock_client_class):
    import pandas as pd
    mock_config = MagicMock()
    mock_config.currency_pair = "USD_JPY"
    mock_config.currency_pairs = ["USD_JPY"]
    mock_config.risk_per_trade = 0.01
    mock_config.api_token = "test"
    mock_config.account_id = "acc"
    mock_config.environment = "practice"
    mock_config.slack_webhook_url = None
    mock_config.initial_capital = 1_000_000
    mock_config.max_daily_loss_pct = 5.0
    mock_config.max_drawdown_pct = 15.0
    mock_config.max_consecutive_losses = 5
    mock_config.trading_start_hour = 0
    mock_config.trading_end_hour = 24

    mock_client = MagicMock()
    mock_client.get_current_price.return_value = {"bid": 145.0, "ask": 145.02}
    mock_client.get_open_positions.return_value = [{
        "instrument": "USD_JPY",
        "long": {"units": "1000"},
        "short": {"units": "0"},
    }]
    mock_client.get_transactions_since.return_value = {"transactions": [], "lastTransactionID": "0"}
    mock_client.close_position.return_value = {
        "longOrderFillTransaction": {"pl": "-2500.0", "id": "999"},
    }
    mock_client_class.return_value = mock_client

    runner = PollingRunner(config=mock_config, strategies=["ma_macd"])
    # Force a sell signal so the runner takes the close path on a long position.
    sell_df = pd.DataFrame({
        "datetime": [pd.Timestamp("2024-01-01")],
        "signal": [-1],
    })
    runner.strategies[0].generate_signals = MagicMock(return_value=sell_df)

    runner.run_cycle()

    mock_client.close_position.assert_called_once_with("USD_JPY")
    assert runner.circuit_breaker.daily_pnl == -2500.0
    assert runner.circuit_breaker.consecutive_losses == 1


def test_extract_realized_pnl_handles_partial_fills():
    from src.runner.polling_runner import _extract_realized_pnl
    response = {
        "longOrderFillTransaction": {"pl": "1500.5"},
        "shortOrderFillTransaction": {"pl": "-200"},
    }
    assert _extract_realized_pnl(response) == 1300.5
    assert _extract_realized_pnl({}) == 0.0
    assert _extract_realized_pnl(None) == 0.0


def test_runner_processes_multiple_pairs():
    from unittest.mock import MagicMock, patch
    mock_config = MagicMock()
    mock_config.currency_pairs = ["USD_JPY", "EUR_USD"]
    mock_config.risk_per_trade = 0.01
    mock_config.api_token = "test"
    mock_config.account_id = "acc"
    mock_config.environment = "practice"
    mock_config.slack_webhook_url = None
    mock_config.initial_capital = 1_000_000
    mock_config.max_daily_loss_pct = 5.0
    mock_config.max_drawdown_pct = 15.0
    mock_config.max_consecutive_losses = 5
    mock_config.trading_start_hour = 0
    mock_config.trading_end_hour = 24

    with patch("src.runner.polling_runner.OandaClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.get_multiple_prices.return_value = {
            "USD_JPY": {"bid": 145.0, "ask": 145.02},
            "EUR_USD": {"bid": 1.085, "ask": 1.0852},
        }
        mock_client.get_open_positions.return_value = []
        mock_client.get_transactions_since.return_value = {"transactions": [], "lastTransactionID": "0"}
        mock_client_class.return_value = mock_client

        runner = PollingRunner(config=mock_config)
        results = runner.run_all_pairs()
        assert len(results) == 2
        assert "USD_JPY" in results
        assert "EUR_USD" in results


@patch("src.runner.polling_runner.OandaClient")
def test_runner_reconciles_external_fills_into_circuit_breaker(mock_client_class):
    import pandas as pd
    mock_config = MagicMock()
    mock_config.currency_pair = "USD_JPY"
    mock_config.currency_pairs = ["USD_JPY"]
    mock_config.risk_per_trade = 0.01
    mock_config.api_token = "t"
    mock_config.account_id = "acc"
    mock_config.environment = "practice"
    mock_config.slack_webhook_url = None
    mock_config.initial_capital = 1_000_000
    mock_config.max_daily_loss_pct = 5.0
    mock_config.max_drawdown_pct = 15.0
    mock_config.max_consecutive_losses = 5
    mock_config.trading_start_hour = 0
    mock_config.trading_end_hour = 24

    mock_client = MagicMock()
    mock_client.get_current_price.return_value = {"bid": 145.0, "ask": 145.02}
    mock_client.get_open_positions.return_value = []
    mock_client.get_transactions_since.return_value = {
        "transactions": [
            {"id": "201", "type": "ORDER_FILL", "pl": "1200.0"},
            {"id": "202", "type": "ORDER_FILL", "pl": "-800.0"},
            {"id": "203", "type": "MARKET_ORDER", "pl": "0"},
        ],
        "lastTransactionID": "203",
    }
    mock_client_class.return_value = mock_client

    runner = PollingRunner(config=mock_config, strategies=["ma_macd"])
    runner.last_transaction_id = "200"
    runner.run_cycle()

    assert runner.circuit_breaker.daily_pnl == 400.0
    assert runner.circuit_breaker.consecutive_losses == 1
    assert runner.last_transaction_id == "203"


@patch("src.runner.polling_runner.OandaClient")
def test_runner_cycle_survives_reconcile_exception(mock_client_class):
    import pandas as pd
    mock_config = MagicMock()
    mock_config.currency_pair = "USD_JPY"
    mock_config.currency_pairs = ["USD_JPY"]
    mock_config.risk_per_trade = 0.01
    mock_config.api_token = "t"
    mock_config.account_id = "acc"
    mock_config.environment = "practice"
    mock_config.slack_webhook_url = None
    mock_config.initial_capital = 1_000_000
    mock_config.max_daily_loss_pct = 5.0
    mock_config.max_drawdown_pct = 15.0
    mock_config.max_consecutive_losses = 5
    mock_config.trading_start_hour = 0
    mock_config.trading_end_hour = 24

    mock_client = MagicMock()
    mock_client.get_transactions_since.side_effect = RuntimeError("network timeout")
    mock_client.get_current_price.return_value = {"bid": 145.0, "ask": 145.02}
    mock_client.get_open_positions.return_value = []
    mock_client_class.return_value = mock_client

    runner = PollingRunner(config=mock_config, strategies=["ma_macd"])
    # Cursor must remain unchanged when the API call raises.
    initial_cursor = runner.last_transaction_id
    result = runner.run_cycle()
    assert result is True  # cycle completes despite reconcile failure
    assert runner.last_transaction_id == initial_cursor
