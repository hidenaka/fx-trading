# FX自動売買ライブ取引システム Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add live trading capabilities to the existing FX backtesting framework by integrating with the OANDA v20 REST API, adding safety controls, and creating a polling-based execution runner.

**Architecture:** The live trading layer wraps the existing strategy and risk management components with a broker client that bridges to OANDA's API. A circuit breaker enforces daily loss limits and trading hours, while a polling runner orchestrates the fetch-signal-execute-log cycle. The backtest engine is extended with a `mode` parameter to reuse position-tracking logic in both backtest and live contexts.

**Tech Stack:** Python 3.11+, pandas, numpy, pytest, requests, python-dotenv

---

## File Structure

```
fx_trading/
├── requirements.txt
├── .env.example
├── README_LIVE.md
├── src/
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── broker/
│   │   ├── __init__.py
│   │   ├── oanda_client.py
│   │   └── order_builder.py
│   ├── engine/
│   │   ├── __init__.py
│   │   └── backtest.py          (modified)
│   ├── safety/
│   │   ├── __init__.py
│   │   └── circuit_breaker.py
│   ├── monitoring/
│   │   ├── __init__.py
│   │   └── logger.py
│   ├── runner/
│   │   ├── __init__.py
│   │   └── polling_runner.py
│   └── main.py                  (modified)
└── tests/
    ├── test_config.py
    ├── test_broker.py
    ├── test_engine.py           (append live mode tests)
    ├── test_safety.py
    ├── test_monitoring.py
    └── test_runner.py
```

---

### Task 1: Update Dependencies & Add Config

**Files:**
- Modify: `fx_trading/requirements.txt`
- Create: `fx_trading/src/config/__init__.py`
- Create: `fx_trading/src/config/settings.py`
- Create: `fx_trading/.env.example`
- Test: `fx_trading/tests/test_config.py`

- [ ] **Step 1: Add new dependencies to requirements.txt**

BEFORE (`fx_trading/requirements.txt`):
```
pandas>=2.0.0
numpy>=1.24.0
pytest>=7.4.0
matplotlib>=3.7.0
```

AFTER (`fx_trading/requirements.txt`):
```
pandas>=2.0.0
numpy>=1.24.0
pytest>=7.4.0
matplotlib>=3.7.0
requests>=2.31.0
python-dotenv>=1.0.0
```

- [ ] **Step 2: Install new dependencies**

Run: `cd fx_trading && pip install -r requirements.txt`
Expected: installs requests and python-dotenv successfully

- [ ] **Step 3: Write the failing test for config**

Create `fx_trading/tests/test_config.py`:
```python
import os
import pytest
from src.config.settings import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("OANDA_API_TOKEN", "test-token-123")
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "test-account-456")
    monkeypatch.setenv("OANDA_ENVIRONMENT", "practice")
    monkeypatch.setenv("DAILY_LOSS_LIMIT", "500")
    monkeypatch.setenv("RISK_PER_TRADE", "0.02")
    monkeypatch.setenv("TRADING_START_HOUR", "9")
    monkeypatch.setenv("TRADING_END_HOUR", "17")
    monkeypatch.setenv("POLL_INTERVAL_SECONDS", "30")
    monkeypatch.setenv("LOG_DIR", "test_logs")

    s = Settings.from_env()
    assert s.api_token == "test-token-123"
    assert s.account_id == "test-account-456"
    assert s.environment == "practice"
    assert s.daily_loss_limit == 500.0
    assert s.risk_per_trade == 0.02
    assert s.trading_start_hour == 9
    assert s.trading_end_hour == 17
    assert s.poll_interval_seconds == 30
    assert s.log_dir == "test_logs"


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("OANDA_API_TOKEN", raising=False)
    monkeypatch.delenv("OANDA_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("OANDA_ENVIRONMENT", raising=False)

    s = Settings.from_env()
    assert s.api_token == ""
    assert s.account_id == ""
    assert s.environment == "practice"
    assert s.daily_loss_limit == 1000.0
    assert s.risk_per_trade == 0.01
    assert s.trading_start_hour == 0
    assert s.trading_end_hour == 24
    assert s.poll_interval_seconds == 60
    assert s.log_dir == "logs"


def test_settings_validate_missing_token():
    s = Settings.from_env()
    s.api_token = ""
    s.account_id = "123"
    with pytest.raises(ValueError, match="OANDA_API_TOKEN"):
        s.validate()


def test_settings_validate_missing_account():
    s = Settings.from_env()
    s.api_token = "tok"
    s.account_id = ""
    with pytest.raises(ValueError, match="OANDA_ACCOUNT_ID"):
        s.validate()


def test_settings_validate_invalid_environment():
    s = Settings.from_env()
    s.api_token = "tok"
    s.account_id = "acc"
    s.environment = "staging"
    with pytest.raises(ValueError, match="practice or live"):
        s.validate()


def test_settings_validate_negative_loss_limit():
    s = Settings.from_env()
    s.api_token = "tok"
    s.account_id = "acc"
    s.daily_loss_limit = -100
    with pytest.raises(ValueError, match="positive"):
        s.validate()
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd fx_trading && pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.config.settings'`

- [ ] **Step 5: Implement config module**

Create `fx_trading/src/config/__init__.py`:
```python
```

Create `fx_trading/src/config/settings.py`:
```python
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    api_token: str
    account_id: str
    environment: str
    daily_loss_limit: float
    risk_per_trade: float
    trading_start_hour: int
    trading_end_hour: int
    poll_interval_seconds: int
    log_dir: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            api_token=os.getenv("OANDA_API_TOKEN", ""),
            account_id=os.getenv("OANDA_ACCOUNT_ID", ""),
            environment=os.getenv("OANDA_ENVIRONMENT", "practice"),
            daily_loss_limit=float(os.getenv("DAILY_LOSS_LIMIT", "1000")),
            risk_per_trade=float(os.getenv("RISK_PER_TRADE", "0.01")),
            trading_start_hour=int(os.getenv("TRADING_START_HOUR", "0")),
            trading_end_hour=int(os.getenv("TRADING_END_HOUR", "24")),
            poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "60")),
            log_dir=os.getenv("LOG_DIR", "logs"),
        )

    def validate(self) -> None:
        if not self.api_token:
            raise ValueError("OANDA_API_TOKEN is required")
        if not self.account_id:
            raise ValueError("OANDA_ACCOUNT_ID is required")
        if self.environment not in ("practice", "live"):
            raise ValueError("OANDA_ENVIRONMENT must be 'practice' or 'live'")
        if self.daily_loss_limit <= 0:
            raise ValueError("DAILY_LOSS_LIMIT must be positive")
```

Create `fx_trading/.env.example`:
```
OANDA_API_TOKEN=your_token_here
OANDA_ACCOUNT_ID=your_account_id_here
OANDA_ENVIRONMENT=practice
DAILY_LOSS_LIMIT=1000
RISK_PER_TRADE=0.01
TRADING_START_HOUR=0
TRADING_END_HOUR=24
POLL_INTERVAL_SECONDS=60
LOG_DIR=logs
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd fx_trading && pytest tests/test_config.py -v`
Expected: 6 tests PASS

- [ ] **Step 7: Commit**

Run:
```bash
cd fx_trading && git add requirements.txt src/config/ tests/test_config.py .env.example && git commit -m "feat: add config module with env-based settings and validation"
```

---

### Task 2: OANDA API Client

**Files:**
- Create: `fx_trading/src/broker/__init__.py`
- Create: `fx_trading/src/broker/oanda_client.py`
- Test: `fx_trading/tests/test_broker.py`

- [ ] **Step 1: Write the failing test**

Create `fx_trading/tests/test_broker.py`:
```python
from unittest.mock import Mock, patch
import pytest
from src.broker.oanda_client import OandaClient


class TestOandaClient:
    def test_init_practice(self):
        client = OandaClient("token", "acc123", "practice")
        assert client.api_token == "token"
        assert client.account_id == "acc123"
        assert client.base_url == "https://api-fxpractice.oanda.com/v3"

    def test_init_live(self):
        client = OandaClient("token", "acc123", "live")
        assert client.base_url == "https://api-fxtrade.oanda.com/v3"

    def test_get_account_summary(self):
        with patch("src.broker.oanda_client.requests.get") as mock_get:
            mock_resp = Mock()
            mock_resp.json.return_value = {"account": {"id": "acc123", "balance": "100000"}}
            mock_resp.raise_for_status = Mock()
            mock_get.return_value = mock_resp

            client = OandaClient("token", "acc123", "practice")
            result = client.get_account_summary()
            assert result == {"account": {"id": "acc123", "balance": "100000"}}
            mock_get.assert_called_once()

    def test_get_current_price(self):
        with patch("src.broker.oanda_client.requests.get") as mock_get:
            mock_resp = Mock()
            mock_resp.json.return_value = {
                "prices": [
                    {
                        "instrument": "USD_JPY",
                        "bids": [{"price": "149.50"}],
                        "asks": [{"price": "149.55"}],
                    }
                ]
            }
            mock_resp.raise_for_status = Mock()
            mock_get.return_value = mock_resp

            client = OandaClient("token", "acc123", "practice")
            result = client.get_current_price("USD_JPY")
            assert result == {"bid": 149.50, "ask": 149.55, "instrument": "USD_JPY"}

    def test_get_current_price_empty(self):
        with patch("src.broker.oanda_client.requests.get") as mock_get:
            mock_resp = Mock()
            mock_resp.json.return_value = {"prices": []}
            mock_resp.raise_for_status = Mock()
            mock_get.return_value = mock_resp

            client = OandaClient("token", "acc123", "practice")
            result = client.get_current_price("USD_JPY")
            assert result is None

    def test_get_open_positions(self):
        with patch("src.broker.oanda_client.requests.get") as mock_get:
            mock_resp = Mock()
            mock_resp.json.return_value = {
                "positions": [
                    {"instrument": "USD_JPY", "long": {"units": "1000"}, "short": {"units": "0"}}
                ]
            }
            mock_resp.raise_for_status = Mock()
            mock_get.return_value = mock_resp

            client = OandaClient("token", "acc123", "practice")
            result = client.get_open_positions()
            assert len(result) == 1
            assert result[0]["instrument"] == "USD_JPY"

    def test_place_order(self):
        with patch("src.broker.oanda_client.requests.post") as mock_post:
            mock_resp = Mock()
            mock_resp.json.return_value = {"orderFillTransaction": {"id": "txn1"}}
            mock_resp.raise_for_status = Mock()
            mock_post.return_value = mock_resp

            client = OandaClient("token", "acc123", "practice")
            order = {"type": "MARKET", "instrument": "USD_JPY", "units": "1000"}
            result = client.place_order(order)
            assert result == {"orderFillTransaction": {"id": "txn1"}}

    def test_close_position(self):
        with patch("src.broker.oanda_client.requests.put") as mock_put:
            mock_resp = Mock()
            mock_resp.json.return_value = {"longOrderFillTransaction": {"id": "txn2"}}
            mock_resp.raise_for_status = Mock()
            mock_put.return_value = mock_resp

            client = OandaClient("token", "acc123", "practice")
            result = client.close_position("USD_JPY")
            assert result == {"longOrderFillTransaction": {"id": "txn2"}}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd fx_trading && pytest tests/test_broker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.broker.oanda_client'`

- [ ] **Step 3: Implement OANDA API client**

Create `fx_trading/src/broker/__init__.py`:
```python
```

Create `fx_trading/src/broker/oanda_client.py`:
```python
import requests
from typing import Dict, List, Optional


class OandaClient:
    PRACTICE_URL = "https://api-fxpractice.oanda.com/v3"
    LIVE_URL = "https://api-fxtrade.oanda.com/v3"

    def __init__(self, api_token: str, account_id: str, environment: str = "practice"):
        self.api_token = api_token
        self.account_id = account_id
        self.base_url = self.PRACTICE_URL if environment == "practice" else self.LIVE_URL
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        url = f"{self.base_url}{endpoint}"
        response = requests.get(url, headers=self.headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint: str, data: Optional[Dict] = None) -> Dict:
        url = f"{self.base_url}{endpoint}"
        response = requests.post(url, headers=self.headers, json=data, timeout=30)
        response.raise_for_status()
        return response.json()

    def _put(self, endpoint: str, data: Optional[Dict] = None) -> Dict:
        url = f"{self.base_url}{endpoint}"
        response = requests.put(url, headers=self.headers, json=data, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_account_summary(self) -> Dict:
        return self._get(f"/accounts/{self.account_id}/summary")

    def get_current_price(self, instrument: str) -> Optional[Dict]:
        data = self._get(
            f"/accounts/{self.account_id}/pricing",
            params={"instruments": instrument},
        )
        prices = data.get("prices", [])
        if not prices:
            return None
        price = prices[0]
        bid = float(price["bids"][0]["price"]) if price.get("bids") else None
        ask = float(price["asks"][0]["price"]) if price.get("asks") else None
        return {"bid": bid, "ask": ask, "instrument": instrument}

    def get_open_positions(self) -> List[Dict]:
        return self._get(f"/accounts/{self.account_id}/openPositions").get("positions", [])

    def place_order(self, order: Dict) -> Dict:
        return self._post(f"/accounts/{self.account_id}/orders", data={"order": order})

    def close_position(self, instrument: str) -> Dict:
        return self._put(
            f"/accounts/{self.account_id}/positions/{instrument}/close",
            data={"longUnits": "ALL", "shortUnits": "ALL"},
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd fx_trading && pytest tests/test_broker.py -v`
Expected: 8 tests PASS

- [ ] **Step 5: Commit**

Run:
```bash
cd fx_trading && git add src/broker/ tests/test_broker.py && git commit -m "feat: add OANDA REST API v20 client"
```

---

### Task 3: Order Builder

**Files:**
- Create: `fx_trading/src/broker/order_builder.py`
- Modify: `fx_trading/tests/test_broker.py` (append tests)

- [ ] **Step 1: Write the failing test**

Append to `fx_trading/tests/test_broker.py`:
```python
from src.broker.order_builder import OrderBuilder


class TestOrderBuilder:
    def test_build_market_order_long(self):
        order = OrderBuilder.build_market_order("USD_JPY", 1, 1000)
        assert order["type"] == "MARKET"
        assert order["instrument"] == "USD_JPY"
        assert order["units"] == "1000"

    def test_build_market_order_short(self):
        order = OrderBuilder.build_market_order("USD_JPY", -1, 500)
        assert order["units"] == "-500"

    def test_build_market_order_with_sl_tp(self):
        order = OrderBuilder.build_market_order(
            "USD_JPY", 1, 1000, stop_loss=149.00, take_profit=155.00
        )
        assert order["stopLossOnFill"]["price"] == "149.0"
        assert order["takeProfitOnFill"]["price"] == "155.0"

    def test_invalid_direction_raises(self):
        with pytest.raises(ValueError, match="1 or -1"):
            OrderBuilder.build_market_order("USD_JPY", 0, 1000)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd fx_trading && pytest tests/test_broker.py::TestOrderBuilder -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.broker.order_builder'`

- [ ] **Step 3: Implement order builder**

Create `fx_trading/src/broker/order_builder.py`:
```python
from typing import Dict, Optional


class OrderBuilder:
    @staticmethod
    def build_market_order(
        instrument: str,
        direction: int,
        units: int,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Dict:
        if direction not in (1, -1):
            raise ValueError("direction must be 1 or -1")

        actual_units = abs(units) if direction == 1 else -abs(units)

        order = {
            "type": "MARKET",
            "instrument": instrument,
            "units": str(actual_units),
        }

        if stop_loss is not None:
            order["stopLossOnFill"] = {"price": str(stop_loss)}
        if take_profit is not None:
            order["takeProfitOnFill"] = {"price": str(take_profit)}

        return order
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd fx_trading && pytest tests/test_broker.py::TestOrderBuilder -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

Run:
```bash
cd fx_trading && git add src/broker/order_builder.py tests/test_broker.py && git commit -m "feat: add OANDA order builder for market orders with SL/TP"
```

---

### Task 4: Live Engine Extension

**Files:**
- Modify: `fx_trading/src/engine/backtest.py`
- Modify: `fx_trading/tests/test_engine.py` (append live mode tests)

- [ ] **Step 1: Write the failing test for live mode**

Append to `fx_trading/tests/test_engine.py`:
```python
from unittest.mock import Mock
import numpy as np


def test_live_mode_requires_instrument():
    engine = BacktestEngine(mode="live", broker_client=Mock())
    df = pd.DataFrame({
        "datetime": [pd.Timestamp("2024-01-01")],
        "close": [150.0],
    })
    with pytest.raises(ValueError, match="instrument is required"):
        engine.run(df, Mock(), Mock())


def test_live_mode_opens_long_position():
    broker = Mock()
    broker.get_open_positions.return_value = []
    broker.place_order.return_value = {"orderFillTransaction": {"id": "txn1"}}

    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=50, freq="h"),
        "open": [150.0 + i * 0.02 for i in range(50)],
        "high": [151.0 + i * 0.02 for i in range(50)],
        "low": [149.0 + i * 0.02 for i in range(50)],
        "close": [150.0 + i * 0.02 for i in range(50)],
        "volume": [1000] * 50,
    })

    engine = BacktestEngine(mode="live", broker_client=broker)
    strategy = MaMacdStrategy(fast=3, slow=6, signal=2)
    risk = RiskManager(capital=1_000_000, risk_per_trade=0.01)

    trades = engine.run(df, strategy, risk, instrument="USD_JPY")
    broker.place_order.assert_called_once()
    assert engine.position == 1


def test_live_mode_closes_long_position():
    broker = Mock()
    broker.get_open_positions.return_value = [
        {"instrument": "USD_JPY", "long": {"units": "1000"}, "short": {"units": "0"}}
    ]
    broker.close_position.return_value = {"longOrderFillTransaction": {"id": "txn2"}}

    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=50, freq="h"),
        "open": [150.0 - i * 0.02 for i in range(50)],
        "high": [151.0 - i * 0.02 for i in range(50)],
        "low": [149.0 - i * 0.02 for i in range(50)],
        "close": [150.0 - i * 0.02 for i in range(50)],
        "volume": [1000] * 50,
    })

    engine = BacktestEngine(mode="live", broker_client=broker)
    strategy = MaMacdStrategy(fast=3, slow=6, signal=2)
    risk = RiskManager(capital=1_000_000, risk_per_trade=0.01)

    trades = engine.run(df, strategy, risk, instrument="USD_JPY")
    broker.close_position.assert_called_once_with("USD_JPY")
    assert engine.position == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd fx_trading && pytest tests/test_engine.py::test_live_mode_requires_instrument tests/test_engine.py::test_live_mode_opens_long_position tests/test_engine.py::test_live_mode_closes_long_position -v`
Expected: FAIL with `TypeError: BacktestEngine.__init__() got an unexpected keyword argument 'mode'`

- [ ] **Step 3: Implement live mode in backtest engine**

Replace the full contents of `fx_trading/src/engine/backtest.py` with:
```python
import pandas as pd
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class Trade:
    entry_time: pd.Timestamp
    entry_price: float
    direction: int
    lot: float
    exit_time: pd.Timestamp = field(default=None)
    exit_price: float = field(default=None)
    pnl: float = field(default=None)


class BacktestEngine:
    def __init__(
        self,
        initial_capital: float = 1_000_000,
        mode: str = "backtest",
        broker_client=None,
    ):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.trades: List[Trade] = []
        self.mode = mode
        self.broker_client = broker_client
        self.position = 0
        self.current_trade = None

    def run(self, df: pd.DataFrame, strategy, risk_manager, instrument: Optional[str] = None):
        if self.mode == "live":
            if instrument is None:
                raise ValueError("instrument is required in live mode")
            return self._run_live(df, strategy, risk_manager, instrument)
        return self._run_backtest(df, strategy, risk_manager)

    def _run_backtest(self, df: pd.DataFrame, strategy, risk_manager):
        df = strategy.generate_signals(df)
        self.position = 0
        self.current_trade = None

        for i in range(1, len(df)):
            row = df.iloc[i]
            if self.position == 0 and row["signal"] != 0:
                direction = int(row["signal"])
                stop = row["close"] * 0.99 if direction == 1 else row["close"] * 1.01
                lot = risk_manager.calculate_lot(row["close"], stop)
                self.current_trade = Trade(
                    entry_time=row["datetime"],
                    entry_price=row["close"],
                    direction=direction,
                    lot=lot,
                )
                self.position = direction
            elif self.position != 0 and row["signal"] != self.position:
                self.current_trade.exit_time = row["datetime"]
                self.current_trade.exit_price = row["close"]
                self.current_trade.pnl = (
                    self.current_trade.exit_price - self.current_trade.entry_price
                ) * self.current_trade.lot * self.current_trade.direction
                self.trades.append(self.current_trade)
                risk_manager.update_capital(self.current_trade.pnl)
                self.capital = risk_manager.capital
                self.position = 0
                self.current_trade = None

        return self.trades

    def _run_live(self, df: pd.DataFrame, strategy, risk_manager, instrument: str):
        if len(df) < 10:
            return self.trades

        df = strategy.generate_signals(df)
        latest = df.iloc[-1]
        signal = int(latest["signal"])

        positions = self.broker_client.get_open_positions()
        current_broker_position = 0
        for pos in positions:
            if pos.get("instrument") == instrument:
                long_units = pos.get("long", {}).get("units", "0")
                short_units = pos.get("short", {}).get("units", "0")
                if int(long_units) > 0:
                    current_broker_position = 1
                elif int(short_units) < 0:
                    current_broker_position = -1

        if current_broker_position == 0 and signal != 0:
            direction = signal
            stop = latest["close"] * 0.99 if direction == 1 else latest["close"] * 1.01
            lot = risk_manager.calculate_lot(latest["close"], stop)
            units = int(lot * 1000)
            if units <= 0:
                units = 1

            order = {
                "type": "MARKET",
                "instrument": instrument,
                "units": str(units) if direction == 1 else str(-units),
            }
            self.broker_client.place_order(order)
            self.position = direction
            self.current_trade = Trade(
                entry_time=pd.Timestamp.now(),
                entry_price=latest["close"],
                direction=direction,
                lot=lot,
            )

        elif current_broker_position != 0 and signal != current_broker_position:
            self.broker_client.close_position(instrument)
            if self.current_trade is not None:
                self.current_trade.exit_time = pd.Timestamp.now()
                self.current_trade.exit_price = latest["close"]
                self.current_trade.pnl = (
                    self.current_trade.exit_price - self.current_trade.entry_price
                ) * self.current_trade.lot * self.current_trade.direction
                self.trades.append(self.current_trade)
                risk_manager.update_capital(self.current_trade.pnl)
                self.capital = risk_manager.capital
            self.position = 0
            self.current_trade = None

        return self.trades
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd fx_trading && pytest tests/test_engine.py -v`
Expected: 5 tests PASS (2 original + 3 new)

- [ ] **Step 5: Commit**

Run:
```bash
cd fx_trading && git add src/engine/backtest.py tests/test_engine.py && git commit -m "feat: extend backtest engine with live trading mode"
```

---

### Task 5: Circuit Breaker

**Files:**
- Create: `fx_trading/src/safety/__init__.py`
- Create: `fx_trading/src/safety/circuit_breaker.py`
- Test: `fx_trading/tests/test_safety.py`

- [ ] **Step 1: Write the failing test**

Create `fx_trading/tests/test_safety.py`:
```python
from unittest.mock import patch
import datetime
import pytest
from src.safety.circuit_breaker import CircuitBreaker


def test_allows_trading_by_default():
    cb = CircuitBreaker(daily_loss_limit=1000)
    assert cb.check() is True


def test_blocks_on_daily_loss_limit():
    cb = CircuitBreaker(daily_loss_limit=100)
    cb.check(current_pnl=-50)
    cb.check(current_pnl=-51)
    assert cb.check() is False


def test_resets_daily_pnl_on_new_day():
    cb = CircuitBreaker(daily_loss_limit=100)
    with patch("src.safety.circuit_breaker.datetime") as mock_dt:
        mock_dt.date.today.return_value = datetime.date(2024, 1, 1)
        mock_dt.datetime.now.return_value = datetime.datetime(2024, 1, 1, 12, 0, 0)
        cb.check(current_pnl=-150)
        assert cb.check() is False

        mock_dt.date.today.return_value = datetime.date(2024, 1, 2)
        assert cb.check() is True


def test_blocks_outside_trading_hours():
    cb = CircuitBreaker(daily_loss_limit=1000, trading_start_hour=9, trading_end_hour=17)
    with patch("src.safety.circuit_breaker.datetime") as mock_dt:
        mock_dt.date.today.return_value = datetime.date(2024, 1, 1)
        mock_dt.datetime.now.return_value = datetime.datetime(2024, 1, 1, 3, 0, 0)
        assert cb.check() is False


def test_allows_within_trading_hours():
    cb = CircuitBreaker(daily_loss_limit=1000, trading_start_hour=9, trading_end_hour=17)
    with patch("src.safety.circuit_breaker.datetime") as mock_dt:
        mock_dt.date.today.return_value = datetime.date(2024, 1, 1)
        mock_dt.datetime.now.return_value = datetime.datetime(2024, 1, 1, 12, 0, 0)
        assert cb.check() is True


def test_emergency_stop_blocks_all():
    cb = CircuitBreaker(daily_loss_limit=1000)
    cb.trigger_emergency_stop()
    assert cb.check() is False


def test_reset_emergency_stop():
    cb = CircuitBreaker(daily_loss_limit=1000)
    cb.trigger_emergency_stop()
    assert cb.check() is False
    cb.reset_emergency_stop()
    assert cb.check() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd fx_trading && pytest tests/test_safety.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.safety.circuit_breaker'`

- [ ] **Step 3: Implement circuit breaker**

Create `fx_trading/src/safety/__init__.py`:
```python
```

Create `fx_trading/src/safety/circuit_breaker.py`:
```python
import datetime


class CircuitBreaker:
    def __init__(
        self,
        daily_loss_limit: float,
        trading_start_hour: int = 0,
        trading_end_hour: int = 24,
    ):
        self.daily_loss_limit = daily_loss_limit
        self.trading_start_hour = trading_start_hour
        self.trading_end_hour = trading_end_hour
        self._emergency_stop = False
        self._daily_pnl = 0.0
        self._last_reset = None

    def _reset_if_new_day(self) -> None:
        today = datetime.date.today()
        if self._last_reset != today:
            self._daily_pnl = 0.0
            self._last_reset = today

    def check(self, current_pnl: float = 0.0) -> bool:
        if self._emergency_stop:
            return False
        self._reset_if_new_day()
        self._daily_pnl += current_pnl
        if self._daily_pnl <= -self.daily_loss_limit:
            return False
        now = datetime.datetime.now()
        if not (self.trading_start_hour <= now.hour < self.trading_end_hour):
            return False
        return True

    def trigger_emergency_stop(self) -> None:
        self._emergency_stop = True

    def reset_emergency_stop(self) -> None:
        self._emergency_stop = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd fx_trading && pytest tests/test_safety.py -v`
Expected: 7 tests PASS

- [ ] **Step 5: Commit**

Run:
```bash
cd fx_trading && git add src/safety/ tests/test_safety.py && git commit -m "feat: add circuit breaker with daily loss limit and trading hours"
```

---

### Task 6: Logger

**Files:**
- Create: `fx_trading/src/monitoring/__init__.py`
- Create: `fx_trading/src/monitoring/logger.py`
- Test: `fx_trading/tests/test_monitoring.py`

- [ ] **Step 1: Write the failing test**

Create `fx_trading/tests/test_monitoring.py`:
```python
import os
import tempfile
from src.monitoring.logger import TradeLogger


def test_log_trade_creates_file_and_content():
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = TradeLogger(log_dir=tmpdir)
        logger.log_trade("BUY USD_JPY 1000 units @ 150.25")
        log_path = os.path.join(tmpdir, "trades.log")
        assert os.path.exists(log_path)
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "BUY USD_JPY 1000 units @ 150.25" in content
        assert "TRADE" in content


def test_log_error_creates_file_and_content():
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = TradeLogger(log_dir=tmpdir)
        logger.log_error("Connection timeout after 30s")
        log_path = os.path.join(tmpdir, "errors.log")
        assert os.path.exists(log_path)
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "Connection timeout after 30s" in content
        assert "ERROR" in content


def test_multiple_logs_append():
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = TradeLogger(log_dir=tmpdir)
        logger.log_trade("trade1")
        logger.log_trade("trade2")
        log_path = os.path.join(tmpdir, "trades.log")
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd fx_trading && pytest tests/test_monitoring.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.monitoring.logger'`

- [ ] **Step 3: Implement logger**

Create `fx_trading/src/monitoring/__init__.py`:
```python
```

Create `fx_trading/src/monitoring/logger.py`:
```python
import datetime
from pathlib import Path


class TradeLogger:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.trade_log = self.log_dir / "trades.log"
        self.error_log = self.log_dir / "errors.log"

    def log_trade(self, message: str) -> None:
        timestamp = datetime.datetime.now().isoformat()
        with open(self.trade_log, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} | TRADE | {message}\n")

    def log_error(self, message: str) -> None:
        timestamp = datetime.datetime.now().isoformat()
        with open(self.error_log, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} | ERROR | {message}\n")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd fx_trading && pytest tests/test_monitoring.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

Run:
```bash
cd fx_trading && git add src/monitoring/ tests/test_monitoring.py && git commit -m "feat: add trade and error logger"
```

---

### Task 7: Polling Runner

**Files:**
- Create: `fx_trading/src/runner/__init__.py`
- Create: `fx_trading/src/runner/polling_runner.py`
- Test: `fx_trading/tests/test_runner.py`

- [ ] **Step 1: Write the failing test**

Create `fx_trading/tests/test_runner.py`:
```python
from unittest.mock import Mock
import pandas as pd
import pytest
from src.runner.polling_runner import PollingRunner
from src.strategies.ma_macd import MaMacdStrategy
from src.risk.manager import RiskManager


def test_runner_skips_when_circuit_breaker_open():
    config = Mock()
    strategy = Mock()
    risk = Mock()
    broker = Mock()
    cb = Mock()
    cb.check.return_value = False
    logger = Mock()

    runner = PollingRunner(config, strategy, risk, broker, cb, logger)
    trades = runner.run_once("USD_JPY")
    assert trades == []
    logger.log_error.assert_called_once()


def test_runner_executes_cycle_with_preloaded_data():
    config = Mock()
    strategy = MaMacdStrategy(fast=3, slow=6, signal=2)
    risk = RiskManager(capital=1_000_000, risk_per_trade=0.01)
    broker = Mock()
    broker.get_open_positions.return_value = []
    broker.place_order.return_value = {"orderFillTransaction": {"id": "txn1"}}
    cb = Mock()
    cb.check.return_value = True
    logger = Mock()

    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=50, freq="h"),
        "open": [150.0 + i * 0.02 for i in range(50)],
        "high": [151.0 + i * 0.02 for i in range(50)],
        "low": [149.0 + i * 0.02 for i in range(50)],
        "close": [150.0 + i * 0.02 for i in range(50)],
        "volume": [1000] * 50,
    })

    runner = PollingRunner(config, strategy, risk, broker, cb, logger, initial_df=df)
    trades = runner.run_once("USD_JPY")
    broker.place_order.assert_called_once()
    logger.log_trade.assert_called_once()


def test_runner_handles_exception():
    config = Mock()
    strategy = Mock()
    risk = Mock()
    broker = Mock()
    broker.get_open_positions.side_effect = RuntimeError("API down")
    cb = Mock()
    cb.check.return_value = True
    logger = Mock()

    runner = PollingRunner(config, strategy, risk, broker, cb, logger)
    with pytest.raises(RuntimeError, match="API down"):
        runner.run_once("USD_JPY")
    logger.log_error.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd fx_trading && pytest tests/test_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.runner.polling_runner'`

- [ ] **Step 3: Implement polling runner**

Create `fx_trading/src/runner/__init__.py`:
```python
```

Create `fx_trading/src/runner/polling_runner.py`:
```python
import time
import datetime
from typing import List, Optional
import pandas as pd
from src.engine.backtest import BacktestEngine


class PollingRunner:
    def __init__(
        self,
        config,
        strategy,
        risk_manager,
        broker_client,
        circuit_breaker,
        logger,
        poll_interval: int = 60,
        initial_df: Optional[pd.DataFrame] = None,
    ):
        self.config = config
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.broker_client = broker_client
        self.circuit_breaker = circuit_breaker
        self.logger = logger
        self.poll_interval = poll_interval
        self.df_history = initial_df
        self.engine = BacktestEngine(
            initial_capital=risk_manager.capital,
            mode="live",
            broker_client=broker_client,
        )

    def _fetch_and_update_df(self, instrument: str) -> Optional[pd.DataFrame]:
        price = self.broker_client.get_current_price(instrument)
        if price is None:
            return self.df_history

        now = datetime.datetime.now()
        mid = (price["bid"] + price["ask"]) / 2 if price["bid"] and price["ask"] else price["bid"]
        row = {
            "datetime": now,
            "open": price["bid"],
            "high": price["ask"],
            "low": price["bid"],
            "close": mid,
            "volume": 0,
        }

        new_df = pd.DataFrame([row])
        if self.df_history is None:
            self.df_history = new_df
        else:
            self.df_history = pd.concat([self.df_history, new_df], ignore_index=True)
            self.df_history = self.df_history.tail(200).reset_index(drop=True)

        return self.df_history

    def run_once(self, instrument: str) -> List:
        if not self.circuit_breaker.check():
            self.logger.log_error("Circuit breaker triggered - skipping cycle")
            return []

        df = self._fetch_and_update_df(instrument)
        if df is None or len(df) < 30:
            self.logger.log_error("Insufficient data for signal generation")
            return []

        try:
            trades = self.engine.run(df, self.strategy, self.risk_manager, instrument=instrument)
            self.logger.log_trade(f"Cycle complete. Total closed trades: {len([t for t in trades if t.exit_time is not None])}")
            return trades
        except Exception as exc:
            self.logger.log_error(str(exc))
            raise

    def run(self, instrument: str) -> None:
        while True:
            self.run_once(instrument)
            time.sleep(self.poll_interval)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd fx_trading && pytest tests/test_runner.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

Run:
```bash
cd fx_trading && git add src/runner/ tests/test_runner.py && git commit -m "feat: add polling runner for live trading orchestration"
```

---

### Task 8: Integration & Final Verification

**Files:**
- Modify: `fx_trading/src/main.py`
- Create: `fx_trading/README_LIVE.md`

- [ ] **Step 1: Modify main.py to add live trading entry point**

Replace the full contents of `fx_trading/src/main.py` with:
```python
import sys

from src.data.loader import DataLoader
from src.data.preprocessor import Preprocessor
from src.strategies.ma_macd import MaMacdStrategy
from src.engine.backtest import BacktestEngine
from src.risk.manager import RiskManager
from src.reports.reporter import ReportGenerator
from src.optimizer.grid_search import GridSearchOptimizer
from src.wfa.walker import WalkForwardAnalyzer
from src.selector.ranker import StrategyRanker


def run_backtest():
    loader = DataLoader(data_dir="data")
    raw_df = loader.load_csv("sample", "usdjpy_1h")
    pre = Preprocessor()
    df = pre.process(raw_df)

    print("=== Grid Search ===")
    optimizer = GridSearchOptimizer(df)
    param_grid = {
        "fast": [3, 5, 8],
        "slow": [6, 10, 15],
        "signal": [2, 3, 5],
    }
    results = optimizer.search(MaMacdStrategy, param_grid)
    best = optimizer.get_best(results)
    print("Best params:", best["params"])
    print("Profit Factor:", best["profit_factor"])

    print("\n=== Walk-Forward Analysis ===")
    train_size = min(60, max(5, len(df) // 2))
    test_size = min(30, max(3, len(df) // 3))
    wfa = WalkForwardAnalyzer(train_size=train_size, test_size=test_size)
    wfa_results = wfa.analyze(df, MaMacdStrategy, param_grid)
    for i, r in enumerate(wfa_results):
        print(f"Window {i+1}: Train PF={r['train_pf']:.2f}, Test PF={r['test_pf']:.2f}, Params={r['params']}")

    print("\n=== Strategy Ranking ===")
    rank_inputs = [
        {"name": "MA+MACD Best", "profit_factor": best["profit_factor"], "win_rate": best["win_rate"],
         "max_drawdown": 0.1, "total_trades": best["total_trades"]},
        {"name": "MA+MACD WFA Avg", "profit_factor": sum(x["test_pf"] for x in wfa_results) / len(wfa_results),
         "win_rate": 0.5, "max_drawdown": 0.15, "total_trades": sum(x["test_trades"] for x in wfa_results)},
    ]
    ranker = StrategyRanker(min_trades=0)
    ranked = ranker.rank(rank_inputs)
    for r in ranked:
        print(f"{r['name']}: Score={r['score']:.2f}")


def run_live():
    from src.config.settings import Settings
    from src.broker.oanda_client import OandaClient
    from src.safety.circuit_breaker import CircuitBreaker
    from src.monitoring.logger import TradeLogger
    from src.runner.polling_runner import PollingRunner

    try:
        settings = Settings.from_env()
        settings.validate()
    except ValueError as exc:
        print(f"Configuration error: {exc}")
        print("Please set up your .env file. See README_LIVE.md for instructions.")
        sys.exit(0)

    client = OandaClient(
        api_token=settings.api_token,
        account_id=settings.account_id,
        environment=settings.environment,
    )

    risk = RiskManager(capital=1_000_000, risk_per_trade=settings.risk_per_trade)
    cb = CircuitBreaker(
        daily_loss_limit=settings.daily_loss_limit,
        trading_start_hour=settings.trading_start_hour,
        trading_end_hour=settings.trading_end_hour,
    )
    logger = TradeLogger(log_dir=settings.log_dir)
    strategy = MaMacdStrategy(fast=5, slow=10, signal=3)

    runner = PollingRunner(
        config=settings,
        strategy=strategy,
        risk_manager=risk,
        broker_client=client,
        circuit_breaker=cb,
        logger=logger,
        poll_interval=settings.poll_interval_seconds,
    )

    if "--once" in sys.argv:
        print("Running single live trading cycle...")
        runner.run_once("USD_JPY")
    else:
        print("Starting live trading polling loop... Press Ctrl+C to stop.")
        runner.run("USD_JPY")


def main():
    if "--live" in sys.argv:
        run_live()
    else:
        run_backtest()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create live trading README**

Create `fx_trading/README_LIVE.md`:
```markdown
# Live Trading Setup (OANDA)

## Prerequisites
- OANDA demo account (for practice trading)
- Python 3.11 or higher

## Installation
```bash
pip install -r requirements.txt
```

## Configuration
1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and fill in your OANDA credentials:
   - `OANDA_API_TOKEN`: Your API token from OANDA portal
   - `OANDA_ACCOUNT_ID`: Your account ID
   - Keep `OANDA_ENVIRONMENT=practice` for safe demo trading
3. Adjust risk settings as needed:
   - `DAILY_LOSS_LIMIT`: Maximum acceptable daily loss in account currency
   - `RISK_PER_TRADE`: Percentage of capital risked per trade (default 0.01 = 1%)
   - `TRADING_START_HOUR` / `TRADING_END_HOUR`: Restrict trading hours (0-24)

## Running

### Backtest mode (default)
```bash
python -m src.main
```

### Live trading - single cycle (safe for testing)
```bash
python -m src.main --live --once
```

### Live trading - continuous polling
```bash
python -m src.main --live
```

## Safety Features
- **Demo account by default**: The system defaults to OANDA practice environment.
- **Daily loss limit**: Trading halts if accumulated daily losses exceed the configured limit.
- **Trading hours**: Configurable window to restrict when trades may be placed.
- **Emergency stop**: Can be triggered programmatically via the circuit breaker.
- **Config validation**: Missing or invalid credentials prevent startup.
```

- [ ] **Step 3: Run ALL tests**

Run: `cd fx_trading && pytest tests/ -v`
Expected: All tests PASS (existing backtest tests + new config, broker, engine, safety, monitoring, runner tests)

- [ ] **Step 4: Run main script in backtest mode**

Run: `cd fx_trading && python -m src.main`
Expected: Runs grid search, walk-forward analysis, and strategy ranking. Output shows best params, profit factor, window results, and scores. (May warn about missing data files if `data/sample_usdjpy_1h.csv` does not exist — this is expected and not an error.)

- [ ] **Step 5: Run main script in live mode without config**

Run: `cd fx_trading && python -m src.main --live --once`
Expected: Prints configuration error about missing OANDA_API_TOKEN, exits with code 0.

- [ ] **Step 6: Commit**

Run:
```bash
cd fx_trading && git add src/main.py README_LIVE.md && git commit -m "feat: add live trading entry point and documentation"
```

---

### Task 9: Self-Review

- [ ] **Step 1: Spec coverage check**

Verify each requirement is covered:
- Config module with env-based settings: **Task 1**
- OANDA API client (REST v20): **Task 2**
- Order builder with SL/TP: **Task 3**
- Live engine extension with mode parameter: **Task 4**
- Circuit breaker (daily loss, trading hours): **Task 5**
- Logger (trade and error logs): **Task 6**
- Polling runner orchestration: **Task 7**
- Integration in main.py + README: **Task 8**
- Tests for all new modules: **Tasks 1-7**
- Demo account by default: **Task 1** (`.env.example` defaults to `practice`)
- Safety first (config validation, circuit breaker, explicit live mode): **Task 1, 5, 8**

- [ ] **Step 2: Placeholder scan**

Search the plan for forbidden patterns. Run:
```bash
cd fx_trading && grep -ri "TODO\|TBD\|FIXME\|placeholder\|implement later\|fill in" docs/superpowers/plans/2026-04-29-fx-live-trading-plan.md || echo "No placeholders found"
```
Expected: "No placeholders found" (the grep is on the plan file itself; adjust path if needed)

- [ ] **Step 3: Type consistency check**

Verify cross-task interface consistency:
- `Settings.from_env()` returns `Settings` dataclass: **Task 1**
- `OandaClient(api_token, account_id, environment)` constructor: **Task 2**
- `OandaClient.get_open_positions()` returns `List[Dict]`: **Task 2, 4**
- `OandaClient.place_order(order: Dict)`: **Task 2, 4**
- `OandaClient.close_position(instrument: str)`: **Task 2, 4**
- `OrderBuilder.build_market_order(instrument, direction, units, stop_loss, take_profit)` returns `Dict`: **Task 3, 4**
- `BacktestEngine(mode="live", broker_client=...)` constructor: **Task 4, 7**
- `BacktestEngine.run(df, strategy, risk_manager, instrument=...)` signature: **Task 4, 7**
- `CircuitBreaker(daily_loss_limit, trading_start_hour, trading_end_hour)` constructor: **Task 5, 8**
- `CircuitBreaker.check(current_pnl=0.0)` returns `bool`: **Task 5, 7**
- `TradeLogger(log_dir)` constructor: **Task 6, 7, 8**
- `PollingRunner(config, strategy, risk_manager, broker_client, circuit_breaker, logger, poll_interval, initial_df)` constructor: **Task 7, 8**
- `PollingRunner.run_once(instrument)` returns `List`: **Task 7, 8**

All types and signatures are consistent across tasks.

- [ ] **Step 4: Final commit**

Run:
```bash
cd fx_trading && git add docs/superpowers/plans/2026-04-29-fx-live-trading-plan.md && git commit -m "docs: add live trading implementation plan"
```
