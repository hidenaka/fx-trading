import pytest
from unittest.mock import patch
from src.broker.oanda_client import OandaClient

def test_client_constructs_practice_url():
    client = OandaClient(api_token="test", account_id="acc123", environment="practice")
    assert client.base_url == "https://api-fxpractice.oanda.com/v3"

def test_client_constructs_live_url():
    client = OandaClient(api_token="test", account_id="acc123", environment="live")
    assert client.base_url == "https://api-fxtrade.oanda.com/v3"

@patch("src.broker.oanda_client.requests.get")
def test_get_current_price(mock_get):
    mock_get.return_value.json.return_value = {
        "prices": [{"instrument": "USD_JPY", "closeoutBid": "145.50", "closeoutAsk": "145.52"}]
    }
    mock_get.return_value.status_code = 200
    client = OandaClient(api_token="test", account_id="acc123", environment="practice")
    price = client.get_current_price("USD_JPY")
    assert price["bid"] == 145.50
    assert price["ask"] == 145.52

@patch("src.broker.oanda_client.requests.get")
def test_get_open_positions(mock_get):
    mock_get.return_value.json.return_value = {"positions": []}
    mock_get.return_value.status_code = 200
    client = OandaClient(api_token="test", account_id="acc123", environment="practice")
    positions = client.get_open_positions()
    assert positions == []

@patch("src.broker.oanda_client.requests.post")
def test_place_order(mock_post):
    mock_post.return_value.json.return_value = {"orderFillTransaction": {"id": "123"}}
    mock_post.return_value.status_code = 201
    client = OandaClient(api_token="test", account_id="acc123", environment="practice")
    result = client.place_order({"units": "100"})
    assert result["orderFillTransaction"]["id"] == "123"

def test_get_account_summary_raises_on_error():
    with patch("src.broker.oanda_client.requests.get") as mock_get:
        mock_get.return_value.status_code = 401
        mock_get.return_value.text = "Unauthorized"
        client = OandaClient(api_token="bad", account_id="acc123", environment="practice")
        with pytest.raises(RuntimeError):
            client.get_account_summary()

from src.broker.order_builder import OrderBuilder

def test_build_market_order_long():
    builder = OrderBuilder(instrument="USD_JPY")
    order = builder.build_market_order(direction=1, units=1000, stop_loss=145.0, take_profit=147.0)
    assert order["type"] == "MARKET"
    assert order["instrument"] == "USD_JPY"
    assert order["units"] == "1000"
    assert order["stopLossOnFill"]["price"] == "145.00"
    assert order["takeProfitOnFill"]["price"] == "147.00"

def test_build_market_order_short():
    builder = OrderBuilder(instrument="USD_JPY")
    order = builder.build_market_order(direction=-1, units=1000, stop_loss=147.0, take_profit=145.0)
    assert order["units"] == "-1000"

def test_build_market_order_without_stop():
    builder = OrderBuilder(instrument="USD_JPY")
    order = builder.build_market_order(direction=1, units=500)
    assert "stopLossOnFill" not in order
    assert "takeProfitOnFill" not in order
