import pytest
from unittest.mock import patch, MagicMock
from src.data.oanda_fetcher import OandaDataFetcher

def test_fetcher_constructs_correct_url():
    fetcher = OandaDataFetcher(api_token="test", environment="practice")
    assert fetcher.base_url == "https://api-fxpractice.oanda.com/v3"

@patch("src.data.oanda_fetcher.requests.get")
def test_fetch_candles(mock_get):
    mock_get.return_value.json.return_value = {
        "candles": [
            {"time": "2024-01-01T00:00:00Z", "mid": {"o": "150.0", "h": "151.0", "l": "149.0", "c": "150.5"}, "volume": 1000},
            {"time": "2024-01-01T01:00:00Z", "mid": {"o": "150.5", "h": "151.5", "l": "150.0", "c": "151.0"}, "volume": 1200},
        ]
    }
    mock_get.return_value.status_code = 200
    fetcher = OandaDataFetcher(api_token="test", environment="practice")
    df = fetcher.fetch_candles("USD_JPY", granularity="H1", count=2)
    assert len(df) == 2
    assert "open" in df.columns
    assert "close" in df.columns
    assert df.iloc[0]["open"] == 150.0

@patch("src.data.oanda_fetcher.requests.get")
def test_fetch_to_csv(mock_get, tmp_path):
    mock_get.return_value.json.return_value = {
        "candles": [
            {"time": "2024-01-01T00:00:00Z", "mid": {"o": "150.0", "h": "151.0", "l": "149.0", "c": "150.5"}, "volume": 1000},
        ]
    }
    mock_get.return_value.status_code = 200
    fetcher = OandaDataFetcher(api_token="test", environment="practice")
    output_file = tmp_path / "test.csv"
    fetcher.fetch_to_csv("USD_JPY", str(output_file), granularity="H1", count=1)
    assert output_file.exists()
    content = output_file.read_text()
    assert "datetime" in content
    assert "150.0" in content
