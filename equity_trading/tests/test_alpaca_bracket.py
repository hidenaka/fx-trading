"""Bracket order submission unit tests (mocked Alpaca SDK)."""
from unittest.mock import MagicMock, patch

import pytest


def test_submit_bracket_buy_constructs_correct_request():
    from equity_trading.src.broker.alpaca_client import AlpacaClient

    with patch(
        "equity_trading.src.broker.alpaca_client.TradingClient"
    ) as mock_trading_cls, patch(
        "equity_trading.src.broker.alpaca_client.StockHistoricalDataClient"
    ):
        mock_trading_cls.return_value.submit_order.return_value = MagicMock(
            id="parent-123",
            client_order_id="my-client-id-abc",
        )
        client = AlpacaClient(
            api_key="PKtest",
            secret_key="secret",
            base_url="https://paper-api.alpaca.markets",
        )
        result = client.submit_bracket_buy(
            symbol="XLK",
            qty=10,
            stop_price=245.50,
            target_price=252.30,
        )

    assert result == {"entry_order_id": "parent-123", "client_order_id": "my-client-id-abc"}
    # Verify the SDK was called with bracket request
    submit_call = mock_trading_cls.return_value.submit_order.call_args
    req = submit_call.args[0] if submit_call.args else submit_call.kwargs.get("order_data")
    # Some SDK versions pass via kwarg "order_data", others positionally - support both
    assert req is not None
    # Check key fields
    assert req.symbol == "XLK"
    assert req.qty == 10
    # take_profit limit and stop_loss stop should match (rounded to 2dp)
    # The SDK may store these as TakeProfitRequest / StopLossRequest objects
    assert getattr(req.take_profit, "limit_price", None) == 252.30
    assert getattr(req.stop_loss, "stop_price", None) == 245.50


def test_submit_bracket_buy_rounds_prices_to_two_decimals():
    from equity_trading.src.broker.alpaca_client import AlpacaClient

    with patch(
        "equity_trading.src.broker.alpaca_client.TradingClient"
    ) as mock_trading_cls, patch(
        "equity_trading.src.broker.alpaca_client.StockHistoricalDataClient"
    ):
        mock_trading_cls.return_value.submit_order.return_value = MagicMock(
            id="x", client_order_id="y",
        )
        client = AlpacaClient(
            api_key="PK", secret_key="s",
            base_url="https://paper-api.alpaca.markets",
        )
        client.submit_bracket_buy(
            symbol="SPY",
            qty=5,
            stop_price=599.123456,    # → 599.12
            target_price=601.987654,  # → 601.99
        )

    submit_call = mock_trading_cls.return_value.submit_order.call_args
    req = submit_call.args[0] if submit_call.args else submit_call.kwargs.get("order_data")
    assert req.stop_loss.stop_price == 599.12
    assert req.take_profit.limit_price == 601.99
