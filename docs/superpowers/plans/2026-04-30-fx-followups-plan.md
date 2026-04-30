# FX Trading Follow-ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the four remaining gaps from the loss-resistance hardening: ML feature scaling, broker-side trade reconciliation, WFA aggregate reporting in the CLI, and dashboard exposure of risk-adjusted metrics.

**Architecture:**
- Task 1 wraps sklearn estimators in a `Pipeline(StandardScaler, model)` so all numeric features are normalized; grid-search params are renamed with the `clf__` prefix.
- Task 2 adds an OANDA `transactions/sinceid` poll inside `PollingRunner.run_cycle` to feed `CircuitBreaker.record_pnl` for SL/TP-driven exits the runner never observes.
- Task 3 calls the existing `WalkForwardAnalyzer.summarize()` from `main.run_backtest` and prints OOS aggregates.
- Task 4 routes batch backtests through `ReportGenerator` so the dashboard JSON gains Sharpe/Sortino/Max DD without re-implementing math.

**Tech Stack:** Python 3.12, scikit-learn 1.8, pandas 2.3, pytest, requests, OANDA REST v3.

All work happens inside `/Users/hideakimacbookair/自動トレード/fx_trading/` unless otherwise noted. Run tests with `python3 -m pytest -q` from that directory.

---

## File Structure

| Task | Files Created | Files Modified |
|---|---|---|
| 1 | — | `src/ml/trainer.py`, `tests/test_ml.py` |
| 2 | — | `src/broker/oanda_client.py`, `src/runner/polling_runner.py`, `tests/test_broker.py`, `tests/test_runner.py` |
| 3 | — | `src/main.py` |
| 4 | — | `src/main.py`, `tests/test_reports.py` (no new file; reuses `ReportGenerator`) |

The four tasks are mutually independent — they touch disjoint modules except for `main.py` (Tasks 3 and 4 both touch it, but in different functions: `run_backtest` vs `run_batch_backtest`). Run them in any order, but if parallelizing, give Tasks 3 and 4 to different subagents only after both have read the file.

---

## Task 1: Wrap ML estimators in a scaling pipeline

Why: Logistic regression on the current feature set fails to converge — `bb_upper_1 ≈ 150`, `returns ≈ 0.001`, ATR is in price units. The Bb features dominate the loss surface and `lbfgs` hits its iteration limit. A `StandardScaler` step inside an sklearn `Pipeline` removes that imbalance and applies the scaler correctly per CV fold.

**Files:**
- Modify: `src/ml/trainer.py`
- Modify: `tests/test_ml.py`

- [ ] **Step 1: Write failing test for Pipeline structure**

Append to `tests/test_ml.py`:

```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def test_trainer_train_returns_pipeline_with_scaler():
    df = _synth_df(n=120)
    fe = FeatureEngineer()
    X, y = fe.prepare(df)
    trainer = MLTrainer(model_type="logistic_regression")
    model = trainer.train(X, y)
    assert isinstance(model, Pipeline)
    assert isinstance(model.named_steps["scaler"], StandardScaler)
    assert "clf" in model.named_steps


def test_trainer_grid_search_uses_scaled_pipeline():
    df = _synth_df(n=200)
    fe = FeatureEngineer()
    X, y = fe.prepare(df)
    trainer = MLTrainer(model_type="logistic_regression")
    model, best_params = trainer.train_with_grid_search(X, y)
    assert isinstance(model, Pipeline)
    # Grid keys must be prefixed with the pipeline step name.
    assert any(k.startswith("clf__") for k in best_params)


def test_trainer_logistic_regression_converges_with_scaler():
    import warnings
    from sklearn.exceptions import ConvergenceWarning
    df = _synth_df(n=300)
    fe = FeatureEngineer()
    X, y = fe.prepare(df)
    trainer = MLTrainer(model_type="logistic_regression")
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        trainer.train(X, y)  # would raise if LR fails to converge
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_ml.py::test_trainer_train_returns_pipeline_with_scaler tests/test_ml.py::test_trainer_grid_search_uses_scaled_pipeline tests/test_ml.py::test_trainer_logistic_regression_converges_with_scaler -v
```

Expected: all three FAIL — first two with `AssertionError` (model is bare `LogisticRegression`), third with `ConvergenceWarning` raised as error.

- [ ] **Step 3: Replace `MLTrainer` model construction with a Pipeline**

Replace the entire body of `src/ml/trainer.py` with:

```python
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple

class MLTrainer:
    def __init__(self, model_type: str = "logistic_regression", cv=None):
        self.model_type = model_type
        self.cv = cv if cv is not None else TimeSeriesSplit(n_splits=5)
        self.model = None

    def _create_pipeline(self) -> Pipeline:
        if self.model_type == "logistic_regression":
            clf = LogisticRegression(max_iter=1000, random_state=42)
        elif self.model_type == "random_forest":
            clf = RandomForestClassifier(n_estimators=100, random_state=42)
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")
        # StandardScaler is fit per CV fold via Pipeline, avoiding the
        # train/validation leak you'd get from scaling the full X up front.
        return Pipeline([("scaler", StandardScaler()), ("clf", clf)])

    def train(self, X: pd.DataFrame, y: pd.Series) -> Pipeline:
        self.model = self._create_pipeline()
        self.model.fit(X, y)
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

    def train_with_grid_search(self, X: pd.DataFrame, y: pd.Series) -> Tuple[Pipeline, Dict[str, Any]]:
        pipeline = self._create_pipeline()
        if self.model_type == "logistic_regression":
            param_grid = {"clf__C": [0.01, 0.1, 1, 10], "clf__max_iter": [1000]}
        elif self.model_type == "random_forest":
            param_grid = {"clf__n_estimators": [50, 100, 200], "clf__max_depth": [3, 5, 10]}
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

        grid = GridSearchCV(pipeline, param_grid, cv=self.cv, scoring="accuracy")
        grid.fit(X, y)
        self.model = grid.best_estimator_
        return self.model, grid.best_params_

    @staticmethod
    def chronological_split(
        X: pd.DataFrame, y: pd.Series, test_size: float = 0.2
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
        if not 0 < test_size < 1:
            raise ValueError("test_size must be in (0, 1)")
        n = len(X)
        split = int(n * (1 - test_size))
        X_train, X_test = X.iloc[:split], X.iloc[split:]
        y_train, y_test = y.iloc[:split], y.iloc[split:]
        return X_train, X_test, y_train, y_test
```

- [ ] **Step 4: Run targeted tests**

```bash
python3 -m pytest tests/test_ml.py -v
```

Expected: all 18 tests PASS (15 prior + 3 new). The convergence-warning test confirms scaling fixed the lbfgs issue.

- [ ] **Step 5: Run full suite to confirm no regression**

```bash
python3 -m pytest -q
```

Expected: 130+ tests pass. No new failures.

- [ ] **Step 6: Commit**

```bash
git add src/ml/trainer.py tests/test_ml.py
git commit -m "feat(ml): wrap estimators in StandardScaler pipeline so lbfgs converges"
```

---

## Task 2: Reconcile broker-side trade closures into the circuit breaker

Why: When a position is closed by SL or TP, the broker fills the order without the runner ever calling `close_position`. Today that PnL never reaches `CircuitBreaker.record_pnl`, so accumulated drawdown and consecutive-loss counters silently miss those trades. We poll the OANDA `transactions/sinceid` endpoint each cycle, look for `ORDER_FILL` transactions with a non-zero `pl`, and feed them in.

**Files:**
- Modify: `src/broker/oanda_client.py` (add `get_transactions_since`)
- Modify: `src/runner/polling_runner.py` (add `_reconcile_realized_pnl`)
- Modify: `tests/test_broker.py` (test transactions API)
- Modify: `tests/test_runner.py` (test reconciliation)

OANDA endpoint reference: `GET /v3/accounts/{accountID}/transactions/sinceid?id={lastTransactionID}` returns `{"transactions": [...], "lastTransactionID": "..."}`. Each transaction with `type == "ORDER_FILL"` carries a `pl` string (account-currency PnL) and an `id`. We persist the highest seen `id`.

- [ ] **Step 1: Write failing test for transactions API client method**

Append to `tests/test_broker.py`:

```python
@patch("src.broker.oanda_client.requests.get")
def test_get_transactions_since(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "transactions": [
            {"id": "101", "type": "ORDER_FILL", "pl": "1500.0"},
            {"id": "102", "type": "ORDER_FILL", "pl": "-300.0"},
            {"id": "103", "type": "MARKET_ORDER", "pl": "0.0"},
        ],
        "lastTransactionID": "103",
    }
    client = OandaClient(api_token="t", account_id="acc", environment="practice")
    result = client.get_transactions_since("100")
    assert result["lastTransactionID"] == "103"
    assert len(result["transactions"]) == 3
    # Verify the URL/params used the sinceid endpoint with the supplied id.
    args, kwargs = mock_get.call_args
    assert "transactions/sinceid" in args[0]
    assert kwargs["params"] == {"id": "100"}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_broker.py::test_get_transactions_since -v
```

Expected: FAIL with `AttributeError: 'OandaClient' object has no attribute 'get_transactions_since'`.

- [ ] **Step 3: Implement `get_transactions_since` in OandaClient**

Append the following method to `src/broker/oanda_client.py` immediately after `close_position` (before `_put`):

```python
    def get_transactions_since(self, last_transaction_id: str) -> Dict:
        # OANDA returns every transaction strictly after the given ID, plus the
        # account's current latest ID. Caller is responsible for filtering by
        # type (ORDER_FILL is the one that carries realized PnL).
        return self._get(
            f"accounts/{self.account_id}/transactions/sinceid",
            params={"id": last_transaction_id},
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_broker.py::test_get_transactions_since -v
```

Expected: PASS.

- [ ] **Step 5: Write failing test for runner reconciliation**

Append to `tests/test_runner.py`:

```python
@patch("src.runner.polling_runner.OandaClient")
def test_runner_reconciles_external_fills_into_circuit_breaker(mock_client_class):
    import pandas as pd
    mock_config = MagicMock()
    mock_config.currency_pair = "USD_JPY"
    mock_config.currency_pairs = ["USD_JPY"]
    mock_config.risk_per_trade = 0.01
    mock_config.api_token = "t"
    mock_config.account_id = "acc"
    mock_config.environment = "practice"
    mock_config.slack_webhook_url = None
    mock_config.initial_capital = 1_000_000
    mock_config.max_daily_loss_pct = 5.0
    mock_config.max_drawdown_pct = 15.0
    mock_config.max_consecutive_losses = 5
    mock_config.trading_start_hour = 0
    mock_config.trading_end_hour = 24

    mock_client = MagicMock()
    mock_client.get_current_price.return_value = {"bid": 145.0, "ask": 145.02}
    mock_client.get_open_positions.return_value = []
    # Two fills happened between cycles: one win, one SL hit.
    mock_client.get_transactions_since.return_value = {
        "transactions": [
            {"id": "201", "type": "ORDER_FILL", "pl": "1200.0"},
            {"id": "202", "type": "ORDER_FILL", "pl": "-800.0"},
            {"id": "203", "type": "MARKET_ORDER", "pl": "0"},
        ],
        "lastTransactionID": "203",
    }
    mock_client_class.return_value = mock_client

    runner = PollingRunner(config=mock_config, strategies=["ma_macd"])
    runner.last_transaction_id = "200"  # baseline
    runner.run_cycle()

    # CB should have recorded both fills (one win, one loss).
    assert runner.circuit_breaker.daily_pnl == 400.0  # 1200 - 800
    # Consecutive losses resets after the win, then increments to 1 on loss.
    assert runner.circuit_breaker.consecutive_losses == 1
    # Cursor advanced to the broker's latest ID.
    assert runner.last_transaction_id == "203"
```

- [ ] **Step 6: Run test to verify it fails**

```bash
python3 -m pytest tests/test_runner.py::test_runner_reconciles_external_fills_into_circuit_breaker -v
```

Expected: FAIL — runner has no `last_transaction_id` attribute and no reconciliation step.

- [ ] **Step 7: Add reconciliation to PollingRunner**

In `src/runner/polling_runner.py`, add the attribute initialization inside `__init__` directly after `self.dry_run = False`:

```python
        # Cursor for OANDA's transactions/sinceid stream. "0" tells the broker
        # to return every transaction the account has ever had on first call;
        # we update to the broker's latest ID after each successful poll.
        self.last_transaction_id = "0"
```

Then add a new method to the class (place it between `_sync_exposure_from_broker` and `run_all_pairs`):

```python
    def _reconcile_realized_pnl(self, now: datetime.datetime) -> None:
        # Pulls every fill since the last cursor and feeds non-zero PnL into
        # the circuit breaker. SL/TP fills go through here even though the
        # runner never calls close_position for them.
        try:
            response = self.client.get_transactions_since(self.last_transaction_id)
        except Exception as exc:
            self.logger.log_error(f"Transaction reconcile failed: {exc}")
            return
        for txn in response.get("transactions", []) or []:
            if txn.get("type") != "ORDER_FILL":
                continue
            try:
                pl = float(txn.get("pl", 0) or 0)
            except (TypeError, ValueError):
                continue
            if pl == 0:
                continue
            self.circuit_breaker.record_pnl(pl, now=now)
        new_cursor = response.get("lastTransactionID")
        if new_cursor:
            self.last_transaction_id = str(new_cursor)
```

Wire the call into `run_cycle`. Find the existing block:

```python
        # 1. Check circuit breaker
        if not self.circuit_breaker.is_trading_allowed(now):
            self.logger.log_info("Trading not allowed by circuit breaker")
            return False
```

Insert the reconcile call **before** the circuit-breaker check (so today's blow-up triggers the breaker before we attempt another order):

```python
        # 0. Pull broker fills that happened outside our control (SL/TP) so
        # the circuit breaker has the full PnL picture before deciding.
        self._reconcile_realized_pnl(now)

        # 1. Check circuit breaker
        if not self.circuit_breaker.is_trading_allowed(now):
            self.logger.log_info("Trading not allowed by circuit breaker")
            return False
```

The existing `close_position` path in `run_cycle` already calls `record_pnl` via `_extract_realized_pnl`. To prevent double-counting that same fill on the next cycle, advance the cursor immediately after a manual close. Find the manual-close block and add the cursor refresh right after the `record_pnl` call:

```python
                if signal != 0 and signal != current_direction:
                    close_response = self.client.close_position(instrument)
                    realized_pnl = _extract_realized_pnl(close_response)
                    self.circuit_breaker.record_pnl(realized_pnl, now=now)
                    # Advance cursor past this fill so the reconcile loop on
                    # the next cycle does not re-apply the same PnL.
                    fill_id = (
                        close_response.get("longOrderFillTransaction", {}).get("id")
                        or close_response.get("shortOrderFillTransaction", {}).get("id")
                    )
                    if fill_id:
                        self.last_transaction_id = str(fill_id)
                    self.exposure_manager.unregister(instrument)
```

- [ ] **Step 8: Run runner test to confirm it passes**

```bash
python3 -m pytest tests/test_runner.py::test_runner_reconciles_external_fills_into_circuit_breaker -v
```

Expected: PASS.

- [ ] **Step 9: Run full suite to confirm no regression**

```bash
python3 -m pytest -q
```

Expected: 130+ tests pass.

- [ ] **Step 10: Commit**

```bash
git add src/broker/oanda_client.py src/runner/polling_runner.py tests/test_broker.py tests/test_runner.py
git commit -m "feat(runner): reconcile SL/TP fills via transactions/sinceid"
```

---

## Task 3: Surface `WalkForwardAnalyzer.summarize()` in the CLI backtest

Why: The summarize() method already aggregates OOS metrics across windows, but `main.run_backtest` only prints per-window results. Users see fragmented numbers and miss the OOS profit factor and WFA efficiency that tell them whether the strategy actually generalizes.

**Files:**
- Modify: `src/main.py` (function `run_backtest`)

- [ ] **Step 1: Locate the WFA loop in `run_backtest`**

Open `src/main.py` and find this block inside `run_backtest`:

```python
            print(f"\n=== Walk-Forward Analysis: {name} | {pair} ===")
            train_size = min(60, max(5, len(df) // 2))
            test_size = min(30, max(3, len(df) // 3))
            wfa = WalkForwardAnalyzer(train_size=train_size, test_size=test_size)
            wfa_results = wfa.analyze(df, strategy_cls, param_grid)
            for i, r in enumerate(wfa_results):
                print(f"Window {i+1}: Train PF={r['train_pf']:.2f}, Test PF={r['test_pf']:.2f}, Params={r['params']}")
```

- [ ] **Step 2: Append the summary block right after the per-window loop**

Replace the block above with:

```python
            print(f"\n=== Walk-Forward Analysis: {name} | {pair} ===")
            train_size = min(60, max(5, len(df) // 2))
            test_size = min(30, max(3, len(df) // 3))
            wfa = WalkForwardAnalyzer(train_size=train_size, test_size=test_size)
            wfa_results = wfa.analyze(df, strategy_cls, param_grid)
            for i, r in enumerate(wfa_results):
                print(f"Window {i+1}: Train PF={r['train_pf']:.2f}, Test PF={r['test_pf']:.2f}, Params={r['params']}")

            wfa_summary = wfa.summarize(wfa_results)
            print(
                f"\n--- WFA Summary ({name} | {pair}) ---\n"
                f"  Windows:           {wfa_summary['windows']}\n"
                f"  OOS trades:        {wfa_summary['oos_total_trades']}\n"
                f"  OOS profit factor: {wfa_summary['oos_profit_factor']:.2f}\n"
                f"  OOS win rate:      {wfa_summary['oos_win_rate']:.2%}\n"
                f"  OOS total PnL:     {wfa_summary['oos_total_pnl']:.2f}\n"
                f"  Avg WFA efficiency:{wfa_summary['avg_wfa_efficiency']:.2f}  (test_pf / train_pf)\n"
                f"  Param change ratio:{wfa_summary['param_change_ratio']:.2%}  (instability indicator)"
            )
```

- [ ] **Step 3: Smoke-check the CLI parses without error**

```bash
python3 -c "from src import main; print('main importable')"
```

Expected output: `main importable`. (We do not run the full backtest here — it requires CSVs.)

- [ ] **Step 4: Run the full test suite to confirm nothing broke**

```bash
python3 -m pytest -q
```

Expected: 130+ tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/main.py
git commit -m "feat(cli): print WFA OOS summary in run_backtest"
```

---

## Task 4: Pipe risk-adjusted metrics into the dashboard JSON

Why: `run_batch_backtest` computes win-rate and PF inline and writes them to `dashboard/data/batch_*.json`, but the dashboard now has access to Sharpe, Sortino, Max Drawdown, and average holding time via `ReportGenerator`. Switching the inline calc to the reporter gives the dashboard those numbers without reimplementing them.

**Files:**
- Modify: `src/main.py` (function `run_batch_backtest`)
- Modify: `tests/test_reports.py` (lock the JSON-shape contract)

- [ ] **Step 1: Add a contract test for the report dictionary keys**

Append to `tests/test_reports.py`:

```python
def test_report_dict_includes_dashboard_keys():
    # The dashboard JSON contract relies on these exact keys; if any are
    # renamed or dropped, the dashboard will silently show blanks. Lock them.
    trades = [
        Trade(entry_time=pd.Timestamp("2024-01-01"), entry_price=150.0, direction=1, lot=1.0,
              exit_time=pd.Timestamp("2024-01-02"), exit_price=151.0, pnl=1000.0),
        Trade(entry_time=pd.Timestamp("2024-01-03"), entry_price=151.0, direction=1, lot=1.0,
              exit_time=pd.Timestamp("2024-01-04"), exit_price=150.0, pnl=-1500.0),
    ]
    report = ReportGenerator(initial_capital=1_000_000).generate(trades)
    required_keys = {
        "total_trades", "win_rate", "profit_factor", "total_pnl",
        "max_drawdown_pct", "max_drawdown_abs",
        "sharpe_ratio", "sortino_ratio", "avg_holding_hours",
    }
    assert required_keys.issubset(report.keys())
```

- [ ] **Step 2: Run the test and confirm it passes (already supported)**

```bash
python3 -m pytest tests/test_reports.py::test_report_dict_includes_dashboard_keys -v
```

Expected: PASS — `ReportGenerator` already returns these keys, this test guards against future regression.

- [ ] **Step 3: Replace the inline metrics calc in `run_batch_backtest`**

Find the block in `src/main.py`:

```python
        for name in strategy_names:
            strategy = StrategyFactory.create(name)
            risk = RiskManager(capital=settings.initial_capital, risk_per_trade=settings.risk_per_trade)
            engine = BacktestEngine(initial_capital=settings.initial_capital)
            trades = engine.run(df, strategy, risk)
            
            winning_trades = [t for t in trades if t.pnl and t.pnl > 0]
            losing_trades = [t for t in trades if t.pnl and t.pnl <= 0]
            
            gross_profit = sum(t.pnl for t in winning_trades)
            gross_loss = abs(sum(t.pnl for t in losing_trades))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
            win_rate = len(winning_trades) / len(trades) if trades else 0
            
            result = {
                "pair": pair,
                "strategy": name,
                "total_trades": len(trades),
                "win_rate": round(win_rate, 4),
                "profit_factor": round(profit_factor, 4),
                "final_capital": round(engine.capital, 2),
            }
            all_results.append(result)
            print(f"{name:20s} | Trades: {result['total_trades']:3d} | Win Rate: {result['win_rate']:.2%} | PF: {result['profit_factor']:.2f} | Capital: ¥{result['final_capital']:,.0f}")
```

Replace it with:

```python
        for name in strategy_names:
            strategy = StrategyFactory.create(name)
            risk = RiskManager(capital=settings.initial_capital, risk_per_trade=settings.risk_per_trade)
            engine = BacktestEngine(initial_capital=settings.initial_capital)
            trades = engine.run(df, strategy, risk)

            report = ReportGenerator(initial_capital=settings.initial_capital).generate(trades)
            pf = report["profit_factor"]
            pf_value = float("inf") if pf == float("inf") else round(pf, 4)
            result = {
                "pair": pair,
                "strategy": name,
                "total_trades": report["total_trades"],
                "win_rate": round(report["win_rate"], 4),
                "profit_factor": pf_value,
                "total_pnl": round(report["total_pnl"], 2),
                "max_drawdown_pct": round(report["max_drawdown_pct"], 2),
                "max_drawdown_abs": round(report["max_drawdown_abs"], 2),
                "sharpe_ratio": round(report["sharpe_ratio"], 3),
                "sortino_ratio": round(report["sortino_ratio"], 3),
                "avg_holding_hours": round(report["avg_holding_hours"], 2),
                "final_capital": round(engine.capital, 2),
            }
            all_results.append(result)
            print(
                f"{name:20s} | Trades: {result['total_trades']:3d} | "
                f"Win Rate: {result['win_rate']:.2%} | PF: {result['profit_factor']:.2f} | "
                f"Sharpe: {result['sharpe_ratio']:.2f} | "
                f"MaxDD: {result['max_drawdown_pct']:.2f}% | "
                f"Capital: ¥{result['final_capital']:,.0f}"
            )
```

Add the import at the top of `src/main.py` near the other imports (after `from src.reports.reporter import ReportGenerator` if not already there):

```python
from src.reports.reporter import ReportGenerator
```

(Check first — `ReportGenerator` is already imported at the top of `src/main.py`. If so, skip the import line.)

- [ ] **Step 4: Update the summary table footer to include the new columns**

Find the existing summary block at the bottom of `run_batch_backtest`:

```python
    # Summary table
    print("\n=== Batch Backtest Summary ===")
    print(f"{'Pair':<12} {'Strategy':<15} {'Trades':>6} {'Win%':>8} {'PF':>8} {'Capital':>15}")
    print("-" * 65)
    for r in all_results:
        print(f"{r['pair']:<12} {r['strategy']:<15} {r['total_trades']:>6} {r['win_rate']:>7.1%} {r['profit_factor']:>8.2f} ¥{r['final_capital']:>13,.0f}")
```

Replace with:

```python
    # Summary table
    print("\n=== Batch Backtest Summary ===")
    header = f"{'Pair':<12} {'Strategy':<15} {'Trades':>6} {'Win%':>8} {'PF':>8} {'Sharpe':>8} {'MaxDD%':>8} {'Capital':>15}"
    print(header)
    print("-" * len(header))
    for r in all_results:
        print(
            f"{r['pair']:<12} {r['strategy']:<15} {r['total_trades']:>6} "
            f"{r['win_rate']:>7.1%} {r['profit_factor']:>8.2f} "
            f"{r['sharpe_ratio']:>8.2f} {r['max_drawdown_pct']:>7.2f}% "
            f"¥{r['final_capital']:>13,.0f}"
        )
```

- [ ] **Step 5: Smoke-check that main still imports**

```bash
python3 -c "from src import main; print('main importable')"
```

Expected output: `main importable`.

- [ ] **Step 6: Run full suite**

```bash
python3 -m pytest -q
```

Expected: 130+ tests pass (one new test from Step 1 added; everything else unchanged).

- [ ] **Step 7: Commit**

```bash
git add src/main.py tests/test_reports.py
git commit -m "feat(dashboard): export Sharpe/Sortino/MaxDD via ReportGenerator"
```

---

## Self-Review

**Spec coverage:**
- ML特徴量のスケーリング → Task 1 (StandardScaler in Pipeline, convergence test)
- SL/TP外部クローズ監視 → Task 2 (transactions/sinceid + reconcile + cursor advance)
- main.py の WFA 出力 summarize → Task 3
- ダッシュボードに新指標 → Task 4

All four spec items are covered.

**Placeholder scan:** No "TBD", "implement later", or "similar to". Every step has either exact code or exact commands with expected output.

**Type consistency:**
- `MLTrainer.train_with_grid_search` returns `Tuple[Pipeline, Dict[str, Any]]` (Task 1) — matches usage in tests.
- `OandaClient.get_transactions_since(last_transaction_id: str) -> Dict` — caller in `_reconcile_realized_pnl` passes `self.last_transaction_id` (str) and reads `lastTransactionID` (str). Consistent.
- `WalkForwardAnalyzer.summarize` keys printed in Task 3 match what `walker.py:summarize` actually returns: `windows`, `oos_total_trades`, `oos_profit_factor`, `oos_win_rate`, `oos_total_pnl`, `avg_wfa_efficiency`, `param_change_ratio`.
- `ReportGenerator.generate` keys used in Task 4 match `reporter.py`: `total_trades`, `win_rate`, `profit_factor`, `total_pnl`, `max_drawdown_pct`, `max_drawdown_abs`, `sharpe_ratio`, `sortino_ratio`, `avg_holding_hours`.

All identifiers verified against current source.
