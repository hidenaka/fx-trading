# FX自動売買 大規模拡張 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 複数通貨ペア対応、Webダッシュボード、機械学習予測モデルの3つの拡張を既存FX自動売買システムに追加する。

**Architecture:** 複数通貨ペアを独立に監視・取引。バックテスト結果とポートフォリオ状況をJSONにエクスポートし、HTML/Chart.jsダッシュボードで可視化。scikit-learnでML予測モデルを学習し、テクニカル戦略と組み合わせてシグナル生成。

**Tech Stack:** Python 3.11+, pandas, numpy, pytest, requests, scikit-learn, HTML5, Tailwind CSS CDN, Chart.js CDN

---

## File Structure Map

| File | Responsibility |
|------|----------------|
| `src/config/settings.py` | Multi-pair env var parsing, backward-compatible `currency_pair` |
| `src/data/loader.py` | Load single or multiple pair CSVs |
| `src/broker/oanda_client.py` | Batch price fetch for multiple instruments |
| `src/runner/polling_runner.py` | Iterate pairs, process each independently |
| `src/main.py` | Run backtest/live for all configured pairs |
| `src/api/__init__.py` | Package marker |
| `src/api/data_exporter.py` | Export backtest results and trades to JSON |
| `src/api/server.py` | HTTP server serving JSON API + static dashboard |
| `dashboard/index.html` | Tailwind CSS dashboard layout |
| `dashboard/app.js` | Chart.js rendering, fetch JSON data |
| `dashboard/data/` | JSON output directory |
| `src/ml/__init__.py` | Package marker |
| `src/ml/feature_engineer.py` | OHLCV → ML features + target |
| `src/ml/predictor.py` | LogisticRegression / RandomForest wrapper |
| `src/ml/trainer.py` | Train, save, load, evaluate models |
| `src/ml/strategy.py` | Strategy interface wrapper around ML predictor |
| `src/strategies/factory.py` | Register ML strategies |
| `tests/test_multi_pair.py` | Multi-pair config, data loading, broker tests |
| `tests/test_runner.py` | Updated runner tests for multi-pair |
| `tests/test_api.py` | Data exporter JSON tests |
| `tests/test_ml.py` | ML feature, predictor, trainer, strategy tests |
| `requirements.txt` | Add scikit-learn |

---

### Task 1: Multi-Currency Config & Data Loading

**Files:**
- Modify: `src/config/settings.py`
- Modify: `src/data/loader.py`
- Modify: `src/broker/oanda_client.py`
- Create: `tests/test_multi_pair.py`

- [ ] **Step 1: Write the failing test**

Create `/Users/hideakimacbookair/自動トレード/fx_trading/tests/test_multi_pair.py`:

```python
import os
import tempfile
import pandas as pd
from unittest.mock import patch
from src.config.settings import Settings
from src.data.loader import DataLoader
from src.broker.oanda_client import OandaClient


def test_settings_loads_multiple_pairs(monkeypatch):
    monkeypatch.setenv("OANDA_API_TOKEN", "test")
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "test")
    monkeypatch.setenv("CURRENCY_PAIRS", "USD_JPY,EUR_USD,GBP_JPY")
    settings = Settings()
    assert settings.currency_pairs == ["USD_JPY", "EUR_USD", "GBP_JPY"]
    assert settings.currency_pair == "USD_JPY"


def test_settings_defaults_single_pair(monkeypatch):
    monkeypatch.setenv("OANDA_API_TOKEN", "test")
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "test")
    settings = Settings()
    assert settings.currency_pairs == ["USD_JPY"]
    assert settings.currency_pair == "USD_JPY"


def test_settings_backward_compatible_with_currency_pair(monkeypatch):
    monkeypatch.setenv("OANDA_API_TOKEN", "test")
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "test")
    monkeypatch.setenv("CURRENCY_PAIR", "EUR_USD")
    # CURRENCY_PAIRS not set, should fall back to CURRENCY_PAIR
    settings = Settings()
    assert settings.currency_pairs == ["EUR_USD"]
    assert settings.currency_pair == "EUR_USD"


def test_data_loader_loads_multiple_pairs():
    with tempfile.TemporaryDirectory() as tmpdir:
        df1 = pd.DataFrame({
            "datetime": ["2024-01-01", "2024-01-02"],
            "open": [1.0, 1.1],
            "high": [1.1, 1.2],
            "low": [0.9, 1.0],
            "close": [1.05, 1.15],
            "volume": [100, 200],
        })
        df2 = pd.DataFrame({
            "datetime": ["2024-01-01", "2024-01-02"],
            "open": [150.0, 151.0],
            "high": [151.0, 152.0],
            "low": [149.0, 150.0],
            "close": [150.5, 151.5],
            "volume": [1000, 2000],
        })
        df1.to_csv(os.path.join(tmpdir, "usdjpy_1h.csv"), index=False)
        df2.to_csv(os.path.join(tmpdir, "eurusd_1h.csv"), index=False)

        loader = DataLoader(data_dir=tmpdir)
        result = loader.load_multiple(["USD_JPY", "EUR_USD"], "1h")
        assert "USD_JPY" in result
        assert "EUR_USD" in result
        assert result["USD_JPY"] is not None
        assert result["EUR_USD"] is not None
        assert len(result["USD_JPY"]) == 2
        assert len(result["EUR_USD"]) == 2


def test_data_loader_returns_none_for_missing_pair():
    with tempfile.TemporaryDirectory() as tmpdir:
        df1 = pd.DataFrame({
            "datetime": ["2024-01-01"],
            "open": [1.0],
            "high": [1.1],
            "low": [0.9],
            "close": [1.05],
            "volume": [100],
        })
        df1.to_csv(os.path.join(tmpdir, "usdjpy_1h.csv"), index=False)
        loader = DataLoader(data_dir=tmpdir)
        result = loader.load_multiple(["USD_JPY", "GBP_JPY"], "1h")
        assert result["USD_JPY"] is not None
        assert result["GBP_JPY"] is None


@patch("src.broker.oanda_client.requests.get")
def test_oanda_client_get_current_prices(mock_get):
    mock_get.return_value.json.return_value = {
        "prices": [
            {"instrument": "USD_JPY", "closeoutBid": "145.50", "closeoutAsk": "145.52"},
            {"instrument": "EUR_USD", "closeoutBid": "1.0850", "closeoutAsk": "1.0852"},
        ]
    }
    mock_get.return_value.status_code = 200
    client = OandaClient(api_token="test", account_id="acc123", environment="practice")
    prices = client.get_current_prices(["USD_JPY", "EUR_USD"])
    assert "USD_JPY" in prices
    assert "EUR_USD" in prices
    assert prices["USD_JPY"]["bid"] == 145.50
    assert prices["EUR_USD"]["ask"] == 1.0852
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && pytest tests/test_multi_pair.py -v
```

Expected:
```
FAILED tests/test_multi_pair.py::test_settings_loads_multiple_pairs - AttributeError: 'Settings' object has no attribute 'currency_pairs'
FAILED tests/test_multi_pair.py::test_data_loader_loads_multiple_pairs - AttributeError: 'DataLoader' object has no attribute 'load_multiple'
FAILED tests/test_multi_pair.py::test_oanda_client_get_current_prices - AttributeError: 'OandaClient' object has no attribute 'get_current_prices'
```

- [ ] **Step 3: Modify `src/config/settings.py`**

Full file:

```python
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    def __init__(self):
        self.api_token = os.getenv("OANDA_API_TOKEN")
        self.account_id = os.getenv("OANDA_ACCOUNT_ID")
        self.environment = os.getenv("OANDA_ENVIRONMENT", "practice")
        self.risk_per_trade = float(os.getenv("RISK_PER_TRADE", "0.01"))

        # Support CURRENCY_PAIRS (comma-separated) with fallback to legacy CURRENCY_PAIR
        currency_pairs_str = os.getenv("CURRENCY_PAIRS")
        if currency_pairs_str is None:
            currency_pairs_str = os.getenv("CURRENCY_PAIR", "USD_JPY")
        self.currency_pairs = [p.strip() for p in currency_pairs_str.split(",") if p.strip()]
        self.currency_pair = self.currency_pairs[0]

        self.initial_capital = float(os.getenv("INITIAL_CAPITAL", "1000000"))
        self.max_daily_loss_pct = float(os.getenv("MAX_DAILY_LOSS_PCT", "5.0"))
        self.trading_start_hour = int(os.getenv("TRADING_START_HOUR", "7"))
        self.trading_end_hour = int(os.getenv("TRADING_END_HOUR", "6"))
        self.granularity = os.getenv("GRANULARITY", "H1")
        self.slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        self.validate()

    def validate(self):
        if not self.api_token:
            raise ValueError("OANDA_API_TOKEN is required")
        if not self.account_id:
            raise ValueError("OANDA_ACCOUNT_ID is required")
        if self.environment not in ("practice", "live"):
            raise ValueError("OANDA_ENVIRONMENT must be 'practice' or 'live'")
```

- [ ] **Step 4: Modify `src/data/loader.py`**

Full file:

```python
import pandas as pd
from pathlib import Path
from typing import Dict, Optional


class DataLoader:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)

    def load_csv(self, symbol: str, timeframe: str) -> pd.DataFrame:
        path = self.data_dir / f"{symbol}_{timeframe}.csv"
        df = pd.read_csv(path, parse_dates=["datetime"])
        return df

    def load_multiple(self, pairs: list, timeframe: str) -> Dict[str, Optional[pd.DataFrame]]:
        result = {}
        for pair in pairs:
            symbol = pair.replace("_", "").lower()
            try:
                df = self.load_csv(symbol, timeframe)
                result[pair] = df
            except FileNotFoundError:
                result[pair] = None
        return result
```

- [ ] **Step 5: Modify `src/broker/oanda_client.py`**

Add the `get_current_prices` method. Full file:

```python
import requests
import time
from typing import Dict, List, Optional

class OandaClient:
    def __init__(self, api_token: str, account_id: str, environment: str = "practice"):
        self.api_token = api_token
        self.account_id = account_id
        self.environment = environment
        if environment == "live":
            self.base_url = "https://api-fxtrade.oanda.com/v3"
        else:
            self.base_url = "https://api-fxpractice.oanda.com/v3"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, headers=self.headers, params=params, timeout=30)
        if response.status_code == 429:
            time.sleep(1)
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
        if response.status_code >= 400:
            raise RuntimeError(f"OANDA API error: {response.status_code} {response.text}")
        return response.json()

    def _post(self, endpoint: str, data: Dict) -> Dict:
        url = f"{self.base_url}/{endpoint}"
        response = requests.post(url, headers=self.headers, json=data, timeout=30)
        if response.status_code == 429:
            time.sleep(1)
            response = requests.post(url, headers=self.headers, json=data, timeout=30)
        if response.status_code >= 400:
            raise RuntimeError(f"OANDA API error: {response.status_code} {response.text}")
        return response.json()

    def get_account_summary(self) -> Dict:
        return self._get(f"accounts/{self.account_id}/summary")

    def get_current_price(self, instrument: str) -> Dict:
        result = self._get(f"accounts/{self.account_id}/pricing", params={"instruments": instrument})
        price = result["prices"][0]
        return {
            "bid": float(price["closeoutBid"]),
            "ask": float(price["closeoutAsk"]),
            "instrument": price["instrument"],
        }

    def get_current_prices(self, instruments: List[str]) -> Dict[str, Dict]:
        """Fetch prices for multiple instruments in one request."""
        instruments_str = ",".join(instruments)
        result = self._get(f"accounts/{self.account_id}/pricing", params={"instruments": instruments_str})
        prices = {}
        for price in result.get("prices", []):
            inst = price["instrument"]
            prices[inst] = {
                "bid": float(price["closeoutBid"]),
                "ask": float(price["closeoutAsk"]),
                "instrument": inst,
            }
        return prices

    def get_open_positions(self) -> List[Dict]:
        result = self._get(f"accounts/{self.account_id}/openPositions")
        return result.get("positions", [])

    def place_order(self, order: Dict) -> Dict:
        return self._post(f"accounts/{self.account_id}/orders", {"order": order})

    def close_position(self, instrument: str, long_units: str = "ALL", short_units: str = "ALL") -> Dict:
        data = {}
        if long_units:
            data["longUnits"] = long_units
        if short_units:
            data["shortUnits"] = short_units
        return self._put(f"accounts/{self.account_id}/positions/{instrument}/close", data)

    def _put(self, endpoint: str, data: Dict) -> Dict:
        url = f"{self.base_url}/{endpoint}"
        response = requests.put(url, headers=self.headers, json=data, timeout=30)
        if response.status_code >= 400:
            raise RuntimeError(f"OANDA API error: {response.status_code} {response.text}")
        return response.json()
```

- [ ] **Step 6: Run tests to verify they pass**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && pytest tests/test_multi_pair.py tests/test_config.py tests/test_data.py tests/test_broker.py -v
```

Expected:
```
============================= test session starts ==============================
collected ... items
tests/test_multi_pair.py::test_settings_loads_multiple_pairs PASSED
tests/test_multi_pair.py::test_settings_defaults_single_pair PASSED
tests/test_multi_pair.py::test_settings_backward_compatible_with_currency_pair PASSED
tests/test_multi_pair.py::test_data_loader_loads_multiple_pairs PASSED
tests/test_multi_pair.py::test_data_loader_returns_none_for_missing_pair PASSED
tests/test_multi_pair.py::test_oanda_client_get_current_prices PASSED
tests/test_config.py::test_settings_loads_from_env PASSED
tests/test_config.py::test_settings_defaults PASSED
tests/test_config.py::test_settings_raises_on_missing_token PASSED
tests/test_data.py::test_load_csv PASSED
tests/test_data.py::test_preprocessor_sorts_and_drops_na PASSED
tests/test_broker.py::test_client_constructs_practice_url PASSED
tests/test_broker.py::test_client_constructs_live_url PASSED
tests/test_broker.py::test_get_current_price PASSED
tests/test_broker.py::test_get_open_positions PASSED
tests/test_broker.py::test_place_order PASSED
tests/test_broker.py::test_get_account_summary_raises_on_error PASSED
tests/test_broker.py::test_build_market_order_long PASSED
tests/test_broker.py::test_build_market_order_short PASSED
tests/test_broker.py::test_build_market_order_without_stop PASSED
============================== ... passed in ...s ============================
```

- [ ] **Step 7: Commit**

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && git add src/config/settings.py src/data/loader.py src/broker/oanda_client.py tests/test_multi_pair.py && git commit -m "feat: add multi-currency pair support in config, data loader, and broker"
```

---

### Task 2: Multi-Currency Runner

**Files:**
- Modify: `src/runner/polling_runner.py`
- Modify: `src/main.py`
- Modify: `tests/test_runner.py`

- [ ] **Step 1: Write the failing test**

Overwrite `/Users/hideakimacbookair/自動トレード/fx_trading/tests/test_runner.py`:

```python
from unittest.mock import MagicMock, patch
from src.runner.polling_runner import PollingRunner


def test_runner_constructs_with_dependencies():
    mock_config = MagicMock()
    mock_config.currency_pairs = ["USD_JPY"]
    mock_config.risk_per_trade = 0.01
    runner = PollingRunner(config=mock_config)
    assert runner.config.currency_pairs == ["USD_JPY"]


@patch("src.runner.polling_runner.OandaClient")
def test_runner_checks_circuit_breaker(mock_client_class):
    mock_config = MagicMock()
    mock_config.currency_pairs = ["USD_JPY"]
    mock_config.risk_per_trade = 0.01
    mock_config.api_token = "test"
    mock_config.account_id = "acc"
    mock_config.environment = "practice"

    runner = PollingRunner(config=mock_config)
    runner.circuit_breaker.is_trading_allowed = MagicMock(return_value=False)
    result = runner.run_cycle()
    assert result is False


@patch("src.runner.polling_runner.OandaClient")
def test_runner_fetches_prices(mock_client_class):
    mock_config = MagicMock()
    mock_config.currency_pairs = ["USD_JPY"]
    mock_config.risk_per_trade = 0.01
    mock_config.api_token = "test"
    mock_config.account_id = "acc"
    mock_config.environment = "practice"

    mock_client = MagicMock()
    mock_client.get_current_prices.return_value = {"USD_JPY": {"bid": 145.0, "ask": 145.02, "instrument": "USD_JPY"}}
    mock_client.get_open_positions.return_value = []
    mock_client_class.return_value = mock_client

    runner = PollingRunner(config=mock_config)
    runner.run_cycle()
    mock_client.get_current_prices.assert_called_once_with(["USD_JPY"])


@patch("src.runner.polling_runner.OandaClient")
def test_runner_uses_multiple_strategies(mock_client_class):
    mock_config = MagicMock()
    mock_config.currency_pairs = ["USD_JPY"]
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
    mock_config.currency_pairs = ["USD_JPY"]
    mock_config.risk_per_trade = 0.01
    mock_config.api_token = "test"
    mock_config.account_id = "acc"
    mock_config.environment = "practice"
    mock_config.slack_webhook_url = None

    runner = PollingRunner(config=mock_config, strategies=["ma_macd"])
    import pandas as pd
    df = pd.DataFrame({
        "datetime": [pd.Timestamp("2024-01-01")],
        "signal": [1],
    })
    runner.strategies[0].generate_signals = MagicMock(return_value=df)

    signal = runner._aggregate_signals(df)
    assert signal == 1


@patch("src.runner.polling_runner.OandaClient")
def test_runner_processes_multiple_pairs(mock_client_class):
    mock_config = MagicMock()
    mock_config.currency_pairs = ["USD_JPY", "EUR_USD"]
    mock_config.risk_per_trade = 0.01
    mock_config.api_token = "test"
    mock_config.account_id = "acc"
    mock_config.environment = "practice"
    mock_config.slack_webhook_url = None

    mock_client = MagicMock()
    mock_client.get_current_prices.return_value = {
        "USD_JPY": {"bid": 145.0, "ask": 145.02, "instrument": "USD_JPY"},
        "EUR_USD": {"bid": 1.085, "ask": 1.0852, "instrument": "EUR_USD"},
    }
    mock_client.get_open_positions.return_value = []
    mock_client_class.return_value = mock_client

    runner = PollingRunner(config=mock_config, strategies=["ma_macd"])
    result = runner.run_cycle()
    assert result is True
    mock_client.get_current_prices.assert_called_once_with(["USD_JPY", "EUR_USD"])
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && pytest tests/test_runner.py -v
```

Expected:
```
FAILED tests/test_runner.py::test_runner_fetches_prices - AssertionError: Expected call: get_current_prices(['USD_JPY'])
Actual call: get_current_price('USD_JPY')
FAILED tests/test_runner.py::test_runner_processes_multiple_pairs - AssertionError: Expected call: get_current_prices(['USD_JPY', 'EUR_USD'])
```

- [ ] **Step 3: Modify `src/runner/polling_runner.py`**

Full file:

```python
import datetime
from typing import Optional, List, Union
from src.config.settings import Settings
from src.broker.oanda_client import OandaClient
from src.broker.order_builder import OrderBuilder
from src.risk.manager import RiskManager
from src.strategies.factory import StrategyFactory
from src.strategies.base import Strategy
from src.safety.circuit_breaker import CircuitBreaker
from src.monitoring.logger import TradeLogger

class PollingRunner:
    def __init__(
        self,
        config: Optional[Settings] = None,
        strategies: Optional[List[Union[str, Strategy]]] = None,
    ):
        self.config = config or Settings()
        self.client = OandaClient(
            api_token=self.config.api_token,
            account_id=self.config.account_id,
            environment=self.config.environment,
        )
        self.circuit_breaker = CircuitBreaker(
            max_daily_loss_pct=self.config.max_daily_loss_pct,
            trading_start_hour=self.config.trading_start_hour,
            trading_end_hour=self.config.trading_end_hour,
            initial_capital=self.config.initial_capital,
        )
        self.logger = TradeLogger()
        self.risk_manager = RiskManager(
            capital=self.config.initial_capital,
            risk_per_trade=self.config.risk_per_trade,
        )

        if strategies is None:
            strategies = ["ma_macd"]

        self.strategies: List[Strategy] = []
        for s in strategies:
            if isinstance(s, str):
                self.strategies.append(StrategyFactory.create(s))
            else:
                self.strategies.append(s)

    def _aggregate_signals(self, df) -> int:
        """Aggregate signals from all strategies by majority vote."""
        signals = []
        for strategy in self.strategies:
            sig_df = strategy.generate_signals(df.copy())
            signal = int(sig_df.iloc[-1]["signal"])
            signals.append(signal)

        buy_votes = sum(1 for s in signals if s == 1)
        sell_votes = sum(1 for s in signals if s == -1)
        neutral_votes = sum(1 for s in signals if s == 0)

        if buy_votes > sell_votes and buy_votes > neutral_votes:
            return 1
        elif sell_votes > buy_votes and sell_votes > neutral_votes:
            return -1
        else:
            return 0

    def _run_pair_cycle(self, pair: str, price: dict, positions: List[dict]) -> bool:
        now = datetime.datetime.now()
        import pandas as pd
        df = pd.DataFrame({
            "datetime": [now],
            "open": [price["bid"]],
            "high": [price["ask"]],
            "low": [price["bid"]],
            "close": [price["ask"]],
            "volume": [1],
        })

        signal = self._aggregate_signals(df)

        # Find position for this specific pair
        pair_positions = [p for p in positions if p.get("instrument") == pair]
        current_pos = pair_positions[0] if pair_positions else None

        order_builder = OrderBuilder(instrument=pair)

        if current_pos is None:
            if signal != 0:
                entry_price = price["ask"] if signal == 1 else price["bid"]
                stop_loss = entry_price * 0.99 if signal == 1 else entry_price * 1.01
                take_profit = entry_price * 1.02 if signal == 1 else entry_price * 0.98
                units = int(self.risk_manager.calculate_lot(entry_price, stop_loss))

                if units > 0:
                    order = order_builder.build_market_order(
                        direction=signal,
                        units=units,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                    )
                    result = self.client.place_order(order)
                    self.logger.log_trade(
                        pair,
                        "BUY" if signal == 1 else "SELL",
                        units,
                        entry_price,
                    )
                    self.logger.log_info(f"Order placed: {result}")
        else:
            long_units = float(current_pos.get("long", {}).get("units", 0))
            short_units = float(current_pos.get("short", {}).get("units", 0))
            current_direction = 1 if long_units > 0 else -1 if short_units < 0 else 0

            if signal != 0 and signal != current_direction:
                self.client.close_position(pair)
                self.logger.log_trade(
                    pair,
                    "CLOSE",
                    0,
                    price["bid"] if current_direction == 1 else price["ask"],
                )
        return True

    def run_cycle(self) -> bool:
        now = datetime.datetime.now()

        if not self.circuit_breaker.is_trading_allowed(now):
            self.logger.log_info("Trading not allowed by circuit breaker")
            return False

        try:
            prices = self.client.get_current_prices(self.config.currency_pairs)
            positions = self.client.get_open_positions()

            success = True
            for pair in self.config.currency_pairs:
                if pair not in prices:
                    self.logger.log_error(f"No price data for {pair}")
                    success = False
                    continue
                try:
                    self._run_pair_cycle(pair, prices[pair], positions)
                except Exception as e:
                    self.logger.log_error(f"Error in cycle for {pair}: {e}")
                    success = False

            return success

        except Exception as e:
            self.logger.log_error(f"Error in trading cycle: {e}")
            return False
```

- [ ] **Step 4: Modify `src/main.py`**

Full file:

```python
import argparse
from src.data.loader import DataLoader
from src.data.preprocessor import Preprocessor
from src.strategies.factory import StrategyFactory
from src.engine.backtest import BacktestEngine
from src.risk.manager import RiskManager
from src.reports.reporter import ReportGenerator
from src.optimizer.grid_search import GridSearchOptimizer
from src.wfa.walker import WalkForwardAnalyzer
from src.selector.ranker import StrategyRanker
from src.runner.polling_runner import PollingRunner
from src.config.settings import Settings
from src.api.data_exporter import DataExporter


def run_backtest():
    settings = Settings()
    loader = DataLoader(data_dir="data")
    pre = Preprocessor()

    all_pair_results = {}

    for pair in settings.currency_pairs:
        symbol = pair.replace("_", "").lower()
        try:
            raw_df = loader.load_csv(symbol, "1h")
        except FileNotFoundError:
            print(f"Data not found for {pair}, skipping...")
            continue

        df = pre.process(raw_df)

        strategy_names = StrategyFactory.available_strategies()
        pair_results = []

        for name in strategy_names:
            print(f"\n=== Grid Search: {name} | {pair} ===")
            optimizer = GridSearchOptimizer(df)
            param_grid = {
                "fast": [3, 5, 8],
                "slow": [6, 10, 15],
                "signal": [2, 3, 5],
            }
            strategy_cls = StrategyFactory._registry[name]
            results = optimizer.search(strategy_cls, param_grid)
            best = optimizer.get_best(results)
            print("Best params:", best["params"])
            print("Profit Factor:", best["profit_factor"])

            print(f"\n=== Walk-Forward Analysis: {name} | {pair} ===")
            train_size = min(60, max(5, len(df) // 2))
            test_size = min(30, max(3, len(df) // 3))
            wfa = WalkForwardAnalyzer(train_size=train_size, test_size=test_size)
            wfa_results = wfa.analyze(df, strategy_cls, param_grid)
            for i, r in enumerate(wfa_results):
                print(f"Window {i+1}: Train PF={r['train_pf']:.2f}, Test PF={r['test_pf']:.2f}, Params={r['params']}")

            pair_results.append({
                "name": f"{name} Best",
                "profit_factor": best["profit_factor"],
                "win_rate": best["win_rate"],
                "max_drawdown": 0.1,
                "total_trades": best["total_trades"],
            })
            pair_results.append({
                "name": f"{name} WFA Avg",
                "profit_factor": sum(x["test_pf"] for x in wfa_results) / len(wfa_results) if wfa_results else 0,
                "win_rate": 0.5,
                "max_drawdown": 0.15,
                "total_trades": sum(x["test_trades"] for x in wfa_results),
            })

        print(f"\n=== Strategy Ranking | {pair} ===")
        ranker = StrategyRanker(min_trades=0)
        ranked = ranker.rank(pair_results)
        for r in ranked:
            print(f"{r['name']}: Score={r['score']:.2f}")

        all_pair_results[pair] = pair_results

    exporter = DataExporter(output_dir="dashboard/data")
    exporter.export_backtest_results(all_pair_results)
    print("\nBacktest results exported to dashboard/data/backtest_results.json")


def run_live():
    print("=== Live Trading Mode ===")
    print("WARNING: This will connect to OANDA and potentially place real orders!")
    settings = Settings()
    print(f"Environment: {settings.environment}")
    print(f"Currency Pairs: {settings.currency_pairs}")
    print(f"Risk per trade: {settings.risk_per_trade * 100}%")

    runner = PollingRunner(config=settings)
    result = runner.run_cycle()
    if result:
        print("Trading cycle completed successfully")
    else:
        print("Trading cycle did not execute")


def main():
    parser = argparse.ArgumentParser(description="FX Auto Trading System")
    parser.add_argument("--live", action="store_true", help="Run in live trading mode")
    parser.add_argument("--backtest", action="store_true", help="Run backtest (default)")
    args = parser.parse_args()

    if args.live:
        run_live()
    else:
        run_backtest()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && pytest tests/test_runner.py -v
```

Expected:
```
============================= test session starts ==============================
tests/test_runner.py::test_runner_constructs_with_dependencies PASSED
tests/test_runner.py::test_runner_checks_circuit_breaker PASSED
tests/test_runner.py::test_runner_fetches_prices PASSED
tests/test_runner.py::test_runner_uses_multiple_strategies PASSED
tests/test_runner.py::test_runner_aggregates_signals PASSED
tests/test_runner.py::test_runner_processes_multiple_pairs PASSED
============================== 6 passed in ...s ==============================
```

- [ ] **Step 6: Commit**

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && git add src/runner/polling_runner.py src/main.py tests/test_runner.py && git commit -m "feat: multi-currency polling runner and backtest loop"
```

---

### Task 3: JSON Data Exporter

**Files:**
- Create: `src/api/__init__.py`
- Create: `src/api/data_exporter.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Create `/Users/hideakimacbookair/自動トレード/fx_trading/tests/test_api.py`:

```python
import json
import tempfile
import os
from src.api.data_exporter import DataExporter


def test_exporter_creates_backtest_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = DataExporter(output_dir=tmpdir)
        results = {
            "USD_JPY": [
                {"name": "ma_macd Best", "profit_factor": 1.5, "total_trades": 10, "win_rate": 0.6, "max_drawdown": 0.1}
            ]
        }
        path = exporter.export_backtest_results(results)
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert "pairs" in data
        assert data["pairs"]["USD_JPY"][0]["name"] == "ma_macd Best"
        assert "generated_at" in data


def test_exporter_creates_trade_log_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = DataExporter(output_dir=tmpdir)
        trades = [
            {"instrument": "USD_JPY", "direction": "BUY", "units": 1000, "price": 145.0, "time": "2024-01-01T00:00:00"}
        ]
        path = exporter.export_trade_log(trades)
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert data["trades"][0]["instrument"] == "USD_JPY"
        assert "generated_at" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && pytest tests/test_api.py -v
```

Expected:
```
FAILED tests/test_api.py::test_exporter_creates_backtest_json - ModuleNotFoundError: No module named 'src.api.data_exporter'
```

- [ ] **Step 3: Create `src/api/__init__.py`**

```python
# src/api package
```

- [ ] **Step 4: Create `src/api/data_exporter.py`**

Full file:

```python
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class DataExporter:
    def __init__(self, output_dir: str = "dashboard/data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_backtest_results(self, results: Dict[str, List[Dict]]) -> str:
        """Export backtest results per pair to JSON."""
        filepath = self.output_dir / "backtest_results.json"
        payload = {
            "generated_at": datetime.now().isoformat(),
            "pairs": results,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
        return str(filepath)

    def export_trade_log(self, trades: List[Dict]) -> str:
        """Export trade log to JSON."""
        filepath = self.output_dir / "trade_log.json"
        payload = {
            "generated_at": datetime.now().isoformat(),
            "trades": trades,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
        return str(filepath)
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && pytest tests/test_api.py -v
```

Expected:
```
============================= test session starts ==============================
tests/test_api.py::test_exporter_creates_backtest_json PASSED
tests/test_api.py::test_exporter_creates_trade_log_json PASSED
============================== 2 passed in ...s ==============================
```

- [ ] **Step 6: Commit**

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && git add src/api/__init__.py src/api/data_exporter.py tests/test_api.py && git commit -m "feat: add JSON data exporter for dashboard"
```

---

### Task 4: Web Dashboard Frontend

**Files:**
- Create: `dashboard/index.html`
- Create: `dashboard/app.js`
- Create: `dashboard/data/` directory

- [ ] **Step 1: Create `dashboard/index.html`**

Full file:

```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FX Trading Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
</head>
<body class="bg-gray-100 text-gray-800">
  <div class="container mx-auto px-4 py-8">
    <h1 class="text-3xl font-bold mb-6">FX自動売買ダッシュボード</h1>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div class="bg-white rounded-lg shadow p-6">
        <h2 class="text-xl font-semibold mb-4">バックテスト PnL（ペア別）</h2>
        <canvas id="pnlChart"></canvas>
      </div>

      <div class="bg-white rounded-lg shadow p-6">
        <h2 class="text-xl font-semibold mb-4">戦略ランキング（トップ10）</h2>
        <canvas id="rankChart"></canvas>
      </div>
    </div>

    <div class="mt-6 bg-white rounded-lg shadow p-6">
      <h2 class="text-xl font-semibold mb-4">取引履歴</h2>
      <div id="tradeLog" class="overflow-x-auto">
        <p class="text-gray-500">データを読み込み中...</p>
      </div>
    </div>
  </div>

  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create `dashboard/app.js`**

Full file:

```javascript
const API_BASE = '';

async function loadJSON(path) {
  try {
    const res = await fetch(`${API_BASE}${path}`);
    if (!res.ok) return null;
    return res.json();
  } catch (e) {
    console.error('Failed to load', path, e);
    return null;
  }
}

async function renderCharts() {
  const backtestData = await loadJSON('/api/backtest');
  const tradeData = await loadJSON('/api/trades');

  renderPnlChart(backtestData);
  renderRankChart(backtestData);
  renderTradeLog(tradeData);
}

function renderPnlChart(data) {
  const ctx = document.getElementById('pnlChart');
  if (!ctx) return;
  const context = ctx.getContext('2d');
  if (!data || !data.pairs) {
    context.font = '16px sans-serif';
    context.fillText('データがありません', 10, 50);
    return;
  }

  const labels = Object.keys(data.pairs);
  const values = labels.map(pair => {
    const results = data.pairs[pair];
    const totalPnl = results.reduce((sum, r) => sum + (r.total_pnl || 0), 0);
    return totalPnl;
  });

  new Chart(context, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Total PnL',
        data: values,
        backgroundColor: 'rgba(59, 130, 246, 0.5)',
        borderColor: 'rgba(59, 130, 246, 1)',
        borderWidth: 1,
      }]
    },
    options: {
      responsive: true,
      scales: { y: { beginAtZero: true } }
    }
  });
}

function renderRankChart(data) {
  const ctx = document.getElementById('rankChart');
  if (!ctx) return;
  const context = ctx.getContext('2d');
  if (!data || !data.pairs) {
    context.font = '16px sans-serif';
    context.fillText('データがありません', 10, 50);
    return;
  }

  const allResults = [];
  Object.values(data.pairs).forEach(results => {
    results.forEach(r => allResults.push(r));
  });

  const sorted = allResults.sort((a, b) => (b.score || 0) - (a.score || 0)).slice(0, 10);
  const labels = sorted.map(r => r.name);
  const scores = sorted.map(r => r.score || 0);

  new Chart(context, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Score',
        data: scores,
        backgroundColor: 'rgba(16, 185, 129, 0.5)',
        borderColor: 'rgba(16, 185, 129, 1)',
        borderWidth: 1,
      }]
    },
    options: {
      responsive: true,
      indexAxis: 'y',
      scales: { x: { beginAtZero: true } }
    }
  });
}

function renderTradeLog(data) {
  const container = document.getElementById('tradeLog');
  if (!container) return;
  if (!data || !data.trades || data.trades.length === 0) {
    container.innerHTML = '<p class="text-gray-500">取引履歴がありません</p>';
    return;
  }

  let html = '<table class="min-w-full text-sm text-left"><thead class="bg-gray-50"><tr>'
    + '<th class="px-4 py-2">時間</th><th class="px-4 py-2">通貨ペア</th>'
    + '<th class="px-4 py-2">方向</th><th class="px-4 py-2">数量</th><th class="px-4 py-2">価格</th>'
    + '</tr></thead><tbody>';

  data.trades.slice(0, 50).forEach(t => {
    html += `<tr class="border-b">
      <td class="px-4 py-2">${t.time || '-'}</td>
      <td class="px-4 py-2">${t.instrument || '-'}</td>
      <td class="px-4 py-2">${t.direction || '-'}</td>
      <td class="px-4 py-2">${t.units || '-'}</td>
      <td class="px-4 py-2">${t.price || '-'}</td>
    </tr>`;
  });

  html += '</tbody></table>';
  container.innerHTML = html;
}

document.addEventListener('DOMContentLoaded', renderCharts);
```

- [ ] **Step 3: Create `dashboard/data/` directory**

Run:
```bash
mkdir -p /Users/hideakimacbookair/自動トレード/fx_trading/dashboard/data
```

Create a sample `dashboard/data/backtest_results.json` so the dashboard renders something on first open:

```bash
cat > /Users/hideakimacbookair/自動トレード/fx_trading/dashboard/data/backtest_results.json << 'EOF'
{
  "generated_at": "2024-01-01T00:00:00",
  "pairs": {
    "USD_JPY": [
      {"name": "ma_macd Best", "profit_factor": 1.5, "win_rate": 0.6, "max_drawdown": 0.1, "total_trades": 10, "total_pnl": 50000, "score": 2.5},
      {"name": "ma_macd WFA Avg", "profit_factor": 1.3, "win_rate": 0.55, "max_drawdown": 0.15, "total_trades": 8, "total_pnl": 30000, "score": 2.0}
    ]
  }
}
EOF
```

Create an empty trade log:
```bash
cat > /Users/hideakimacbookair/自動トレード/fx_trading/dashboard/data/trade_log.json << 'EOF'
{"generated_at": "2024-01-01T00:00:00", "trades": []}
EOF
```

- [ ] **Step 4: Verify by opening dashboard**

Run a simple Python HTTP server from the project root to verify static files load:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && python3 -m http.server 8888 &
```

Then in another terminal, verify the HTML and JS are served:
```bash
curl -s http://localhost:8888/dashboard/index.html | head -n 5
curl -s http://localhost:8888/dashboard/app.js | head -n 5
```

Expected output for first curl:
```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
```

Expected output for second curl:
```javascript
const API_BASE = '';

async function loadJSON(path) {
```

Kill the background server:
```bash
pkill -f "http.server 8888"
```

- [ ] **Step 5: Commit**

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && git add dashboard/index.html dashboard/app.js dashboard/data/ && git commit -m "feat: add static web dashboard with Tailwind CSS and Chart.js"
```

---

### Task 5: Dashboard API Server

**Files:**
- Create: `src/api/server.py`

- [ ] **Step 1: Write the failing test (curl verification script)**

Create a temporary test script `/Users/hideakimacbookair/自動トレード/fx_trading/tests/test_server.sh`:

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")/.."
python3 -m src.api.server &
PID=$!
sleep 2
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/backtest | grep -q "200\|404"
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/index.html | grep -q "200"
kill $PID || true
echo "PASS"
```

Run it to see it fail because `src/api/server.py` does not exist yet:
```bash
chmod +x /Users/hideakimacbookair/自動トレード/fx_trading/tests/test_server.sh
/Users/hideakimacbookair/自動トレード/fx_trading/tests/test_server.sh
```

Expected:
```
/usr/bin/python3: Error while finding module specification for 'src.api.server' (ModuleNotFoundError: No module named 'src.api.server')
```

- [ ] **Step 2: Create `src/api/server.py`**

Full file:

```python
import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path


def make_handler(data_dir: str):
    class DashboardHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            self._data_dir = Path(data_dir)
            self._data_dir.mkdir(parents=True, exist_ok=True)
            super().__init__(*args, directory="dashboard", **kwargs)

        def do_GET(self):
            if self.path == "/api/backtest":
                self._serve_json(self._data_dir / "backtest_results.json")
            elif self.path == "/api/trades":
                self._serve_json(self._data_dir / "trade_log.json")
            else:
                super().do_GET()

        def _serve_json(self, filepath: Path):
            if not filepath.exists():
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b'{"error": "Not found"}')
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            with open(filepath, "rb") as f:
                self.wfile.write(f.read())

        def log_message(self, format, *args):
            # Suppress default logging noise
            pass

    return DashboardHandler


def run_server(port: int = 8080):
    server_address = ("", port)
    handler_class = make_handler(data_dir="dashboard/data")
    httpd = HTTPServer(server_address, handler_class)
    print(f"Starting dashboard server on http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server")
        httpd.shutdown()


if __name__ == "__main__":
    run_server()
```

- [ ] **Step 3: Run the curl verification script**

Run:
```bash
chmod +x /Users/hideakimacbookair/自動トレード/fx_trading/tests/test_server.sh
/Users/hideakimacbookair/自動トレード/fx_trading/tests/test_server.sh
```

Expected:
```
PASS
```

Also manually verify the endpoints:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && python3 -m src.api.server &
SERVER_PID=$!
sleep 2
curl -s http://localhost:8080/api/backtest | python3 -m json.tool | head -n 5
curl -s http://localhost:8080/api/trades | python3 -m json.tool | head -n 3
kill $SERVER_PID
```

Expected:
```json
{
    "generated_at": "2024-01-01T00:00:00",
    "pairs": {
        "USD_JPY": [
            {
                "max_drawdown": 0.1,
...
{
    "generated_at": "2024-01-01T00:00:00",
    "trades": []
}
```

- [ ] **Step 4: Commit**

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && git add src/api/server.py tests/test_server.sh && git commit -m "feat: add simple HTTP API server for dashboard JSON endpoints"
```

---

### Task 6: ML Feature Engineer

**Files:**
- Create: `src/ml/__init__.py`
- Create: `src/ml/feature_engineer.py`
- Create: `tests/test_ml.py` (partial, expanded in later tasks)

- [ ] **Step 1: Write the failing test**

Create `/Users/hideakimacbookair/自動トレード/fx_trading/tests/test_ml.py` with the feature engineer tests:

```python
import pandas as pd
import numpy as np
import os
import tempfile
from src.ml.feature_engineer import FeatureEngineer


def test_feature_engineer_creates_features_and_target():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=50, freq="h"),
        "open": [150.0] * 50,
        "high": [151.0] * 50,
        "low": [149.0] * 50,
        "close": [150.0 + i * 0.1 for i in range(50)],
        "volume": [1000] * 50,
    })
    fe = FeatureEngineer(lookback=3)
    X, y = fe.create_features_and_target(df)
    assert len(X) > 0
    assert len(X) == len(y)
    assert "close_lag_1" in X.columns
    assert "sma_5" in X.columns
    assert set(y.unique()).issubset({-1, 0, 1})


def test_feature_engineer_creates_features_only():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=50, freq="h"),
        "open": [150.0] * 50,
        "high": [151.0] * 50,
        "low": [149.0] * 50,
        "close": [150.0 + i * 0.1 for i in range(50)],
        "volume": [1000] * 50,
    })
    fe = FeatureEngineer(lookback=3)
    X = fe.create_features(df)
    assert len(X) == len(df)
    assert "sma_10" in X.columns
    assert "target" not in X.columns
    assert "future_close" not in X.columns
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && pytest tests/test_ml.py -v
```

Expected:
```
FAILED tests/test_ml.py::test_feature_engineer_creates_features_and_target - ModuleNotFoundError: No module named 'src.ml.feature_engineer'
```

- [ ] **Step 3: Create `src/ml/__init__.py`**

```python
# src/ml package
```

- [ ] **Step 4: Create `src/ml/feature_engineer.py`**

Full file:

```python
import pandas as pd
import numpy as np
from typing import Tuple


class FeatureEngineer:
    def __init__(self, lookback: int = 10):
        self.lookback = lookback

    def _build_common(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df = df.sort_values("datetime").reset_index(drop=True)

        df["returns"] = df["close"].pct_change()
        for lag in range(1, self.lookback + 1):
            df[f"close_lag_{lag}"] = df["close"].shift(lag)
            df[f"volume_lag_{lag}"] = df["volume"].shift(lag)

        df["sma_5"] = df["close"].rolling(window=5).mean()
        df["sma_10"] = df["close"].rolling(window=10).mean()
        df["ema_5"] = df["close"].ewm(span=5, adjust=False).mean()
        df["volatility_5"] = df["close"].rolling(window=5).std()
        df["high_low_range"] = df["high"] - df["low"]
        df["open_close_range"] = abs(df["open"] - df["close"])

        return df

    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self._build_common(df)
        feature_cols = [c for c in df.columns if c not in [
            "datetime", "open", "high", "low", "close", "volume"
        ]]
        return df[feature_cols]

    def create_features_and_target(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        df = self._build_common(df)
        df["future_close"] = df["close"].shift(-1)
        df["target"] = np.where(df["future_close"] > df["close"], 1,
                               np.where(df["future_close"] < df["close"], -1, 0))

        feature_cols = [c for c in df.columns if c not in [
            "datetime", "open", "high", "low", "close", "volume",
            "future_close", "target"
        ]]

        valid = df.dropna()
        X = valid[feature_cols]
        y = valid["target"]
        return X, y
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && pytest tests/test_ml.py -v
```

Expected:
```
============================= test session starts ==============================
tests/test_ml.py::test_feature_engineer_creates_features_and_target PASSED
tests/test_ml.py::test_feature_engineer_creates_features_only PASSED
============================== 2 passed in ...s ==============================
```

- [ ] **Step 6: Commit**

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && git add src/ml/__init__.py src/ml/feature_engineer.py tests/test_ml.py && git commit -m "feat: add ML feature engineer"
```

---

### Task 7: ML Predictor

**Files:**
- Create: `src/ml/predictor.py`
- Create: `src/ml/trainer.py`
- Modify: `tests/test_ml.py` (append tests)
- Modify: `requirements.txt`

- [ ] **Step 1: Write the failing test**

Append to `/Users/hideakimacbookair/自動トレード/fx_trading/tests/test_ml.py`:

```python
from src.ml.predictor import MLPredictor
from src.ml.trainer import MLTrainer


def test_predictor_trains_and_predicts():
    X = pd.DataFrame({
        "a": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "b": [10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
    })
    y = pd.Series([1, 1, 1, -1, -1, -1, 1, 1, -1, -1])
    predictor = MLPredictor(model_type="logistic_regression")
    predictor.fit(X, y)
    preds = predictor.predict(X)
    assert len(preds) == len(X)
    assert set(preds).issubset({-1, 0, 1})


def test_predictor_save_and_load():
    X = pd.DataFrame({
        "a": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "b": [10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
    })
    y = pd.Series([1, 1, 1, -1, -1, -1, 1, 1, -1, -1])
    predictor = MLPredictor(model_type="logistic_regression")
    predictor.fit(X, y)

    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
        path = f.name
    try:
        predictor.save(path)
        new_predictor = MLPredictor(model_type="logistic_regression")
        new_predictor.load(path)
        preds = new_predictor.predict(X)
        assert len(preds) == len(X)
    finally:
        os.unlink(path)


def test_trainer_runs_and_returns_metrics():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=50, freq="h"),
        "open": [150.0] * 50,
        "high": [151.0] * 50,
        "low": [149.0] * 50,
        "close": [150.0 + i * 0.1 for i in range(50)],
        "volume": [1000] * 50,
    })
    trainer = MLTrainer(model_type="logistic_regression")
    metrics = trainer.train(df)
    assert "train_accuracy" in metrics
    assert "test_accuracy" in metrics
    assert 0 <= metrics["train_accuracy"] <= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && pytest tests/test_ml.py -v
```

Expected:
```
FAILED tests/test_ml.py::test_predictor_trains_and_predicts - ModuleNotFoundError: No module named 'src.ml.predictor'
FAILED tests/test_ml.py::test_predictor_save_and_load - ModuleNotFoundError: No module named 'src.ml.predictor'
FAILED tests/test_ml.py::test_trainer_runs_and_returns_metrics - ModuleNotFoundError: No module named 'src.ml.trainer'
```

- [ ] **Step 3: Update `requirements.txt`**

Add `scikit-learn` to the end of the file:

```
pandas>=2.0.0
numpy>=1.24.0
pytest>=7.4.0
matplotlib>=3.7.0
requests>=2.31.0
python-dotenv>=1.0.0
scikit-learn>=1.3.0
```

Install it:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && pip install scikit-learn>=1.3.0
```

- [ ] **Step 4: Create `src/ml/predictor.py`**

Full file:

```python
import pickle
from typing import Optional
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier


class MLPredictor:
    def __init__(self, model_type: str = "logistic_regression"):
        self.model_type = model_type
        self.model = None

    def fit(self, X: pd.DataFrame, y: pd.Series):
        if self.model_type == "logistic_regression":
            self.model = LogisticRegression(max_iter=1000, multi_class="multinomial")
        elif self.model_type == "random_forest":
            self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        else:
            raise ValueError(f"Unknown model_type: {self.model_type}")
        self.model.fit(X, y)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Model not trained. Call fit() first.")
        return self.model.predict(X)

    def predict_proba(self, X: pd.DataFrame) -> Optional[np.ndarray]:
        if self.model is None:
            raise RuntimeError("Model not trained. Call fit() first.")
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(X)
        return None

    def save(self, path: str):
        if self.model is None:
            raise RuntimeError("Model not trained.")
        with open(path, "wb") as f:
            pickle.dump(self.model, f)

    def load(self, path: str):
        with open(path, "rb") as f:
            self.model = pickle.load(f)
```

- [ ] **Step 5: Create `src/ml/trainer.py`**

Full file:

```python
from typing import Dict
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

from .predictor import MLPredictor
from .feature_engineer import FeatureEngineer


class MLTrainer:
    def __init__(self, model_type: str = "logistic_regression", test_size: float = 0.2):
        self.model_type = model_type
        self.test_size = test_size
        self.predictor = MLPredictor(model_type=model_type)
        self.feature_engineer = FeatureEngineer()

    def train(self, df: pd.DataFrame) -> Dict:
        X, y = self.feature_engineer.create_features_and_target(df)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=self.test_size, shuffle=False
        )
        self.predictor.fit(X_train, y_train)
        train_pred = self.predictor.predict(X_train)
        test_pred = self.predictor.predict(X_test)
        metrics = {
            "train_accuracy": accuracy_score(y_train, train_pred),
            "test_accuracy": accuracy_score(y_test, test_pred),
        }
        return metrics

    def save_model(self, path: str):
        self.predictor.save(path)

    def load_model(self, path: str):
        self.predictor.load(path)

    def evaluate(self, df: pd.DataFrame) -> Dict:
        X, y = self.feature_engineer.create_features_and_target(df)
        pred = self.predictor.predict(X)
        return {
            "accuracy": accuracy_score(y, pred),
            "report": classification_report(y, pred, output_dict=True, zero_division=0),
        }
```

- [ ] **Step 6: Run tests to verify they pass**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && pytest tests/test_ml.py -v
```

Expected:
```
============================= test session starts ==============================
tests/test_ml.py::test_feature_engineer_creates_features_and_target PASSED
tests/test_ml.py::test_feature_engineer_creates_features_only PASSED
tests/test_ml.py::test_predictor_trains_and_predicts PASSED
tests/test_ml.py::test_predictor_save_and_load PASSED
tests/test_ml.py::test_trainer_runs_and_returns_metrics PASSED
============================== 5 passed in ...s ==============================
```

- [ ] **Step 7: Commit**

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && git add src/ml/predictor.py src/ml/trainer.py tests/test_ml.py requirements.txt && git commit -m "feat: add ML predictor and trainer with scikit-learn"
```

---

### Task 8: ML Strategy Wrapper

**Files:**
- Create: `src/ml/strategy.py`
- Modify: `src/strategies/factory.py`
- Modify: `tests/test_ml.py` (append tests)

- [ ] **Step 1: Write the failing test**

Append to `/Users/hideakimacbookair/自動トレード/fx_trading/tests/test_ml.py`:

```python
from src.ml.strategy import MLStrategy


def test_ml_strategy_generates_signals():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=50, freq="h"),
        "open": [150.0] * 50,
        "high": [151.0] * 50,
        "low": [149.0] * 50,
        "close": [150.0 + i * 0.1 for i in range(50)],
        "volume": [1000] * 50,
    })
    strategy = MLStrategy(model_type="logistic_regression")
    metrics = strategy.train(df)
    assert "train_accuracy" in metrics

    result = strategy.generate_signals(df)
    assert "signal" in result.columns
    assert result.iloc[-1]["signal"] in [-1, 0, 1]


def test_ml_strategy_registered_in_factory():
    from src.strategies.factory import StrategyFactory
    strategy = StrategyFactory.create("ml_logistic")
    assert isinstance(strategy, MLStrategy)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && pytest tests/test_ml.py::test_ml_strategy_generates_signals tests/test_ml.py::test_ml_strategy_registered_in_factory -v
```

Expected:
```
FAILED tests/test_ml.py::test_ml_strategy_generates_signals - ModuleNotFoundError: No module named 'src.ml.strategy'
FAILED tests/test_ml.py::test_ml_strategy_registered_in_factory - ModuleNotFoundError: No module named 'src.ml.strategy'
```

- [ ] **Step 3: Create `src/ml/strategy.py`**

Full file:

```python
import pandas as pd
from src.strategies.base import Strategy
from .predictor import MLPredictor
from .feature_engineer import FeatureEngineer


class MLStrategy(Strategy):
    def __init__(self, model_type: str = "logistic_regression", model_path: str = None):
        self.feature_engineer = FeatureEngineer()
        self.predictor = MLPredictor(model_type=model_type)
        if model_path:
            self.predictor.load(model_path)

    def train(self, df: pd.DataFrame) -> dict:
        from .trainer import MLTrainer
        trainer = MLTrainer(model_type=self.predictor.model_type)
        trainer.predictor = self.predictor
        trainer.feature_engineer = self.feature_engineer
        metrics = trainer.train(df)
        return metrics

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        features_df = self.feature_engineer.create_features(df)
        valid_idx = features_df.dropna().index
        if len(valid_idx) == 0:
            df["signal"] = 0
            return df

        latest_idx = valid_idx[-1]
        latest_features = features_df.loc[[latest_idx]]
        prediction = self.predictor.predict(latest_features)[0]
        df["signal"] = 0
        df.loc[latest_idx, "signal"] = int(prediction)
        return df
```

- [ ] **Step 4: Modify `src/strategies/factory.py`**

Full file:

```python
from typing import Dict, Type, List
from .base import Strategy
from .ma_macd import MaMacdStrategy
from .ma_cross import MaCrossStrategy
from .dow_theory import DowTheoryStrategy
from .stochastic import StochasticStrategy
from src.ml.strategy import MLStrategy

class StrategyFactory:
    _registry: Dict[str, Type[Strategy]] = {
        "ma_macd": MaMacdStrategy,
        "ma_cross": MaCrossStrategy,
        "dow_theory": DowTheoryStrategy,
        "stochastic": StochasticStrategy,
        "ml_logistic": MLStrategy,
    }

    @classmethod
    def available_strategies(cls) -> List[str]:
        return list(cls._registry.keys())

    @classmethod
    def create(cls, name: str, **kwargs) -> Strategy:
        if name not in cls._registry:
            raise ValueError(f"Unknown strategy: {name}. Available: {cls.available_strategies()}")
        return cls._registry[name](**kwargs)

    @classmethod
    def register(cls, name: str, strategy_class: Type[Strategy]):
        cls._registry[name] = strategy_class
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && pytest tests/test_ml.py -v
```

Expected:
```
============================= test session starts ==============================
tests/test_ml.py::test_feature_engineer_creates_features_and_target PASSED
tests/test_ml.py::test_feature_engineer_creates_features_only PASSED
tests/test_ml.py::test_predictor_trains_and_predicts PASSED
tests/test_ml.py::test_predictor_save_and_load PASSED
tests/test_ml.py::test_trainer_runs_and_returns_metrics PASSED
tests/test_ml.py::test_ml_strategy_generates_signals PASSED
tests/test_ml.py::test_ml_strategy_registered_in_factory PASSED
============================== 7 passed in ...s ==============================
```

Also verify the factory tests still pass:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && pytest tests/test_factory.py -v
```

Expected:
```
tests/test_factory.py::test_factory_lists_available_strategies PASSED
tests/test_factory.py::test_factory_creates_ma_macd PASSED
tests/test_factory.py::test_factory_raises_on_unknown_strategy PASSED
============================== 3 passed in ...s ==============================
```

- [ ] **Step 6: Commit**

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && git add src/ml/strategy.py src/strategies/factory.py tests/test_ml.py && git commit -m "feat: add ML strategy wrapper and register in factory"
```

---

### Task 9: Final Verification

**Files:** All modified/created above

- [ ] **Step 1: Run ALL tests**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && pytest tests/ -v
```

Expected:
```
============================= test session starts ==============================
collected ... items
tests/test_api.py::test_exporter_creates_backtest_json PASSED
tests/test_api.py::test_exporter_creates_trade_log_json PASSED
tests/test_broker.py::test_client_constructs_practice_url PASSED
tests/test_broker.py::test_client_constructs_live_url PASSED
tests/test_broker.py::test_get_current_price PASSED
tests/test_broker.py::test_get_open_positions PASSED
tests/test_broker.py::test_place_order PASSED
tests/test_broker.py::test_get_account_summary_raises_on_error PASSED
tests/test_broker.py::test_build_market_order_long PASSED
tests/test_broker.py::test_build_market_order_short PASSED
tests/test_broker.py::test_build_market_order_without_stop PASSED
tests/test_config.py::test_settings_loads_from_env PASSED
tests/test_config.py::test_settings_defaults PASSED
tests/test_config.py::test_settings_raises_on_missing_token PASSED
tests/test_data.py::test_load_csv PASSED
tests/test_data.py::test_preprocessor_sorts_and_drops_na PASSED
tests/test_engine.py::test_backtest_runs_and_produces_trades PASSED
tests/test_engine.py::test_backtest_capital_changes PASSED
tests/test_engine.py::test_engine_supports_backtest_mode PASSED
tests/test_engine.py::test_engine_supports_live_mode PASSED
tests/test_engine.py::test_live_mode_checks_position_before_entry PASSED
tests/test_factory.py::test_factory_lists_available_strategies PASSED
tests/test_factory.py::test_factory_creates_ma_macd PASSED
tests/test_factory.py::test_factory_raises_on_unknown_strategy PASSED
tests/test_ml.py::test_feature_engineer_creates_features_and_target PASSED
tests/test_ml.py::test_feature_engineer_creates_features_only PASSED
tests/test_ml.py::test_predictor_trains_and_predicts PASSED
tests/test_ml.py::test_predictor_save_and_load PASSED
tests/test_ml.py::test_trainer_runs_and_returns_metrics PASSED
tests/test_ml.py::test_ml_strategy_generates_signals PASSED
tests/test_ml.py::test_ml_strategy_registered_in_factory PASSED
tests/test_monitoring.py ... PASSED
tests/test_multi_pair.py::test_settings_loads_multiple_pairs PASSED
tests/test_multi_pair.py::test_settings_defaults_single_pair PASSED
tests/test_multi_pair.py::test_settings_backward_compatible_with_currency_pair PASSED
tests/test_multi_pair.py::test_data_loader_loads_multiple_pairs PASSED
tests/test_multi_pair.py::test_data_loader_returns_none_for_missing_pair PASSED
tests/test_multi_pair.py::test_oanda_client_get_current_prices PASSED
tests/test_notifications.py ... PASSED
tests/test_optimizer.py::test_grid_search_runs PASSED
tests/test_optimizer.py::test_grid_search_finds_best PASSED
tests/test_reports.py ... PASSED
tests/test_risk.py ... PASSED
tests/test_runner.py::test_runner_constructs_with_dependencies PASSED
tests/test_runner.py::test_runner_checks_circuit_breaker PASSED
tests/test_runner.py::test_runner_fetches_prices PASSED
tests/test_runner.py::test_runner_uses_multiple_strategies PASSED
tests/test_runner.py::test_runner_aggregates_signals PASSED
tests/test_runner.py::test_runner_processes_multiple_pairs PASSED
tests/test_safety.py ... PASSED
tests/test_selector.py ... PASSED
tests/test_strategies.py ... PASSED
tests/test_wfa.py::test_walk_forward_splits_data PASSED
tests/test_wfa.py::test_walk_forward_runs_analysis PASSED
============================== ... passed in ...s ============================
```

- [ ] **Step 2: Run backtest with multi-pair**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && python -m src.main --backtest
```

Expected output (truncated):
```
=== Grid Search: ma_macd | USD_JPY ===
Best params: {'fast': ..., 'slow': ..., 'signal': ...}
Profit Factor: ...

=== Walk-Forward Analysis: ma_macd | USD_JPY ===
Window 1: Train PF=..., Test PF=..., Params=...

=== Strategy Ranking | USD_JPY ===
ma_macd Best: Score=...
...
Backtest results exported to dashboard/data/backtest_results.json
```

Verify the JSON file was updated:
```bash
cat /Users/hideakimacbookair/自動トレード/fx_trading/dashboard/data/backtest_results.json | python3 -m json.tool | head -n 10
```

Expected:
```json
{
    "generated_at": "...",
    "pairs": {
        "USD_JPY": [
            ...
```

- [ ] **Step 3: Verify dashboard server**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && python3 -m src.api.server &
SERVER_PID=$!
sleep 2
curl -s http://localhost:8080/api/backtest | python3 -m json.tool | head -n 5
curl -s http://localhost:8080/index.html | head -n 5
kill $SERVER_PID
```

Expected:
```json
{
    "generated_at": "...",
    "pairs": {
        "USD_JPY": [
            {
...
```

And for index.html:
```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
```

- [ ] **Step 4: Final commit**

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && git add -A && git commit -m "feat: complete multi-pair, dashboard, and ML extensions"
```

---

## Self-Review Checklist

1. **Spec coverage:**
   - Multi-Currency Pair Support: Tasks 1-2 cover settings, loader, broker, runner, main.
   - Web Dashboard: Tasks 3-5 cover JSON exporter, HTML/JS frontend, HTTP server.
   - Machine Learning Predictor: Tasks 6-8 cover feature engineer, predictor, trainer, strategy wrapper, factory registration.

2. **Placeholder scan:**
   - No TBD, TODO, or placeholders found.
   - Every code step shows full file contents or exact diff.
   - Every test shows exact assertion code.
   - Every verification shows exact run command and expected output.

3. **Type consistency:**
   - `Settings.currency_pairs` is `List[str]` everywhere.
   - `DataLoader.load_multiple` returns `Dict[str, Optional[pd.DataFrame]]`.
   - `OandaClient.get_current_prices` returns `Dict[str, Dict]`.
   - `MLStrategy` implements `Strategy.generate_signals(df) -> df`.
   - Factory registers `MLStrategy` under key `"ml_logistic"`.
   - `DataExporter` methods return `str` (filepath).

4. **Static web app rules compliance:**
   - Dashboard uses Tailwind CSS CDN and Chart.js CDN only.
   - No build tools, no frameworks, no npm.
   - Files are copy-paste deployable.
   - Server is plain Python `http.server` compatible.
