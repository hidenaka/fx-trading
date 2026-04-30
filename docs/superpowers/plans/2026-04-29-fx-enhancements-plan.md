# FX自動売買 強化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** OANDAから実データ取得、ダッシュボードリアルタイム更新、ML精度向上の3つの強化を実装する。

**Architecture:** OANDA APIフェッチャーを追加、ダッシュボードを5秒ポーリングに拡張、ML特徴量にMACD/ボリンジャーバンド/ATR等を追加しGridSearchCVで最適化。

**Tech Stack:** Python 3.11+, pandas, numpy, pytest, requests, scikit-learn, HTML5/JS

---

## File Structure

```
fx_trading/
├── data/
│   ├── sample_usdjpy_1h.csv
│   └── __init__.py
├── dashboard/
│   ├── index.html
│   ├── app.js
│   └── data/
│       └── .gitkeep
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── server.py
│   │   └── data_exporter.py
│   ├── broker/
│   │   ├── __init__.py
│   │   └── oanda_client.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   ├── preprocessor.py
│   │   └── oanda_fetcher.py          # NEW
│   ├── engine/
│   │   ├── __init__.py
│   │   └── backtest.py
│   ├── ml/
│   │   ├── __init__.py
│   │   ├── feature_engineer.py       # MODIFIED
│   │   ├── predictor.py
│   │   ├── strategy.py
│   │   └── trainer.py                # MODIFIED
│   ├── monitoring/
│   │   ├── __init__.py
│   │   ├── logger.py
│   │   └── slack.py
│   ├── notifications/
│   │   ├── __init__.py
│   │   └── slack_notifier.py
│   ├── optimizer/
│   │   ├── __init__.py
│   │   └── grid_search.py
│   ├── reports/
│   │   ├── __init__.py
│   │   └── reporter.py
│   ├── risk/
│   │   ├── __init__.py
│   │   └── manager.py
│   ├── runner/
│   │   ├── __init__.py
│   │   └── polling_runner.py
│   ├── safety/
│   │   ├── __init__.py
│   │   └── circuit_breaker.py
│   ├── selector/
│   │   ├── __init__.py
│   │   └── ranker.py
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── dow_theory.py
│   │   ├── factory.py
│   │   ├── ma_cross.py
│   │   ├── ma_macd.py
│   │   └── stochastic.py
│   └── wfa/
│       ├── __init__.py
│       └── walker.py
├── tests/
│   ├── test_api.py
│   ├── test_config.py
│   ├── test_data.py
│   ├── test_fetcher.py               # NEW
│   ├── test_ml.py                    # MODIFIED
│   ├── test_reports.py
│   ├── test_runner.py
│   ├── test_strategies.py
│   └── test_wfa.py
├── .env.example
├── requirements.txt
└── logs/
    └── trades.log
```

---

### Task 1: OANDA Data Fetcher

**Goal:** Create `src/data/oanda_fetcher.py` to fetch historical candlestick data from OANDA API v3 and save to CSV format compatible with the existing `DataLoader`.

**TDD Steps:**

#### Step 1.1: Write the test first

Create `/Users/hideakimacbookair/自動トレード/fx_trading/tests/test_fetcher.py`:

```python
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from src.data.oanda_fetcher import OandaDataFetcher


def test_fetcher_returns_dataframe():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "instrument": "USD_JPY",
        "granularity": "H1",
        "candles": [
            {
                "time": "2024-01-01T00:00:00.000000000Z",
                "mid": {"o": "145.000", "h": "145.500", "l": "144.800", "c": "145.200"},
                "volume": 1000,
                "complete": True,
            },
            {
                "time": "2024-01-01T01:00:00.000000000Z",
                "mid": {"o": "145.200", "h": "145.800", "l": "145.100", "c": "145.600"},
                "volume": 1200,
                "complete": True,
            },
        ],
    }
    with patch("src.data.oanda_fetcher.requests.get", return_value=mock_response):
        fetcher = OandaDataFetcher(api_token="test-token", environment="practice")
        df = fetcher.fetch_candles("USD_JPY", "H1", count=2)
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["datetime", "open", "high", "low", "close", "volume"]
        assert len(df) == 2
        assert df.iloc[0]["open"] == 145.0
        assert df.iloc[0]["high"] == 145.5
        assert df.iloc[0]["low"] == 144.8
        assert df.iloc[0]["close"] == 145.2
        assert df.iloc[0]["volume"] == 1000
        assert df.iloc[1]["close"] == 145.6


def test_fetcher_saves_csv(tmp_path):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candles": [
            {
                "time": "2024-01-01T00:00:00.000000000Z",
                "mid": {"o": "145.000", "h": "145.500", "l": "144.800", "c": "145.200"},
                "volume": 1000,
                "complete": True,
            }
        ],
    }
    filepath = tmp_path / "test_usd_jpy.csv"
    with patch("src.data.oanda_fetcher.requests.get", return_value=mock_response):
        fetcher = OandaDataFetcher(api_token="test-token")
        df = fetcher.fetch_candles("USD_JPY", "H1", count=1)
        fetcher.save_to_csv(df, str(filepath))

    assert filepath.exists()
    loaded = pd.read_csv(filepath, parse_dates=["datetime"])
    assert len(loaded) == 1
    assert loaded.iloc[0]["close"] == 145.2


def test_fetcher_skips_incomplete_candles():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candles": [
            {
                "time": "2024-01-01T00:00:00.000000000Z",
                "mid": {"o": "145.000", "h": "145.500", "l": "144.800", "c": "145.200"},
                "volume": 1000,
                "complete": False,
            },
            {
                "time": "2024-01-01T01:00:00.000000000Z",
                "mid": {"o": "145.200", "h": "145.800", "l": "145.100", "c": "145.600"},
                "volume": 1200,
                "complete": True,
            },
        ],
    }
    with patch("src.data.oanda_fetcher.requests.get", return_value=mock_response):
        fetcher = OandaDataFetcher(api_token="test-token")
        df = fetcher.fetch_candles("USD_JPY", "H1", count=2)
        assert len(df) == 1
        assert df.iloc[0]["close"] == 145.6


def test_fetcher_returns_empty_on_no_candles():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"candles": []}
    with patch("src.data.oanda_fetcher.requests.get", return_value=mock_response):
        fetcher = OandaDataFetcher(api_token="test-token")
        df = fetcher.fetch_candles("USD_JPY", "H1", count=0)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
```

**Run command:**
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && python3 -m pytest tests/test_fetcher.py -v
```

**Expected output:**
```
============================= test session starts ==============================
...
ERROR tests/test_fetcher.py - ModuleNotFoundError: No module named 'src.data.oanda_fetcher'
========================= 4 errors in 0.01s ==========================
```

#### Step 1.2: Implement the fetcher

Create `/Users/hideakimacbookair/自動トレード/fx_trading/src/data/oanda_fetcher.py`:

```python
import pandas as pd
import requests
from typing import Optional


class OandaDataFetcher:
    """Fetches historical candlestick data from OANDA API v3."""

    def __init__(self, api_token: str, environment: str = "practice"):
        self.api_token = api_token
        self.environment = environment
        if environment == "live":
            self.base_url = "https://api-fxtrade.oanda.com/v3"
        else:
            self.base_url = "https://api-fxpractice.oanda.com/v3"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def fetch_candles(
        self,
        instrument: str,
        granularity: str = "H1",
        count: int = 500,
        price: str = "M",
    ) -> pd.DataFrame:
        """Fetch candles and return as DataFrame with columns: datetime, open, high, low, close, volume."""
        endpoint = f"instruments/{instrument}/candles"
        params = {
            "granularity": granularity,
            "count": count,
            "price": price,
        }
        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, headers=self.headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        candles = data.get("candles", [])
        if not candles:
            return pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume"])

        rows = []
        for c in candles:
            if not c.get("complete", True):
                continue
            mid = c.get("mid", {})
            rows.append({
                "datetime": c["time"],
                "open": float(mid.get("o", 0)),
                "high": float(mid.get("h", 0)),
                "low": float(mid.get("l", 0)),
                "close": float(mid.get("c", 0)),
                "volume": int(c.get("volume", 0)),
            })

        df = pd.DataFrame(rows)
        df["datetime"] = pd.to_datetime(df["datetime"])
        return df

    def save_to_csv(self, df: pd.DataFrame, filepath: str):
        """Save DataFrame to CSV in the format expected by DataLoader."""
        df.to_csv(filepath, index=False)
```

**Run command:**
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && python3 -m pytest tests/test_fetcher.py -v
```

**Expected output:**
```
============================= test session starts ==============================
tests/test_fetcher.py::test_fetcher_returns_dataframe PASSED
tests/test_fetcher.py::test_fetcher_saves_csv PASSED
tests/test_fetcher.py::test_fetcher_skips_incomplete_candles PASSED
tests/test_fetcher.py::test_fetcher_returns_empty_on_no_candles PASSED

============================== 4 passed in 0.12s ===============================
```

#### Step 1.3: Commit

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && git add src/data/oanda_fetcher.py tests/test_fetcher.py && git commit -m "feat: add OANDA historical data fetcher with tests"
```

---

### Task 2: Fetch CLI Command

**Goal:** Modify `src/main.py` to add `--fetch-data` CLI command that fetches and saves data for all configured currency pairs.

#### Step 2.1: Implement the CLI command

Edit `/Users/hideakimacbookair/自動トレード/fx_trading/src/main.py`:

Replace the `main()` function and add `run_fetch_data()`:

```python
import argparse
from src.data.loader import DataLoader
from src.data.preprocessor import Preprocessor
from src.data.oanda_fetcher import OandaDataFetcher
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
    settings = Settings()
    all_results = []

    for pair in settings.currency_pairs:
        print(f"\n=== Backtest Pair: {pair} ===")
        try:
            raw_df = loader.load_csv(pair.lower(), "1h")
        except FileNotFoundError:
            print(f"Data file for {pair} not found, skipping.")
            continue
        pre = Preprocessor()
        df = pre.process(raw_df)

        strategy_names = StrategyFactory.available_strategies()

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

            all_results.append({
                "name": f"{pair} {name} Best",
                "profit_factor": best["profit_factor"],
                "win_rate": best["win_rate"],
                "max_drawdown": 0.1,
                "total_trades": best["total_trades"],
            })
            all_results.append({
                "name": f"{pair} {name} WFA Avg",
                "profit_factor": sum(x["test_pf"] for x in wfa_results) / len(wfa_results) if wfa_results else 0,
                "win_rate": 0.5,
                "max_drawdown": 0.15,
                "total_trades": sum(x["test_trades"] for x in wfa_results),
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
    print(f"Currency Pairs: {settings.currency_pairs}")
    print(f"Risk per trade: {settings.risk_per_trade * 100}%")

    runner = PollingRunner(config=settings)
    results = runner.run_all_pairs()
    print(f"Trading cycle results: {results}")


def run_fetch_data():
    print("=== Fetch Historical Data from OANDA ===")
    settings = Settings()
    fetcher = OandaDataFetcher(
        api_token=settings.api_token,
        environment=settings.environment,
    )
    granularity = settings.granularity
    # Map granularity to loader-compatible timeframe suffix
    timeframe_map = {"H1": "1h", "M1": "1m", "D": "1d"}
    timeframe = timeframe_map.get(granularity, granularity.lower())

    for pair in settings.currency_pairs:
        print(f"Fetching {pair} {granularity} ...")
        try:
            df = fetcher.fetch_candles(pair, granularity=granularity, count=500)
            filepath = f"data/{pair.lower()}_{timeframe}.csv"
            fetcher.save_to_csv(df, filepath)
            print(f"Saved {len(df)} rows to {filepath}")
        except Exception as e:
            print(f"Failed to fetch {pair}: {e}")


def main():
    parser = argparse.ArgumentParser(description="FX Auto Trading System")
    parser.add_argument("--live", action="store_true", help="Run in live trading mode")
    parser.add_argument("--backtest", action="store_true", help="Run backtest (default)")
    parser.add_argument("--fetch-data", action="store_true", help="Fetch historical data from OANDA")
    args = parser.parse_args()

    if args.fetch_data:
        run_fetch_data()
    elif args.live:
        run_live()
    else:
        run_backtest()


if __name__ == "__main__":
    main()
```

#### Step 2.2: Test manually (with mocked env)

**Run command:**
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && OANDA_API_TOKEN=test-token OANDA_ACCOUNT_ID=test-account python3 -m src.main --fetch-data
```

**Expected output:**
```
=== Fetch Historical Data from OANDA ===
Fetching USD_JPY H1 ...
Failed to fetch USD_JPY: 401 Client Error: Unauthorized for url: https://api-fxpractice.oanda.com/v3/instruments/USD_JPY/candles
```

*(Note: 401 is expected with a dummy token; the wiring is correct. To verify the code path without a real token, run the unit tests which cover the fetcher logic.)*

**Verify tests still pass:**
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && python3 -m pytest tests/ -q
```

**Expected output:**
```
.......................................................................  [100%]
75 passed in 5.12s
```

#### Step 2.3: Commit

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && git add src/main.py && git commit -m "feat: add --fetch-data CLI command to download OANDA historical data"
```

---

### Task 3: Dashboard Real-time Updates

**Goal:** Modify `dashboard/app.js` to poll every 5 seconds with diff detection, auto-update DOM only when data changes, and add a timestamp display.

#### Step 3.1: Update HTML to add timestamp element

Edit `/Users/hideakimacbookair/自動トレード/fx_trading/dashboard/index.html`:

Replace the header div to add a timestamp element:

```html
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FX Auto Trading Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background-color: #0f172a; color: #e2e8f0; }
        .card { background-color: #1e293b; border-radius: 0.5rem; padding: 1rem; }
    </style>
</head>
<body class="p-4">
    <div class="max-w-7xl mx-auto">
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-3xl font-bold text-center flex-1">FX Auto Trading Dashboard</h1>
            <p id="last-updated" class="text-sm text-gray-400">Last updated: -</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div class="card">
                <h2 class="text-lg font-semibold text-gray-400">Total Capital</h2>
                <p id="capital" class="text-2xl font-bold text-green-400">-</p>
            </div>
            <div class="card">
                <h2 class="text-lg font-semibold text-gray-400">Daily P&L</h2>
                <p id="daily-pnl" class="text-2xl font-bold">-</p>
            </div>
            <div class="card">
                <h2 class="text-lg font-semibold text-gray-400">Win Rate</h2>
                <p id="win-rate" class="text-2xl font-bold text-blue-400">-</p>
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div class="card">
                <h2 class="text-lg font-semibold mb-4">Equity Curve</h2>
                <canvas id="equity-chart"></canvas>
            </div>
            <div class="card">
                <h2 class="text-lg font-semibold mb-4">Strategy Ranking</h2>
                <div id="strategy-list"></div>
            </div>
        </div>

        <div class="card">
            <h2 class="text-lg font-semibold mb-4">Open Positions</h2>
            <table class="w-full text-left">
                <thead>
                    <tr class="text-gray-400 border-b border-gray-700">
                        <th class="pb-2">Pair</th>
                        <th class="pb-2">Direction</th>
                        <th class="pb-2">Units</th>
                        <th class="pb-2">Entry Price</th>
                    </tr>
                </thead>
                <tbody id="positions-table"></tbody>
            </table>
        </div>
    </div>

    <script src="app.js"></script>
</body>
</html>
```

#### Step 3.2: Implement polling with diff detection in app.js

Edit `/Users/hideakimacbookair/自動トレード/fx_trading/dashboard/app.js`:

```javascript
let lastData = { portfolio: null, equity: null, backtest: null };
let equityChart = null;

async function loadData() {
    try {
        const portfolio = await fetchData('portfolio.json');
        const equity = await fetchData('equity_curve.json');
        const backtest = await fetchLatestBacktest();

        const hasChanged = hasDataChanged(portfolio, equity, backtest);
        if (hasChanged) {
            updateDashboard(portfolio, equity, backtest);
            lastData = { portfolio, equity, backtest };
        }
        updateTimestamp();
    } catch (e) {
        console.error('Failed to load data:', e);
        document.getElementById('capital').textContent = 'No Data';
    }
}

async function fetchData(filename) {
    try {
        const response = await fetch(`http://localhost:8000/${filename}`);
        if (response.ok) return await response.json();
    } catch (e) {}
    // Fallback to local file
    const response = await fetch(`data/${filename}`);
    if (!response.ok) return null;
    return await response.json();
}

async function fetchLatestBacktest() {
    try {
        const response = await fetch('http://localhost:8000/batch_backtest.json');
        if (response.ok) return await response.json();
    } catch (e) {}
    try {
        const response = await fetch('data/batch_backtest.json');
        if (response.ok) return await response.json();
    } catch (e) {}
    return null;
}

function hasDataChanged(portfolio, equity, backtest) {
    return JSON.stringify(portfolio) !== JSON.stringify(lastData.portfolio) ||
           JSON.stringify(equity) !== JSON.stringify(lastData.equity) ||
           JSON.stringify(backtest) !== JSON.stringify(lastData.backtest);
}

function updateTimestamp() {
    const el = document.getElementById('last-updated');
    if (el) {
        el.textContent = `Last updated: ${new Date().toLocaleTimeString()}`;
    }
}

function updateDashboard(portfolio, equity, backtest) {
    if (portfolio) {
        document.getElementById('capital').textContent =
            portfolio.capital ? `¥${portfolio.capital.toLocaleString()}` : '-';
        document.getElementById('daily-pnl').textContent =
            portfolio.daily_pnl ? `${portfolio.daily_pnl > 0 ? '+' : ''}${portfolio.daily_pnl.toLocaleString()}` : '-';
        document.getElementById('daily-pnl').className =
            `text-2xl font-bold ${portfolio.daily_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`;

        // Update positions table
        const tbody = document.getElementById('positions-table');
        tbody.innerHTML = '';
        if (portfolio.positions) {
            portfolio.positions.forEach(pos => {
                const row = document.createElement('tr');
                row.className = 'border-b border-gray-700';
                row.innerHTML = `
                    <td class="py-2">${pos.instrument}</td>
                    <td class="py-2 ${pos.units > 0 ? 'text-green-400' : 'text-red-400'}">${pos.units > 0 ? 'LONG' : 'SHORT'}</td>
                    <td class="py-2">${Math.abs(pos.units)}</td>
                    <td class="py-2">${pos.entry_price || '-'}</td>
                `;
                tbody.appendChild(row);
            });
        }
    }

    if (equity && equity.length > 0) {
        renderEquityChart(equity);
    }

    if (backtest) {
        document.getElementById('win-rate').textContent =
            backtest.win_rate ? `${(backtest.win_rate * 100).toFixed(1)}%` : '-';

        // Update strategy ranking if batch results exist
        const strategyList = document.getElementById('strategy-list');
        if (backtest.results && strategyList) {
            strategyList.innerHTML = '';
            backtest.results.forEach(r => {
                const div = document.createElement('div');
                div.className = 'flex justify-between py-1 border-b border-gray-700';
                div.innerHTML = `
                    <span>${r.pair} ${r.strategy}</span>
                    <span class="${r.profit_factor >= 1.0 ? 'text-green-400' : 'text-red-400'}">PF ${r.profit_factor.toFixed(2)}</span>
                `;
                strategyList.appendChild(div);
            });
        }
    }
}

function renderEquityChart(equityData) {
    const ctx = document.getElementById('equity-chart').getContext('2d');
    const labels = equityData.map((_, i) => i);
    const data = equityData.map(d => d.capital || d);

    if (equityChart) {
        equityChart.data.labels = labels;
        equityChart.data.datasets[0].data = data;
        equityChart.update();
        return;
    }

    equityChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Capital',
                data: data,
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                fill: true,
                tension: 0.4,
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: { display: false },
                y: {
                    grid: { color: '#334155' },
                    ticks: { color: '#94a3b8' }
                }
            }
        }
    });
}

// Load data on page load and refresh every 5 seconds
loadData();
setInterval(loadData, 5000);
```

#### Step 3.3: Verify in browser

Start the dashboard server in one terminal:
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && python3 -m src.api.server
```

Expected output:
```
Dashboard server running at http://localhost:8000
```

Open `http://localhost:8000` in a browser. The page should load, show "No Data" or dash values, and the "Last updated:" timestamp should refresh every 5 seconds.

*(No automated test for browser behavior; verify manually.)*

#### Step 3.4: Commit

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && git add dashboard/app.js dashboard/index.html && git commit -m "feat: dashboard 5-second polling with diff detection and timestamp display"
```

---

### Task 4: ML Feature Enhancement

**Goal:** Modify `src/ml/feature_engineer.py` to add MACD histogram, Bollinger Bands (±1σ, ±2σ), ATR, and price pattern features.

**TDD Steps:**

#### Step 4.1: Add tests for new features

Edit `/Users/hideakimacbookair/自動トレード/fx_trading/tests/test_ml.py`:

Replace the entire file with:

```python
import pandas as pd
import numpy as np
from src.ml.predictor import MLPredictor
from src.ml.trainer import MLTrainer
from src.ml.feature_engineer import FeatureEngineer


def _create_test_df(n=100, seed=42):
    np.random.seed(seed)
    prices = np.random.randn(n).cumsum() + 150
    return pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=n, freq="h"),
        "open": prices + np.random.randn(n) * 0.1,
        "high": prices + np.abs(np.random.randn(n)) * 0.5,
        "low": prices - np.abs(np.random.randn(n)) * 0.5,
        "close": prices + np.random.randn(n) * 0.1,
        "volume": np.random.randint(1000, 2000, n),
    })


def test_feature_engineer_creates_features():
    df = _create_test_df(50)
    fe = FeatureEngineer()
    X, y = fe.prepare(df)
    assert X.shape[0] > 0
    assert X.shape[1] >= 5
    assert len(y) == X.shape[0]
    assert set(y.unique()).issubset({0, 1})


def test_feature_engineer_returns_dataframe():
    df = _create_test_df(50)
    df["open"] = [150.0] * 50
    df["high"] = [151.0] * 50
    df["low"] = [149.0] * 50
    df["close"] = [150.0 + i * 0.01 for i in range(50)]
    df["volume"] = [1000] * 50
    fe = FeatureEngineer()
    X, y = fe.prepare(df)
    assert isinstance(X, pd.DataFrame)


def test_feature_engineer_macd_histogram():
    df = _create_test_df(50)
    fe = FeatureEngineer()
    X, y = fe.prepare(df)
    assert "macd_histogram" in X.columns
    assert "macd_line" in X.columns
    assert "macd_signal" in X.columns


def test_feature_engineer_bollinger_bands():
    df = _create_test_df(50)
    fe = FeatureEngineer()
    X, y = fe.prepare(df)
    assert "bb_upper_1" in X.columns
    assert "bb_lower_1" in X.columns
    assert "bb_upper_2" in X.columns
    assert "bb_lower_2" in X.columns
    assert "dist_bb_upper_1" in X.columns
    assert "dist_bb_lower_1" in X.columns
    assert "dist_bb_upper_2" in X.columns
    assert "dist_bb_lower_2" in X.columns


def test_feature_engineer_atr():
    df = _create_test_df(50)
    fe = FeatureEngineer()
    X, y = fe.prepare(df)
    assert "atr" in X.columns
    assert X["atr"].notna().sum() > 0


def test_feature_engineer_price_patterns():
    df = _create_test_df(50)
    fe = FeatureEngineer()
    X, y = fe.prepare(df)
    assert "doji" in X.columns
    assert "hammer" in X.columns
    assert "bullish_engulfing" in X.columns
    assert set(X["doji"].unique()).issubset({0, 1})
    assert set(X["hammer"].unique()).issubset({0, 1})
    assert set(X["bullish_engulfing"].unique()).issubset({0, 1})


def test_predictor_trains_and_predicts():
    np.random.seed(42)
    df = _create_test_df(100)
    fe = FeatureEngineer()
    X, y = fe.prepare(df)

    trainer = MLTrainer()
    model = trainer.train(X, y)

    predictor = MLPredictor(model)
    proba = predictor.predict_proba(X.iloc[:5])
    assert proba.shape == (5, 2)
    assert (proba >= 0).all() and (proba <= 1).all()


def test_trainer_evaluates_model():
    np.random.seed(42)
    df = _create_test_df(100)
    fe = FeatureEngineer()
    X, y = fe.prepare(df)

    trainer = MLTrainer()
    model = trainer.train(X, y)
    metrics = trainer.evaluate(X, y)
    assert "accuracy" in metrics
    assert 0 <= metrics["accuracy"] <= 1
```

**Run command:**
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && python3 -m pytest tests/test_ml.py -v
```

**Expected output:**
```
============================= test session starts ==============================
...
tests/test_ml.py::test_feature_engineer_macd_histogram FAILED
tests/test_ml.py::test_feature_engineer_bollinger_bands FAILED
tests/test_ml.py::test_feature_engineer_atr FAILED
tests/test_ml.py::test_feature_engineer_price_patterns FAILED
============================== 4 failed, 4 passed ============================
```

#### Step 4.2: Implement new features

Edit `/Users/hideakimacbookair/自動トレード/fx_trading/src/ml/feature_engineer.py`:

```python
import pandas as pd
import numpy as np
from typing import Tuple


class FeatureEngineer:
    def __init__(self, lookback: int = 10):
        self.lookback = lookback

    def prepare(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        df = df.copy()

        # Returns
        df["returns"] = df["close"].pct_change()

        # Moving averages
        df["sma_5"] = df["close"].rolling(window=5).mean()
        df["sma_10"] = df["close"].rolling(window=10).mean()
        df["sma_20"] = df["close"].rolling(window=20).mean()

        # Distance from MAs
        df["dist_sma5"] = (df["close"] - df["sma_5"]) / df["sma_5"]
        df["dist_sma10"] = (df["close"] - df["sma_10"]) / df["sma_10"]

        # Volatility
        df["volatility"] = df["returns"].rolling(window=10).std()

        # Price range
        df["range"] = (df["high"] - df["low"]) / df["close"]

        # Volume change
        df["volume_change"] = df["volume"].pct_change()

        # RSI-like feature
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df["rsi"] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))

        # MACD
        df["ema_12"] = df["close"].ewm(span=12, adjust=False).mean()
        df["ema_26"] = df["close"].ewm(span=26, adjust=False).mean()
        df["macd_line"] = df["ema_12"] - df["ema_26"]
        df["macd_signal"] = df["macd_line"].ewm(span=9, adjust=False).mean()
        df["macd_histogram"] = df["macd_line"] - df["macd_signal"]

        # Bollinger Bands
        df["bb_sma"] = df["sma_20"]
        df["bb_std"] = df["close"].rolling(window=20).std()
        df["bb_upper_1"] = df["bb_sma"] + df["bb_std"]
        df["bb_lower_1"] = df["bb_sma"] - df["bb_std"]
        df["bb_upper_2"] = df["bb_sma"] + 2 * df["bb_std"]
        df["bb_lower_2"] = df["bb_sma"] - 2 * df["bb_std"]
        df["dist_bb_upper_1"] = (df["close"] - df["bb_upper_1"]) / df["bb_sma"]
        df["dist_bb_lower_1"] = (df["close"] - df["bb_lower_1"]) / df["bb_sma"]
        df["dist_bb_upper_2"] = (df["close"] - df["bb_upper_2"]) / df["bb_sma"]
        df["dist_bb_lower_2"] = (df["close"] - df["bb_lower_2"]) / df["bb_sma"]

        # ATR (Average True Range)
        df["tr"] = np.maximum(
            df["high"] - df["low"],
            np.maximum(
                abs(df["high"] - df["close"].shift(1)),
                abs(df["low"] - df["close"].shift(1)),
            ),
        )
        df["atr"] = df["tr"].rolling(window=14).mean()

        # Price patterns
        body = abs(df["close"] - df["open"])
        candle_range = df["high"] - df["low"]
        lower_shadow = df[["open", "close"]].min(axis=1) - df["low"]

        df["doji"] = (body / (candle_range + 1e-9) < 0.1).astype(int)
        df["hammer"] = (
            (lower_shadow / (candle_range + 1e-9) > 0.6) &
            (body / (candle_range + 1e-9) < 0.3)
        ).astype(int)
        df["bullish_engulfing"] = (
            (df["close"] > df["open"]) &
            (df["close"].shift(1) < df["open"].shift(1)) &
            (df["open"] < df["close"].shift(1)) &
            (df["close"] > df["open"].shift(1))
        ).astype(int)

        # Target: 1 if next close is higher, 0 otherwise
        df["target"] = (df["close"].shift(-1) > df["close"]).astype(int)

        # Select feature columns
        feature_cols = [
            "returns", "dist_sma5", "dist_sma10",
            "volatility", "range", "volume_change", "rsi",
            "macd_line", "macd_signal", "macd_histogram",
            "bb_upper_1", "bb_lower_1", "bb_upper_2", "bb_lower_2",
            "dist_bb_upper_1", "dist_bb_lower_1", "dist_bb_upper_2", "dist_bb_lower_2",
            "atr",
            "doji", "hammer", "bullish_engulfing",
        ]

        # Drop NaN rows
        df = df.dropna()

        X = df[feature_cols]
        y = df["target"]

        return X, y
```

**Run command:**
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && python3 -m pytest tests/test_ml.py -v
```

**Expected output:**
```
============================= test session starts ==============================
tests/test_ml.py::test_feature_engineer_creates_features PASSED
tests/test_ml.py::test_feature_engineer_returns_dataframe PASSED
tests/test_ml.py::test_feature_engineer_macd_histogram PASSED
tests/test_ml.py::test_feature_engineer_bollinger_bands PASSED
tests/test_ml.py::test_feature_engineer_atr PASSED
tests/test_ml.py::test_feature_engineer_price_patterns PASSED
tests/test_ml.py::test_predictor_trains_and_predicts PASSED
tests/test_ml.py::test_trainer_evaluates_model PASSED

============================== 8 passed in 0.85s ===============================
```

#### Step 4.3: Commit

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && git add src/ml/feature_engineer.py tests/test_ml.py && git commit -m "feat: add MACD, Bollinger Bands, ATR, and price pattern features to ML pipeline"
```

---

### Task 5: ML Hyperparameter Tuning

**Goal:** Modify `src/ml/trainer.py` to add `train_with_grid_search` using `GridSearchCV`.

**TDD Steps:**

#### Step 5.1: Add test for grid search

Edit `/Users/hideakimacbookair/自動トレード/fx_trading/tests/test_ml.py`:

Append the following test to the end of the file:

```python

def test_trainer_grid_search():
    np.random.seed(42)
    df = _create_test_df(100)
    fe = FeatureEngineer()
    X, y = fe.prepare(df)

    trainer = MLTrainer(model_type="logistic_regression")
    model = trainer.train_with_grid_search(X, y)
    assert model is not None
    metrics = trainer.evaluate(X, y)
    assert "accuracy" in metrics
    assert 0 <= metrics["accuracy"] <= 1


def test_trainer_grid_search_random_forest():
    np.random.seed(42)
    df = _create_test_df(100)
    fe = FeatureEngineer()
    X, y = fe.prepare(df)

    trainer = MLTrainer(model_type="random_forest")
    param_grid = {"n_estimators": [10, 20], "max_depth": [3, 5]}
    model = trainer.train_with_grid_search(X, y, param_grid=param_grid)
    assert model is not None
    metrics = trainer.evaluate(X, y)
    assert "accuracy" in metrics
```

**Run command:**
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && python3 -m pytest tests/test_ml.py::test_trainer_grid_search tests/test_ml.py::test_trainer_grid_search_random_forest -v
```

**Expected output:**
```
============================= test session starts ==============================
...
ERROR tests/test_ml.py::test_trainer_grid_search - AttributeError: 'MLTrainer' object has no attribute 'train_with_grid_search'
============================== 2 errors in 0.05s ============================
```

#### Step 5.2: Implement grid search

Edit `/Users/hideakimacbookair/自動トレード/fx_trading/src/ml/trainer.py`:

```python
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score
from sklearn.model_selection import GridSearchCV
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional


class MLTrainer:
    def __init__(self, model_type: str = "logistic_regression"):
        self.model_type = model_type
        self.model = None

    def _create_model(self):
        if self.model_type == "logistic_regression":
            return LogisticRegression(max_iter=1000, random_state=42)
        elif self.model_type == "random_forest":
            return RandomForestClassifier(n_estimators=100, random_state=42)
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

    def train(self, X: pd.DataFrame, y: pd.Series) -> Any:
        self.model = self._create_model()
        self.model.fit(X, y)
        return self.model

    def train_with_grid_search(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        param_grid: Optional[Dict[str, list]] = None,
    ) -> Any:
        model = self._create_model()
        if param_grid is None:
            param_grid = {
                "logistic_regression": {"C": [0.01, 0.1, 1.0, 10.0]},
                "random_forest": {"n_estimators": [50, 100], "max_depth": [3, 5, None]},
            }.get(self.model_type, {})
        grid = GridSearchCV(
            model,
            param_grid,
            cv=3,
            scoring="accuracy",
        )
        grid.fit(X, y)
        self.model = grid.best_estimator_
        return self.model

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        if self.model is None:
            raise RuntimeError("Model not trained yet")
        preds = self.model.predict(X)
        return {
            "accuracy": accuracy_score(y, preds),
            "precision": precision_score(y, preds, zero_division=0),
            "recall": recall_score(y, preds, zero_division=0),
        }
```

**Run command:**
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && python3 -m pytest tests/test_ml.py -v
```

**Expected output:**
```
============================= test session starts ==============================
tests/test_ml.py::test_feature_engineer_creates_features PASSED
tests/test_ml.py::test_feature_engineer_returns_dataframe PASSED
tests/test_ml.py::test_feature_engineer_macd_histogram PASSED
tests/test_ml.py::test_feature_engineer_bollinger_bands PASSED
tests/test_ml.py::test_feature_engineer_atr PASSED
tests/test_ml.py::test_feature_engineer_price_patterns PASSED
tests/test_ml.py::test_predictor_trains_and_predicts PASSED
tests/test_ml.py::test_trainer_evaluates_model PASSED
tests/test_ml.py::test_trainer_grid_search PASSED
tests/test_ml.py::test_trainer_grid_search_random_forest PASSED

============================== 10 passed in 2.15s ==============================
```

#### Step 5.3: Commit

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && git add src/ml/trainer.py tests/test_ml.py && git commit -m "feat: add GridSearchCV hyperparameter optimization to ML trainer"
```

---

### Task 6: Batch Backtest Command

**Goal:** Modify `src/main.py` to add `--batch-backtest` that runs all pairs × all strategies and exports results to JSON for the dashboard.

#### Step 6.1: Add batch backtest export method to DataExporter

Edit `/Users/hideakimacbookair/自動トレード/fx_trading/src/api/data_exporter.py`:

```python
import json
import os
from datetime import datetime
from typing import Dict, Any


class DataExporter:
    def __init__(self, output_dir: str = "dashboard/data"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def export_backtest_result(self, strategy_name: str, data: Dict[str, Any]) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backtest_{strategy_name}_{timestamp}.json"
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        return filepath

    def export_portfolio(self, portfolio: Dict[str, Any]) -> str:
        filepath = os.path.join(self.output_dir, "portfolio.json")
        with open(filepath, "w") as f:
            json.dump(portfolio, f, indent=2, default=str)
        return filepath

    def export_equity_curve(self, equity_data: list) -> str:
        filepath = os.path.join(self.output_dir, "equity_curve.json")
        with open(filepath, "w") as f:
            json.dump(equity_data, f, indent=2, default=str)
        return filepath

    def export_batch_backtest(self, data: Dict[str, Any]) -> str:
        """Export batch backtest results to a fixed filename for dashboard consumption."""
        filepath = os.path.join(self.output_dir, "batch_backtest.json")
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        return filepath
```

#### Step 6.2: Implement batch backtest in main.py

Edit `/Users/hideakimacbookair/自動トレード/fx_trading/src/main.py`:

Add imports and the new function:

```python
import argparse
from src.data.loader import DataLoader
from src.data.preprocessor import Preprocessor
from src.data.oanda_fetcher import OandaDataFetcher
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
    loader = DataLoader(data_dir="data")
    settings = Settings()
    all_results = []

    for pair in settings.currency_pairs:
        print(f"\n=== Backtest Pair: {pair} ===")
        try:
            raw_df = loader.load_csv(pair.lower(), "1h")
        except FileNotFoundError:
            print(f"Data file for {pair} not found, skipping.")
            continue
        pre = Preprocessor()
        df = pre.process(raw_df)

        strategy_names = StrategyFactory.available_strategies()

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

            all_results.append({
                "name": f"{pair} {name} Best",
                "profit_factor": best["profit_factor"],
                "win_rate": best["win_rate"],
                "max_drawdown": 0.1,
                "total_trades": best["total_trades"],
            })
            all_results.append({
                "name": f"{pair} {name} WFA Avg",
                "profit_factor": sum(x["test_pf"] for x in wfa_results) / len(wfa_results) if wfa_results else 0,
                "win_rate": 0.5,
                "max_drawdown": 0.15,
                "total_trades": sum(x["test_trades"] for x in wfa_results),
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
    print(f"Currency Pairs: {settings.currency_pairs}")
    print(f"Risk per trade: {settings.risk_per_trade * 100}%")

    runner = PollingRunner(config=settings)
    results = runner.run_all_pairs()
    print(f"Trading cycle results: {results}")


def run_fetch_data():
    print("=== Fetch Historical Data from OANDA ===")
    settings = Settings()
    fetcher = OandaDataFetcher(
        api_token=settings.api_token,
        environment=settings.environment,
    )
    granularity = settings.granularity
    timeframe_map = {"H1": "1h", "M1": "1m", "D": "1d"}
    timeframe = timeframe_map.get(granularity, granularity.lower())

    for pair in settings.currency_pairs:
        print(f"Fetching {pair} {granularity} ...")
        try:
            df = fetcher.fetch_candles(pair, granularity=granularity, count=500)
            filepath = f"data/{pair.lower()}_{timeframe}.csv"
            fetcher.save_to_csv(df, filepath)
            print(f"Saved {len(df)} rows to {filepath}")
        except Exception as e:
            print(f"Failed to fetch {pair}: {e}")


def run_batch_backtest():
    print("=== Batch Backtest: All Pairs × All Strategies ===")
    loader = DataLoader(data_dir="data")
    settings = Settings()
    exporter = DataExporter(output_dir="dashboard/data")
    all_results = []

    strategy_names = StrategyFactory.available_strategies()

    for pair in settings.currency_pairs:
        print(f"\n--- Pair: {pair} ---")
        try:
            raw_df = loader.load_csv(pair.lower(), "1h")
        except FileNotFoundError:
            print(f"Data file for {pair} not found, skipping.")
            continue
        pre = Preprocessor()
        df = pre.process(raw_df)

        for name in strategy_names:
            strategy = StrategyFactory.create(name)
            engine = BacktestEngine(initial_capital=settings.initial_capital)
            risk = RiskManager(
                capital=settings.initial_capital,
                risk_per_trade=settings.risk_per_trade,
            )
            trades = engine.run(df.copy(), strategy, risk)
            reporter = ReportGenerator(initial_capital=settings.initial_capital)
            report = reporter.generate(trades)

            result = {
                "pair": pair,
                "strategy": name,
                "total_trades": report["total_trades"],
                "win_rate": report["win_rate"],
                "profit_factor": report["profit_factor"],
                "total_pnl": report["total_pnl"],
            }
            all_results.append(result)
            print(f"  {name}: Trades={report['total_trades']}, PF={report['profit_factor']:.2f}, WR={report['win_rate']:.2f}")

    summary = {
        "results": all_results,
        "pairs": settings.currency_pairs,
        "strategies": strategy_names,
        "count": len(all_results),
    }
    filepath = exporter.export_batch_backtest(summary)
    print(f"\nBatch backtest complete. {len(all_results)} results exported to {filepath}")


def main():
    parser = argparse.ArgumentParser(description="FX Auto Trading System")
    parser.add_argument("--live", action="store_true", help="Run in live trading mode")
    parser.add_argument("--backtest", action="store_true", help="Run backtest (default)")
    parser.add_argument("--fetch-data", action="store_true", help="Fetch historical data from OANDA")
    parser.add_argument("--batch-backtest", action="store_true", help="Run batch backtest for all pairs and strategies")
    args = parser.parse_args()

    if args.fetch_data:
        run_fetch_data()
    elif args.batch_backtest:
        run_batch_backtest()
    elif args.live:
        run_live()
    else:
        run_backtest()


if __name__ == "__main__":
    main()
```

#### Step 6.3: Test the batch backtest command

**Run command:**
```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && OANDA_API_TOKEN=test-token OANDA_ACCOUNT_ID=test-account python3 -m src.main --batch-backtest
```

**Expected output:**
```
=== Batch Backtest: All Pairs × All Strategies ===

--- Pair: USD_JPY ---
  ma_macd: Trades=4, PF=1.23, WR=0.50
  ma_cross: Trades=3, PF=0.00, WR=0.33
  dow_theory: Trades=2, PF=inf, WR=1.00
  stochastic: Trades=5, PF=0.85, WR=0.40
  ml_strategy: Trades=0, PF=0.00, WR=0.00

Batch backtest complete. 5 results exported to dashboard/data/batch_backtest.json
```

*(Note: exact trade counts and metrics depend on the sample data; the command must complete without errors and create `dashboard/data/batch_backtest.json`.)*

**Verify the JSON file was created:**
```bash
cat /Users/hideakimacbookair/自動トレード/fx_trading/dashboard/data/batch_backtest.json | head -20
```

**Expected output:**
```json
{
  "results": [
    {
      "pair": "USD_JPY",
      "strategy": "ma_macd",
      "total_trades": ...
```

#### Step 6.4: Commit

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && git add src/main.py src/api/data_exporter.py && git commit -m "feat: add --batch-backtest CLI command exporting results to dashboard JSON"
```

---

### Task 7: Final Verification

**Goal:** Run all tests, run the backtest, and verify no regressions.

#### Step 7.1: Run all tests

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && python3 -m pytest tests/ -v
```

**Expected output:**
```
============================= test session starts ==============================
tests/test_api.py::test_exporter_creates_json_file PASSED
tests/test_api.py::test_exporter_exports_portfolio PASSED
tests/test_config.py::test_settings_loads_from_env PASSED
tests/test_config.py::test_settings_defaults PASSED
tests/test_config.py::test_settings_raises_on_missing_token PASSED
tests/test_data.py::test_load_csv PASSED
tests/test_data.py::test_preprocessor_sorts_and_drops_na PASSED
tests/test_fetcher.py::test_fetcher_returns_dataframe PASSED
tests/test_fetcher.py::test_fetcher_saves_csv PASSED
tests/test_fetcher.py::test_fetcher_skips_incomplete_candles PASSED
tests/test_fetcher.py::test_fetcher_returns_empty_on_no_candles PASSED
tests/test_ml.py::test_feature_engineer_creates_features PASSED
tests/test_ml.py::test_feature_engineer_returns_dataframe PASSED
tests/test_ml.py::test_feature_engineer_macd_histogram PASSED
tests/test_ml.py::test_feature_engineer_bollinger_bands PASSED
tests/test_ml.py::test_feature_engineer_atr PASSED
tests/test_ml.py::test_feature_engineer_price_patterns PASSED
tests/test_ml.py::test_predictor_trains_and_predicts PASSED
tests/test_ml.py::test_trainer_evaluates_model PASSED
tests/test_ml.py::test_trainer_grid_search PASSED
tests/test_ml.py::test_trainer_grid_search_random_forest PASSED
tests/test_reports.py ... PASSED
tests/test_runner.py ... PASSED
tests/test_strategies.py ... PASSED
tests/test_wfa.py ... PASSED

============================== 79 passed in 8.32s ==============================
```

*(Note: 71 original + 4 fetcher + 4 ML feature + 2 ML grid search = 81 expected. The exact count may vary by 1-2 if test_reports.py or test_wfa.py has a different count than shown here. The key is ALL tests pass with zero failures.)*

#### Step 7.2: Run default backtest to ensure no regression

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && OANDA_API_TOKEN=test-token OANDA_ACCOUNT_ID=test-account python3 -m src.main --backtest
```

**Expected output:**
```
=== Backtest Pair: USD_JPY ===

=== Grid Search: ma_macd | USD_JPY ===
Best params: {...}
Profit Factor: ...

=== Walk-Forward Analysis: ma_macd | USD_JPY ===
Window 1: Train PF=..., Test PF=..., Params={...}
...
=== Strategy Ranking ===
USD_JPY ma_macd Best: Score=...
```

#### Step 7.3: Final commit (if not already committed)

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && git status
```

Ensure working tree is clean. If there are any remaining changes:

```bash
cd /Users/hideakimacbookair/自動トレード/fx_trading && git add -A && git commit -m "feat: complete FX enhancements - OANDA fetcher, dashboard polling, ML features, batch backtest"
```

---

## Summary of Changes

| Task | Files Created | Files Modified | Tests Added |
|------|--------------|----------------|-------------|
| 1. OANDA Fetcher | `src/data/oanda_fetcher.py` | - | `tests/test_fetcher.py` (4 tests) |
| 2. Fetch CLI | - | `src/main.py` | - |
| 3. Dashboard Polling | - | `dashboard/app.js`, `dashboard/index.html` | - |
| 4. ML Features | - | `src/ml/feature_engineer.py` | `tests/test_ml.py` (+4 tests) |
| 5. ML Grid Search | - | `src/ml/trainer.py` | `tests/test_ml.py` (+2 tests) |
| 6. Batch Backtest | - | `src/main.py`, `src/api/data_exporter.py` | - |

**Total test delta:** +10 tests (from 71 to 81). All must pass.
