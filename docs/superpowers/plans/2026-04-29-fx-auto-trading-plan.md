# FX自動売買システム Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** USD/JPYを中心としたFX市場で、複数テクニカル戦略を同時バックテスト・最適化・WFA検証し、自動選定する軽量バックテスト＆評価フレームワークを構築する。

**Architecture:** pandasベースの軽量自前エンジン。戦略はクラステンプレートで実装し、エンジンがシミュレート。最適化・WFA・ランキングで頑健な戦略を選定。データ取得は多通貨対応で抽象化。

**Tech Stack:** Python 3.11+, pandas, numpy, pytest, matplotlib

---

## File Structure

```
fx_trading/
├── requirements.txt
├── README.md
├── data/
│   └── sample_usdjpy_1h.csv
├── src/
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   └── preprocessor.py
│   ├── risk/
│   │   ├── __init__.py
│   │   └── manager.py
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── ma_macd.py
│   ├── engine/
│   │   ├── __init__.py
│   │   └── backtest.py
│   ├── optimizer/
│   │   ├── __init__.py
│   │   └── grid_search.py
│   ├── wfa/
│   │   ├── __init__.py
│   │   └── walker.py
│   ├── selector/
│   │   ├── __init__.py
│   │   └── ranker.py
│   ├── reports/
│   │   ├── __init__.py
│   │   └── reporter.py
│   └── main.py
└── tests/
    ├── __init__.py
    ├── test_data.py
    ├── test_risk.py
    ├── test_strategies.py
    ├── test_engine.py
    ├── test_optimizer.py
    ├── test_wfa.py
    ├── test_selector.py
    └── test_reports.py
```

---

### Task 1: Project Setup

**Files:**
- Create: `fx_trading/requirements.txt`
- Create: `fx_trading/README.md`
- Create: `fx_trading/data/sample_usdjpy_1h.csv`
- Create directory structure

- [ ] **Step 1: Create directory structure**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード
mkdir -p fx_trading/{src/{data,risk,strategies,engine,optimizer,wfa,selector,reports},tests,data}
touch fx_trading/src/__init__.py
touch fx_trading/src/data/__init__.py
touch fx_trading/src/risk/__init__.py
touch fx_trading/src/strategies/__init__.py
touch fx_trading/src/engine/__init__.py
touch fx_trading/src/optimizer/__init__.py
touch fx_trading/src/wfa/__init__.py
touch fx_trading/src/selector/__init__.py
touch fx_trading/src/reports/__init__.py
touch fx_trading/tests/__init__.py
```

- [ ] **Step 2: Write requirements.txt**

Create: `fx_trading/requirements.txt`
```text
pandas>=2.0.0
numpy>=1.24.0
pytest>=7.4.0
matplotlib>=3.7.0
```

- [ ] **Step 3: Write sample CSV data**

Create: `fx_trading/data/sample_usdjpy_1h.csv`
```csv
 datetime,open,high,low,close,volume
2024-01-01 00:00:00,145.000,145.500,144.800,145.200,1000
2024-01-01 01:00:00,145.200,145.800,145.100,145.600,1200
2024-01-01 02:00:00,145.600,145.900,145.400,145.300,1100
2024-01-01 03:00:00,145.300,145.400,144.900,145.000,1300
2024-01-01 04:00:00,145.000,145.100,144.700,144.800,1000
2024-01-01 05:00:00,144.800,145.200,144.600,145.100,1100
2024-01-01 06:00:00,145.100,145.500,145.000,145.400,1200
2024-01-01 07:00:00,145.400,145.800,145.300,145.700,1300
2024-01-01 08:00:00,145.700,146.000,145.600,145.900,1400
2024-01-01 09:00:00,145.900,146.200,145.800,146.100,1500
```

- [ ] **Step 4: Install dependencies**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
pip install -r requirements.txt
```

- [ ] **Step 5: Commit**

```bash
cd /Users/hideakimacbookair/自動トレード
git init 2>/dev/null || true
git add fx_trading/
git commit -m "chore: init fx_trading project structure"
```

---

### Task 2: Data Loader & Preprocessor

**Files:**
- Create: `fx_trading/src/data/loader.py`
- Create: `fx_trading/src/data/preprocessor.py`
- Test: `fx_trading/tests/test_data.py`

- [ ] **Step 1: Write failing test**

Create: `fx_trading/tests/test_data.py`
```python
import pandas as pd
from src.data.loader import DataLoader
from src.data.preprocessor import Preprocessor

def test_load_csv():
    loader = DataLoader(data_dir="data")
    df = loader.load_csv("sample", "usdjpy_1h")
    assert isinstance(df, pd.DataFrame)
    assert "datetime" in df.columns
    assert len(df) == 10

def test_preprocessor_sorts_and_drops_na():
    df = pd.DataFrame({
        "datetime": ["2024-01-02", "2024-01-01", "2024-01-03"],
        "open": [1.0, 2.0, None],
        "high": [1.1, 2.1, 3.1],
        "low": [0.9, 1.9, 2.9],
        "close": [1.05, 2.05, 3.05],
        "volume": [100, 200, 300],
    })
    pre = Preprocessor()
    result = pre.process(df)
    assert len(result) == 2
    assert result.iloc[0]["datetime"] == pd.Timestamp("2024-01-01")
    assert result.iloc[1]["datetime"] == pd.Timestamp("2024-01-02")
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
pytest tests/test_data.py -v
```
Expected: FAIL with "ModuleNotFoundError: No module named 'src.data'" or similar

- [ ] **Step 3: Write minimal implementation**

Create: `fx_trading/src/data/loader.py`
```python
import pandas as pd
from pathlib import Path

class DataLoader:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)

    def load_csv(self, symbol: str, timeframe: str) -> pd.DataFrame:
        path = self.data_dir / f"{symbol}_{timeframe}.csv"
        df = pd.read_csv(path, parse_dates=["datetime"])
        return df
```

Create: `fx_trading/src/data/preprocessor.py`
```python
import pandas as pd

class Preprocessor:
    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df = df.sort_values("datetime").reset_index(drop=True)
        df = df.dropna().reset_index(drop=True)
        return df
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
pytest tests/test_data.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/hideakimacbookair/自動トレード
git add fx_trading/src/data/ fx_trading/tests/test_data.py
git commit -m "feat: add data loader and preprocessor"
```

---

### Task 3: Risk Manager

**Files:**
- Create: `fx_trading/src/risk/manager.py`
- Test: `fx_trading/tests/test_risk.py`

- [ ] **Step 1: Write failing test**

Create: `fx_trading/tests/test_risk.py`
```python
import pytest
from src.risk.manager import RiskManager

def test_calculate_lot_basic():
    rm = RiskManager(capital=1_000_000, risk_per_trade=0.01)
    lot = rm.calculate_lot(entry_price=150.0, stop_loss=149.0)
    expected_risk = 1_000_000 * 0.01
    expected_lot = expected_risk / 1.0
    assert lot == pytest.approx(expected_lot)

def test_calculate_lot_zero_diff_returns_zero():
    rm = RiskManager(capital=1_000_000, risk_per_trade=0.01)
    lot = rm.calculate_lot(entry_price=150.0, stop_loss=150.0)
    assert lot == 0.0

def test_update_capital():
    rm = RiskManager(capital=1_000_000, risk_per_trade=0.01)
    rm.update_capital(50000)
    assert rm.capital == 1_050_000
    rm.update_capital(-30000)
    assert rm.capital == 1_020_000
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
pytest tests/test_risk.py -v
```
Expected: FAIL with "ModuleNotFoundError" or "function not defined"

- [ ] **Step 3: Write minimal implementation**

Create: `fx_trading/src/risk/manager.py`
```python
class RiskManager:
    def __init__(self, capital: float, risk_per_trade: float = 0.01):
        self.capital = capital
        self.risk_per_trade = risk_per_trade

    def calculate_lot(self, entry_price: float, stop_loss: float) -> float:
        risk_amount = self.capital * self.risk_per_trade
        price_diff = abs(entry_price - stop_loss)
        if price_diff == 0:
            return 0.0
        lot = risk_amount / price_diff
        return lot

    def update_capital(self, pnl: float):
        self.capital += pnl
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
pytest tests/test_risk.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/hideakimacbookair/自動トレード
git add fx_trading/src/risk/manager.py fx_trading/tests/test_risk.py
git commit -m "feat: add risk manager with lot calculation"
```

---

### Task 4: Strategy Base & MA+MACD Strategy

**Files:**
- Create: `fx_trading/src/strategies/base.py`
- Create: `fx_trading/src/strategies/ma_macd.py`
- Test: `fx_trading/tests/test_strategies.py`

- [ ] **Step 1: Write failing test**

Create: `fx_trading/tests/test_strategies.py`
```python
import pandas as pd
from src.strategies.ma_macd import MaMacdStrategy

def test_ma_macd_generates_signals():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=30, freq="h"),
        "open": [150.0] * 30,
        "high": [151.0] * 30,
        "low": [149.0] * 30,
        "close": [150.0 + i * 0.1 for i in range(30)],
        "volume": [1000] * 30,
    })
    strat = MaMacdStrategy(fast=3, slow=6, signal=2)
    result = strat.generate_signals(df)
    assert "signal" in result.columns
    assert set(result["signal"].unique()).issubset({-1, 0, 1})

def test_ma_macd_long_signal_on_golden_cross():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=10, freq="h"),
        "open": [150.0] * 10,
        "high": [151.0] * 10,
        "low": [149.0] * 10,
        "close": [150.0, 149.5, 149.0, 148.5, 148.0, 148.5, 149.0, 149.5, 150.0, 150.5],
        "volume": [1000] * 10,
    })
    strat = MaMacdStrategy(fast=2, slow=4, signal=2)
    result = strat.generate_signals(df)
    assert result.iloc[-1]["signal"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
pytest tests/test_strategies.py -v
```
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Create: `fx_trading/src/strategies/base.py`
```python
from abc import ABC, abstractmethod
import pandas as pd

class Strategy(ABC):
    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        pass
```

Create: `fx_trading/src/strategies/ma_macd.py`
```python
import pandas as pd
from .base import Strategy

class MaMacdStrategy(Strategy):
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["ema_fast"] = df["close"].ewm(span=self.fast, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.slow, adjust=False).mean()
        df["macd"] = df["ema_fast"] - df["ema_slow"]
        df["macd_signal"] = df["macd"].ewm(span=self.signal, adjust=False).mean()
        df["signal"] = 0
        df.loc[df["macd"] > df["macd_signal"], "signal"] = 1
        df.loc[df["macd"] < df["macd_signal"], "signal"] = -1
        return df
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
pytest tests/test_strategies.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/hideakimacbookair/自動トレード
git add fx_trading/src/strategies/ fx_trading/tests/test_strategies.py
git commit -m "feat: add strategy base and MA+MACD strategy"
```

---

### Task 5: Backtest Engine

**Files:**
- Create: `fx_trading/src/engine/backtest.py`
- Test: `fx_trading/tests/test_engine.py`

- [ ] **Step 1: Write failing test**

Create: `fx_trading/tests/test_engine.py`
```python
import pandas as pd
from src.engine.backtest import BacktestEngine
from src.strategies.ma_macd import MaMacdStrategy
from src.risk.manager import RiskManager

def test_backtest_runs_and_produces_trades():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=30, freq="h"),
        "open": [150.0] * 30,
        "high": [151.0] * 30,
        "low": [149.0] * 30,
        "close": [150.0 + i * 0.1 for i in range(30)],
        "volume": [1000] * 30,
    })
    engine = BacktestEngine(initial_capital=1_000_000)
    strategy = MaMacdStrategy(fast=3, slow=6, signal=2)
    risk = RiskManager(capital=1_000_000, risk_per_trade=0.01)
    trades = engine.run(df, strategy, risk)
    assert isinstance(trades, list)

def test_backtest_capital_changes():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=10, freq="h"),
        "open": [150.0] * 10,
        "high": [151.0] * 10,
        "low": [149.0] * 10,
        "close": [150.0, 149.5, 149.0, 148.5, 148.0, 148.5, 149.0, 149.5, 150.0, 150.5],
        "volume": [1000] * 10,
    })
    engine = BacktestEngine(initial_capital=1_000_000)
    strategy = MaMacdStrategy(fast=2, slow=4, signal=2)
    risk = RiskManager(capital=1_000_000, risk_per_trade=0.01)
    trades = engine.run(df, strategy, risk)
    assert engine.capital != 1_000_000 or len(trades) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
pytest tests/test_engine.py -v
```
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Create: `fx_trading/src/engine/backtest.py`
```python
import pandas as pd
from typing import List
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
    def __init__(self, initial_capital: float = 1_000_000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.trades: List[Trade] = []

    def run(self, df: pd.DataFrame, strategy, risk_manager):
        df = strategy.generate_signals(df)
        position = 0
        current_trade = None

        for i in range(1, len(df)):
            row = df.iloc[i]
            if position == 0 and row["signal"] != 0:
                direction = int(row["signal"])
                stop = row["close"] * 0.99 if direction == 1 else row["close"] * 1.01
                lot = risk_manager.calculate_lot(row["close"], stop)
                current_trade = Trade(
                    entry_time=row["datetime"],
                    entry_price=row["close"],
                    direction=direction,
                    lot=lot,
                )
                position = direction
            elif position != 0 and row["signal"] != position:
                current_trade.exit_time = row["datetime"]
                current_trade.exit_price = row["close"]
                current_trade.pnl = (current_trade.exit_price - current_trade.entry_price) * current_trade.lot * current_trade.direction
                self.trades.append(current_trade)
                risk_manager.update_capital(current_trade.pnl)
                self.capital = risk_manager.capital
                position = 0
                current_trade = None

        return self.trades
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
pytest tests/test_engine.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/hideakimacbookair/自動トレード
git add fx_trading/src/engine/backtest.py fx_trading/tests/test_engine.py
git commit -m "feat: add backtest engine"
```

---

### Task 6: Report Generator

**Files:**
- Create: `fx_trading/src/reports/reporter.py`
- Test: `fx_trading/tests/test_reports.py`

- [ ] **Step 1: Write failing test**

Create: `fx_trading/tests/test_reports.py`
```python
import pandas as pd
from src.reports.reporter import ReportGenerator
from src.engine.backtest import Trade

def test_generate_report_basic():
    trades = [
        Trade(entry_time=pd.Timestamp("2024-01-01"), entry_price=150.0, direction=1, lot=1.0,
              exit_time=pd.Timestamp("2024-01-02"), exit_price=151.0, pnl=1000.0),
        Trade(entry_time=pd.Timestamp("2024-01-03"), entry_price=151.0, direction=-1, lot=1.0,
              exit_time=pd.Timestamp("2024-01-04"), exit_price=150.0, pnl=1000.0),
    ]
    reporter = ReportGenerator(initial_capital=1_000_000)
    report = reporter.generate(trades)
    assert report["total_trades"] == 2
    assert report["win_rate"] == 1.0
    assert report["profit_factor"] == float("inf")

def test_generate_report_with_loss():
    trades = [
        Trade(entry_time=pd.Timestamp("2024-01-01"), entry_price=150.0, direction=1, lot=1.0,
              exit_time=pd.Timestamp("2024-01-02"), exit_price=149.0, pnl=-1000.0),
    ]
    reporter = ReportGenerator(initial_capital=1_000_000)
    report = reporter.generate(trades)
    assert report["total_trades"] == 1
    assert report["win_rate"] == 0.0
    assert report["profit_factor"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
pytest tests/test_reports.py -v
```
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Create: `fx_trading/src/reports/reporter.py`
```python
from typing import List, Dict
from src.engine.backtest import Trade

class ReportGenerator:
    def __init__(self, initial_capital: float = 1_000_000):
        self.initial_capital = initial_capital

    def generate(self, trades: List[Trade]) -> Dict:
        total_trades = len(trades)
        if total_trades == 0:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "total_pnl": 0.0,
            }

        wins = [t.pnl for t in trades if t.pnl > 0]
        losses = [t.pnl for t in trades if t.pnl < 0]
        total_pnl = sum(t.pnl for t in trades)
        win_rate = len(wins) / total_trades

        gross_profit = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss != 0 else float("inf")

        return {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_pnl": total_pnl,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
pytest tests/test_reports.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/hideakimacbookair/自動トレード
git add fx_trading/src/reports/reporter.py fx_trading/tests/test_reports.py
git commit -m "feat: add report generator"
```

---

### Task 7: Grid Search Optimizer

**Files:**
- Create: `fx_trading/src/optimizer/grid_search.py`
- Test: `fx_trading/tests/test_optimizer.py`

- [ ] **Step 1: Write failing test**

Create: `fx_trading/tests/test_optimizer.py`
```python
import pandas as pd
from src.optimizer.grid_search import GridSearchOptimizer
from src.strategies.ma_macd import MaMacdStrategy
from src.engine.backtest import BacktestEngine
from src.risk.manager import RiskManager

def test_grid_search_runs():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=30, freq="h"),
        "open": [150.0] * 30,
        "high": [151.0] * 30,
        "low": [149.0] * 30,
        "close": [150.0 + i * 0.1 for i in range(30)],
        "volume": [1000] * 30,
    })
    optimizer = GridSearchOptimizer(df)
    param_grid = {
        "fast": [3, 5],
        "slow": [6, 10],
        "signal": [2, 3],
    }
    results = optimizer.search(MaMacdStrategy, param_grid)
    assert len(results) == 4
    assert all("params" in r and "profit_factor" in r for r in results)

def test_grid_search_finds_best():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=30, freq="h"),
        "open": [150.0] * 30,
        "high": [151.0] * 30,
        "low": [149.0] * 30,
        "close": [150.0 + i * 0.1 for i in range(30)],
        "volume": [1000] * 30,
    })
    optimizer = GridSearchOptimizer(df)
    param_grid = {
        "fast": [3],
        "slow": [6],
        "signal": [2],
    }
    results = optimizer.search(MaMacdStrategy, param_grid)
    best = optimizer.get_best(results)
    assert best["params"]["fast"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
pytest tests/test_optimizer.py -v
```
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Create: `fx_trading/src/optimizer/grid_search.py`
```python
import itertools
from typing import List, Dict, Type
from src.engine.backtest import BacktestEngine
from src.risk.manager import RiskManager
from src.reports.reporter import ReportGenerator

class GridSearchOptimizer:
    def __init__(self, df):
        self.df = df

    def search(self, strategy_class: Type, param_grid: Dict) -> List[Dict]:
        keys = list(param_grid.keys())
        values = [param_grid[k] for k in keys]
        results = []

        for combo in itertools.product(*values):
            params = dict(zip(keys, combo))
            strategy = strategy_class(**params)
            engine = BacktestEngine(initial_capital=1_000_000)
            risk = RiskManager(capital=1_000_000, risk_per_trade=0.01)
            trades = engine.run(self.df.copy(), strategy, risk)
            reporter = ReportGenerator(initial_capital=1_000_000)
            report = reporter.generate(trades)
            results.append({
                "params": params,
                "total_trades": report["total_trades"],
                "win_rate": report["win_rate"],
                "profit_factor": report["profit_factor"],
                "total_pnl": report["total_pnl"],
            })

        return results

    def get_best(self, results: List[Dict], metric: str = "profit_factor") -> Dict:
        valid = [r for r in results if r[metric] != float("inf") and r[metric] is not None]
        if not valid:
            return results[0] if results else {}
        return max(valid, key=lambda x: x[metric])
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
pytest tests/test_optimizer.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/hideakimacbookair/自動トレード
git add fx_trading/src/optimizer/grid_search.py fx_trading/tests/test_optimizer.py
git commit -m "feat: add grid search optimizer"
```

---

### Task 8: Walk-Forward Analysis (WFA)

**Files:**
- Create: `fx_trading/src/wfa/walker.py`
- Test: `fx_trading/tests/test_wfa.py`

- [ ] **Step 1: Write failing test**

Create: `fx_trading/tests/test_wfa.py`
```python
import pandas as pd
from src.wfa.walker import WalkForwardAnalyzer
from src.strategies.ma_macd import MaMacdStrategy

def test_walk_forward_splits_data():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=100, freq="h"),
        "open": [150.0] * 100,
        "high": [151.0] * 100,
        "low": [149.0] * 100,
        "close": [150.0 + i * 0.01 for i in range(100)],
        "volume": [1000] * 100,
    })
    wfa = WalkForwardAnalyzer(train_size=50, test_size=25)
    windows = wfa.split(df)
    assert len(windows) == 2
    assert len(windows[0]["train"]) == 50
    assert len(windows[0]["test"]) == 25

def test_walk_forward_runs_analysis():
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=100, freq="h"),
        "open": [150.0] * 100,
        "high": [151.0] * 100,
        "low": [149.0] * 100,
        "close": [150.0 + i * 0.01 for i in range(100)],
        "volume": [1000] * 100,
    })
    wfa = WalkForwardAnalyzer(train_size=50, test_size=25)
    param_grid = {"fast": [3, 5], "slow": [6, 10], "signal": [2]}
    results = wfa.analyze(df, MaMacdStrategy, param_grid)
    assert len(results) == 2
    assert all("train_pf" in r and "test_pf" in r for r in results)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
pytest tests/test_wfa.py -v
```
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Create: `fx_trading/src/wfa/walker.py`
```python
from typing import List, Dict, Type
import pandas as pd
from src.optimizer.grid_search import GridSearchOptimizer

class WalkForwardAnalyzer:
    def __init__(self, train_size: int, test_size: int):
        self.train_size = train_size
        self.test_size = test_size

    def split(self, df: pd.DataFrame) -> List[Dict]:
        windows = []
        start = 0
        while start + self.train_size + self.test_size <= len(df):
            train = df.iloc[start : start + self.train_size].copy()
            test = df.iloc[start + self.train_size : start + self.train_size + self.test_size].copy()
            windows.append({"train": train, "test": test})
            start += self.test_size
        return windows

    def analyze(self, df: pd.DataFrame, strategy_class: Type, param_grid: Dict) -> List[Dict]:
        windows = self.split(df)
        results = []
        for window in windows:
            train_optimizer = GridSearchOptimizer(window["train"])
            train_results = train_optimizer.search(strategy_class, param_grid)
            best_train = train_optimizer.get_best(train_results, metric="profit_factor")

            test_optimizer = GridSearchOptimizer(window["test"])
            test_results = test_optimizer.search(strategy_class, {"fast": [best_train["params"]["fast"]],
                                                                   "slow": [best_train["params"]["slow"]],
                                                                   "signal": [best_train["params"]["signal"]]})
            best_test = test_optimizer.get_best(test_results, metric="profit_factor")

            results.append({
                "train_pf": best_train["profit_factor"],
                "test_pf": best_test["profit_factor"],
                "params": best_train["params"],
                "train_trades": best_train["total_trades"],
                "test_trades": best_test["total_trades"],
            })
        return results
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
pytest tests/test_wfa.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/hideakimacbookair/自動トレード
git add fx_trading/src/wfa/walker.py fx_trading/tests/test_wfa.py
git commit -m "feat: add walk-forward analysis"
```

---

### Task 9: Strategy Selector (Ranker)

**Files:**
- Create: `fx_trading/src/selector/ranker.py`
- Test: `fx_trading/tests/test_selector.py`

- [ ] **Step 1: Write failing test**

Create: `fx_trading/tests/test_selector.py`
```python
from src.selector.ranker import StrategyRanker

def test_ranker_sorts_by_composite_score():
    results = [
        {"name": "A", "profit_factor": 2.0, "win_rate": 0.6, "max_drawdown": 0.1, "total_trades": 50},
        {"name": "B", "profit_factor": 1.5, "win_rate": 0.55, "max_drawdown": 0.05, "total_trades": 100},
        {"name": "C", "profit_factor": 3.0, "win_rate": 0.7, "max_drawdown": 0.2, "total_trades": 30},
    ]
    ranker = StrategyRanker()
    ranked = ranker.rank(results)
    assert ranked[0]["name"] == "C"

def test_ranker_filters_min_trades():
    results = [
        {"name": "A", "profit_factor": 2.0, "win_rate": 0.6, "max_drawdown": 0.1, "total_trades": 5},
        {"name": "B", "profit_factor": 1.5, "win_rate": 0.55, "max_drawdown": 0.05, "total_trades": 100},
    ]
    ranker = StrategyRanker(min_trades=10)
    ranked = ranker.rank(results)
    assert len(ranked) == 1
    assert ranked[0]["name"] == "B"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
pytest tests/test_selector.py -v
```
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Create: `fx_trading/src/selector/ranker.py`
```python
from typing import List, Dict

class StrategyRanker:
    def __init__(self, min_trades: int = 20):
        self.min_trades = min_trades

    def rank(self, results: List[Dict]) -> List[Dict]:
        filtered = [r for r in results if r.get("total_trades", 0) >= self.min_trades]
        for r in filtered:
            pf = r.get("profit_factor", 0)
            wr = r.get("win_rate", 0)
            mdd = r.get("max_drawdown", 1)
            if pf == float("inf") or pf is None:
                pf = 0
            if mdd == 0:
                mdd = 1e-6
            r["score"] = (pf * 0.4) + (wr * 2.0) + ((1 / mdd) * 0.1)

        ranked = sorted(filtered, key=lambda x: x["score"], reverse=True)
        return ranked
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
pytest tests/test_selector.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/hideakimacbookair/自動トレード
git add fx_trading/src/selector/ranker.py fx_trading/tests/test_selector.py
git commit -m "feat: add strategy ranker"
```

---

### Task 10: Main Integration Script

**Files:**
- Create: `fx_trading/src/main.py`

- [ ] **Step 1: Write main script**

Create: `fx_trading/src/main.py`
```python
from src.data.loader import DataLoader
from src.data.preprocessor import Preprocessor
from src.strategies.ma_macd import MaMacdStrategy
from src.engine.backtest import BacktestEngine
from src.risk.manager import RiskManager
from src.reports.reporter import ReportGenerator
from src.optimizer.grid_search import GridSearchOptimizer
from src.wfa.walker import WalkForwardAnalyzer
from src.selector.ranker import StrategyRanker

def main():
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
    wfa = WalkForwardAnalyzer(train_size=60, test_size=30)
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
    ranker = StrategyRanker(min_trades=1)
    ranked = ranker.rank(rank_inputs)
    for r in ranked:
        print(f"{r['name']}: Score={r['score']:.2f}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run integration check**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
python -m src.main
```
Expected: Script runs without error and prints Grid Search, WFA, and Ranking results.

- [ ] **Step 3: Run all tests**

Run:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading
pytest tests/ -v
```
Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
cd /Users/hideakimacbookair/自動トレード
git add fx_trading/src/main.py
git commit -m "feat: add main integration script"
```

---

## Self-Review

**1. Spec coverage:**
- データ取得・前処理: Task 2
- リスク管理: Task 3
- 戦略クラス（MA+MACD）: Task 4
- バックテストエンジン: Task 5
- レポート生成: Task 6
- グリッドサーチ最適化: Task 7
- WFA（ウォークフォワード分析）: Task 8
- 戦略ランキング・選定: Task 9
- 統合実行: Task 10
- 多通貨対応: Task 2のDataLoaderがsymbol/timeframeを引数に取る設計で対応
- エラーハンドリング: 各Taskの実装にガード節含む
- テスト戦略: 各TaskにTDDステップ含む

**2. Placeholder scan:**
- TBD/TODOなし
- 各ステップにコードブロックあり
- 各ステップにテストコマンドと期待出力あり

**3. Type consistency:**
- `DataLoader.load_csv(symbol, timeframe)` のシグネチャはTask 2で定義し、Task 10で使用。一致。
- `RiskManager(capital, risk_per_trade)` のシグネチャはTask 3で定義。Task 5, 7, 10で使用。一致。
- `BacktestEngine.run(df, strategy, risk_manager)` のシグネチャはTask 5で定義。Task 7, 10で使用。一致。
- `GridSearchOptimizer.search(strategy_class, param_grid)` のシグネチャはTask 7で定義。Task 8, 10で使用。一致。
