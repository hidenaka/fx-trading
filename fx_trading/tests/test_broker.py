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
