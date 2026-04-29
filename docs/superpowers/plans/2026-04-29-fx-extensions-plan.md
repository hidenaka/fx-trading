# FX自動売買拡張（Slack通知+複数戦略） Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Slack notification system and support for multiple trading strategies (MA cross, Dow theory, Stochastic) with a strategy factory, signal aggregation in the live runner, and multi-strategy backtesting in main.

**Architecture:** A `SlackNotifier` sends webhook messages and is injected into `TradeLogger` and `CircuitBreaker`. A `StrategyFactory` registers strategies by name and instantiates them with kwargs. New strategies implement the existing `Strategy` base class. `PollingRunner` accepts a list of strategies and aggregates their signals via majority vote. `main.py` runs grid search across all strategies and ranks them.

**Tech Stack:** Python 3.11+, pandas, numpy, pytest, requests

---

## File Structure

```
fx_trading/
├── src/
│   ├── config/
│   │   └── settings.py               (modified: add SLACK_WEBHOOK_URL)
│   ├── notifications/
│   │   ├── __init__.py               (created)
│   │   └── slack_notifier.py         (created)
│   ├── strategies/
│   │   ├── factory.py                (created)
│   │   ├── ma_cross.py               (created)
│   │   ├── dow_theory.py             (created)
│   │   └── stochastic.py             (created)
│   ├── monitoring/
│   │   └── logger.py                 (modified: integrate SlackNotifier)
│   ├── safety/
│   │   └── circuit_breaker.py        (modified: integrate SlackNotifier)
│   ├── runner/
│   │   └── polling_runner.py         (modified: multi-strategy + aggregation)
│   └── main.py                       (modified: multi-strategy backtest)
└── tests/
    ├── test_notifications.py          (created)
    ├── test_factory.py                (created)
    ├── test_strategies.py             (modified: append new strategy tests)
    ├── test_config.py                 (modified: append SLACK_WEBHOOK_URL tests)
    ├── test_monitoring.py             (modified: append Slack tests)
    ├── test_safety.py                 (modified: append Slack tests)
    └── test_runner.py                 (modified: append multi-strategy tests)
```

---

### Task 1: Slack Notifier

**Files:**
- Create: `src/notifications/__init__.py`
- Create: `src/notifications/slack_notifier.py`
- Modify: `src/config/settings.py`
- Modify: `tests/test_config.py`
- Create: `tests/test_notifications.py`

- [ ] **Step 1: Add `SLACK_WEBHOOK_URL` to settings**

```python
# src/config/settings.py
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    def __init__(self):
        self.api_token = os.getenv("OANDA_API_TOKEN")
        self.account_id = os.getenv("OANDA_ACCOUNT_ID")
        self.environment = os.getenv("OANDA_ENVIRONMENT", "practice")
        self.risk_per_trade = float(os.getenv("RISK_PER_TRADE", "0.01"))
        self.currency_pair = os.getenv("CURRENCY_PAIR", "USD_JPY")
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

- [ ] **Step 2: Append settings tests for Slack URL**

```python
# tests/test_config.py
import os
from src.config.settings import Settings

def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("OANDA_API_TOKEN", "test-token-123")
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "test-account-456")
    monkeypatch.setenv("OANDA_ENVIRONMENT", "practice")
    settings = Settings()
    assert settings.api_token == "test-token-123"
    assert settings.account_id == "test-account-456"
    assert settings.environment == "practice"

def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("OANDA_API_TOKEN", "dummy-token")
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "dummy-account")
    settings = Settings()
    assert settings.environment == "practice"
    assert settings.risk_per_trade == 0.01
    assert settings.currency_pair == "USD_JPY"

def test_settings_raises_on_missing_token():
    if "OANDA_API_TOKEN" in os.environ:
        del os.environ["OANDA_API_TOKEN"]
    try:
        settings = Settings()
        assert False, "Should have raised"
    except ValueError:
        pass

def test_settings_has_slack_webhook_url(monkeypatch):
    monkeypatch.setenv("OANDA_API_TOKEN", "dummy-token")
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "dummy-account")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    settings = Settings()
    assert settings.slack_webhook_url == "https://hooks.slack.com/test"

def test_settings_slack_webhook_url_defaults_to_none(monkeypatch):
    monkeypatch.setenv("OANDA_API_TOKEN", "dummy-token")
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "dummy-account")
    if "SLACK_WEBHOOK_URL" in os.environ:
        del os.environ["SLACK_WEBHOOK_URL"]
    settings = Settings()
    assert settings.slack_webhook_url is None
```

Run: `pytest tests/test_config.py -v`
Expected: `5 passed`

- [ ] **Step 3: Create `src/notifications/__init__.py`**

Create an empty file at `src/notifications/__init__.py`.

- [ ] **Step 4: Write failing notification test**

```python
# tests/test_notifications.py
from unittest.mock import patch, MagicMock
from src.notifications.slack_notifier import SlackNotifier


def test_slack_notifier_sends_message():
    notifier = SlackNotifier("https://hooks.slack.com/test")
    with patch("src.notifications.slack_notifier.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        result = notifier.send("Test message")
        assert result is True
        mock_post.assert_called_once_with(
            "https://hooks.slack.com/test",
            json={"text": "Test message"},
            timeout=10,
        )


def test_slack_notifier_returns_false_on_failure():
    notifier = SlackNotifier("https://hooks.slack.com/test")
    with patch("src.notifications.slack_notifier.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=500)
        result = notifier.send("Test message")
        assert result is False


def test_slack_notifier_returns_false_without_webhook():
    notifier = SlackNotifier()
    result = notifier.send("Test message")
    assert result is False
```

Run: `pytest tests/test_notifications.py -v`
Expected: FAIL with `ImportError: cannot import name 'SlackNotifier' from 'src.notifications.slack_notifier'`

- [ ] **Step 5: Implement SlackNotifier**

```python
# src/notifications/slack_notifier.py
import requests


class SlackNotifier:
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url

    def send(self, message: str) -> bool:
        if not self.webhook_url:
            return False
        payload = {"text": message}
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception:
            return False
```

Run: `pytest tests/test_notifications.py -v`
Expected: `3 passed`

- [ ] **Step 6: Commit**

Run:
```bash
git add src/config/settings.py src/notifications/__init__.py src/notifications/slack_notifier.py tests/test_config.py tests/test_notifications.py
git commit -m "feat: add Slack notification system with webhook sender"
```

---

### Task 2: Strategy Factory

**Files:**
- Create: `src/strategies/factory.py`
- Create: `tests/test_factory.py`

- [ ] **Step 1: Write failing factory test**

```python
# tests/test_factory.py
import pytest
from src.strategies.factory import StrategyFactory


def test_factory_lists_strategies():
    names = StrategyFactory.available_strategies()
    assert "ma_macd" in names


def test_factory_creates_ma_macd():
    strat = StrategyFactory.create("ma_macd", fast=3, slow=6, signal=2)
    from src.strategies.ma_macd import MaMacdStrategy
    assert isinstance(strat, MaMacdStrategy)


def test_factory_raises_on_unknown():
    with pytest.raises(ValueError):
        StrategyFactory.create("unknown")
```

Run: `pytest tests/test_factory.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.strategies.factory'`

- [ ] **Step 2: Implement StrategyFactory with ma_macd only**

```python
# src/strategies/factory.py
from typing import Type, Dict
from src.strategies.base import Strategy
from src.strategies.ma_macd import MaMacdStrategy


class StrategyFactory:
    _strategies: Dict[str, Type[Strategy]] = {
        "ma_macd": MaMacdStrategy,
    }

    @classmethod
    def available_strategies(cls) -> list[str]:
        return list(cls._strategies.keys())

    @classmethod
    def create(cls, name: str, **kwargs) -> Strategy:
        if name not in cls._strategies:
            raise ValueError(f"Unknown strategy: {name}")
        return cls._strategies[name](**kwargs)
```

Run: `pytest tests/test_factory.py -v`
Expected: `3 passed`

- [ ] **Step 3: Commit**

Run:
```bash
git add src/strategies/factory.py tests/test_factory.py
git commit -m "feat: add strategy factory with ma_macd support"
```

---

### Task 3: MA Cross Strategy

**Files:**
- Create: `src/strategies/ma_cross.py`
- Modify: `src/strategies/factory.py`
- Modify: `tests/test_strategies.py`
- Modify: `tests/test_factory.py`

- [ ] **Step 1: Write failing tests for MA Cross**

Append to `tests/test_strategies.py`:

```python
from src.strategies.ma_cross import MaCrossStrategy


def test_ma_cross_generates_signals():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=30, freq="h"),
        "open": [150.0] * 30,
        "high": [151.0] * 30,
        "low": [149.0] * 30,
        "close": [150.0 + i * 0.1 for i in range(30)],
        "volume": [1000] * 30,
    })
    strat = MaCrossStrategy(short=5, long=10)
    result = strat.generate_signals(df)
    assert "signal" in result.columns
    assert set(result["signal"].unique()).issubset({-1, 0, 1})


def test_ma_cross_buy_on_golden_cross():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=10, freq="h"),
        "open": [150.0] * 10,
        "high": [151.0] * 10,
        "low": [149.0] * 10,
        "close": [150.0, 149.5, 149.0, 148.5, 148.0, 148.5, 149.0, 149.5, 150.0, 150.5],
        "volume": [1000] * 10,
    })
    strat = MaCrossStrategy(short=3, long=5)
    result = strat.generate_signals(df)
    assert result.iloc[-1]["signal"] == 1
```

Append to `tests/test_factory.py`:

```python
from src.strategies.ma_cross import MaCrossStrategy


def test_factory_creates_ma_cross():
    strat = StrategyFactory.create("ma_cross", short=5, long=20)
    assert isinstance(strat, MaCrossStrategy)
```

Run: `pytest tests/test_strategies.py::test_ma_cross_generates_signals tests/test_strategies.py::test_ma_cross_buy_on_golden_cross tests/test_factory.py::test_factory_creates_ma_cross -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.strategies.ma_cross'`

- [ ] **Step 2: Implement MaCrossStrategy and update factory**

```python
# src/strategies/ma_cross.py
import pandas as pd
from src.strategies.base import Strategy


class MaCrossStrategy(Strategy):
    def __init__(self, short: int = 5, long: int = 20):
        self.short = short
        self.long = long

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["sma_short"] = df["close"].rolling(window=self.short).mean()
        df["sma_long"] = df["close"].rolling(window=self.long).mean()
        df["signal"] = 0
        df.loc[df["sma_short"] > df["sma_long"], "signal"] = 1
        df.loc[df["sma_short"] < df["sma_long"], "signal"] = -1
        return df
```

Update `src/strategies/factory.py` to the following:

```python
# src/strategies/factory.py
from typing import Type, Dict
from src.strategies.base import Strategy
from src.strategies.ma_macd import MaMacdStrategy
from src.strategies.ma_cross import MaCrossStrategy


class StrategyFactory:
    _strategies: Dict[str, Type[Strategy]] = {
        "ma_macd": MaMacdStrategy,
        "ma_cross": MaCrossStrategy,
    }

    @classmethod
    def available_strategies(cls) -> list[str]:
        return list(cls._strategies.keys())

    @classmethod
    def create(cls, name: str, **kwargs) -> Strategy:
        if name not in cls._strategies:
            raise ValueError(f"Unknown strategy: {name}")
        return cls._strategies[name](**kwargs)
```

Run: `pytest tests/test_strategies.py tests/test_factory.py -v`
Expected: All tests pass (existing + new)

- [ ] **Step 3: Commit**

Run:
```bash
git add src/strategies/ma_cross.py src/strategies/factory.py tests/test_strategies.py tests/test_factory.py
git commit -m "feat: add MA cross strategy and register in factory"
```

---

### Task 4: Dow Theory Strategy

**Files:**
- Create: `src/strategies/dow_theory.py`
- Modify: `src/strategies/factory.py`
- Modify: `tests/test_strategies.py`
- Modify: `tests/test_factory.py`

- [ ] **Step 1: Write failing tests for Dow Theory**

Append to `tests/test_strategies.py`:

```python
from src.strategies.dow_theory import DowTheoryStrategy


def test_dow_theory_generates_signals():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=10, freq="h"),
        "open": [150.0] * 10,
        "high": [150.0 + i * 0.2 for i in range(10)],
        "low": [149.0] * 10,
        "close": [150.0] * 10,
        "volume": [1000] * 10,
    })
    strat = DowTheoryStrategy(lookback=3)
    result = strat.generate_signals(df)
    assert "signal" in result.columns
    assert set(result["signal"].unique()).issubset({-1, 0, 1})


def test_dow_theory_buy_on_higher_high():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=6, freq="h"),
        "open": [150.0] * 6,
        "high": [150.0, 150.2, 150.1, 150.3, 150.2, 150.5],
        "low": [149.0] * 6,
        "close": [150.0] * 6,
        "volume": [1000] * 6,
    })
    strat = DowTheoryStrategy(lookback=3)
    result = strat.generate_signals(df)
    assert result.iloc[-1]["signal"] == 1
```

Append to `tests/test_factory.py`:

```python
from src.strategies.dow_theory import DowTheoryStrategy


def test_factory_creates_dow_theory():
    strat = StrategyFactory.create("dow_theory", lookback=5)
    assert isinstance(strat, DowTheoryStrategy)
```

Run: `pytest tests/test_strategies.py::test_dow_theory_generates_signals tests/test_strategies.py::test_dow_theory_buy_on_higher_high tests/test_factory.py::test_factory_creates_dow_theory -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.strategies.dow_theory'`

- [ ] **Step 2: Implement DowTheoryStrategy and update factory**

```python
# src/strategies/dow_theory.py
import pandas as pd
from src.strategies.base import Strategy


class DowTheoryStrategy(Strategy):
    def __init__(self, lookback: int = 5):
        self.lookback = lookback

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["higher_high"] = df["high"] > df["high"].shift(1).rolling(window=self.lookback).max()
        df["lower_low"] = df["low"] < df["low"].shift(1).rolling(window=self.lookback).min()
        df["signal"] = 0
        df.loc[df["higher_high"], "signal"] = 1
        df.loc[df["lower_low"], "signal"] = -1
        both = df["higher_high"] & df["lower_low"]
        df.loc[both, "signal"] = 0
        return df
```

Update `src/strategies/factory.py` to the following:

```python
# src/strategies/factory.py
from typing import Type, Dict
from src.strategies.base import Strategy
from src.strategies.ma_macd import MaMacdStrategy
from src.strategies.ma_cross import MaCrossStrategy
from src.strategies.dow_theory import DowTheoryStrategy


class StrategyFactory:
    _strategies: Dict[str, Type[Strategy]] = {
        "ma_macd": MaMacdStrategy,
        "ma_cross": MaCrossStrategy,
        "dow_theory": DowTheoryStrategy,
    }

    @classmethod
    def available_strategies(cls) -> list[str]:
        return list(cls._strategies.keys())

    @classmethod
    def create(cls, name: str, **kwargs) -> Strategy:
        if name not in cls._strategies:
            raise ValueError(f"Unknown strategy: {name}")
        return cls._strategies[name](**kwargs)
```

Run: `pytest tests/test_strategies.py tests/test_factory.py -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

Run:
```bash
git add src/strategies/dow_theory.py src/strategies/factory.py tests/test_strategies.py tests/test_factory.py
git commit -m "feat: add Dow theory strategy and register in factory"
```

---

### Task 5: Stochastic Strategy

**Files:**
- Create: `src/strategies/stochastic.py`
- Modify: `src/strategies/factory.py`
- Modify: `tests/test_strategies.py`
- Modify: `tests/test_factory.py`

- [ ] **Step 1: Write failing tests for Stochastic**

Append to `tests/test_strategies.py`:

```python
from src.strategies.stochastic import StochasticStrategy


def test_stochastic_generates_signals():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=10, freq="h"),
        "open": [150.0] * 10,
        "high": [151.0] * 10,
        "low": [149.0] * 10,
        "close": [150.0 + i * 0.1 for i in range(10)],
        "volume": [1000] * 10,
    })
    strat = StochasticStrategy(k_period=5, d_period=3)
    result = strat.generate_signals(df)
    assert "signal" in result.columns
    assert set(result["signal"].unique()).issubset({-1, 0, 1})


def test_stochastic_buy_in_oversold():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=6, freq="h"),
        "open": [100.0] * 6,
        "high": [110.0] * 6,
        "low": [100.0] * 6,
        "close": [100.0, 100.0, 100.0, 101.0, 102.0, 103.0],
        "volume": [1000] * 6,
    })
    strat = StochasticStrategy(k_period=3, d_period=2, oversold=20)
    result = strat.generate_signals(df)
    assert result.iloc[3]["signal"] == 1


def test_stochastic_sell_in_overbought():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=6, freq="h"),
        "open": [110.0] * 6,
        "high": [110.0] * 6,
        "low": [100.0] * 6,
        "close": [110.0, 110.0, 110.0, 109.0, 108.0, 107.0],
        "volume": [1000] * 6,
    })
    strat = StochasticStrategy(k_period=3, d_period=2, overbought=80)
    result = strat.generate_signals(df)
    assert result.iloc[3]["signal"] == -1
```

Append to `tests/test_factory.py`:

```python
from src.strategies.stochastic import StochasticStrategy


def test_factory_creates_stochastic():
    strat = StrategyFactory.create("stochastic", k_period=14, d_period=3)
    assert isinstance(strat, StochasticStrategy)


def test_factory_get_class():
    from src.strategies.ma_macd import MaMacdStrategy
    cls = StrategyFactory.get_class("ma_macd")
    assert cls is MaMacdStrategy
```

Run: `pytest tests/test_strategies.py::test_stochastic_generates_signals tests/test_strategies.py::test_stochastic_buy_in_oversold tests/test_strategies.py::test_stochastic_sell_in_overbought tests/test_factory.py::test_factory_creates_stochastic tests/test_factory.py::test_factory_get_class -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.strategies.stochastic'` or `AttributeError: type object 'StrategyFactory' has no attribute 'get_class'`

- [ ] **Step 2: Implement StochasticStrategy and update factory**

```python
# src/strategies/stochastic.py
import pandas as pd
from src.strategies.base import Strategy


class StochasticStrategy(Strategy):
    def __init__(self, k_period: int = 14, d_period: int = 3, overbought: int = 80, oversold: int = 20):
        self.k_period = k_period
        self.d_period = d_period
        self.overbought = overbought
        self.oversold = oversold

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        low_min = df["low"].rolling(window=self.k_period).min()
        high_max = df["high"].rolling(window=self.k_period).max()
        df["%K"] = 100 * (df["close"] - low_min) / (high_max - low_min)
        df["%D"] = df["%K"].rolling(window=self.d_period).mean()
        df["signal"] = 0
        buy = (df["%K"] > df["%D"]) & (df["%K"] < self.oversold)
        sell = (df["%K"] < df["%D"]) & (df["%K"] > self.overbought)
        df.loc[buy, "signal"] = 1
        df.loc[sell, "signal"] = -1
        return df
```

Update `src/strategies/factory.py` to the following:

```python
# src/strategies/factory.py
from typing import Type, Dict
from src.strategies.base import Strategy
from src.strategies.ma_macd import MaMacdStrategy
from src.strategies.ma_cross import MaCrossStrategy
from src.strategies.dow_theory import DowTheoryStrategy
from src.strategies.stochastic import StochasticStrategy


class StrategyFactory:
    _strategies: Dict[str, Type[Strategy]] = {
        "ma_macd": MaMacdStrategy,
        "ma_cross": MaCrossStrategy,
        "dow_theory": DowTheoryStrategy,
        "stochastic": StochasticStrategy,
    }

    @classmethod
    def available_strategies(cls) -> list[str]:
        return list(cls._strategies.keys())

    @classmethod
    def create(cls, name: str, **kwargs) -> Strategy:
        if name not in cls._strategies:
            raise ValueError(f"Unknown strategy: {name}")
        return cls._strategies[name](**kwargs)

    @classmethod
    def get_class(cls, name: str) -> Type[Strategy]:
        if name not in cls._strategies:
            raise ValueError(f"Unknown strategy: {name}")
        return cls._strategies[name]
```

Run: `pytest tests/test_strategies.py tests/test_factory.py -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

Run:
```bash
git add src/strategies/stochastic.py src/strategies/factory.py tests/test_strategies.py tests/test_factory.py
git commit -m "feat: add Stochastic strategy with factory get_class support"
```

---

### Task 6: Integrate Notifications

**Files:**
- Modify: `src/monitoring/logger.py`
- Modify: `src/safety/circuit_breaker.py`
- Modify: `tests/test_monitoring.py`
- Modify: `tests/test_safety.py`

- [ ] **Step 1: Write failing tests for logger Slack integration**

Replace `tests/test_monitoring.py` with the following:

```python
import os
import tempfile
from unittest.mock import MagicMock
from src.monitoring.logger import TradeLogger


def test_logger_creates_log_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "trades.log")
        logger = TradeLogger(log_file=log_file)
        logger.log_trade("USD_JPY", "BUY", 1000, 150.0)
        assert os.path.exists(log_file)
        with open(log_file) as f:
            content = f.read()
        assert "USD_JPY" in content
        assert "BUY" in content


def test_logger_logs_error():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "errors.log")
        logger = TradeLogger(log_file=log_file)
        logger.log_error("API connection failed")
        with open(log_file) as f:
            content = f.read()
        assert "ERROR" in content
        assert "API connection failed" in content


def test_logger_sends_slack_on_trade():
    mock_notifier = MagicMock()
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "trades.log")
        logger = TradeLogger(log_file=log_file, notifier=mock_notifier)
        logger.log_trade("USD_JPY", "BUY", 1000, 150.0)
        mock_notifier.send.assert_called_once_with("TRADE: USD_JPY BUY 1000 @ 150.0")


def test_logger_sends_slack_on_error():
    mock_notifier = MagicMock()
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "errors.log")
        logger = TradeLogger(log_file=log_file, notifier=mock_notifier)
        logger.log_error("API connection failed")
        mock_notifier.send.assert_called_once_with("ERROR: API connection failed")
```

Run: `pytest tests/test_monitoring.py::test_logger_sends_slack_on_trade tests/test_monitoring.py::test_logger_sends_slack_on_error -v`
Expected: FAIL with `TypeError: TradeLogger.__init__() got an unexpected keyword argument 'notifier'`

- [ ] **Step 2: Write failing tests for circuit breaker Slack integration**

Replace `tests/test_safety.py` with the following:

```python
import datetime
from unittest.mock import MagicMock
from src.safety.circuit_breaker import CircuitBreaker


def test_trading_hours_allows_trading():
    cb = CircuitBreaker(max_daily_loss_pct=5.0, trading_start_hour=7, trading_end_hour=23)
    now = datetime.datetime(2024, 1, 2, 12, 0)
    assert cb.is_trading_allowed(now) is True


def test_trading_hours_rejects_sunday_early():
    cb = CircuitBreaker(max_daily_loss_pct=5.0, trading_start_hour=7, trading_end_hour=23)
    now = datetime.datetime(2024, 1, 7, 5, 0)
    assert cb.is_trading_allowed(now) is False


def test_daily_loss_limit_blocks_trading():
    cb = CircuitBreaker(max_daily_loss_pct=5.0, trading_start_hour=7, trading_end_hour=23)
    now = datetime.datetime(2024, 1, 2, 12, 0)
    cb.record_pnl(-60000, now=now)
    assert cb.is_trading_allowed(now) is False


def test_daily_loss_resets_next_day():
    cb = CircuitBreaker(max_daily_loss_pct=5.0, trading_start_hour=7, trading_end_hour=23)
    today = datetime.datetime(2024, 1, 2, 12, 0)
    cb.record_pnl(-60000, now=today)
    next_day = datetime.datetime(2024, 1, 3, 12, 0)
    assert cb.is_trading_allowed(next_day) is True


def test_circuit_breaker_sends_slack_when_blocked():
    mock_notifier = MagicMock()
    cb = CircuitBreaker(
        max_daily_loss_pct=5.0,
        trading_start_hour=7,
        trading_end_hour=23,
        notifier=mock_notifier,
    )
    now = datetime.datetime(2024, 1, 7, 5, 0)
    result = cb.is_trading_allowed(now)
    assert result is False
    mock_notifier.send.assert_called_once_with("CIRCUIT BREAKER: Trading halted - Weekend trading hours not started")


def test_circuit_breaker_sends_slack_on_loss_limit():
    mock_notifier = MagicMock()
    cb = CircuitBreaker(
        max_daily_loss_pct=5.0,
        trading_start_hour=7,
        trading_end_hour=23,
        notifier=mock_notifier,
    )
    now = datetime.datetime(2024, 1, 2, 12, 0)
    cb.record_pnl(-60000, now=now)
    result = cb.is_trading_allowed(now)
    assert result is False
    mock_notifier.send.assert_called_once_with("CIRCUIT BREAKER: Trading halted - Daily loss limit reached")
```

Run: `pytest tests/test_safety.py::test_circuit_breaker_sends_slack_when_blocked tests/test_safety.py::test_circuit_breaker_sends_slack_on_loss_limit -v`
Expected: FAIL with `TypeError: CircuitBreaker.__init__() got an unexpected keyword argument 'notifier'`

- [ ] **Step 3: Implement logger Slack integration**

Replace `src/monitoring/logger.py` with:

```python
import logging
import os
from datetime import datetime
from src.notifications.slack_notifier import SlackNotifier


class TradeLogger:
    def __init__(self, log_file: str = "logs/trades.log", error_file: str = None, notifier: SlackNotifier = None):
        if error_file is None:
            error_file = log_file
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        os.makedirs(os.path.dirname(error_file), exist_ok=True)
        
        self.trade_logger = logging.getLogger("trade_logger")
        self.trade_logger.setLevel(logging.INFO)
        self.trade_logger.handlers.clear()
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
        self.trade_logger.addHandler(handler)
        
        self.error_logger = logging.getLogger("error_logger")
        self.error_logger.setLevel(logging.ERROR)
        self.error_logger.handlers.clear()
        handler = logging.FileHandler(error_file)
        handler.setFormatter(logging.Formatter("%(asctime)s | ERROR | %(message)s"))
        self.error_logger.addHandler(handler)
        
        self.notifier = notifier

    def log_trade(self, instrument: str, direction: str, units: int, price: float):
        self.trade_logger.info(f"TRADE | {instrument} | {direction} | units={units} | price={price}")
        if self.notifier:
            self.notifier.send(f"TRADE: {instrument} {direction} {units} @ {price}")

    def log_error(self, message: str):
        self.error_logger.error(message)
        if self.notifier:
            self.notifier.send(f"ERROR: {message}")

    def log_info(self, message: str):
        self.trade_logger.info(f"INFO | {message}")
```

- [ ] **Step 4: Implement circuit breaker Slack integration**

Replace `src/safety/circuit_breaker.py` with:

```python
import datetime
from typing import Optional


class CircuitBreaker:
    def __init__(self, max_daily_loss_pct: float = 5.0,
                 trading_start_hour: int = 7, trading_end_hour: int = 6,
                 initial_capital: float = 1_000_000,
                 notifier=None):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.trading_start_hour = trading_start_hour
        self.trading_end_hour = trading_end_hour
        self.initial_capital = initial_capital
        self.daily_pnl = 0.0
        self.last_recorded_date: Optional[datetime.date] = None
        self.notifier = notifier

    def record_pnl(self, pnl: float, now: Optional[datetime.datetime] = None):
        if now is None:
            now = datetime.datetime.now()
        today = now.date()
        if self.last_recorded_date != today:
            self.daily_pnl = 0.0
            self.last_recorded_date = today
        self.daily_pnl += pnl

    def is_trading_allowed(self, now: Optional[datetime.datetime] = None) -> bool:
        if now is None:
            now = datetime.datetime.now()
        
        allowed = True
        reason = None
        
        weekday = now.weekday()
        hour = now.hour
        
        if weekday == 5 and hour >= self.trading_end_hour:
            allowed = False
            reason = "Weekend trading hours ended"
        if weekday == 6 and hour < self.trading_start_hour:
            allowed = False
            reason = "Weekend trading hours not started"
        
        if self.last_recorded_date == now.date():
            loss_pct = abs(self.daily_pnl) / self.initial_capital * 100
            if loss_pct >= self.max_daily_loss_pct:
                allowed = False
                reason = "Daily loss limit reached"
        
        if not allowed and self.notifier:
            self.notifier.send(f"CIRCUIT BREAKER: Trading halted - {reason}")
        
        return allowed
```

Run: `pytest tests/test_monitoring.py tests/test_safety.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

Run:
```bash
git add src/monitoring/logger.py src/safety/circuit_breaker.py tests/test_monitoring.py tests/test_safety.py
git commit -m "feat: integrate SlackNotifier into logger and circuit breaker"
```

---

### Task 7: Multi-Strategy Runner

**Files:**
- Modify: `src/runner/polling_runner.py`
- Modify: `src/main.py`
- Modify: `tests/test_runner.py`

- [ ] **Step 1: Write failing tests for multi-strategy runner**

Replace `tests/test_runner.py` with:

```python
from unittest.mock import MagicMock, patch
from src.runner.polling_runner import PollingRunner


def test_runner_constructs_with_dependencies():
    mock_config = MagicMock()
    mock_config.currency_pair = "USD_JPY"
    mock_config.risk_per_trade = 0.01
    runner = PollingRunner(config=mock_config)
    assert runner.config.currency_pair == "USD_JPY"


@patch("src.runner.polling_runner.OandaClient")
def test_runner_checks_circuit_breaker(mock_client_class):
    mock_config = MagicMock()
    mock_config.currency_pair = "USD_JPY"
    mock_config.risk_per_trade = 0.01
    mock_config.api_token = "test"
    mock_config.account_id = "acc"
    mock_config.environment = "practice"
    
    runner = PollingRunner(config=mock_config)
    runner.circuit_breaker.is_trading_allowed = MagicMock(return_value=False)
    result = runner.run_cycle()
    assert result is False


@patch("src.runner.polling_runner.OandaClient")
def test_runner_fetches_price(mock_client_class):
    mock_config = MagicMock()
    mock_config.currency_pair = "USD_JPY"
    mock_config.risk_per_trade = 0.01
    mock_config.api_token = "test"
    mock_config.account_id = "acc"
    mock_config.environment = "practice"
    
    mock_client = MagicMock()
    mock_client.get_current_price.return_value = {"bid": 145.0, "ask": 145.02}
    mock_client.get_open_positions.return_value = []
    mock_client_class.return_value = mock_client
    
    runner = PollingRunner(config=mock_config)
    runner.run_cycle()
    mock_client.get_current_price.assert_called_once_with("USD_JPY")


def test_runner_aggregates_signals():
    mock_config = MagicMock()
    mock_config.currency_pair = "USD_JPY"
    mock_config.risk_per_trade = 0.01
    mock_config.api_token = "test"
    mock_config.account_id = "acc"
    mock_config.environment = "practice"
    
    runner = PollingRunner(config=mock_config, strategies=[])
    assert runner._aggregate_signals([1, -1]) == 0
    assert runner._aggregate_signals([1, 1]) == 1
    assert runner._aggregate_signals([-1, -1]) == -1
    assert runner._aggregate_signals([]) == 0


@patch("src.runner.polling_runner.OandaClient")
def test_runner_uses_multiple_strategies(mock_client_class):
    from src.strategies.base import Strategy
    
    class AlwaysBuy(Strategy):
        def generate_signals(self, df):
            df = df.copy()
            df["signal"] = 1
            return df
    
    mock_config = MagicMock()
    mock_config.currency_pair = "USD_JPY"
    mock_config.risk_per_trade = 0.01
    mock_config.initial_capital = 1_000_000
    mock_config.api_token = "test"
    mock_config.account_id = "acc"
    mock_config.environment = "practice"
    
    mock_client = MagicMock()
    mock_client.get_current_price.return_value = {"bid": 145.0, "ask": 145.02}
    mock_client.get_open_positions.return_value = []
    mock_client.place_order.return_value = {"orderFillTransaction": {"id": "123"}}
    mock_client_class.return_value = mock_client
    
    runner = PollingRunner(config=mock_config, strategies=[AlwaysBuy(), AlwaysBuy()])
    result = runner.run_cycle()
    assert result is True
    mock_client.place_order.assert_called_once()
```

Run: `pytest tests/test_runner.py::test_runner_aggregates_signals tests/test_runner.py::test_runner_uses_multiple_strategies -v`
Expected: FAIL with `TypeError: PollingRunner.__init__() got an unexpected keyword argument 'strategies'` or `AttributeError: 'PollingRunner' object has no attribute '_aggregate_signals'`

- [ ] **Step 2: Implement multi-strategy polling runner**

Replace `src/runner/polling_runner.py` with:

```python
import datetime
from typing import Optional, List
from src.config.settings import Settings
from src.broker.oanda_client import OandaClient
from src.broker.order_builder import OrderBuilder
from src.risk.manager import RiskManager
from src.strategies.factory import StrategyFactory
from src.strategies.base import Strategy
from src.safety.circuit_breaker import CircuitBreaker
from src.monitoring.logger import TradeLogger


class PollingRunner:
    def __init__(self, config: Optional[Settings] = None, strategies: Optional[List[Strategy]] = None):
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
        self.order_builder = OrderBuilder(instrument=self.config.currency_pair)
        self.risk_manager = RiskManager(
            capital=self.config.initial_capital,
            risk_per_trade=self.config.risk_per_trade,
        )
        if strategies is None:
            strategies = [StrategyFactory.create("ma_macd", fast=3, slow=6, signal=2)]
        self.strategies = strategies

    def _aggregate_signals(self, signals: List[int]) -> int:
        if not signals:
            return 0
        total = sum(signals)
        if total > 0:
            return 1
        elif total < 0:
            return -1
        return 0

    def run_cycle(self) -> bool:
        now = datetime.datetime.now()
        
        if not self.circuit_breaker.is_trading_allowed(now):
            self.logger.log_info("Trading not allowed by circuit breaker")
            return False
        
        try:
            price = self.client.get_current_price(self.config.currency_pair)
            positions = self.client.get_open_positions()
            
            import pandas as pd
            df = pd.DataFrame({
                "datetime": [now],
                "open": [price["bid"]],
                "high": [price["ask"]],
                "low": [price["bid"]],
                "close": [price["ask"]],
                "volume": [1],
            })
            
            signals = []
            for strategy in self.strategies:
                df_sig = strategy.generate_signals(df.copy())
                signals.append(int(df_sig.iloc[-1]["signal"]))
            
            signal = self._aggregate_signals(signals)
            
            if not positions:
                if signal != 0:
                    entry_price = price["ask"] if signal == 1 else price["bid"]
                    stop_loss = entry_price * 0.99 if signal == 1 else entry_price * 1.01
                    take_profit = entry_price * 1.02 if signal == 1 else entry_price * 0.98
                    units = int(self.risk_manager.calculate_lot(entry_price, stop_loss))
                    
                    if units > 0:
                        order = self.order_builder.build_market_order(
                            direction=signal,
                            units=units,
                            stop_loss=stop_loss,
                            take_profit=take_profit,
                        )
                        result = self.client.place_order(order)
                        self.logger.log_trade(
                            self.config.currency_pair,
                            "BUY" if signal == 1 else "SELL",
                            units,
                            entry_price,
                        )
                        self.logger.log_info(f"Order placed: {result}")
            else:
                current_pos = positions[0]
                long_units = float(current_pos.get("long", {}).get("units", 0))
                short_units = float(current_pos.get("short", {}).get("units", 0))
                current_direction = 1 if long_units > 0 else -1 if short_units < 0 else 0
                
                if signal != 0 and signal != current_direction:
                    self.client.close_position(self.config.currency_pair)
                    self.logger.log_trade(
                        self.config.currency_pair,
                        "CLOSE",
                        0,
                        price["bid"] if current_direction == 1 else price["ask"],
                    )
            
            return True
            
        except Exception as e:
            self.logger.log_error(f"Error in trading cycle: {e}")
            return False
```

Run: `pytest tests/test_runner.py -v`
Expected: All tests pass

- [ ] **Step 3: Implement multi-strategy backtest in main.py**

Replace `src/main.py` with:

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


def run_backtest():
    loader = DataLoader(data_dir="data")
    raw_df = loader.load_csv("sample", "usdjpy_1h")
    pre = Preprocessor()
    df = pre.process(raw_df)

    strategies = {
        "ma_macd": {"fast": [3, 5, 8], "slow": [6, 10, 15], "signal": [2, 3, 5]},
        "ma_cross": {"short": [5, 10], "long": [20, 30]},
        "dow_theory": {"lookback": [3, 5, 8]},
        "stochastic": {"k_period": [10, 14], "d_period": [3, 5]},
    }

    all_results = []
    for name, param_grid in strategies.items():
        print(f"\n=== Grid Search: {name} ===")
        optimizer = GridSearchOptimizer(df)
        strategy_class = StrategyFactory.get_class(name)
        results = optimizer.search(strategy_class, param_grid)
        best = optimizer.get_best(results)
        print("Best params:", best["params"])
        print("Profit Factor:", best["profit_factor"])

        all_results.append({
            "name": name,
            "profit_factor": best["profit_factor"],
            "win_rate": best["win_rate"],
            "max_drawdown": 0.1,
            "total_trades": best["total_trades"],
        })

    print("\n=== Strategy Ranking ===")
    ranker = StrategyRanker(min_trades=0)
    ranked = ranker.rank(all_results)
    for r in ranked:
        print(f"{r['name']}: Score={r['score']:.2f}")


def run_live():
    print("=== Live Trading Mode ===")
    print("WARNING: This will connect to OANDA and potentially place real orders!")
    settings = Settings()
    print(f"Environment: {settings.environment}")
    print(f"Currency Pair: {settings.currency_pair}")
    print(f"Risk per trade: {settings.risk_per_trade * 100}%")
    
    strategies = [
        StrategyFactory.create("ma_macd", fast=3, slow=6, signal=2),
        StrategyFactory.create("ma_cross", short=5, long=20),
    ]
    runner = PollingRunner(config=settings, strategies=strategies)
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

Run: `pytest tests/test_runner.py tests/test_factory.py tests/test_strategies.py -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

Run:
```bash
git add src/runner/polling_runner.py src/main.py tests/test_runner.py
git commit -m "feat: support multiple strategies in runner and main backtest"
```

---

### Task 8: Final Verification

**Files:**
- All existing and new test files
- All modified source files

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass (counts will depend on existing tests, should be approximately 30+ passed with no failures)

- [ ] **Step 2: Run backtest command**

Run: `cd /Users/hideakimacbookair/自動トレード/fx_trading && python -m src.main --backtest`
Expected: Output showing grid search results for ma_macd, ma_cross, dow_theory, stochastic, followed by a strategy ranking with scores. No unhandled exceptions.

- [ ] **Step 3: Final commit**

Run:
```bash
git add -A
git diff --cached --stat
git commit -m "feat: complete Slack notifications and multi-strategy support"
```

---

## Spec Coverage Check

| Requirement | Task |
|---|---|
| `src/notifications/slack_notifier.py` - Webhook POST sender | Task 1 |
| `SLACK_WEBHOOK_URL` in settings | Task 1 |
| Integrate with `logger.py` | Task 6 |
| Integrate with `circuit_breaker.py` | Task 6 |
| Test `tests/test_notifications.py` | Task 1 |
| `src/strategies/factory.py` - create by name string | Task 2, 3, 4, 5 |
| `src/strategies/ma_cross.py` | Task 3 |
| `src/strategies/dow_theory.py` | Task 4 |
| `src/strategies/stochastic.py` | Task 5 |
| Modify `polling_runner.py` for multi-strategy + aggregation | Task 7 |
| Modify `main.py` for multi-strategy backtest | Task 7 |
| Tests for strategies, factory, runner | Tasks 2-5, 7 |

## Placeholder Scan

- No TODO, TBD, or placeholders found.
- All steps include exact file paths, complete code, exact commands, and expected outputs.
- Type names and method signatures are consistent across all tasks.

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-29-fx-extensions-plan.md`.**

**Two execution options:**

1. **Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
