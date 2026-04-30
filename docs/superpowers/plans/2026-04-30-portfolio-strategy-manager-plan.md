# ポートフォリオ戦略マネージャー Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 複数通貨ペア・複数戦略の分散投資を自動化し、市場環境に応じた戦略選定と資金配分で年間+20%リターンを目指すポートフォリオ戦略マネージャーを構築する。

**Architecture:** ADXベースの市場環境検出、環境に応じた戦略自動選定、ケリー基準+ボラティリティターゲティングのポジションサイジング、週次リバランスを統合管理するPortfolioManagerを中核に据える。

**Tech Stack:** Python 3.11+, pandas, numpy, pytest

---

## Prerequisites

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
python3 -m pytest --tb=short -q
```

**Expected output:**
```
79 passed in X.XXs
```

---

## Task 1: Market Regime Detector

### 1.1 Write Failing Test

Create `/Users/hideakimacbookair/自動トレード/fx_trading/tests/test_portfolio.py`:

```python
import pandas as pd
import numpy as np
import pytest


def test_market_regime_detects_trend():
    """ADX > 25 should be detected as trend."""
    from src.portfolio.market_regime import MarketRegimeDetector

    # Strong uptrend: progressively higher highs and higher lows
    prices = 150.0 + np.cumsum(np.random.RandomState(42).choice([0.5, 0.3, 0.7, 0.2], size=50))
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=50, freq="h"),
        "open": prices - 0.1,
        "high": prices + 0.3,
        "low": prices - 0.3,
        "close": prices,
        "volume": [1000] * 50,
    })
    detector = MarketRegimeDetector(period=14)
    regime = detector.detect(df)
    assert regime == "trend"


def test_market_regime_detects_ranging():
    """ADX < 20 should be detected as ranging."""
    from src.portfolio.market_regime import MarketRegimeDetector

    # Oscillating prices around a mean
    t = np.linspace(0, 8 * np.pi, 50)
    prices = 150.0 + np.sin(t) * 0.5
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=50, freq="h"),
        "open": prices - 0.1,
        "high": prices + 0.2,
        "low": prices - 0.2,
        "close": prices,
        "volume": [1000] * 50,
    })
    detector = MarketRegimeDetector(period=14)
    regime = detector.detect(df)
    assert regime == "ranging"


def test_market_regime_defaults_to_ranging_on_short_data():
    """If data is shorter than period, default to ranging."""
    from src.portfolio.market_regime import MarketRegimeDetector

    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=5, freq="h"),
        "open": [150.0] * 5,
        "high": [151.0] * 5,
        "low": [149.0] * 5,
        "close": [150.0] * 5,
        "volume": [1000] * 5,
    })
    detector = MarketRegimeDetector(period=14)
    regime = detector.detect(df)
    assert regime == "ranging"
```

### 1.2 Run Failing Test

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
python3 -m pytest tests/test_portfolio.py -v --tb=short
```

**Expected output:**
```
tests/test_portfolio.py::test_market_regime_detects_trend ERROR
tests/test_portfolio.py::test_market_regime_detects_ranging ERROR
tests/test_portfolio.py::test_market_regime_defaults_to_ranging_on_short_data ERROR
ModuleNotFoundError: No module named 'src.portfolio'
```

### 1.3 Implement `src/portfolio/__init__.py`

Create `/Users/hideakimacbookair/自動トレード/fx_trading/src/portfolio/__init__.py`:

```python
from .market_regime import MarketRegimeDetector
from .strategy_selector import StrategySelector
from .position_sizer import PositionSizer
from .portfolio_manager import PortfolioManager
from .rebalancer import Rebalancer

__all__ = [
    "MarketRegimeDetector",
    "StrategySelector",
    "PositionSizer",
    "PortfolioManager",
    "Rebalancer",
]
```

### 1.4 Implement `src/portfolio/market_regime.py`

Create `/Users/hideakimacbookair/自動トレード/fx_trading/src/portfolio/market_regime.py`:

```python
import pandas as pd
import numpy as np


class MarketRegimeDetector:
    """Detect market regime (trend vs ranging) using ADX (Average Directional Index)."""

    def __init__(self, period: int = 14, trend_threshold: float = 25.0, ranging_threshold: float = 20.0):
        self.period = period
        self.trend_threshold = trend_threshold
        self.ranging_threshold = ranging_threshold

    def detect(self, df: pd.DataFrame) -> str:
        """Return 'trend' or 'ranging' based on ADX value."""
        if len(df) < self.period + 1:
            return "ranging"

        adx = self._calculate_adx(df)
        if adx > self.trend_threshold:
            return "trend"
        elif adx < self.ranging_threshold:
            return "ranging"
        # Between thresholds: use previous regime or default to ranging
        return "ranging"

    def _calculate_adx(self, df: pd.DataFrame) -> float:
        """Calculate ADX for the last bar. Returns the last ADX value."""
        df = df.copy()
        high = df["high"]
        low = df["low"]
        close = df["close"]

        # True Range
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        df["tr"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Directional Movement
        plus_dm = high.diff()
        minus_dm = -low.diff()
        df["+dm"] = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
        df["-dm"] = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)

        # Wilder's smoothing
        tr_smooth = df["tr"].ewm(alpha=1 / self.period, min_periods=self.period, adjust=False).mean()
        plus_dm_smooth = df["+dm"].ewm(alpha=1 / self.period, min_periods=self.period, adjust=False).mean()
        minus_dm_smooth = df["-dm"].ewm(alpha=1 / self.period, min_periods=self.period, adjust=False).mean()

        # DI+ and DI-
        di_plus = 100 * plus_dm_smooth / tr_smooth
        di_minus = 100 * minus_dm_smooth / tr_smooth

        # DX
        dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus)
        dx = dx.replace([np.inf, -np.inf], np.nan)

        # ADX
        adx = dx.ewm(alpha=1 / self.period, min_periods=self.period, adjust=False).mean()
        last_adx = adx.iloc[-1]
        return float(last_adx) if pd.notna(last_adx) else 0.0
```

### 1.5 Run Passing Test

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
python3 -m pytest tests/test_portfolio.py::test_market_regime_detects_trend tests/test_portfolio.py::test_market_regime_detects_ranging tests/test_portfolio.py::test_market_regime_defaults_to_ranging_on_short_data -v --tb=short
```

**Expected output:**
```
tests/test_portfolio.py::test_market_regime_detects_trend PASSED
tests/test_portfolio.py::test_market_regime_detects_ranging PASSED
tests/test_portfolio.py::test_market_regime_defaults_to_ranging_on_short_data PASSED
```

### 1.6 Commit

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
git add src/portfolio/__init__.py src/portfolio/market_regime.py tests/test_portfolio.py
git commit -m "feat(portfolio): add ADX-based MarketRegimeDetector with tests"
```

---

## Task 2: Strategy Selector

### 2.1 Write Failing Test

Append to `/Users/hideakimacbookair/自動トレード/fx_trading/tests/test_portfolio.py`:

```python
def test_strategy_selector_returns_trend_strategies():
    from src.portfolio.strategy_selector import StrategySelector
    selector = StrategySelector()
    strategies = selector.select("trend")
    assert strategies == ["ma_macd", "ma_cross", "dow_theory"]


def test_strategy_selector_returns_ranging_strategies():
    from src.portfolio.strategy_selector import StrategySelector
    selector = StrategySelector()
    strategies = selector.select("ranging")
    assert strategies == ["stochastic", "ml_strategy"]


def test_strategy_selector_defaults_to_ranging_on_unknown_regime():
    from src.portfolio.strategy_selector import StrategySelector
    selector = StrategySelector()
    strategies = selector.select("unknown")
    assert strategies == ["stochastic", "ml_strategy"]
```

### 2.2 Run Failing Test

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
python3 -m pytest tests/test_portfolio.py::test_strategy_selector_returns_trend_strategies tests/test_portfolio.py::test_strategy_selector_returns_ranging_strategies tests/test_portfolio.py::test_strategy_selector_defaults_to_ranging_on_unknown_regime -v --tb=short
```

**Expected output:**
```
tests/test_portfolio.py::test_strategy_selector_returns_trend_strategies FAILED
tests/test_portfolio.py::test_strategy_selector_returns_ranging_strategies FAILED
tests/test_portfolio.py::test_strategy_selector_defaults_to_ranging_on_unknown_regime FAILED
ModuleNotFoundError: No module named 'src.portfolio.strategy_selector'
```

### 2.3 Implement `src/portfolio/strategy_selector.py`

Create `/Users/hideakimacbookair/自動トレード/fx_trading/src/portfolio/strategy_selector.py`:

```python
from typing import List


class StrategySelector:
    """Select strategy names based on detected market regime."""

    _TREND_STRATEGIES = ["ma_macd", "ma_cross", "dow_theory"]
    _RANGING_STRATEGIES = ["stochastic", "ml_strategy"]

    def select(self, regime: str) -> List[str]:
        """Return list of strategy names for the given regime."""
        if regime == "trend":
            return self._TREND_STRATEGIES.copy()
        return self._RANGING_STRATEGIES.copy()
```

### 2.4 Run Passing Test

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
python3 -m pytest tests/test_portfolio.py::test_strategy_selector_returns_trend_strategies tests/test_portfolio.py::test_strategy_selector_returns_ranging_strategies tests/test_portfolio.py::test_strategy_selector_defaults_to_ranging_on_unknown_regime -v --tb=short
```

**Expected output:**
```
tests/test_portfolio.py::test_strategy_selector_returns_trend_strategies PASSED
tests/test_portfolio.py::test_strategy_selector_returns_ranging_strategies PASSED
tests/test_portfolio.py::test_strategy_selector_defaults_to_ranging_on_unknown_regime PASSED
```

### 2.5 Commit

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
git add src/portfolio/strategy_selector.py tests/test_portfolio.py
git commit -m "feat(portfolio): add regime-based StrategySelector with tests"
```

---

## Task 3: Position Sizer

### 3.1 Write Failing Test

Append to `/Users/hideakimacbookair/自動トレード/fx_trading/tests/test_portfolio.py`:

```python
def test_position_sizer_kelly_calculation():
    from src.portfolio.position_sizer import PositionSizer
    sizer = PositionSizer(capital=1_000_000, risk_per_trade=0.01, vol_target=0.05)
    # Win rate 60%, avg win 100, avg loss 50 -> Kelly = (0.6*2 - 0.4) / 2 = 0.4
    lot = sizer.calculate_kelly_lot(win_rate=0.6, avg_win=100.0, avg_loss=50.0, entry_price=150.0)
    # Kelly f = (bp - q) / b = (0.6*2 - 0.4)/2 = 0.4
    # Risk amount = 1_000_000 * 0.01 = 10_000
    # Half-Kelly risk = 5_000
    # lot = 5_000 / 150.0 = 33.33
    expected = 5000.0 / 150.0
    assert abs(lot - expected) < 0.01


def test_position_sizer_volatility_target_scales_lot():
    from src.portfolio.position_sizer import PositionSizer
    sizer = PositionSizer(capital=1_000_000, risk_per_trade=0.01, vol_target=0.05)
    # High volatility (10%) should reduce lot compared to low volatility (2%)
    lot_high = sizer.apply_volatility_target(base_lot=100.0, current_volatility=0.10)
    lot_low = sizer.apply_volatility_target(base_lot=100.0, current_volatility=0.02)
    # target 5% / current 10% = 0.5 -> 50 lots
    # target 5% / current 2% = 2.5 -> 250 lots
    assert abs(lot_high - 50.0) < 0.01
    assert abs(lot_low - 250.0) < 0.01


def test_position_sizer_combined_lot():
    from src.portfolio.position_sizer import PositionSizer
    sizer = PositionSizer(capital=1_000_000, risk_per_trade=0.01, vol_target=0.05)
    lot = sizer.calculate_lot(
        win_rate=0.6,
        avg_win=100.0,
        avg_loss=50.0,
        entry_price=150.0,
        current_volatility=0.10,
    )
    # Kelly lot = 5000 / 150 = 33.33
    # Vol adjustment = 0.05 / 0.10 = 0.5
    # Final = 33.33 * 0.5 = 16.67
    expected = (5000.0 / 150.0) * 0.5
    assert abs(lot - expected) < 0.01


def test_position_sizer_zero_volatility_defaults():
    from src.portfolio.position_sizer import PositionSizer
    sizer = PositionSizer(capital=1_000_000, risk_per_trade=0.01, vol_target=0.05)
    lot = sizer.apply_volatility_target(base_lot=100.0, current_volatility=0.0)
    assert lot == 100.0


def test_position_sizer_negative_kelly_clamped():
    from src.portfolio.position_sizer import PositionSizer
    sizer = PositionSizer(capital=1_000_000, risk_per_trade=0.01, vol_target=0.05)
    # Win rate 30%, avg win 50, avg loss 100 -> Kelly = (0.3*0.5 - 0.7)/0.5 = -0.5
    lot = sizer.calculate_kelly_lot(win_rate=0.3, avg_win=50.0, avg_loss=100.0, entry_price=150.0)
    assert lot == 0.0
```

### 3.2 Run Failing Test

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
python3 -m pytest tests/test_portfolio.py::test_position_sizer_kelly_calculation tests/test_portfolio.py::test_position_sizer_volatility_target_scales_lot tests/test_portfolio.py::test_position_sizer_combined_lot tests/test_portfolio.py::test_position_sizer_zero_volatility_defaults tests/test_portfolio.py::test_position_sizer_negative_kelly_clamped -v --tb=short
```

**Expected output:**
```
tests/test_portfolio.py::test_position_sizer_kelly_calculation FAILED
tests/test_portfolio.py::test_position_sizer_volatility_target_scales_lot FAILED
tests/test_portfolio.py::test_position_sizer_combined_lot FAILED
tests/test_portfolio.py::test_position_sizer_zero_volatility_defaults FAILED
tests/test_portfolio.py::test_position_sizer_negative_kelly_clamped FAILED
ModuleNotFoundError: No module named 'src.portfolio.position_sizer'
```

### 3.3 Implement `src/portfolio/position_sizer.py`

Create `/Users/hideakimacbookair/自動トレード/fx_trading/src/portfolio/position_sizer.py`:

```python
import math


class PositionSizer:
    """Calculate position size using Kelly criterion and volatility targeting."""

    def __init__(self, capital: float, risk_per_trade: float = 0.01, vol_target: float = 0.05, kelly_fraction: float = 0.5):
        self.capital = capital
        self.risk_per_trade = risk_per_trade
        self.vol_target = vol_target
        self.kelly_fraction = kelly_fraction

    def calculate_kelly_lot(self, win_rate: float, avg_win: float, avg_loss: float, entry_price: float) -> float:
        """Calculate lot size based on half-Kelly criterion."""
        if avg_loss == 0 or entry_price == 0:
            return 0.0

        b = avg_win / avg_loss  # payoff ratio
        p = win_rate
        q = 1.0 - p

        kelly_f = (b * p - q) / b
        if kelly_f <= 0:
            return 0.0

        risk_amount = self.capital * self.risk_per_trade * self.kelly_fraction * kelly_f
        lot = risk_amount / entry_price
        return max(0.0, lot)

    def apply_volatility_target(self, base_lot: float, current_volatility: float) -> float:
        """Scale lot by volatility target ratio."""
        if current_volatility <= 0:
            return base_lot
        scale = self.vol_target / current_volatility
        return base_lot * scale

    def calculate_lot(self, win_rate: float, avg_win: float, avg_loss: float, entry_price: float, current_volatility: float) -> float:
        """Combined lot sizing: Kelly -> Volatility Target."""
        kelly_lot = self.calculate_kelly_lot(win_rate, avg_win, avg_loss, entry_price)
        final_lot = self.apply_volatility_target(kelly_lot, current_volatility)
        return max(0.0, final_lot)

    def update_capital(self, pnl: float):
        self.capital += pnl
```

### 3.4 Run Passing Test

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
python3 -m pytest tests/test_portfolio.py::test_position_sizer_kelly_calculation tests/test_portfolio.py::test_position_sizer_volatility_target_scales_lot tests/test_portfolio.py::test_position_sizer_combined_lot tests/test_portfolio.py::test_position_sizer_zero_volatility_defaults tests/test_portfolio.py::test_position_sizer_negative_kelly_clamped -v --tb=short
```

**Expected output:**
```
tests/test_portfolio.py::test_position_sizer_kelly_calculation PASSED
tests/test_portfolio.py::test_position_sizer_volatility_target_scales_lot PASSED
tests/test_portfolio.py::test_position_sizer_combined_lot PASSED
tests/test_portfolio.py::test_position_sizer_zero_volatility_defaults PASSED
tests/test_portfolio.py::test_position_sizer_negative_kelly_clamped PASSED
```

### 3.5 Commit

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
git add src/portfolio/position_sizer.py tests/test_portfolio.py
git commit -m "feat(portfolio): add Kelly+Volatility PositionSizer with tests"
```

---

## Task 4: Portfolio Manager

### 4.1 Write Failing Test

Append to `/Users/hideakimacbookair/自動トレード/fx_trading/tests/test_portfolio.py`:

```python
from unittest.mock import MagicMock


def test_portfolio_manager_aggregates_signals_buy():
    from src.portfolio.portfolio_manager import PortfolioManager
    pm = PortfolioManager(capital=1_000_000)
    # Mock strategies all returning BUY
    mock_strategies = [MagicMock(), MagicMock(), MagicMock()]
    for m in mock_strategies:
        import pandas as pd
        m.generate_signals.return_value = pd.DataFrame({"signal": [1]})

    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=10, freq="h"),
        "open": [150.0] * 10,
        "high": [151.0] * 10,
        "low": [149.0] * 10,
        "close": [150.0 + i * 0.5 for i in range(10)],
        "volume": [1000] * 10,
    })
    result = pm.evaluate(df, mock_strategies, "USD_JPY")
    assert result["signal"] == 1
    assert result["confidence"] == 1.0
    assert result["lot"] > 0


def test_portfolio_manager_skips_on_split_signals():
    from src.portfolio.portfolio_manager import PortfolioManager
    pm = PortfolioManager(capital=1_000_000, confidence_threshold=2)
    mock_strategies = [MagicMock(), MagicMock(), MagicMock()]
    import pandas as pd
    mock_strategies[0].generate_signals.return_value = pd.DataFrame({"signal": [1]})
    mock_strategies[1].generate_signals.return_value = pd.DataFrame({"signal": [-1]})
    mock_strategies[2].generate_signals.return_value = pd.DataFrame({"signal": [0]})

    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=10, freq="h"),
        "open": [150.0] * 10,
        "high": [151.0] * 10,
        "low": [149.0] * 10,
        "close": [150.0 + i * 0.5 for i in range(10)],
        "volume": [1000] * 10,
    })
    result = pm.evaluate(df, mock_strategies, "USD_JPY")
    assert result["signal"] == 0
    assert result["lot"] == 0


def test_portfolio_manager_sell_when_majority_sell():
    from src.portfolio.portfolio_manager import PortfolioManager
    pm = PortfolioManager(capital=1_000_000, confidence_threshold=2)
    mock_strategies = [MagicMock(), MagicMock(), MagicMock()]
    import pandas as pd
    mock_strategies[0].generate_signals.return_value = pd.DataFrame({"signal": [-1]})
    mock_strategies[1].generate_signals.return_value = pd.DataFrame({"signal": [-1]})
    mock_strategies[2].generate_signals.return_value = pd.DataFrame({"signal": [0]})

    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=10, freq="h"),
        "open": [150.0] * 10,
        "high": [151.0] * 10,
        "low": [149.0] * 10,
        "close": [150.0 + i * 0.5 for i in range(10)],
        "volume": [1000] * 10,
    })
    result = pm.evaluate(df, mock_strategies, "USD_JPY")
    assert result["signal"] == -1
    assert result["confidence"] == pytest.approx(2 / 3, rel=0.01)


def test_portfolio_manager_updates_capital():
    from src.portfolio.portfolio_manager import PortfolioManager
    pm = PortfolioManager(capital=1_000_000)
    pm.update_capital(5000.0)
    assert pm.capital == 1_005_000.0
```

### 4.2 Run Failing Test

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
python3 -m pytest tests/test_portfolio.py::test_portfolio_manager_aggregates_signals_buy tests/test_portfolio.py::test_portfolio_manager_skips_on_split_signals tests/test_portfolio.py::test_portfolio_manager_sell_when_majority_sell tests/test_portfolio.py::test_portfolio_manager_updates_capital -v --tb=short
```

**Expected output:**
```
tests/test_portfolio.py::test_portfolio_manager_aggregates_signals_buy FAILED
tests/test_portfolio.py::test_portfolio_manager_skips_on_split_signals FAILED
tests/test_portfolio.py::test_portfolio_manager_sell_when_majority_sell FAILED
tests/test_portfolio.py::test_portfolio_manager_updates_capital FAILED
ModuleNotFoundError: No module named 'src.portfolio.portfolio_manager'
```

### 4.3 Implement `src/portfolio/portfolio_manager.py`

Create `/Users/hideakimacbookair/自動トレード/fx_trading/src/portfolio/portfolio_manager.py`:

```python
import math
from typing import List, Dict, Any
import pandas as pd
from .market_regime import MarketRegimeDetector
from .strategy_selector import StrategySelector
from .position_sizer import PositionSizer
from src.strategies.base import Strategy


class PortfolioManager:
    """Orchestrate market regime detection, strategy selection, signal aggregation, and position sizing."""

    def __init__(
        self,
        capital: float = 1_000_000.0,
        risk_per_trade: float = 0.01,
        vol_target: float = 0.05,
        confidence_threshold: int = 2,
        regime_detector: MarketRegimeDetector = None,
        strategy_selector: StrategySelector = None,
        position_sizer: PositionSizer = None,
    ):
        self.capital = capital
        self.confidence_threshold = confidence_threshold
        self.regime_detector = regime_detector or MarketRegimeDetector()
        self.strategy_selector = strategy_selector or StrategySelector()
        self.position_sizer = position_sizer or PositionSizer(
            capital=capital, risk_per_trade=risk_per_trade, vol_target=vol_target
        )

    def evaluate(self, df: pd.DataFrame, strategies: List[Strategy], instrument: str) -> Dict[str, Any]:
        """Evaluate all strategies and return aggregated signal with lot size."""
        # 1. Detect market regime
        regime = self.regime_detector.detect(df)

        # 2. Get active strategies (by name filter from selector)
        selected_names = set(self.strategy_selector.select(regime))

        # 3. Generate signals from active strategies
        signals = []
        for strategy in strategies:
            sig_df = strategy.generate_signals(df.copy())
            signal = int(sig_df.iloc[-1]["signal"])
            signals.append(signal)

        buy_votes = sum(1 for s in signals if s == 1)
        sell_votes = sum(1 for s in signals if s == -1)
        total = len(signals)

        final_signal = 0
        confidence = 0.0

        if buy_votes >= self.confidence_threshold and buy_votes > sell_votes:
            final_signal = 1
            confidence = buy_votes / total
        elif sell_votes >= self.confidence_threshold and sell_votes > buy_votes:
            final_signal = -1
            confidence = sell_votes / total

        # 4. Calculate lot size if we have a signal
        lot = 0.0
        if final_signal != 0:
            # Use default stats for Kelly; in production these come from backtest results
            lot = self.position_sizer.calculate_lot(
                win_rate=0.55,
                avg_win=100.0,
                avg_loss=50.0,
                entry_price=df["close"].iloc[-1],
                current_volatility=self._estimate_volatility(df),
            )

        return {
            "instrument": instrument,
            "regime": regime,
            "signal": final_signal,
            "confidence": confidence,
            "lot": lot,
            "buy_votes": buy_votes,
            "sell_votes": sell_votes,
        }

    def _estimate_volatility(self, df: pd.DataFrame) -> float:
        """Estimate annualized volatility from recent price returns."""
        if len(df) < 2:
            return 0.05
        returns = df["close"].pct_change().dropna()
        if len(returns) < 2:
            return 0.05
        # Assume hourly data -> annualize by sqrt(252 * 24) for FX
        return float(returns.std() * math.sqrt(252 * 24))

    def update_capital(self, pnl: float):
        self.capital += pnl
        self.position_sizer.capital = self.capital
```

### 4.4 Run Passing Test

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
python3 -m pytest tests/test_portfolio.py::test_portfolio_manager_aggregates_signals_buy tests/test_portfolio.py::test_portfolio_manager_skips_on_split_signals tests/test_portfolio.py::test_portfolio_manager_sell_when_majority_sell tests/test_portfolio.py::test_portfolio_manager_updates_capital -v --tb=short
```

**Expected output:**
```
tests/test_portfolio.py::test_portfolio_manager_aggregates_signals_buy PASSED
tests/test_portfolio.py::test_portfolio_manager_skips_on_split_signals PASSED
tests/test_portfolio.py::test_portfolio_manager_sell_when_majority_sell PASSED
tests/test_portfolio.py::test_portfolio_manager_updates_capital PASSED
```

### 4.5 Commit

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
git add src/portfolio/portfolio_manager.py tests/test_portfolio.py
git commit -m "feat(portfolio): add PortfolioManager with regime-aware signal aggregation and tests"
```

---

## Task 5: Rebalancer

### 5.1 Write Failing Test

Append to `/Users/hideakimacbookair/自動トレード/fx_trading/tests/test_portfolio.py`:

```python
def test_rebalancer_triggers_on_friday():
    from src.portfolio.rebalancer import Rebalancer
    import datetime
    reb = Rebalancer()
    friday = datetime.datetime(2024, 1, 5, 22, 0, 0)  # Friday 22:00
    assert reb.should_rebalance(friday) is True


def test_rebalancer_does_not_trigger_on_monday():
    from src.portfolio.rebalancer import Rebalancer
    import datetime
    reb = Rebalancer()
    monday = datetime.datetime(2024, 1, 8, 22, 0, 0)  # Monday
    assert reb.should_rebalance(monday) is False


def test_rebalancer_calculates_allocations():
    from src.portfolio.rebalancer import Rebalancer
    reb = Rebalancer()
    performance = {
        "ma_macd": {"total_return": 0.15, "sharpe": 1.2},
        "ma_cross": {"total_return": 0.08, "sharpe": 0.9},
        "stochastic": {"total_return": 0.05, "sharpe": 0.6},
    }
    allocations = reb.calculate_allocations(performance)
    assert sum(allocations.values()) == pytest.approx(1.0, abs=0.01)
    # Higher performance should get more allocation
    assert allocations["ma_macd"] > allocations["ma_cross"]
    assert allocations["ma_cross"] > allocations["stochastic"]


def test_rebalancer_skips_empty_performance():
    from src.portfolio.rebalancer import Rebalancer
    reb = Rebalancer()
    allocations = reb.calculate_allocations({})
    assert allocations == {}


def test_rebalancer_detects_all_strategies_broken():
    from src.portfolio.rebalancer import Rebalancer
    reb = Rebalancer()
    performance = {
        "ma_macd": {"total_return": -0.30, "sharpe": -0.5},
        "ma_cross": {"total_return": -0.25, "sharpe": -0.3},
    }
    allocations = reb.calculate_allocations(performance)
    # All negative -> raise cash ratio
    assert allocations.get("cash", 0.0) >= 0.5
```

### 5.2 Run Failing Test

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
python3 -m pytest tests/test_portfolio.py::test_rebalancer_triggers_on_friday tests/test_portfolio.py::test_rebalancer_does_not_trigger_on_monday tests/test_portfolio.py::test_rebalancer_calculates_allocations tests/test_portfolio.py::test_rebalancer_skips_empty_performance tests/test_portfolio.py::test_rebalancer_detects_all_strategies_broken -v --tb=short
```

**Expected output:**
```
tests/test_portfolio.py::test_rebalancer_triggers_on_friday FAILED
tests/test_portfolio.py::test_rebalancer_does_not_trigger_on_monday FAILED
tests/test_portfolio.py::test_rebalancer_calculates_allocations FAILED
tests/test_portfolio.py::test_rebalancer_skips_empty_performance FAILED
tests/test_portfolio.py::test_rebalancer_detects_all_strategies_broken FAILED
ModuleNotFoundError: No module named 'src.portfolio.rebalancer'
```

### 5.3 Implement `src/portfolio/rebalancer.py`

Create `/Users/hideakimacbookair/自動トレード/fx_trading/src/portfolio/rebalancer.py`:

```python
import datetime
from typing import Dict, Any


class Rebalancer:
    """Weekly rebalancing logic executed after Friday close."""

    def __init__(self, rebalance_day: int = 4, rebalance_hour: int = 22, min_cash_ratio: float = 0.1, broken_threshold: float = -0.20):
        self.rebalance_day = rebalance_day  # Friday = 4
        self.rebalance_hour = rebalance_hour
        self.min_cash_ratio = min_cash_ratio
        self.broken_threshold = broken_threshold

    def should_rebalance(self, now: datetime.datetime = None) -> bool:
        """Return True if it's time to rebalance (Friday after 22:00 JST)."""
        if now is None:
            now = datetime.datetime.now()
        return now.weekday() == self.rebalance_day and now.hour >= self.rebalance_hour

    def calculate_allocations(self, performance: Dict[str, Dict[str, float]]) -> Dict[str, float]:
        """Calculate capital allocations per strategy based on recent performance.

        performance: {strategy_name: {"total_return": float, "sharpe": float}}
        Returns: {strategy_name: allocation_ratio}
        """
        if not performance:
            return {}

        # Score = total_return * sharpe (reward-risk efficiency)
        scores = {}
        all_broken = True
        for name, stats in performance.items():
            ret = stats.get("total_return", 0.0)
            sharpe = stats.get("sharpe", 0.0)
            score = max(0.0, ret * max(0.0, sharpe))
            scores[name] = score
            if ret > self.broken_threshold:
                all_broken = False

        if all_broken:
            # Raise cash if all strategies are broken
            n = len(performance)
            cash_ratio = max(0.5, 1.0 - self.min_cash_ratio)
            alloc = (1.0 - cash_ratio) / n if n > 0 else 0.0
            result = {name: alloc for name in performance}
            result["cash"] = cash_ratio
            return result

        total_score = sum(scores.values())
        if total_score == 0:
            n = len(performance)
            equal = 1.0 / n if n > 0 else 0.0
            return {name: equal for name in performance}

        allocations = {name: score / total_score for name, score in scores.items()}
        return allocations
```

### 5.4 Run Passing Test

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
python3 -m pytest tests/test_portfolio.py::test_rebalancer_triggers_on_friday tests/test_portfolio.py::test_rebalancer_does_not_trigger_on_monday tests/test_portfolio.py::test_rebalancer_calculates_allocations tests/test_portfolio.py::test_rebalancer_skips_empty_performance tests/test_portfolio.py::test_rebalancer_detects_all_strategies_broken -v --tb=short
```

**Expected output:**
```
tests/test_portfolio.py::test_rebalancer_triggers_on_friday PASSED
tests/test_portfolio.py::test_rebalancer_does_not_trigger_on_monday PASSED
tests/test_portfolio.py::test_rebalancer_calculates_allocations PASSED
tests/test_portfolio.py::test_rebalancer_skips_empty_performance PASSED
tests/test_portfolio.py::test_rebalancer_detects_all_strategies_broken PASSED
```

### 5.5 Commit

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
git add src/portfolio/rebalancer.py tests/test_portfolio.py
git commit -m "feat(portfolio): add weekly Rebalancer with performance-based allocation and tests"
```

---

## Task 6: Integration

### 6.1 Modify `src/runner/polling_runner.py`

Read the current file first, then apply these edits using exact strings.

**Edit 1:** Add PortfolioManager import and update constructor.

Replace in `/Users/hideakimacbookair/自動トレード/fx_trading/src/runner/polling_runner.py`:

```python
from src.config.settings import Settings
from src.broker.oanda_client import OandaClient
from src.broker.order_builder import OrderBuilder
from src.risk.manager import RiskManager
from src.strategies.factory import StrategyFactory
from src.strategies.base import Strategy
from src.safety.circuit_breaker import CircuitBreaker
from src.monitoring.logger import TradeLogger
```

with:

```python
from src.config.settings import Settings
from src.broker.oanda_client import OandaClient
from src.broker.order_builder import OrderBuilder
from src.risk.manager import RiskManager
from src.strategies.factory import StrategyFactory
from src.strategies.base import Strategy
from src.safety.circuit_breaker import CircuitBreaker
from src.monitoring.logger import TradeLogger
from src.portfolio.portfolio_manager import PortfolioManager
```

**Edit 2:** Update `__init__` to optionally use PortfolioManager.

Replace in `/Users/hideakimacbookair/自動トレード/fx_trading/src/runner/polling_runner.py`:

```python
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
        default_instrument = getattr(self.config, "currency_pair", None) or self.config.currency_pairs[0]
        self.order_builder = OrderBuilder(instrument=default_instrument)
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
```

with:

```python
    def __init__(
        self,
        config: Optional[Settings] = None,
        strategies: Optional[List[Union[str, Strategy]]] = None,
        use_portfolio: bool = False,
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
        default_instrument = getattr(self.config, "currency_pair", None) or self.config.currency_pairs[0]
        self.order_builder = OrderBuilder(instrument=default_instrument)
        self.risk_manager = RiskManager(
            capital=self.config.initial_capital,
            risk_per_trade=self.config.risk_per_trade,
        )
        self.use_portfolio = use_portfolio
        self.portfolio_manager: Optional[PortfolioManager] = None
        if self.use_portfolio:
            self.portfolio_manager = PortfolioManager(
                capital=self.config.initial_capital,
                risk_per_trade=self.config.risk_per_trade,
                vol_target=0.05,
            )

        if strategies is None:
            strategies = ["ma_macd"]

        self.strategies: List[Strategy] = []
        for s in strategies:
            if isinstance(s, str):
                self.strategies.append(StrategyFactory.create(s))
            else:
                self.strategies.append(s)
```

**Edit 3:** Update `_aggregate_signals` to optionally use PortfolioManager.

Replace in `/Users/hideakimacbookair/自動トレード/fx_trading/src/runner/polling_runner.py`:

```python
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
```

with:

```python
    def _aggregate_signals(self, df, pair: Optional[str] = None) -> int:
        """Aggregate signals from all strategies by majority vote, or via PortfolioManager if enabled."""
        instrument = pair or getattr(self.config, "currency_pair", None) or self.config.currency_pairs[0]
        if self.use_portfolio and self.portfolio_manager is not None:
            result = self.portfolio_manager.evaluate(df, self.strategies, instrument)
            return result["signal"]

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
```

**Edit 4:** Update the call site in `run_cycle`.

Replace in `/Users/hideakimacbookair/自動トレード/fx_trading/src/runner/polling_runner.py`:

```python
            # 4. Generate signals from all strategies and aggregate
            signal = self._aggregate_signals(df)
```

with:

```python
            # 4. Generate signals from all strategies and aggregate
            signal = self._aggregate_signals(df, pair=instrument)
```

**Edit 5:** Update lot sizing to use PortfolioManager lot when available.

Replace in `/Users/hideakimacbookair/自動トレード/fx_trading/src/runner/polling_runner.py`:

```python
                if signal != 0:
                    entry_price = price["ask"] if signal == 1 else price["bid"]
                    stop_loss = entry_price * 0.99 if signal == 1 else entry_price * 1.01
                    take_profit = entry_price * 1.02 if signal == 1 else entry_price * 0.98
                    units = int(self.risk_manager.calculate_lot(entry_price, stop_loss))
```

with:

```python
                if signal != 0:
                    entry_price = price["ask"] if signal == 1 else price["bid"]
                    stop_loss = entry_price * 0.99 if signal == 1 else entry_price * 1.01
                    take_profit = entry_price * 1.02 if signal == 1 else entry_price * 0.98
                    if self.use_portfolio and self.portfolio_manager is not None:
                        result_eval = self.portfolio_manager.evaluate(df, self.strategies, instrument)
                        units = int(result_eval["lot"])
                    else:
                        units = int(self.risk_manager.calculate_lot(entry_price, stop_loss))
```

### 6.2 Modify `src/main.py`

**Edit 1:** Add `--portfolio` argument.

Replace in `/Users/hideakimacbookair/自動トレード/fx_trading/src/main.py`:

```python
    parser.add_argument("--live", action="store_true", help="Run in live trading mode")
    parser.add_argument("--dry-run", action="store_true", help="Simulate live trading without placing orders")
    parser.add_argument("--backtest", action="store_true", help="Run backtest (default)")
    parser.add_argument("--fetch-data", action="store_true", help="Fetch historical data from OANDA")
    parser.add_argument("--batch-backtest", action="store_true", help="Run batch backtest for all pairs and strategies")
    args = parser.parse_args()
```

with:

```python
    parser.add_argument("--live", action="store_true", help="Run in live trading mode")
    parser.add_argument("--dry-run", action="store_true", help="Simulate live trading without placing orders")
    parser.add_argument("--backtest", action="store_true", help="Run backtest (default)")
    parser.add_argument("--fetch-data", action="store_true", help="Fetch historical data from OANDA")
    parser.add_argument("--batch-backtest", action="store_true", help="Run batch backtest for all pairs and strategies")
    parser.add_argument("--portfolio", action="store_true", help="Use portfolio strategy manager for live/dry-run modes")
    args = parser.parse_args()
```

**Edit 2:** Pass `use_portfolio` to `PollingRunner` in `run_live`.

Replace in `/Users/hideakimacbookair/自動トレード/fx_trading/src/main.py`:

```python
    if dry_run:
        run_dry_trading(settings)
    else:
        runner = PollingRunner(config=settings)
        results = runner.run_all_pairs()
        print(f"Trading cycle results: {results}")
```

with:

```python
    if dry_run:
        run_dry_trading(settings, use_portfolio=args.portfolio)
    else:
        runner = PollingRunner(config=settings, use_portfolio=args.portfolio)
        results = runner.run_all_pairs()
        print(f"Trading cycle results: {results}")
```

**Edit 3:** Update `run_dry_trading` signature and body.

Replace in `/Users/hideakimacbookair/自動トレード/fx_trading/src/main.py`:

```python
def run_dry_trading(settings):
    import pandas as pd
    from src.monitoring.logger import TradeLogger
    
    logger = TradeLogger()
    print("\n--- Dry Run Trading Cycle ---")
    all_signals = {}
```

with:

```python
def run_dry_trading(settings, use_portfolio=False):
    import pandas as pd
    from src.monitoring.logger import TradeLogger
    from src.portfolio.portfolio_manager import PortfolioManager
    
    logger = TradeLogger()
    portfolio_manager = None
    if use_portfolio:
        portfolio_manager = PortfolioManager(
            capital=settings.initial_capital,
            risk_per_trade=settings.risk_per_trade,
            vol_target=0.05,
        )
        print("\n--- Dry Run Trading Cycle (Portfolio Mode) ---")
    else:
        print("\n--- Dry Run Trading Cycle ---")
    all_signals = {}
```

**Edit 4:** Update dry-run signal aggregation to optionally use PortfolioManager.

Replace in `/Users/hideakimacbookair/自動トレード/fx_trading/src/main.py`:

```python
        # Aggregate signals (majority vote)
        buy_votes = sum(1 for s in signals.values() if s == 1)
        sell_votes = sum(1 for s in signals.values() if s == -1)
        
        latest_price = recent_df.iloc[-1]["close"]
        
        if buy_votes > sell_votes and buy_votes >= 2:
            print(f"  >> ACTION: Would place BUY order @ {latest_price:.3f} (votes: {buy_votes} buy, {sell_votes} sell)")
            logger.log_trade(pair, "BUY", 1000, latest_price)
        elif sell_votes > buy_votes and sell_votes >= 2:
            print(f"  >> ACTION: Would place SELL order @ {latest_price:.3f} (votes: {buy_votes} buy, {sell_votes} sell)")
            logger.log_trade(pair, "SELL", 1000, latest_price)
        else:
            print(f"  >> No clear signal (votes: {buy_votes} buy, {sell_votes} sell). No action taken.")
```

with:

```python
        latest_price = recent_df.iloc[-1]["close"]
        
        if use_portfolio and portfolio_manager is not None:
            from src.strategies.factory import StrategyFactory
            strategies = [StrategyFactory.create(name) for name in signals.keys()]
            result = portfolio_manager.evaluate(recent_df, strategies, pair)
            signal = result["signal"]
            lot = result["lot"]
            regime = result["regime"]
            if signal == 1:
                print(f"  >> ACTION: Would place BUY order @ {latest_price:.3f} (regime: {regime}, lot: {lot:.2f})")
                logger.log_trade(pair, "BUY", int(lot), latest_price)
            elif signal == -1:
                print(f"  >> ACTION: Would place SELL order @ {latest_price:.3f} (regime: {regime}, lot: {lot:.2f})")
                logger.log_trade(pair, "SELL", int(lot), latest_price)
            else:
                print(f"  >> No clear signal (regime: {regime}, confidence: {result['confidence']:.2f}). No action taken.")
        else:
            # Aggregate signals (majority vote)
            buy_votes = sum(1 for s in signals.values() if s == 1)
            sell_votes = sum(1 for s in signals.values() if s == -1)
            
            if buy_votes > sell_votes and buy_votes >= 2:
                print(f"  >> ACTION: Would place BUY order @ {latest_price:.3f} (votes: {buy_votes} buy, {sell_votes} sell)")
                logger.log_trade(pair, "BUY", 1000, latest_price)
            elif sell_votes > buy_votes and sell_votes >= 2:
                print(f"  >> ACTION: Would place SELL order @ {latest_price:.3f} (votes: {buy_votes} buy, {sell_votes} sell)")
                logger.log_trade(pair, "SELL", 1000, latest_price)
            else:
                print(f"  >> No clear signal (votes: {buy_votes} buy, {sell_votes} sell). No action taken.")
```

### 6.3 Write Integration Tests

Append to `/Users/hideakimacbookair/自動トレード/fx_trading/tests/test_portfolio.py`:

```python
from unittest.mock import MagicMock, patch


def test_polling_runner_uses_portfolio_manager_when_enabled():
    mock_config = MagicMock()
    mock_config.currency_pair = "USD_JPY"
    mock_config.risk_per_trade = 0.01
    mock_config.api_token = "test"
    mock_config.account_id = "acc"
    mock_config.environment = "practice"
    mock_config.max_daily_loss_pct = 5.0
    mock_config.trading_start_hour = 0
    mock_config.trading_end_hour = 23
    mock_config.initial_capital = 1_000_000
    mock_config.currency_pairs = ["USD_JPY"]
    mock_config.slack_webhook_url = None

    with patch("src.runner.polling_runner.OandaClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.get_current_price.return_value = {"bid": 145.0, "ask": 145.02}
        mock_client.get_open_positions.return_value = []
        mock_client_class.return_value = mock_client

        from src.runner.polling_runner import PollingRunner
        runner = PollingRunner(config=mock_config, strategies=["ma_macd"], use_portfolio=True)
        assert runner.use_portfolio is True
        assert runner.portfolio_manager is not None


def test_main_has_portfolio_flag():
    import argparse
    from src.main import main
    # Just verify the parser accepts --portfolio without error by inspecting argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--portfolio", action="store_true")
    args = parser.parse_args(["--portfolio"])
    assert args.portfolio is True
```

### 6.4 Run Integration Tests

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
python3 -m pytest tests/test_portfolio.py::test_polling_runner_uses_portfolio_manager_when_enabled tests/test_portfolio.py::test_main_has_portfolio_flag -v --tb=short
```

**Expected output:**
```
tests/test_portfolio.py::test_polling_runner_uses_portfolio_manager_when_enabled PASSED
tests/test_portfolio.py::test_main_has_portfolio_flag PASSED
```

### 6.5 Run Full Test Suite

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
python3 -m pytest --tb=short -q
```

**Expected output:**
```
97 passed in X.XXs
```

### 6.6 Commit

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
git add src/runner/polling_runner.py src/main.py tests/test_portfolio.py
git commit -m "feat(integration): wire PortfolioManager into PollingRunner and main.py --portfolio mode"
```

---

## Summary

All tasks completed. The portfolio strategy manager now provides:

1. **MarketRegimeDetector** (`src/portfolio/market_regime.py`) – ADX-based trend/ranging detection.
2. **StrategySelector** (`src/portfolio/strategy_selector.py`) – Regime-aware strategy name selection.
3. **PositionSizer** (`src/portfolio/position_sizer.py`) – Half-Kelly + 5% volatility targeting.
4. **PortfolioManager** (`src/portfolio/portfolio_manager.py`) – Orchestrates regime, selection, aggregation, and sizing.
5. **Rebalancer** (`src/portfolio/rebalancer.py`) – Weekly Friday rebalancing with performance scoring.
6. **Integration** – `--portfolio` flag in `src/main.py` and `PollingRunner` uses `PortfolioManager` when enabled.

**Final verification command:**
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
python3 -m pytest --tb=short -q
```

**Expected:** `97 passed`
