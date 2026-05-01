from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from equity_trading.src.broker.alpaca_client import AlpacaClient


def test_get_historical_bars_returns_dataframe():
    fake_bars = MagicMock()
    fake_bars.df = pd.DataFrame({
        "open": [100.0, 101.0],
        "high": [101.0, 102.0],
        "low": [99.0, 100.0],
        "close": [100.5, 101.5],
        "volume": [10000, 12000],
    })

    with patch("equity_trading.src.broker.alpaca_client.StockHistoricalDataClient") as mock_data, \
         patch("equity_trading.src.broker.alpaca_client.TradingClient"):
        mock_data.return_value.get_stock_bars.return_value = fake_bars

        client = AlpacaClient(api_key="K", secret_key="S")
        df = client.get_historical_bars(
            symbol="SPY",
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 1, 2, tzinfo=timezone.utc),
            timeframe_minutes=5,
        )

    assert len(df) == 2
    assert "close" in df.columns
    assert df["close"].iloc[0] == 100.5


def test_get_account_returns_account_dict():
    fake_account = MagicMock()
    fake_account.account_number = "PA123"
    fake_account.status = "ACTIVE"
    fake_account.currency = "USD"
    fake_account.cash = "100000"
    fake_account.equity = "100000"
    fake_account.buying_power = "200000"
    fake_account.pattern_day_trader = False

    with patch("equity_trading.src.broker.alpaca_client.TradingClient") as mock_trading, \
         patch("equity_trading.src.broker.alpaca_client.StockHistoricalDataClient"):
        mock_trading.return_value.get_account.return_value = fake_account

        client = AlpacaClient(api_key="K", secret_key="S")
        acct = client.get_account()

    assert acct["account_number"] == "PA123"
    assert acct["cash"] == 100000.0
    assert acct["equity"] == 100000.0


def test_paper_url_uses_paper_flag():
    with patch("equity_trading.src.broker.alpaca_client.TradingClient") as mock_trading, \
         patch("equity_trading.src.broker.alpaca_client.StockHistoricalDataClient"):
        AlpacaClient(api_key="K", secret_key="S", base_url="https://paper-api.alpaca.markets")

    args, kwargs = mock_trading.call_args
    assert kwargs.get("paper") is True


def test_live_url_disables_paper_flag():
    with patch("equity_trading.src.broker.alpaca_client.TradingClient") as mock_trading, \
         patch("equity_trading.src.broker.alpaca_client.StockHistoricalDataClient"):
        AlpacaClient(api_key="K", secret_key="S", base_url="https://api.alpaca.markets")

    args, kwargs = mock_trading.call_args
    assert kwargs.get("paper") is False
