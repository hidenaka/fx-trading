import pandas as pd
from src.config.settings import Settings
from src.data.loader import DataLoader
from src.broker.oanda_client import OandaClient
from unittest.mock import patch


def test_settings_parses_multiple_pairs(monkeypatch):
    monkeypatch.setenv("CURRENCY_PAIRS", "USD_JPY,EUR_USD,GBP_JPY")
    monkeypatch.setenv("OANDA_API_TOKEN", "test")
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "test")
    settings = Settings()
    assert settings.currency_pairs == ["USD_JPY", "EUR_USD", "GBP_JPY"]


def test_loader_loads_multiple():
    loader = DataLoader(data_dir="data")
    # Only sample exists, but test the method works
    result = loader.load_multiple(["sample"], "usdjpy_1h")
    assert "sample" in result
    assert isinstance(result["sample"], pd.DataFrame)


@patch("src.broker.oanda_client.requests.get")
def test_client_fetches_multiple_prices(mock_get):
    mock_get.return_value.json.return_value = {
        "prices": [
            {"instrument": "USD_JPY", "closeoutBid": "145.50", "closeoutAsk": "145.52"},
            {"instrument": "EUR_USD", "closeoutBid": "1.0850", "closeoutAsk": "1.0852"},
        ]
    }
    mock_get.return_value.status_code = 200
    client = OandaClient(api_token="test", account_id="acc", environment="practice")
    prices = client.get_multiple_prices(["USD_JPY", "EUR_USD"])
    assert "USD_JPY" in prices
    assert "EUR_USD" in prices
    assert prices["USD_JPY"]["bid"] == 145.50
