from unittest.mock import MagicMock, patch


def test_close_position_returns_order_info():
    from equity_trading.src.broker.alpaca_client import AlpacaClient

    with patch(
        "equity_trading.src.broker.alpaca_client.TradingClient"
    ) as mock_trading_cls, patch(
        "equity_trading.src.broker.alpaca_client.StockHistoricalDataClient"
    ):
        mock_trading_cls.return_value.close_position.return_value = MagicMock(
            id="close-ord-1", qty="10",
        )
        client = AlpacaClient(
            api_key="PK", secret_key="s",
            base_url="https://paper-api.alpaca.markets",
        )
        result = client.close_position("XLK")

    assert result == {"order_id": "close-ord-1", "qty": "10"}
    mock_trading_cls.return_value.close_position.assert_called_once_with("XLK")
