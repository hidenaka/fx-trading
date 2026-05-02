"""Alpaca SDK の薄いラッパー."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest, StopLossRequest, TakeProfitRequest


class AlpacaClient:
    """Trading API と Market Data API の薄いラッパー.

    Paper / Live の差分は base_url の "paper-api" の有無で判定する。
    """

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        base_url: str = "https://paper-api.alpaca.markets",
    ) -> None:
        is_paper = "paper-api" in base_url
        self._trading = TradingClient(api_key, secret_key, paper=is_paper)
        self._data = StockHistoricalDataClient(api_key, secret_key)

    def get_account(self) -> dict[str, Any]:
        """口座情報を辞書で返す."""
        a = self._trading.get_account()
        return {
            "account_number": a.account_number,
            "status": str(a.status),
            "currency": a.currency,
            "cash": float(a.cash),
            "equity": float(a.equity),
            "buying_power": float(a.buying_power),
            "pattern_day_trader": bool(a.pattern_day_trader),
        }

    def get_historical_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe_minutes: int,
    ) -> pd.DataFrame:
        """過去のバー（OHLCV）を pandas DataFrame で返す.

        Args:
            symbol: ティッカー（例 "SPY"）
            start: 開始時刻（UTC tz aware）
            end: 終了時刻（UTC tz aware）
            timeframe_minutes: 1, 5, 15, 60, または 1440 (=日足)
        """
        if timeframe_minutes == 1:
            tf = TimeFrame(1, TimeFrameUnit.Minute)
        elif timeframe_minutes == 5:
            tf = TimeFrame(5, TimeFrameUnit.Minute)
        elif timeframe_minutes == 15:
            tf = TimeFrame(15, TimeFrameUnit.Minute)
        elif timeframe_minutes == 60:
            tf = TimeFrame(1, TimeFrameUnit.Hour)
        elif timeframe_minutes == 1440:
            tf = TimeFrame(1, TimeFrameUnit.Day)
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe_minutes} minutes")

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=start,
            end=end,
        )
        bars = self._data.get_stock_bars(request)
        df = bars.df
        # MultiIndex (symbol, timestamp) を timestamp だけに reduce
        if isinstance(df.index, pd.MultiIndex):
            df = df.reset_index(level=0, drop=True)
        return df

    def submit_bracket_buy(
        self,
        symbol: str,
        qty: int,
        stop_price: float,
        target_price: float,
    ) -> dict[str, str]:
        """Submit a bracket BUY: market entry + stop + take-profit children."""
        req = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=round(float(target_price), 2)),
            stop_loss=StopLossRequest(stop_price=round(float(stop_price), 2)),
        )
        order = self._trading.submit_order(req)
        return {
            "entry_order_id": str(order.id),
            "client_order_id": str(order.client_order_id),
        }
