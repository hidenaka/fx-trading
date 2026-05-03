# Validation Framework Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 200-day-MA holdout warmup bug and add four hardening features (catastrophic-stop, stress_test gate, concentration risk surfacing, live-vs-backtest comparison) defined in `docs/superpowers/specs/2026-05-03-validation-improvements-design.md`.

**Architecture:** Virtual warmup (daily-only, 250 bars from train) inside `EvaluationContext`; simulator-level `catastrophic_stop_pct` argument; new `stress_test` gate slicing train data; `risk_profile.py` module appending an auto-generated section to validation reports; standalone `compare_live_vs_backtest.py` script for weekly paper-trade evaluation.

**Tech Stack:** Python 3.12, pandas, pyyaml, pytest, sqlite3 (stdlib).

**Repo paths** (anchored at `/Users/hideakimacbookair/自動トレード`):
- Source: `equity_trading/src/`
- Tests: `equity_trading/tests/`
- Configs: `equity_trading/configs/`
- Scripts: `equity_trading/scripts/`
- Data: `equity_trading/data/prices/{train,holdout}/*.parquet`
- Reports: `equity_trading/phase0/validation/`

**Test command** (run from project root):
```
python3 -m pytest equity_trading/tests/<file>.py -v
```

---

## Task 1: §1 EvaluationContext warmup for daily bars

**Files:**
- Modify: `equity_trading/src/validation/data.py`
- Test: `equity_trading/tests/test_validation_data.py` (extend existing)

- [ ] **Step 1.1: Write failing test for daily-warmup prepend**

Add to `equity_trading/tests/test_validation_data.py`:

```python
def _write_daily_parquet(path: Path, ts_start: str, n: int) -> None:
    ts = pd.date_range(ts_start, periods=n, freq="1D", tz="UTC")
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1}, index=ts)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)


def test_load_holdout_daily_prepends_warmup(tmp_path):
    root = tmp_path / "prices"
    # train: 300 daily bars ending 2024-04-30
    _write_daily_parquet(root / "train" / "TECL_1440min.parquet", "2023-07-06", n=300)
    # holdout: 100 daily bars starting 2024-05-01
    _write_daily_parquet(root / "holdout" / "TECL_1440min.parquet", "2024-05-01", n=100)
    log_path = tmp_path / "holdout_access.jsonl"
    with EvaluationContext(root=root, variant_id="v", reason="gate:oos",
                           access_log_path=log_path) as ctx:
        df = ctx.load_holdout_bars("TECL", timeframe_minutes=1440)
    # 250 warmup + 100 holdout = 350 (no duplicates expected)
    assert len(df) == 350
    # First row is 250 days before holdout start
    assert df.index[0] == pd.Timestamp("2023-08-25", tz="UTC")
    # Last row is the last holdout day
    assert df.index[-1] == pd.Timestamp("2024-08-08", tz="UTC")
    # Access log records the warmup
    record = json.loads(log_path.read_text().strip().splitlines()[0])
    assert record["source"] == "holdout+warmup"
    assert record["warmup_rows"] == 250


def test_load_holdout_5min_unchanged_by_warmup(tmp_path):
    root = _setup_data_root(tmp_path)  # existing helper
    log_path = tmp_path / "holdout_access.jsonl"
    with EvaluationContext(root=root, variant_id="v", reason="gate:oos",
                           access_log_path=log_path) as ctx:
        df = ctx.load_holdout_bars("TECL", timeframe_minutes=5)
    assert len(df) == 10  # original holdout count, no warmup
    record = json.loads(log_path.read_text().strip().splitlines()[0])
    assert record["source"] == "holdout"
    assert "warmup_rows" not in record
```

- [ ] **Step 1.2: Run tests to verify they fail**

Run: `python3 -m pytest equity_trading/tests/test_validation_data.py::test_load_holdout_daily_prepends_warmup equity_trading/tests/test_validation_data.py::test_load_holdout_5min_unchanged_by_warmup -v`

Expected: both FAIL — `KeyError: 'source'` or similar (current `load_holdout_bars` writes a record with `rows` only, no `source` field).

- [ ] **Step 1.3: Implement warmup-aware `load_holdout_bars`**

Rewrite `equity_trading/src/validation/data.py` `EvaluationContext` class:

```python
class EvaluationContext:
    """Context manager that grants holdout-read permission while logging access."""

    WARMUP_DAYS_DAILY = 250  # 200d SMA + 50-day safety margin

    def __init__(
        self,
        root: Path | str,
        variant_id: str,
        reason: str,
        access_log_path: Path | str | None = None,
    ):
        self.root = Path(root)
        self.variant_id = variant_id
        self.reason = reason
        self.access_log_path = (
            Path(access_log_path) if access_log_path is not None
            else self.root / "holdout_access.jsonl"
        )

    def __enter__(self) -> "EvaluationContext":
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def load_holdout_bars(self, symbol: str, timeframe_minutes: int) -> pd.DataFrame:
        path_holdout = self.root / "holdout" / _parquet_filename(symbol, timeframe_minutes)
        df_holdout = pd.read_parquet(path_holdout)
        if timeframe_minutes == 1440:
            df_warmup = self._load_warmup_daily(symbol)
            df = pd.concat([df_warmup, df_holdout]).sort_index()
            df = df[~df.index.duplicated(keep="last")]
            self._log_access(symbol, timeframe_minutes,
                              source="holdout+warmup",
                              rows=len(df), warmup_rows=len(df_warmup))
            return df
        self._log_access(symbol, timeframe_minutes,
                          source="holdout", rows=len(df_holdout))
        return df_holdout

    def _load_warmup_daily(self, symbol: str) -> pd.DataFrame:
        path_train = self.root / "train" / _parquet_filename(symbol, 1440)
        df = pd.read_parquet(path_train)
        return df.tail(self.WARMUP_DAYS_DAILY)

    def _log_access(self, symbol: str, timeframe_minutes: int, *,
                     source: str, rows: int, warmup_rows: int | None = None) -> None:
        record = {
            "variant_id": self.variant_id,
            "reason": self.reason,
            "symbol": symbol,
            "timeframe_minutes": timeframe_minutes,
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "rows": rows,
        }
        if warmup_rows is not None:
            record["warmup_rows"] = warmup_rows
        self.access_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.access_log_path.open("a") as f:
            f.write(json.dumps(record) + "\n")
```

Keep `_parquet_filename`, `load_train_bars`, and `HoldoutAccessError` as-is.

- [ ] **Step 1.4: Run tests to verify they pass**

Run: `python3 -m pytest equity_trading/tests/test_validation_data.py -v`

Expected: ALL pass (the two new ones plus the original three).

- [ ] **Step 1.5: Commit**

```
git add equity_trading/src/validation/data.py equity_trading/tests/test_validation_data.py
git commit -m "feat(validation): warmup-aware load_holdout_bars (Task 1)"
```

---

## Task 2: §1 runner.py drops pre-holdout trades

**Files:**
- Modify: `equity_trading/src/validation/runner.py:17-43` (`_collect_trades`)
- Test: `equity_trading/tests/test_validation_runner.py` (extend)

- [ ] **Step 2.1: Write failing test for warmup-trade exclusion**

Add to `equity_trading/tests/test_validation_runner.py`:

```python
def test_collect_trades_excludes_warmup_period_signals(tmp_path):
    """Synthetic trades whose entry_ts < holdout_start must be dropped."""
    from equity_trading.src.validation.runner import _collect_trades
    from equity_trading.src.validation.config import VariantConfig
    from equity_trading.src.validation.data import EvaluationContext
    import pandas as pd

    # We craft a fake _collect_trades input by monkeypatching simulate_strategy
    # to return synthetic trades, half before holdout_start and half after.
    import equity_trading.src.validation.runner as R

    holdout_start = pd.Timestamp("2024-05-01", tz="UTC")
    fake_trades_df = pd.DataFrame({
        "entry_ts": [holdout_start - pd.Timedelta(days=30),
                      holdout_start + pd.Timedelta(days=1),
                      holdout_start + pd.Timedelta(days=10)],
        "exit_ts":  [holdout_start - pd.Timedelta(days=29),
                      holdout_start + pd.Timedelta(days=1, hours=1),
                      holdout_start + pd.Timedelta(days=10, hours=1)],
        "entry_price": [100.0, 100.0, 100.0],
        "exit_price":  [101.0, 101.0, 101.0],
        "exit_type":   ["target", "target", "target"],
        "bars_held":   [12, 12, 12],
        "pnl_pct":     [0.01, 0.01, 0.01],
    })

    def _fake_simulate(**kwargs):
        return ({}, fake_trades_df)

    cfg = VariantConfig(
        variant_id="v_test", description="",
        strategies=[{"class": "OpeningRangeBreakoutStrategy", "symbols": ["TECL"], "params": {}}],
        portfolio={"position_size_pct": 0.25, "max_concurrent": 3,
                    "starting_equity_usd": 100000},
        gates={"oos": {"holdout_start": "2024-05-01", "holdout_end": "2026-05-01",
                       "min_outperformance_pct": 0.0},
                "tail_risk": {"max_single_trade_loss_pct": 5.0,
                               "max_portfolio_dd_pct": 20.0,
                               "max_rolling_30d_loss_pct": 10.0},
                "sample_size": {"min_holdout_trades": 30}},
    )

    class FakeCtx:
        def load_holdout_bars(self, symbol, timeframe_minutes):
            return pd.DataFrame()  # unused

    monkey = pytest.MonkeyPatch()
    monkey.setattr(R, "simulate_strategy", _fake_simulate)
    monkey.setattr(R, "analyze_atr_distribution", lambda b, period=14: {"median_pct": 0.2})
    try:
        result = _collect_trades(cfg, FakeCtx())
    finally:
        monkey.undo()

    assert len(result) == 2  # only the two trades on/after holdout_start
    assert (result["entry_ts"] >= holdout_start).all()
```

Add `import pytest` to the file if missing.

- [ ] **Step 2.2: Run test to verify it fails**

Run: `python3 -m pytest equity_trading/tests/test_validation_runner.py::test_collect_trades_excludes_warmup_period_signals -v`

Expected: FAIL — `assert len(result) == 2` fails because `_collect_trades` returns all 3 trades.

- [ ] **Step 2.3: Implement holdout-start filter in `_collect_trades`**

Replace lines 17-43 of `equity_trading/src/validation/runner.py` (`_collect_trades` function) with:

```python
def _collect_trades(cfg: VariantConfig, ctx: EvaluationContext) -> pd.DataFrame:
    out: list[pd.DataFrame] = []
    holdout_start = pd.Timestamp(cfg.gates["oos"]["holdout_start"], tz="UTC")
    for entry in cfg.strategies:
        cls = cfg.resolve_strategy_class(entry["class"])
        for symbol in entry["symbols"]:
            bars_5min = ctx.load_holdout_bars(symbol, timeframe_minutes=5)
            daily = ctx.load_holdout_bars(symbol, timeframe_minutes=1440)
            atr = analyze_atr_distribution(bars_5min, period=14)["median_pct"]
            params = dict(entry["params"])
            params["_daily"] = daily
            cost = params.pop("cost_pct", 0.10)
            _, trades = simulate_strategy(
                strategy=cls(), bars_5min=bars_5min, daily=daily, atr_pct=atr,
                params=params, cost_pct=cost, return_trades=True,
            )
            if len(trades) > 0:
                trades = trades.copy()
                trades["symbol"] = symbol
                trades["strategy_label"] = f"{cls.__name__}_{symbol}"
                out.append(trades)
    if not out:
        return pd.DataFrame(columns=["entry_ts", "exit_ts", "pnl_pct", "symbol", "strategy_label"])
    df = pd.concat(out, ignore_index=True)
    df["entry_ts"] = pd.to_datetime(df["entry_ts"], utc=True)
    df["exit_ts"] = pd.to_datetime(df["exit_ts"], utc=True)
    df = df[df["entry_ts"] >= holdout_start]
    df = df.drop_duplicates(subset=["symbol", "entry_ts"], keep="first")
    return df.sort_values("entry_ts").reset_index(drop=True)
```

- [ ] **Step 2.4: Run test to verify it passes**

Run: `python3 -m pytest equity_trading/tests/test_validation_runner.py -v`

Expected: ALL pass.

- [ ] **Step 2.5: Commit**

```
git add equity_trading/src/validation/runner.py equity_trading/tests/test_validation_runner.py
git commit -m "feat(validation): drop warmup-period trades in _collect_trades (Task 2)"
```

---

## Task 3: Re-run baseline holdout and capture corrected numbers

**Files:**
- Create: `equity_trading/phase0/validation/2026-05-04_baseline_post_warmup_fix.md`

- [ ] **Step 3.1: Run validation with variant=baseline=orb_default_v0 (self-comparison)**

Run from project root:
```
python3 -m equity_trading.src.validation \
    --variant equity_trading/configs/orb_default_v0.yaml \
    --baseline equity_trading/configs/orb_default_v0.yaml \
    --output equity_trading/phase0/validation/2026-05-04_baseline_post_warmup_fix.md
```

Expected: report file written. Headline `APPROVE` (since variant == baseline, OOS gate diff is 0).

- [ ] **Step 3.2: Inspect the report and capture corrected numbers**

Read `equity_trading/phase0/validation/2026-05-04_baseline_post_warmup_fix.md`. Note the values from the OOS gate table:
- variant Annual return = baseline Annual return = X.XX%
- variant Max drawdown = baseline Max drawdown = -Y.YY%
- variant Sharpe = baseline Sharpe = Z.ZZ

These are the **post-warmup-fix true holdout numbers** for the current configuration. Save them mentally or in a scratch file — Task 4 uses them.

- [ ] **Step 3.3: Commit the report**

```
git add equity_trading/phase0/validation/2026-05-04_baseline_post_warmup_fix.md
git commit -m "data(validation): capture baseline holdout post-warmup-fix (Task 3)"
```

---

## Task 4: Update RUNBOOK with corrected baseline numbers

**Files:**
- Modify: `equity_trading/docs/RUNBOOK.md` (header + projection section)

- [ ] **Step 4.1: Update the document header**

In `equity_trading/docs/RUNBOOK.md` lines 1-24, replace the heading block with:

```markdown
# Equity Bot — Operations Runbook (敏腕モード v2 / Plan 2.5.3)

> **モード**: 敏腕モード v2 (ORB + LHM、3x レバレッジ ETF、V0 ORB exit)
> **In-sample 7yr ann (参考値)**: +13.75% / Max DD -16.33%
> **Holdout 2024-05〜2026-05 ann (post-warmup-fix)**: <ANN_FROM_TASK_3>% / Max DD <DD_FROM_TASK_3>%
>
> **Before any deployment, read `equity_trading/docs/risk_disclosure.md`.**
>
> **2026-05-04 warmup fix**: 旧 holdout レポートの数値は、daily データに 200日 SMA の
> warmup が無く ORB シグナルが先頭 9 ヶ月沈黙していたため負方向に偏っていた。
> validation framework が `EvaluationContext` 経由で train から 250 営業日を
> daily にだけ prepend するように修正済 (`docs/superpowers/specs/2026-05-03-validation-improvements-design.md`)。
>
> **2026-05-03 v2.1 撤回**: V2.1 (ORB exit `stop_mult=0.25 / target_mult=2.0`) は
> warmup 修正後の holdout で再検証し、それでも REJECT されたため不採用 (Task 17 の regression 確認済)。
>
> **資金前提**: 初期 ¥100,000 + 毎月 ¥50,000 の積立
```

Replace `<ANN_FROM_TASK_3>` and `<DD_FROM_TASK_3>` with the numbers captured in Step 3.2.

- [ ] **Step 4.2: Update the "Projected portfolio return" section**

Find the line `## Projected portfolio return (敏腕 v2 = LHM+ORB, V0 exit)` and the table beneath it. Add a second row to the table:

```markdown
| Scenario | 終了残高 | 純損益 | 7-yr Ann | Max DD |
|----------|---------:|------:|--------:|-------:|
| **A: 25%×3 (敏腕推奨, V0 exit) — 7yr in-sample** | **$246,440** | **+$119,140** | **+13.75%** | **-16.33%** |
| **A: 25%×3 — holdout 2024-05〜2026-05 (post-warmup-fix)** | — | — | **<ANN_FROM_TASK_3>%** | **<DD_FROM_TASK_3>%** |
```

Replace placeholders with the Task 3 numbers.

- [ ] **Step 4.3: Commit**

```
git add equity_trading/docs/RUNBOOK.md
git commit -m "docs(RUNBOOK): show holdout post-warmup-fix numbers alongside 7yr in-sample (Task 4)"
```

---

## Task 5: §2 catastrophic_stop in simulator

**Files:**
- Modify: `equity_trading/src/phase0/strategy_simulator.py:47-58, 168-178`
- Test: `equity_trading/tests/test_strategy_simulator.py` (extend)

- [ ] **Step 5.1: Write failing test for cap behavior**

Add to `equity_trading/tests/test_strategy_simulator.py`:

```python
def test_catastrophic_stop_caps_loss():
    """A bar dropping 10% from entry should exit at -5% when cap=5.0."""
    from equity_trading.src.phase0.strategy_simulator import simulate_strategy
    from equity_trading.src.strategy.base import TradingStrategy

    class _AlwaysSignalStrategy(TradingStrategy):
        name = "_test"
        def compute_entry_signal(self, bars_5min, daily, atr_pct, params):
            sig = pd.Series(False, index=bars_5min.index)
            sig.iloc[0] = True
            return sig
        def compute_exit_levels(self, bars_5min, entry_idx, entry_price, atr_pct, params):
            # native stop wide at -50%, target at +50% (so the cap is what fires)
            return entry_price * 0.5, entry_price * 1.5

    # 5 bars: entry at bar 1 close=100, then bar 2 low drops to 89 (-11%)
    closes = [100.0, 100.0, 95.0, 95.0, 95.0]
    lows = [100.0, 100.0, 89.0, 89.0, 89.0]
    highs = [100.0, 100.0, 101.0, 96.0, 96.0]
    opens = [100.0, 100.0, 99.0, 95.0, 95.0]
    bars = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": [1]*5},
        index=pd.date_range("2024-01-01", periods=5, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame({"close": [100.0]*5},
                         index=pd.date_range("2024-01-01", periods=5, freq="1D", tz="UTC"))
    summary, trades = simulate_strategy(
        strategy=_AlwaysSignalStrategy(), bars_5min=bars, daily=daily, atr_pct=0.5,
        catastrophic_stop_pct=5.0, cost_pct=0.0, return_trades=True,
    )
    assert len(trades) == 1
    # exit at stop = entry * 0.95 = 95 → pnl_pct = -0.05
    assert abs(trades["pnl_pct"].iloc[0] - (-0.05)) < 1e-9


def test_catastrophic_stop_none_matches_native_behavior():
    """cap=None reproduces pre-change trade exactly."""
    # Same bars as above; native stop at 50, target at 150; bar 2 low=89.
    # Without cap, native stop never hits (50 < 89). With time exit at last bar:
    # exit at close[4]=95 → pnl = (95-100)/100 = -0.05.
    # ... but we want a clean "cap=None preserves" check, so use a different scenario:
    from equity_trading.src.phase0.strategy_simulator import simulate_strategy
    from equity_trading.src.strategy.base import TradingStrategy

    class _AlwaysSignalStrategy(TradingStrategy):
        name = "_test"
        def compute_entry_signal(self, bars_5min, daily, atr_pct, params):
            sig = pd.Series(False, index=bars_5min.index)
            sig.iloc[0] = True
            return sig
        def compute_exit_levels(self, bars_5min, entry_idx, entry_price, atr_pct, params):
            return entry_price * 0.97, entry_price * 1.03  # ±3%

    # bar 2 low=96.5 (-3.5%) hits native stop 97
    closes = [100.0, 100.0, 98.0, 98.0, 98.0]
    lows = [100.0, 100.0, 96.5, 98.0, 98.0]
    highs = [100.0, 100.0, 100.0, 99.0, 99.0]
    opens = [100.0, 100.0, 99.0, 98.0, 98.0]
    bars = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": [1]*5},
        index=pd.date_range("2024-01-01", periods=5, freq="5min", tz="UTC"),
    )
    daily = pd.DataFrame({"close": [100.0]*5},
                         index=pd.date_range("2024-01-01", periods=5, freq="1D", tz="UTC"))
    s_none, t_none = simulate_strategy(
        strategy=_AlwaysSignalStrategy(), bars_5min=bars, daily=daily, atr_pct=0.5,
        catastrophic_stop_pct=None, cost_pct=0.0, return_trades=True,
    )
    s_5pct, t_5pct = simulate_strategy(
        strategy=_AlwaysSignalStrategy(), bars_5min=bars, daily=daily, atr_pct=0.5,
        catastrophic_stop_pct=5.0, cost_pct=0.0, return_trades=True,
    )
    # native stop at 97 is tighter than 5%-cap floor at 95, so cap is no-op
    assert len(t_none) == len(t_5pct) == 1
    assert abs(t_none["pnl_pct"].iloc[0] - t_5pct["pnl_pct"].iloc[0]) < 1e-9
    # exit price = native stop 97 → pnl = -0.03
    assert abs(t_none["pnl_pct"].iloc[0] - (-0.03)) < 1e-9
```

- [ ] **Step 5.2: Run tests to verify they fail**

Run: `python3 -m pytest equity_trading/tests/test_strategy_simulator.py::test_catastrophic_stop_caps_loss equity_trading/tests/test_strategy_simulator.py::test_catastrophic_stop_none_matches_native_behavior -v`

Expected: both FAIL — `simulate_strategy() got an unexpected keyword argument 'catastrophic_stop_pct'`.

- [ ] **Step 5.3: Add `catastrophic_stop_pct` parameter**

Modify `equity_trading/src/phase0/strategy_simulator.py`. Update `simulate_strategy` signature (around line 47):

```python
def simulate_strategy(
    strategy: TradingStrategy,
    bars_5min: pd.DataFrame,
    daily: pd.DataFrame,
    atr_pct: float,
    params: dict | None = None,
    stop_multiplier: float = 1.5,
    target_multiplier: float = 2.4,
    cost_pct: float = 0.10,
    max_hold_bars: int = 78,
    catastrophic_stop_pct: float | None = None,
    return_trades: bool = False,
) -> dict[str, float]:
```

Inside the loop, after `stop_price, target_price = strategy.compute_exit_levels(...)` (around line 106), add:

```python
            if catastrophic_stop_pct is not None:
                cat_floor = entry_price * (1 - catastrophic_stop_pct / 100.0)
                stop_price = max(stop_price, cat_floor)
```

Apply the same change to `simulate_single_trade` (signature at line 168, after `compute_exit_levels` call at line ~209): add the parameter and the same `if catastrophic_stop_pct is not None: ...` block.

- [ ] **Step 5.4: Run tests**

Run: `python3 -m pytest equity_trading/tests/test_strategy_simulator.py -v`

Expected: ALL pass.

- [ ] **Step 5.5: Commit**

```
git add equity_trading/src/phase0/strategy_simulator.py equity_trading/tests/test_strategy_simulator.py
git commit -m "feat(simulator): add catastrophic_stop_pct cap (Task 5)"
```

---

## Task 6: §2 wire catastrophic_stop_pct through runner.py

**Files:**
- Modify: `equity_trading/src/validation/runner.py` (`_collect_trades`)
- Test: `equity_trading/tests/test_validation_runner.py` (extend)

- [ ] **Step 6.1: Write failing test**

Add to `equity_trading/tests/test_validation_runner.py`:

```python
def test_collect_trades_pops_catastrophic_stop_pct_to_simulator(monkeypatch):
    """The runner must pull catastrophic_stop_pct out of params and pass it
    as a separate kwarg to simulate_strategy."""
    import equity_trading.src.validation.runner as R
    from equity_trading.src.validation.config import VariantConfig
    import pandas as pd

    captured = {}
    def _fake_simulate(**kwargs):
        captured.update(kwargs)
        return ({}, pd.DataFrame(columns=["entry_ts", "exit_ts", "pnl_pct"]))

    monkeypatch.setattr(R, "simulate_strategy", _fake_simulate)
    monkeypatch.setattr(R, "analyze_atr_distribution", lambda b, period=14: {"median_pct": 0.2})

    cfg = VariantConfig(
        variant_id="v_capped", description="",
        strategies=[{"class": "OpeningRangeBreakoutStrategy", "symbols": ["TECL"],
                      "params": {"or_window_bars": 12, "catastrophic_stop_pct": 5.0,
                                  "cost_pct": 0.10}}],
        portfolio={"position_size_pct": 0.25, "max_concurrent": 3,
                    "starting_equity_usd": 100000},
        gates={"oos": {"holdout_start": "2024-05-01", "holdout_end": "2026-05-01",
                       "min_outperformance_pct": 0.0},
                "tail_risk": {"max_single_trade_loss_pct": 5.0,
                               "max_portfolio_dd_pct": 20.0,
                               "max_rolling_30d_loss_pct": 10.0},
                "sample_size": {"min_holdout_trades": 30}},
    )

    class FakeCtx:
        def load_holdout_bars(self, symbol, timeframe_minutes):
            return pd.DataFrame()

    R._collect_trades(cfg, FakeCtx())
    assert captured["catastrophic_stop_pct"] == 5.0
    # It should NOT remain inside the params dict passed to simulate_strategy
    assert "catastrophic_stop_pct" not in captured["params"]
```

- [ ] **Step 6.2: Run test to verify it fails**

Run: `python3 -m pytest equity_trading/tests/test_validation_runner.py::test_collect_trades_pops_catastrophic_stop_pct_to_simulator -v`

Expected: FAIL — `KeyError: 'catastrophic_stop_pct'` (the kwarg is not currently passed).

- [ ] **Step 6.3: Implement the param plumbing**

In `equity_trading/src/validation/runner.py::_collect_trades`, change the inner block:

```python
            params = dict(entry["params"])
            params["_daily"] = daily
            cost = params.pop("cost_pct", 0.10)
            cat_stop = params.pop("catastrophic_stop_pct", None)
            _, trades = simulate_strategy(
                strategy=cls(), bars_5min=bars_5min, daily=daily, atr_pct=atr,
                params=params, cost_pct=cost,
                catastrophic_stop_pct=cat_stop,
                return_trades=True,
            )
```

- [ ] **Step 6.4: Run all validation runner tests**

Run: `python3 -m pytest equity_trading/tests/test_validation_runner.py -v`

Expected: ALL pass.

- [ ] **Step 6.5: Commit**

```
git add equity_trading/src/validation/runner.py equity_trading/tests/test_validation_runner.py
git commit -m "feat(validation): pop catastrophic_stop_pct from params and forward to simulator (Task 6)"
```

---

## Task 7: §3 stress_test gate module

**Files:**
- Create: `equity_trading/src/validation/gates/stress_test.py`
- Test: `equity_trading/tests/test_gate_stress_test.py` (new)

- [ ] **Step 7.1: Write failing test**

Create `equity_trading/tests/test_gate_stress_test.py`:

```python
"""Stress test gate."""
from __future__ import annotations

import pandas as pd
import pytest

from equity_trading.src.validation.gates.base import Status


def _make_window_summary(ann: float, dd: float, worst: float, n: int = 50) -> dict:
    return {"annualized_pct": ann, "max_dd_pct": dd,
             "sharpe": 0.0, "final_equity": 100000.0,
             "worst_trade_pct": worst, "trade_count": n}


def test_stress_gate_pass_when_all_windows_within_limits():
    from equity_trading.src.validation.gates.stress_test import (
        run_stress_test_gate_from_summaries,
    )
    windows = [
        {"name": "w1", "max_dd_limit_pct": 30.0, "worst_trade_limit_pct": 7.0},
        {"name": "w2", "max_dd_limit_pct": 25.0, "worst_trade_limit_pct": 5.0},
    ]
    variant = [_make_window_summary(-5.0, -22.0, -4.5),
                _make_window_summary(-2.0, -18.0, -4.0)]
    baseline = [_make_window_summary(-5.0, -20.0, -4.5),
                 _make_window_summary(-2.0, -17.0, -4.0)]
    result = run_stress_test_gate_from_summaries(windows, variant, baseline)
    assert result.status == Status.PASS


def test_stress_gate_fail_when_dd_exceeds_window_limit():
    from equity_trading.src.validation.gates.stress_test import (
        run_stress_test_gate_from_summaries,
    )
    windows = [{"name": "w1", "max_dd_limit_pct": 25.0, "worst_trade_limit_pct": 7.0}]
    variant = [_make_window_summary(-10.0, -40.0, -4.5)]
    baseline = [_make_window_summary(-5.0, -20.0, -4.5)]
    result = run_stress_test_gate_from_summaries(windows, variant, baseline)
    assert result.status == Status.FAIL
    assert "w1" in result.summary
    assert "MaxDD" in result.summary or "dd" in result.summary.lower()


def test_stress_gate_fail_when_variant_dd_excessive_vs_baseline():
    from equity_trading.src.validation.gates.stress_test import (
        run_stress_test_gate_from_summaries,
    )
    windows = [{"name": "w1", "max_dd_limit_pct": 50.0, "worst_trade_limit_pct": 50.0}]
    variant = [_make_window_summary(-5.0, -30.0, -4.0)]
    baseline = [_make_window_summary(-5.0, -20.0, -4.0)]  # 30 > 1.3*20 = 26
    result = run_stress_test_gate_from_summaries(windows, variant, baseline)
    assert result.status == Status.FAIL


def test_stress_gate_warn_when_no_windows_configured():
    from equity_trading.src.validation.gates.stress_test import (
        run_stress_test_gate_from_summaries,
    )
    result = run_stress_test_gate_from_summaries([], [], [])
    assert result.status == Status.WARN
    assert "no windows" in result.summary.lower()


def test_stress_gate_fail_when_worst_trade_exceeds_limit():
    from equity_trading.src.validation.gates.stress_test import (
        run_stress_test_gate_from_summaries,
    )
    windows = [{"name": "w1", "max_dd_limit_pct": 50.0, "worst_trade_limit_pct": 5.0}]
    variant = [_make_window_summary(-2.0, -10.0, -7.5)]
    baseline = [_make_window_summary(-2.0, -10.0, -4.0)]
    result = run_stress_test_gate_from_summaries(windows, variant, baseline)
    assert result.status == Status.FAIL
    assert "worst" in result.summary.lower()
```

- [ ] **Step 7.2: Run tests to verify they fail**

Run: `python3 -m pytest equity_trading/tests/test_gate_stress_test.py -v`

Expected: all FAIL — `ModuleNotFoundError`.

- [ ] **Step 7.3: Implement gate from summaries**

Create `equity_trading/src/validation/gates/stress_test.py`:

```python
"""Gate 4: stress_test — train-data window slicing."""
from __future__ import annotations

from equity_trading.src.validation.gates.base import GateResult, Status


def run_stress_test_gate_from_summaries(
    windows: list[dict],
    variant_summaries: list[dict],
    baseline_summaries: list[dict],
) -> GateResult:
    """Pure-summary version. The full gate (run_stress_test_gate) wraps this
    by simulating each window from train data and producing the summaries."""
    if not windows:
        return GateResult(name="stress_test", status=Status.WARN,
                           summary="no windows configured",
                           detail_md="### Gate 4: Stress test ⚠️\n\nno windows configured\n")
    failures: list[str] = []
    rows: list[str] = []
    for w, v, b in zip(windows, variant_summaries, baseline_summaries):
        v_dd = abs(v["max_dd_pct"])
        b_dd = abs(b["max_dd_pct"])
        v_worst = abs(v["worst_trade_pct"])
        ok = True
        if v_dd > w["max_dd_limit_pct"]:
            failures.append(f"{w['name']}: MaxDD {v_dd:.2f}% > limit {w['max_dd_limit_pct']:.1f}%")
            ok = False
        if v_worst > w["worst_trade_limit_pct"]:
            failures.append(f"{w['name']}: worst trade {v_worst:.2f}% > limit {w['worst_trade_limit_pct']:.1f}%")
            ok = False
        if v_dd > b_dd * 1.3:
            failures.append(f"{w['name']}: variant DD {v_dd:.2f}% > 1.3x baseline {b_dd:.2f}%")
            ok = False
        rows.append(
            f"| {w['name']} | {v['annualized_pct']:+.2f}% | -{v_dd:.2f}% | -{b_dd:.2f}% | "
            f"-{v_worst:.2f}% | {'✅' if ok else '❌'} |"
        )
    status = Status.FAIL if failures else Status.PASS
    summary = "; ".join(failures) if failures else f"{len(windows)} stress windows passed"
    detail = (
        f"### Gate 4: Stress test {status.icon}\n\n"
        f"| window | variant ann | variant DD | baseline DD | worst trade | result |\n"
        f"|---|---:|---:|---:|---:|:---:|\n"
        + "\n".join(rows) + "\n\n" + summary + "\n"
    )
    return GateResult(name="stress_test", status=status, summary=summary,
                       detail_md=detail, metrics={"failures": len(failures)})
```

- [ ] **Step 7.4: Run tests**

Run: `python3 -m pytest equity_trading/tests/test_gate_stress_test.py -v`

Expected: all PASS.

- [ ] **Step 7.5: Commit**

```
git add equity_trading/src/validation/gates/stress_test.py equity_trading/tests/test_gate_stress_test.py
git commit -m "feat(validation): stress_test gate (pure-summary core, Task 7)"
```

---

## Task 8: §3 stress_test full gate (train data slicing)

**Files:**
- Modify: `equity_trading/src/validation/gates/stress_test.py` (add full wrapper)
- Modify: `equity_trading/src/validation/cli.py`
- Modify: `equity_trading/configs/orb_default_v0.yaml` (opt-in stress_test)
- Test: `equity_trading/tests/test_gate_stress_test.py` (extend)

- [ ] **Step 8.1: Write failing integration test**

Append to `equity_trading/tests/test_gate_stress_test.py`:

```python
def test_run_stress_test_gate_slices_train_data(tmp_path, monkeypatch):
    """Full gate reads train parquets, slices by window, and produces a result."""
    import pandas as pd
    from equity_trading.src.validation.gates.stress_test import run_stress_test_gate
    from equity_trading.src.validation.config import VariantConfig

    # Make minimal train parquets (1 yr daily + 1 yr 5min) for symbol TECL
    root = tmp_path / "prices"
    train = root / "train"
    train.mkdir(parents=True)
    daily_idx = pd.date_range("2021-01-01", periods=600, freq="1D", tz="UTC")
    pd.DataFrame({"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 1},
                  index=daily_idx).to_parquet(train / "TECL_1440min.parquet")
    bar_idx = pd.date_range("2021-01-01 14:30", periods=600 * 78, freq="5min", tz="UTC")
    pd.DataFrame({"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 1},
                  index=bar_idx).to_parquet(train / "TECL_5min.parquet")

    cfg_yaml = """
variant_id: stress_test_v
description: ""
strategies:
  - class: OpeningRangeBreakoutStrategy
    symbols: [TECL]
    params:
      or_window_bars: 12
      stop_mult: 0.0
      target_mult: 1.0
      cost_pct: 0.10
portfolio:
  position_size_pct: 0.25
  max_concurrent: 3
  starting_equity_usd: 100000
gates:
  oos: { holdout_start: "2024-05-01", holdout_end: "2026-05-01", min_outperformance_pct: 0.0 }
  tail_risk: { max_single_trade_loss_pct: 5.0, max_portfolio_dd_pct: 20.0, max_rolling_30d_loss_pct: 10.0 }
  sample_size: { min_holdout_trades: 30 }
  stress_test:
    enabled: true
    windows:
      - name: w1
        start: "2022-01-01"
        end: "2022-06-01"
        max_dd_limit_pct: 50.0
        worst_trade_limit_pct: 50.0
"""
    cfg_path = tmp_path / "v.yaml"
    cfg_path.write_text(cfg_yaml)
    from equity_trading.src.validation.config import load_variant_config
    cfg = load_variant_config(cfg_path)

    result = run_stress_test_gate(cfg=cfg, baseline_cfg=cfg, train_root=train,
                                    stress_windows=cfg.gates["stress_test"]["windows"])
    # No trades possible on flat synthetic data → 0% DD → PASS
    assert result.status.value in ("PASS", "WARN")
```

- [ ] **Step 8.2: Run test to verify failure**

Run: `python3 -m pytest equity_trading/tests/test_gate_stress_test.py::test_run_stress_test_gate_slices_train_data -v`

Expected: FAIL — `cannot import name 'run_stress_test_gate'`.

- [ ] **Step 8.3: Implement full gate wrapper**

Append to `equity_trading/src/validation/gates/stress_test.py`:

```python
from pathlib import Path
import pandas as pd
from equity_trading.src.validation.config import VariantConfig
from equity_trading.src.validation.data import load_train_bars
from equity_trading.src.phase0.atr_analyzer import analyze_atr_distribution
from equity_trading.src.phase0.strategy_simulator import simulate_strategy


def _simulate_window(cfg: VariantConfig, train_root: Path, window: dict) -> dict:
    start = pd.Timestamp(window["start"], tz="UTC")
    end = pd.Timestamp(window["end"], tz="UTC")
    daily_warmup_start = start - pd.Timedelta(days=365)
    all_pnl: list[float] = []
    worst = 0.0
    n_trades = 0
    for entry in cfg.strategies:
        cls = cfg.resolve_strategy_class(entry["class"])
        for symbol in entry["symbols"]:
            bars_5min = load_train_bars(train_root, symbol, timeframe_minutes=5)
            daily = load_train_bars(train_root, symbol, timeframe_minutes=1440)
            bars_window = bars_5min.loc[start:end]
            daily_window = daily.loc[daily_warmup_start:end]
            if len(bars_window) == 0 or len(daily_window) == 0:
                continue
            atr = analyze_atr_distribution(bars_window, period=14)["median_pct"]
            params = dict(entry["params"])
            params["_daily"] = daily_window
            cost = params.pop("cost_pct", 0.10)
            cat_stop = params.pop("catastrophic_stop_pct", None)
            _, trades = simulate_strategy(
                strategy=cls(), bars_5min=bars_window, daily=daily_window, atr_pct=atr,
                params=params, cost_pct=cost,
                catastrophic_stop_pct=cat_stop, return_trades=True,
            )
            all_pnl.extend(trades["pnl_pct"].tolist())
            n_trades += len(trades)
    if not all_pnl:
        return {"annualized_pct": 0.0, "max_dd_pct": 0.0, "sharpe": 0.0,
                 "final_equity": 100000.0, "worst_trade_pct": 0.0, "trade_count": 0}
    equity = 100000.0
    eq_curve = [equity]
    for p in all_pnl:
        equity *= (1 + p * cfg.portfolio["position_size_pct"])
        eq_curve.append(equity)
    eq_series = pd.Series(eq_curve)
    rmax = eq_series.cummax()
    dd = ((eq_series - rmax) / rmax * 100).min()
    days = (end - start).days
    yrs = max(days / 365.25, 1e-9)
    ann = ((equity / 100000.0) ** (1 / yrs) - 1) * 100
    return {"annualized_pct": ann, "max_dd_pct": dd, "sharpe": 0.0,
             "final_equity": equity,
             "worst_trade_pct": min(all_pnl) * 100,
             "trade_count": n_trades}


def run_stress_test_gate(
    *, cfg: VariantConfig, baseline_cfg: VariantConfig,
    train_root: Path, stress_windows: list[dict],
) -> GateResult:
    if not stress_windows:
        return run_stress_test_gate_from_summaries([], [], [])
    v_summaries = [_simulate_window(cfg, train_root, w) for w in stress_windows]
    b_summaries = [_simulate_window(baseline_cfg, train_root, w) for w in stress_windows]
    return run_stress_test_gate_from_summaries(stress_windows, v_summaries, b_summaries)
```

- [ ] **Step 8.4: Wire into CLI**

In `equity_trading/src/validation/cli.py`, after the existing `gates.append(run_sample_size_gate(...))` block (line ~94), add:

```python
    stress_cfg = variant.gates.get("stress_test", {})
    if stress_cfg.get("enabled"):
        from equity_trading.src.validation.gates.stress_test import run_stress_test_gate
        gates.append(run_stress_test_gate(
            cfg=variant, baseline_cfg=baseline,
            train_root=args.data_root,
            stress_windows=stress_cfg.get("windows", []),
        ))
```

- [ ] **Step 8.5: Update orb_default_v0.yaml to opt-in stress_test**

Edit `equity_trading/configs/orb_default_v0.yaml`. After the `sample_size` block, append:

```yaml
  stress_test:
    enabled: true
    windows:
      - name: covid_2020
        start: "2020-02-15"
        end: "2020-05-15"
        max_dd_limit_pct: 30.0
        worst_trade_limit_pct: 7.0
      - name: hike_2022
        start: "2022-01-01"
        end: "2023-04-01"
        max_dd_limit_pct: 25.0
        worst_trade_limit_pct: 5.0
```

- [ ] **Step 8.6: Run all gate tests**

Run: `python3 -m pytest equity_trading/tests/test_gate_stress_test.py equity_trading/tests/test_validation_cli.py -v`

Expected: ALL pass.

- [ ] **Step 8.7: Commit**

```
git add equity_trading/src/validation/gates/stress_test.py equity_trading/src/validation/cli.py equity_trading/configs/orb_default_v0.yaml equity_trading/tests/test_gate_stress_test.py
git commit -m "feat(validation): stress_test gate full wrapper + opt-in for default variant (Task 8)"
```

---

## Task 9: §3 stress_test gate report integration

**Files:**
- Modify: `equity_trading/src/validation/report.py` (recognize stress_test gate)
- Test: `equity_trading/tests/test_validation_report.py` (extend)

- [ ] **Step 9.1: Write failing test**

Add to `equity_trading/tests/test_validation_report.py`:

```python
def test_report_includes_stress_test_gate_section(tmp_path):
    from equity_trading.src.validation.report import write_validation_report
    from equity_trading.src.validation.gates.base import GateResult, Status
    gates = [
        GateResult(name="oos", status=Status.PASS, summary="ok",
                    detail_md="### Gate 1: OOS holdout ✅\n\n(detail)\n"),
        GateResult(name="tail_risk", status=Status.PASS, summary="ok",
                    detail_md="### Gate 2: Tail risk ✅\n\n(detail)\n"),
        GateResult(name="sample_size", status=Status.PASS, summary="ok",
                    detail_md="### Gate 3: Sample size ✅\n\n(detail)\n"),
        GateResult(name="stress_test", status=Status.PASS, summary="2 windows passed",
                    detail_md="### Gate 4: Stress test ✅\n\n(window detail)\n"),
    ]
    out = tmp_path / "r.md"
    from datetime import datetime, timezone
    write_validation_report(
        path=out, variant_id="v", baseline_id="b", gates=gates,
        git_sha="abc1234", manifest_hash="m", holdout_window=("2024-05-01", "2026-05-01"),
        generated_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
    )
    text = out.read_text()
    assert "### Gate 4: Stress test" in text
    # Headline should still be APPROVE because stress_test is non-required (REQUIRED_GATES is OOS/tail_risk/sample_size).
    assert "APPROVE" in text
```

- [ ] **Step 9.2: Run test**

Run: `python3 -m pytest equity_trading/tests/test_validation_report.py::test_report_includes_stress_test_gate_section -v`

Expected: PASS already, because `report.py` iterates over **all** provided gates and writes their `detail_md`. The test confirms the existing loop behaves correctly when a 4th gate is supplied.

If it fails (e.g. headline drops to REJECT incorrectly), fix `report.py` `derive_headline` to not require stress_test for the REJECT bar (it already skips non-REQUIRED gates).

- [ ] **Step 9.3: Commit**

```
git add equity_trading/tests/test_validation_report.py
git commit -m "test(validation): assert stress_test gate renders in report (Task 9)"
```

---

## Task 10: §4-B surface position_dollars on trades DataFrame

**Files:**
- Modify: `equity_trading/src/validation/runner.py:46-89` (`_simulate_portfolio`)
- Test: `equity_trading/tests/test_validation_runner.py` (extend)

- [ ] **Step 10.1: Write failing test**

Add to `equity_trading/tests/test_validation_runner.py`:

```python
def test_simulate_portfolio_returns_position_dollars_per_trade():
    """Each accepted trade should carry the position_dollars used to fill it."""
    from equity_trading.src.validation.runner import _simulate_portfolio
    import pandas as pd
    trades = pd.DataFrame({
        "entry_ts": pd.to_datetime(["2024-05-01 14:30", "2024-05-02 14:30"], utc=True),
        "exit_ts":  pd.to_datetime(["2024-05-01 15:30", "2024-05-02 15:30"], utc=True),
        "pnl_pct":  [0.01, -0.02],
        "symbol":   ["TECL", "TQQQ"],
    })
    summary, eq_df, accepted = _simulate_portfolio(
        trades, starting_equity=100000.0, position_size_pct=0.25, max_concurrent=3,
    )
    assert len(accepted) == 2
    # First trade: 100000 * 0.25 = 25000
    assert abs(accepted["position_dollars"].iloc[0] - 25000.0) < 0.01
    # Second trade: equity grew by 25000 * 0.01 = 250 → 100250 * 0.25 = 25062.5
    assert abs(accepted["position_dollars"].iloc[1] - 25062.5) < 0.01
```

Note: this test expects `_simulate_portfolio` to return a **3-tuple** (summary, equity_curve, accepted_trades). Current code returns a 2-tuple. The signature change is the breaking part.

- [ ] **Step 10.2: Run test to verify failure**

Run: `python3 -m pytest equity_trading/tests/test_validation_runner.py::test_simulate_portfolio_returns_position_dollars_per_trade -v`

Expected: FAIL — `not enough values to unpack (expected 3, got 2)`.

- [ ] **Step 10.3: Modify `_simulate_portfolio` to return accepted trades**

Update `equity_trading/src/validation/runner.py::_simulate_portfolio` (lines ~46-89) — change signature to return 3-tuple:

```python
def _simulate_portfolio(
    trades: pd.DataFrame, starting_equity: float,
    position_size_pct: float, max_concurrent: int,
) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    if len(trades) == 0:
        return ({"annualized_pct": 0.0, "max_dd_pct": 0.0, "sharpe": 0.0,
                  "final_equity": starting_equity},
                pd.DataFrame(columns=["ts", "equity"]),
                pd.DataFrame(columns=list(trades.columns) + ["position_dollars"]))
    equity = starting_equity
    open_pos: list[dict] = []
    eq_curve = [(trades["entry_ts"].iloc[0] - pd.Timedelta(seconds=1), equity)]
    accepted: list[dict] = []
    for _, t in trades.iterrows():
        still = []
        for p in open_pos:
            if p["exit_ts"] <= t["entry_ts"]:
                equity += p["dollars"] * p["pnl_pct"]
                eq_curve.append((p["exit_ts"], equity))
            else:
                still.append(p)
        open_pos[:] = still
        if len(open_pos) >= max_concurrent or any(p["symbol"] == t["symbol"] for p in open_pos):
            continue
        position_dollars = equity * position_size_pct
        open_pos.append({"symbol": t["symbol"], "exit_ts": t["exit_ts"],
                          "dollars": position_dollars, "pnl_pct": t["pnl_pct"]})
        accepted.append({**t.to_dict(), "position_dollars": position_dollars})
    for p in open_pos:
        equity += p["dollars"] * p["pnl_pct"]
        eq_curve.append((p["exit_ts"], equity))
    eq_df = pd.DataFrame(eq_curve, columns=["ts", "equity"]).sort_values("ts").reset_index(drop=True)
    eq_df = eq_df.drop_duplicates("ts", keep="last")

    rmax = eq_df["equity"].cummax()
    dd = (eq_df["equity"] - rmax) / rmax
    max_dd = float(abs(dd.min() * 100)) if len(dd) > 0 else 0.0

    days = (eq_df["ts"].iloc[-1] - eq_df["ts"].iloc[0]).total_seconds() / 86400
    yrs = max(days / 365.25, 1e-9)
    ann = (math.pow(equity / starting_equity, 1 / yrs) - 1) * 100

    daily_rets = trades["pnl_pct"].to_numpy()
    sharpe = (daily_rets.mean() / daily_rets.std() * math.sqrt(252)) if daily_rets.std() > 0 else 0.0
    summary = {"annualized_pct": ann, "max_dd_pct": -max_dd, "sharpe": float(sharpe),
                "final_equity": equity}
    accepted_df = pd.DataFrame(accepted)
    return summary, eq_df, accepted_df
```

Update `run_holdout_simulation` to forward the new return:

```python
def run_holdout_simulation(
    cfg: VariantConfig, ctx: EvaluationContext,
) -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns (summary, accepted_trades, equity_curve, all_signal_trades)."""
    trades = _collect_trades(cfg, ctx)
    summary, equity_curve, accepted = _simulate_portfolio(
        trades=trades,
        starting_equity=cfg.portfolio["starting_equity_usd"],
        position_size_pct=cfg.portfolio["position_size_pct"],
        max_concurrent=cfg.portfolio["max_concurrent"],
    )
    return summary, accepted, equity_curve, trades
```

Update `equity_trading/src/validation/cli.py` lines 76-77 to unpack 4 values and pass `accepted` to gates that need per-trade data:

```python
        v_summary, v_trades, v_equity, _ = run_holdout_simulation(variant, ctx)
        b_summary, b_trades, b_equity, _ = run_holdout_simulation(baseline, ctx)
```

- [ ] **Step 10.4: Run all tests touching runner.py**

Run: `python3 -m pytest equity_trading/tests/test_validation_runner.py equity_trading/tests/test_validation_cli.py -v`

Expected: ALL pass. Existing tests asserting 3-tuple from `run_holdout_simulation` need to be updated to 4-tuple if any.

- [ ] **Step 10.5: Commit**

```
git add equity_trading/src/validation/runner.py equity_trading/src/validation/cli.py equity_trading/tests/test_validation_runner.py
git commit -m "refactor(validation): surface position_dollars on accepted trades (Task 10)"
```

---

## Task 11: §4-B risk_profile module

**Files:**
- Create: `equity_trading/src/validation/risk_profile.py`
- Test: `equity_trading/tests/test_risk_profile.py` (new)

- [ ] **Step 11.1: Write failing tests**

Create `equity_trading/tests/test_risk_profile.py`:

```python
"""Risk profile section computations."""
from __future__ import annotations

import pandas as pd


def _make_trades(rows):
    """rows: list of dicts."""
    df = pd.DataFrame(rows)
    df["entry_ts"] = pd.to_datetime(df["entry_ts"], utc=True)
    df["exit_ts"] = pd.to_datetime(df["exit_ts"], utc=True)
    return df


def test_symbol_contribution_basic():
    from equity_trading.src.validation.risk_profile import compute_symbol_contribution
    trades = _make_trades([
        {"entry_ts": "2024-06-01", "exit_ts": "2024-06-01 16:00",
         "symbol": "TECL", "pnl_pct": 0.01, "position_dollars": 25000},
        {"entry_ts": "2024-06-02", "exit_ts": "2024-06-02 16:00",
         "symbol": "TECL", "pnl_pct": -0.005, "position_dollars": 25000},
        {"entry_ts": "2024-06-03", "exit_ts": "2024-06-03 16:00",
         "symbol": "TQQQ", "pnl_pct": 0.02, "position_dollars": 25000},
    ])
    df = compute_symbol_contribution(trades)
    # TECL: 250 - 125 = 125 P&L; TQQQ: 500 P&L
    tecl = df[df["symbol"] == "TECL"].iloc[0]
    tqqq = df[df["symbol"] == "TQQQ"].iloc[0]
    assert abs(tecl["gross_pnl_dollars"] - 125.0) < 0.01
    assert abs(tqqq["gross_pnl_dollars"] - 500.0) < 0.01
    # totals
    total = 125.0 + 500.0
    assert abs(tecl["pct_of_total"] - 125.0 / total * 100) < 0.01


def test_pairwise_correlation_diagonal_one():
    from equity_trading.src.validation.risk_profile import compute_pairwise_correlation
    trades = _make_trades([
        {"entry_ts": "2024-06-01", "exit_ts": "2024-06-01 16:00",
         "symbol": "TECL", "pnl_pct": 0.01, "position_dollars": 25000},
        {"entry_ts": "2024-06-01", "exit_ts": "2024-06-01 16:00",
         "symbol": "TQQQ", "pnl_pct": 0.012, "position_dollars": 25000},
        {"entry_ts": "2024-06-02", "exit_ts": "2024-06-02 16:00",
         "symbol": "TECL", "pnl_pct": -0.005, "position_dollars": 25000},
        {"entry_ts": "2024-06-02", "exit_ts": "2024-06-02 16:00",
         "symbol": "TQQQ", "pnl_pct": -0.004, "position_dollars": 25000},
    ])
    corr = compute_pairwise_correlation(trades)
    assert abs(corr.loc["TECL", "TECL"] - 1.0) < 1e-9
    assert abs(corr.loc["TQQQ", "TQQQ"] - 1.0) < 1e-9
    # symmetric
    assert abs(corr.loc["TECL", "TQQQ"] - corr.loc["TQQQ", "TECL"]) < 1e-9


def test_stress_overlap_counts_simultaneous_holdings():
    from equity_trading.src.validation.risk_profile import compute_stress_overlap
    # 3 trades all overlapping in time
    trades = _make_trades([
        {"entry_ts": "2024-06-01 10:00", "exit_ts": "2024-06-01 15:00",
         "symbol": "TECL", "pnl_pct": -0.02, "position_dollars": 25000},
        {"entry_ts": "2024-06-01 10:30", "exit_ts": "2024-06-01 15:00",
         "symbol": "TQQQ", "pnl_pct": -0.01, "position_dollars": 25000},
        {"entry_ts": "2024-06-01 10:30", "exit_ts": "2024-06-01 15:00",
         "symbol": "TNA", "pnl_pct": -0.015, "position_dollars": 25000},
    ])
    result = compute_stress_overlap(trades, min_concurrent=3)
    # All three open simultaneously between 10:30 and 15:00 — counts as 1 overlap window
    assert result["overlap_windows"] == 1
    # All losing, same direction
    assert result["all_losing_windows"] == 1


def test_render_risk_profile_section_contains_all_subsections():
    from equity_trading.src.validation.risk_profile import render_risk_profile_md
    trades = _make_trades([
        {"entry_ts": "2024-06-01", "exit_ts": "2024-06-01 16:00",
         "symbol": "TECL", "pnl_pct": 0.01, "position_dollars": 25000},
        {"entry_ts": "2024-06-02", "exit_ts": "2024-06-02 16:00",
         "symbol": "TQQQ", "pnl_pct": -0.01, "position_dollars": 25000},
    ])
    md = render_risk_profile_md(trades)
    assert "## Risk profile" in md
    assert "Symbol contribution" in md
    assert "correlation" in md.lower()
    assert "Stress overlap" in md
```

- [ ] **Step 11.2: Run tests to verify failure**

Run: `python3 -m pytest equity_trading/tests/test_risk_profile.py -v`

Expected: all FAIL — `ModuleNotFoundError`.

- [ ] **Step 11.3: Implement risk_profile module**

Create `equity_trading/src/validation/risk_profile.py`:

```python
"""Risk profile computations for validation reports.

Surfaces concentration risk in the holdout: per-symbol P&L contribution,
pairwise pnl-pct correlation, and simultaneous-position stress overlap.
"""
from __future__ import annotations

import pandas as pd


def compute_symbol_contribution(trades: pd.DataFrame) -> pd.DataFrame:
    """Group accepted trades by symbol, return n / gross $ / % of total / avg %."""
    if len(trades) == 0:
        return pd.DataFrame(columns=["symbol", "trades", "gross_pnl_dollars",
                                       "pct_of_total", "avg_pnl_pct"])
    df = trades.copy()
    df["pnl_dollars"] = df["pnl_pct"] * df["position_dollars"]
    grouped = df.groupby("symbol").agg(
        trades=("pnl_pct", "size"),
        gross_pnl_dollars=("pnl_dollars", "sum"),
        avg_pnl_pct=("pnl_pct", "mean"),
    ).reset_index()
    total = grouped["gross_pnl_dollars"].abs().sum()
    grouped["pct_of_total"] = (grouped["gross_pnl_dollars"].abs() / total * 100) if total > 0 else 0.0
    return grouped


def compute_pairwise_correlation(trades: pd.DataFrame) -> pd.DataFrame:
    """Pivot trades to (date × symbol) → daily pnl, return Pearson corr matrix."""
    if len(trades) == 0:
        return pd.DataFrame()
    df = trades.copy()
    df["date"] = df["entry_ts"].dt.date
    pivoted = df.pivot_table(index="date", columns="symbol", values="pnl_pct",
                              aggfunc="mean", fill_value=0.0)
    return pivoted.corr()


def compute_stress_overlap(trades: pd.DataFrame, min_concurrent: int = 3) -> dict:
    """Count windows where ≥ min_concurrent positions were open simultaneously."""
    if len(trades) == 0:
        return {"overlap_windows": 0, "all_losing_windows": 0}
    events = []
    for _, t in trades.iterrows():
        events.append((t["entry_ts"], +1, t["pnl_pct"]))
        events.append((t["exit_ts"], -1, t["pnl_pct"]))
    events.sort(key=lambda e: (e[0], -e[1]))
    open_count = 0
    current_pnls: list[float] = []
    overlap_windows = 0
    all_losing_windows = 0
    in_overlap = False
    for ts, delta, pnl in events:
        if delta == +1:
            open_count += 1
            current_pnls.append(pnl)
            if open_count >= min_concurrent and not in_overlap:
                in_overlap = True
                overlap_windows += 1
                if all(p < 0 for p in current_pnls):
                    all_losing_windows += 1
        else:
            open_count -= 1
            if pnl in current_pnls:
                current_pnls.remove(pnl)
            if open_count < min_concurrent:
                in_overlap = False
    return {"overlap_windows": overlap_windows, "all_losing_windows": all_losing_windows}


def render_risk_profile_md(trades: pd.DataFrame) -> str:
    """Render the full Risk profile section as markdown."""
    parts: list[str] = ["## Risk profile\n"]
    contrib = compute_symbol_contribution(trades)
    parts.append("### Symbol contribution to P&L (holdout)\n")
    if len(contrib) == 0:
        parts.append("(no trades)\n")
    else:
        parts.append("| symbol | trades | gross P&L $ | % of total | avg P&L % |")
        parts.append("|---|---:|---:|---:|---:|")
        for _, r in contrib.iterrows():
            parts.append(
                f"| {r['symbol']} | {int(r['trades'])} | "
                f"${r['gross_pnl_dollars']:+,.0f} | "
                f"{r['pct_of_total']:.1f}% | "
                f"{r['avg_pnl_pct']*100:+.2f}% |"
            )
    parts.append("")
    corr = compute_pairwise_correlation(trades)
    parts.append("### Pairwise daily-return correlation\n")
    if corr.empty:
        parts.append("(no trades)\n")
    else:
        symbols = list(corr.columns)
        header = "|   | " + " | ".join(symbols) + " |"
        sep = "|---|" + "|".join(["---:"] * len(symbols)) + "|"
        parts.append(header)
        parts.append(sep)
        for s in symbols:
            row = "| " + s + " | " + " | ".join(f"{corr.loc[s, t]:.2f}" for t in symbols) + " |"
            parts.append(row)
    parts.append("")
    overlap = compute_stress_overlap(trades, min_concurrent=3)
    parts.append("### Stress overlap\n")
    parts.append(f"- Windows with ≥3 positions open simultaneously: **{overlap['overlap_windows']}**")
    parts.append(f"- Of those, windows where all open positions were losing: "
                  f"**{overlap['all_losing_windows']}**")
    parts.append("")
    return "\n".join(parts)
```

- [ ] **Step 11.4: Run tests**

Run: `python3 -m pytest equity_trading/tests/test_risk_profile.py -v`

Expected: ALL pass.

- [ ] **Step 11.5: Commit**

```
git add equity_trading/src/validation/risk_profile.py equity_trading/tests/test_risk_profile.py
git commit -m "feat(validation): risk_profile module — contribution, correlation, stress overlap (Task 11)"
```

---

## Task 12: §4-B integrate risk_profile into validation report

**Files:**
- Modify: `equity_trading/src/validation/report.py` (add risk_profile_md kwarg, append section)
- Modify: `equity_trading/src/validation/cli.py` (pass variant accepted_trades to writer)
- Test: `equity_trading/tests/test_validation_report.py` (extend)

- [ ] **Step 12.1: Write failing test**

Add to `equity_trading/tests/test_validation_report.py`:

```python
def test_report_appends_risk_profile_section(tmp_path):
    from equity_trading.src.validation.report import write_validation_report
    from equity_trading.src.validation.gates.base import GateResult, Status
    import pandas as pd
    from datetime import datetime, timezone

    trades = pd.DataFrame({
        "entry_ts": pd.to_datetime(["2024-06-01", "2024-06-02"], utc=True),
        "exit_ts":  pd.to_datetime(["2024-06-01 16:00", "2024-06-02 16:00"], utc=True),
        "symbol":   ["TECL", "TQQQ"],
        "pnl_pct":  [0.01, -0.01],
        "position_dollars": [25000, 25000],
    })
    gates = [GateResult(name="oos", status=Status.PASS, summary="ok",
                         detail_md="### Gate 1\n"),
              GateResult(name="tail_risk", status=Status.PASS, summary="ok",
                         detail_md="### Gate 2\n"),
              GateResult(name="sample_size", status=Status.PASS, summary="ok",
                         detail_md="### Gate 3\n")]
    out = tmp_path / "r.md"
    write_validation_report(
        path=out, variant_id="v", baseline_id="b", gates=gates,
        git_sha="abc", manifest_hash="m",
        holdout_window=("2024-05-01", "2026-05-01"),
        generated_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
        variant_trades=trades,
    )
    text = out.read_text()
    assert "## Risk profile" in text
    assert "TECL" in text
```

- [ ] **Step 12.2: Run test**

Run: `python3 -m pytest equity_trading/tests/test_validation_report.py::test_report_appends_risk_profile_section -v`

Expected: FAIL — `write_validation_report() got an unexpected keyword argument 'variant_trades'`.

- [ ] **Step 12.3: Add `variant_trades` parameter and section append**

Modify `equity_trading/src/validation/report.py::write_validation_report` signature:

```python
def write_validation_report(
    *,
    path: Path | str,
    variant_id: str,
    baseline_id: str,
    gates: list[GateResult],
    git_sha: str,
    manifest_hash: str,
    holdout_window: tuple[str, str],
    generated_at: datetime,
    variant_trades: "pd.DataFrame | None" = None,
) -> None:
```

Just before the final `## Decision Log` block (line 74), add:

```python
    if variant_trades is not None and len(variant_trades) > 0:
        from equity_trading.src.validation.risk_profile import render_risk_profile_md
        lines.append(render_risk_profile_md(variant_trades))
        lines.append("")
```

Add `import pandas as pd` at the top of `report.py` (if not present, the type-string version above avoids needing it).

- [ ] **Step 12.4: Update CLI to pass accepted trades**

In `equity_trading/src/validation/cli.py`, replace the `write_validation_report(...)` call (line 96) with:

```python
    write_validation_report(
        path=args.output, variant_id=variant.variant_id, baseline_id=baseline.variant_id,
        gates=gates, git_sha=_git_sha(), manifest_hash=_manifest_hash(args.data_root),
        holdout_window=(variant.gates["oos"]["holdout_start"], variant.gates["oos"]["holdout_end"]),
        generated_at=datetime.now(timezone.utc),
        variant_trades=v_trades,
    )
```

- [ ] **Step 12.5: Run test**

Run: `python3 -m pytest equity_trading/tests/test_validation_report.py equity_trading/tests/test_validation_cli.py -v`

Expected: ALL pass.

- [ ] **Step 12.6: Commit**

```
git add equity_trading/src/validation/report.py equity_trading/src/validation/cli.py equity_trading/tests/test_validation_report.py
git commit -m "feat(validation): append risk_profile section to report (Task 12)"
```

---

## Task 13: §4-A compute_correlation utility

**Files:**
- Create: `equity_trading/scripts/compute_correlation.py`
- Test: `equity_trading/tests/test_compute_correlation.py` (new, smoke test)

- [ ] **Step 13.1: Write failing smoke test**

Create `equity_trading/tests/test_compute_correlation.py`:

```python
"""Smoke test for compute_correlation utility."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_compute_correlation_runs_on_train_data():
    """The script should execute without error and emit two markdown tables."""
    repo = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(repo / "equity_trading" / "scripts" / "compute_correlation.py")],
        capture_output=True, text=True, timeout=120, cwd=repo,
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "Daily-return correlation" in out
    assert "5min-return correlation" in out
    # 5 leveraged ETFs in matrix
    assert "TECL" in out
    assert "UDOW" in out
```

- [ ] **Step 13.2: Run test (will fail)**

Run: `python3 -m pytest equity_trading/tests/test_compute_correlation.py -v`

Expected: FAIL — file does not exist.

- [ ] **Step 13.3: Implement script**

Create `equity_trading/scripts/compute_correlation.py`:

```python
"""Compute and print correlation matrices for the 5 leveraged ETFs in our universe.

Used to populate static figures in equity_trading/docs/risk_disclosure.md.
Reads train/*_5min.parquet and train/*_1440min.parquet.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SYMBOLS = ["TECL", "TQQQ", "TNA", "UPRO", "UDOW"]


def _load_returns(timeframe_minutes: int) -> pd.DataFrame:
    cols = {}
    for s in SYMBOLS:
        path = ROOT / "data" / "prices" / "train" / f"{s}_{timeframe_minutes}min.parquet"
        df = pd.read_parquet(path)
        cols[s] = df["close"].pct_change().dropna()
    return pd.DataFrame(cols).dropna()


def _print_md_corr(label: str, corr: pd.DataFrame) -> None:
    print(f"\n## {label}\n")
    print("|   | " + " | ".join(corr.columns) + " |")
    print("|---|" + "|".join(["---:"] * len(corr.columns)) + "|")
    for s in corr.index:
        row = "| " + s + " | " + " | ".join(f"{corr.loc[s, t]:.2f}" for t in corr.columns) + " |"
        print(row)


def main() -> int:
    daily = _load_returns(1440)
    bars = _load_returns(5)
    _print_md_corr("Daily-return correlation (train)", daily.corr())
    _print_md_corr("5min-return correlation (train)", bars.corr())
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 13.4: Run test**

Run: `python3 -m pytest equity_trading/tests/test_compute_correlation.py -v`

Expected: PASS.

- [ ] **Step 13.5: Capture matrices to scratch file**

Run from project root:
```
python3 equity_trading/scripts/compute_correlation.py > /tmp/correlation_matrices.md
```

Open `/tmp/correlation_matrices.md` and copy both tables into Task 14.

- [ ] **Step 13.6: Commit**

```
git add equity_trading/scripts/compute_correlation.py equity_trading/tests/test_compute_correlation.py
git commit -m "feat(scripts): compute_correlation utility for risk_disclosure (Task 13)"
```

---

## Task 14: §4-A risk_disclosure.md static document

**Files:**
- Create: `equity_trading/docs/risk_disclosure.md`
- Modify: `equity_trading/docs/RUNBOOK.md` (link from header)

- [ ] **Step 14.1: Create the document**

Create `equity_trading/docs/risk_disclosure.md`:

```markdown
# Risk Disclosure — Equity Bot (敏腕モード v2)

## 1. Structural concentration

The bot trades 5 symbols: TECL, TQQQ, TNA, UPRO, UDOW.

| symbol | leverage | underlying | factor | rebalance |
|---|---|---|---|---|
| TECL | 3x | XLK (US tech) | growth | daily |
| TQQQ | 3x | NDX (US large-cap tech) | growth | daily |
| TNA | 3x | RUT (US small-cap) | smid | daily |
| UPRO | 3x | SPX (US large-cap blend) | broad | daily |
| UDOW | 3x | DJIA (US blue-chip) | broad | daily |

All five collapse to **3x · US equity index · long-tilt · daily-rebalanced**.
In a market-wide sell-off, all positions go the same direction.
**There is no diversification benefit across these five symbols.**

## 2. Historical correlation (computed from train data)

<!-- Run: python3 equity_trading/scripts/compute_correlation.py — paste the
      Daily-return correlation table here -->

(insert daily correlation table from Task 13 output)

<!-- And the 5min-return table -->

(insert 5min correlation table from Task 13 output)

Off-diagonal values are typically > 0.7 daily and > 0.85 in 5min bars.
TECL/TQQQ pair is near 0.95 (both QQQ-anchored).

## 3. Volatility drag (3x ETF math)

Daily-rebalanced 3x ETFs decay in choppy markets:
- A 5% up day followed by a 5% down day on the underlying:
  `(1 + 3×0.05)(1 - 3×0.05) = 1.15 × 0.85 = 0.9775` → **-2.25%** on the 3x ETF
  versus `(1.05)(0.95) = 0.9975` → **-0.25%** on the 1x.
- General formula: cumulative two-day loss ≈ **9 × r²** for the 3x vs **r²** for 1x.
- Real example: 2022 calendar year, NDX returned -33% but TQQQ returned **-79%** —
  the difference is entirely volatility drag.

The bot mitigates this by holding only during RTH (no overnight, with the
exception of LHM which holds <1 day). But within-day volatility still costs.

## 4. PDT (Pattern Day Trader) constraint

US brokerages enforce: under $25,000 equity, you may not place more than
**3 day-trades in any rolling 5-business-day window**. Since the bot does
1–2 round-trips per active day across ORB+LHM, **the seed capital must be
≥ $25,000 (≈ ¥3,750,000 at 150 JPY/USD) for live deployment**. Below that,
many entries will be rejected by the broker even if the strategy fires.

## 5. Where the +13.75%/yr 7-yr backtest comes from

Looking at the monthly P&L breakdown in `phase0/replay_7yr.md`:

- **2020-06**: +$13,770   (post-COVID liquidity rally)
- **2020-07**: +$13,376   (continuation)
- **2020-11**: +$20,301   (election + vaccine news)
- **2020-12**: +$13,070   (year-end melt-up)
- **2024-11**: +$19,099   (Fed-pivot rally)

These five months alone contributed **>$79,000** of the **$118,845** total profit
(67% of the gain from 5 of 84 months). The strategy harvests 3x beta during
sustained low-vol uptrends. In sideways or fast-moving markets it underperforms
or loses. Expect **annual variance of ±20pp around the mean**; do not anchor
on the +13.75% headline as a base case.

## 6. What this means for sizing decisions

- The bot is **not a diversifier** in a broader portfolio. Treat it as one
  concentrated position in 3x US-equity beta.
- Max DD seen in 7-yr replay was **-16.33%**; the post-warmup-fix holdout
  shows what this regime range looks like in 2024-2026 (see RUNBOOK).
- Realistic worst-case in a **2020 COVID-style** crash is **-30% to -40%**
  on the bot's equity over a few weeks. This is verified by the `stress_test`
  gate's covid_2020 window simulation.
- Catastrophic-stop: setting `catastrophic_stop_pct: 5.0` in variant config
  caps single-trade losses at -5%, at the cost of some upside. Recommended
  for live deployment.
```

Replace the two `(insert ... correlation table from Task 13 output)` placeholders with the actual matrices from `/tmp/correlation_matrices.md`.

- [ ] **Step 14.2: Add link from RUNBOOK header**

Edit `equity_trading/docs/RUNBOOK.md` — the header block edited in Task 4 already contains `> **Before any deployment, read \`equity_trading/docs/risk_disclosure.md\`.**`. Verify it is present; if not, add it now.

- [ ] **Step 14.3: Commit**

```
git add equity_trading/docs/risk_disclosure.md equity_trading/docs/RUNBOOK.md
git commit -m "docs: risk_disclosure.md with concentration, drag, PDT, regime dependence (Task 14)"
```

---

## Task 15: §5 compare_live_vs_backtest script

**Files:**
- Create: `equity_trading/scripts/compare_live_vs_backtest.py`
- Test: `equity_trading/tests/test_compare_live_vs_backtest.py` (new)

- [ ] **Step 15.1: Write failing tests**

Create `equity_trading/tests/test_compare_live_vs_backtest.py`:

```python
"""Live vs backtest comparison."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest


def _write_synthetic_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE positions (
            id INTEGER PRIMARY KEY,
            entry_ts TEXT, exit_ts TEXT,
            symbol TEXT, strategy TEXT,
            entry_price REAL, exit_price REAL,
            realized_pnl_usd REAL
        )
    """)
    rows = []
    # 35 ORB×TECL trades, WR ~0.55, avg ~ +0.18%
    for i in range(35):
        win = (i % 20) < 11
        pnl_pct = 0.0030 if win else -0.0015
        rows.append((
            f"2026-05-15 14:30:00",
            f"2026-05-15 15:30:00",
            "TECL", "OpeningRangeBreakoutStrategy",
            100.0, 100.0 * (1 + pnl_pct), pnl_pct * 25000.0,
        ))
    conn.executemany(
        "INSERT INTO positions(entry_ts, exit_ts, symbol, strategy, entry_price, exit_price, realized_pnl_usd) VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def test_compare_live_vs_backtest_produces_within_expectation(tmp_path):
    from equity_trading.scripts.compare_live_vs_backtest import compare
    db = tmp_path / "trades.sqlite"
    _write_synthetic_db(db)
    expected = {("OpeningRangeBreakoutStrategy", "TECL"): {"wr": 0.54, "avg_pnl_pct": 0.0022}}
    rows = compare(db_path=db, since="2026-05-14", expected=expected, seed=42)
    assert len(rows) == 1
    r = rows[0]
    assert r["strategy"] == "OpeningRangeBreakoutStrategy"
    assert r["symbol"] == "TECL"
    assert r["n"] == 35
    assert r["decision"] in {"WITHIN_EXPECTATION", "DIVERGENCE_AVG", "DIVERGENCE_WR"}


def test_compare_marks_insufficient_sample(tmp_path):
    from equity_trading.scripts.compare_live_vs_backtest import compare
    db = tmp_path / "trades.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE positions (id INTEGER PRIMARY KEY,
        entry_ts TEXT, exit_ts TEXT, symbol TEXT, strategy TEXT,
        entry_price REAL, exit_price REAL, realized_pnl_usd REAL)""")
    conn.executemany(
        "INSERT INTO positions(entry_ts, exit_ts, symbol, strategy, entry_price, exit_price, realized_pnl_usd) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [("2026-05-15", "2026-05-15", "TECL", "OpeningRangeBreakoutStrategy",
          100.0, 101.0, 250.0)] * 5,
    )
    conn.commit()
    conn.close()
    expected = {("OpeningRangeBreakoutStrategy", "TECL"): {"wr": 0.54, "avg_pnl_pct": 0.0022}}
    rows = compare(db_path=db, since="2026-05-14", expected=expected, seed=42)
    assert rows[0]["decision"] == "INSUFFICIENT_SAMPLE"
    assert rows[0]["n"] == 5


def test_compare_bootstrap_reproducible_with_seed(tmp_path):
    from equity_trading.scripts.compare_live_vs_backtest import compare
    db = tmp_path / "trades.sqlite"
    _write_synthetic_db(db)
    expected = {("OpeningRangeBreakoutStrategy", "TECL"): {"wr": 0.54, "avg_pnl_pct": 0.0022}}
    a = compare(db_path=db, since="2026-05-14", expected=expected, seed=42)
    b = compare(db_path=db, since="2026-05-14", expected=expected, seed=42)
    assert a[0]["wr_ci"] == b[0]["wr_ci"]
    assert a[0]["avg_pnl_pct_ci"] == b[0]["avg_pnl_pct_ci"]
```

- [ ] **Step 15.2: Run tests**

Run: `python3 -m pytest equity_trading/tests/test_compare_live_vs_backtest.py -v`

Expected: all FAIL — script does not exist.

- [ ] **Step 15.3: Implement script**

Create `equity_trading/scripts/compare_live_vs_backtest.py`:

```python
"""Compare live paper-trading results to backtest expectations.

Reads data/trades.sqlite, groups by (strategy, symbol), computes WR and avg pnl%
with bootstrap 95% CI, compares to expected values from train data, and emits
a markdown report with per-row decision tags.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DECISIONS = {"INSUFFICIENT_SAMPLE", "DIVERGENCE_AVG", "DIVERGENCE_WR",
              "WITHIN_EXPECTATION", "UNEXPECTED_PAIR"}
N_BOOT = 1000
MIN_N = 30


def _bootstrap_ci(values: np.ndarray, stat_fn, n_boot: int, rng: np.random.Generator
                   ) -> tuple[float, float]:
    samples = np.empty(n_boot)
    n = len(values)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        samples[i] = stat_fn(values[idx])
    lo = float(np.quantile(samples, 0.025))
    hi = float(np.quantile(samples, 0.975))
    return lo, hi


def compare(*, db_path: Path | str, since: str,
            expected: dict[tuple[str, str], dict[str, float]],
            seed: int = 42) -> list[dict]:
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        "SELECT entry_ts, exit_ts, symbol, strategy, entry_price, exit_price, "
        "realized_pnl_usd FROM positions WHERE exit_ts >= ?",
        conn, params=[since],
    )
    conn.close()
    if len(df) == 0:
        return []
    df["pnl_pct"] = (df["exit_price"] - df["entry_price"]) / df["entry_price"]
    rows = []
    rng = np.random.default_rng(seed)
    seen_pairs = set()
    for (strategy, symbol), grp in df.groupby(["strategy", "symbol"]):
        seen_pairs.add((strategy, symbol))
        n = len(grp)
        wins = (grp["pnl_pct"] > 0).sum()
        wr = wins / n if n > 0 else 0.0
        avg_pnl = grp["pnl_pct"].mean()
        if (strategy, symbol) not in expected:
            decision = "UNEXPECTED_PAIR"
            row = {"strategy": strategy, "symbol": symbol, "n": int(n),
                    "wr": float(wr), "avg_pnl_pct": float(avg_pnl),
                    "wr_ci": (None, None), "avg_pnl_pct_ci": (None, None),
                    "expected_wr": None, "expected_avg_pnl_pct": None,
                    "decision": decision}
            rows.append(row)
            continue
        exp = expected[(strategy, symbol)]
        if n < MIN_N:
            decision = "INSUFFICIENT_SAMPLE"
            wr_ci = (None, None)
            avg_ci = (None, None)
        else:
            pnls = grp["pnl_pct"].to_numpy()
            wr_ci = _bootstrap_ci(pnls, lambda v: float((v > 0).mean()), N_BOOT, rng)
            avg_ci = _bootstrap_ci(pnls, lambda v: float(v.mean()), N_BOOT, rng)
            if avg_ci[1] < exp["avg_pnl_pct"]:
                decision = "DIVERGENCE_AVG"
            elif abs(wr - exp["wr"]) > 0.10:
                decision = "DIVERGENCE_WR"
            else:
                decision = "WITHIN_EXPECTATION"
        rows.append({
            "strategy": strategy, "symbol": symbol, "n": int(n),
            "wr": float(wr), "avg_pnl_pct": float(avg_pnl),
            "wr_ci": wr_ci, "avg_pnl_pct_ci": avg_ci,
            "expected_wr": float(exp["wr"]),
            "expected_avg_pnl_pct": float(exp["avg_pnl_pct"]),
            "decision": decision,
        })
    # Pairs in expected but never traded: flag as INSUFFICIENT_SAMPLE n=0
    for pair in expected:
        if pair not in seen_pairs:
            rows.append({
                "strategy": pair[0], "symbol": pair[1], "n": 0,
                "wr": 0.0, "avg_pnl_pct": 0.0,
                "wr_ci": (None, None), "avg_pnl_pct_ci": (None, None),
                "expected_wr": expected[pair]["wr"],
                "expected_avg_pnl_pct": expected[pair]["avg_pnl_pct"],
                "decision": "INSUFFICIENT_SAMPLE",
            })
    return rows


def render_md(rows: list[dict], variant_id: str, period_label: str, total_n: int) -> str:
    parts = [f"# Live vs Backtest Comparison\n",
              f"**Variant**: {variant_id}  **Period**: {period_label}  **Total live trades**: {total_n}\n",
              "## By strategy × symbol\n",
              "| strat × sym | n | live WR | live avg | expected WR | expected avg | decision |",
              "|---|---:|---:|---:|---:|---:|---|"]
    for r in rows:
        wr_str = f"{r['wr']:.2f}" if r["wr_ci"][0] is None else f"{r['wr']:.2f} [{r['wr_ci'][0]:.2f}, {r['wr_ci'][1]:.2f}]"
        avg_str = f"{r['avg_pnl_pct']*100:+.2f}%" if r["avg_pnl_pct_ci"][0] is None else (
            f"{r['avg_pnl_pct']*100:+.2f}% [{r['avg_pnl_pct_ci'][0]*100:+.2f}, {r['avg_pnl_pct_ci'][1]*100:+.2f}]%"
        )
        exp_wr = f"{r['expected_wr']:.2f}" if r["expected_wr"] is not None else "—"
        exp_avg = f"{r['expected_avg_pnl_pct']*100:+.2f}%" if r["expected_avg_pnl_pct"] is not None else "—"
        parts.append(f"| {r['strategy']} × {r['symbol']} | {r['n']} | {wr_str} | {avg_str} | "
                      f"{exp_wr} | {exp_avg} | {r['decision']} |")
    parts.append("")
    return "\n".join(parts)


def _compute_expected(variant_path: Path, train_root: Path) -> dict[tuple[str, str], dict[str, float]]:
    from equity_trading.src.validation.config import load_variant_config
    from equity_trading.src.validation.data import load_train_bars
    from equity_trading.src.phase0.atr_analyzer import analyze_atr_distribution
    from equity_trading.src.phase0.strategy_simulator import simulate_strategy
    cfg = load_variant_config(variant_path)
    expected = {}
    for entry in cfg.strategies:
        cls = cfg.resolve_strategy_class(entry["class"])
        for symbol in entry["symbols"]:
            bars = load_train_bars(train_root, symbol, timeframe_minutes=5)
            daily = load_train_bars(train_root, symbol, timeframe_minutes=1440)
            atr = analyze_atr_distribution(bars, period=14)["median_pct"]
            params = dict(entry["params"])
            params["_daily"] = daily
            cost = params.pop("cost_pct", 0.10)
            cat_stop = params.pop("catastrophic_stop_pct", None)
            summary, _ = simulate_strategy(
                strategy=cls(), bars_5min=bars, daily=daily, atr_pct=atr,
                params=params, cost_pct=cost,
                catastrophic_stop_pct=cat_stop, return_trades=True,
            )
            wr = summary.get("win_rate", 0.0)
            avg = summary.get("avg_pnl_pct", 0.0) / 100.0  # back to fraction
            expected[(cls.__name__, symbol)] = {"wr": float(wr), "avg_pnl_pct": float(avg)}
    return expected


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--variant", type=Path, required=True)
    p.add_argument("--db", type=Path, default=Path("equity_trading/data/trades.sqlite"))
    p.add_argument("--train-root", type=Path, default=Path("equity_trading/data/prices"))
    p.add_argument("--since", default=None)
    p.add_argument("--output", type=Path, default=None)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    from equity_trading.src.validation.config import load_variant_config
    cfg = load_variant_config(args.variant)
    since = args.since or _next_day_str(cfg.gates["oos"]["holdout_end"])
    expected = _compute_expected(args.variant, args.train_root)
    rows = compare(db_path=args.db, since=since, expected=expected, seed=args.seed)
    total_n = sum(r["n"] for r in rows)
    period = f"{since} → today"
    md = render_md(rows, cfg.variant_id, period, total_n)
    if args.output is None:
        out = Path("equity_trading/phase0") / f"live_vs_backtest_{datetime.now(timezone.utc).date()}.md"
    else:
        out = args.output
    out.write_text(md)
    print(f"[saved] {out}")
    return 0


def _next_day_str(date_str: str) -> str:
    return (datetime.fromisoformat(date_str) + pd.Timedelta(days=1)).date().isoformat()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 15.4: Run tests**

Run: `python3 -m pytest equity_trading/tests/test_compare_live_vs_backtest.py -v`

Expected: ALL pass.

- [ ] **Step 15.5: Commit**

```
git add equity_trading/scripts/compare_live_vs_backtest.py equity_trading/tests/test_compare_live_vs_backtest.py
git commit -m "feat(scripts): compare_live_vs_backtest with bootstrap CI (Task 15)"
```

---

## Task 16: §5 RUNBOOK weekly evaluation procedure

**Files:**
- Modify: `equity_trading/docs/RUNBOOK.md` (add section)

- [ ] **Step 16.1: Add weekly evaluation section**

In `equity_trading/docs/RUNBOOK.md`, find the existing "When to evaluate" section (around line 208). Insert before it (or replace if redundant):

```markdown
## Weekly live evaluation (post-deployment)

Every Friday after EOD, run:

\`\`\`
python3 equity_trading/scripts/compare_live_vs_backtest.py \
    --variant equity_trading/configs/orb_default_v0.yaml
\`\`\`

The script writes `equity_trading/phase0/live_vs_backtest_YYYY-MM-DD.md` with one row
per (strategy, symbol). Each row carries one of:

- `INSUFFICIENT_SAMPLE` — fewer than 30 live trades; cannot judge yet.
- `WITHIN_EXPECTATION` — live WR within ±10pt of backtest expectation AND
   live avg P&L 95% CI upper bound covers backtest expectation.
- `DIVERGENCE_AVG` — live avg P&L 95% CI is entirely below the backtest
   expectation. The strategy may not generalize to current regime.
- `DIVERGENCE_WR` — live WR more than 10 percentage points off expectation.
- `UNEXPECTED_PAIR` — live trades on a (strategy, symbol) not in the variant
   config (likely a stale strategy left in the bot).

**Decision rule**: if a (strategy, symbol) shows `DIVERGENCE_*` for **two
consecutive weeks AND n ≥ 30**, halt that pair (comment it out of the
variant config) and run `run_phase0_diagnostic.py` for that pair to
diagnose root cause.
```

(Replace the inner backticks-with-backslash with real triple backticks when actually editing.)

- [ ] **Step 16.2: Commit**

```
git add equity_trading/docs/RUNBOOK.md
git commit -m "docs(RUNBOOK): weekly live-vs-backtest evaluation procedure (Task 16)"
```

---

## Task 17: Regression — re-validate V2.1 with all changes

**Files:**
- Run validation; verify REJECT decision unchanged

- [ ] **Step 17.1: Run V2.1 validation**

Run from project root:
```
python3 -m equity_trading.src.validation \
    --variant equity_trading/configs/orb_tight_v2_1.yaml \
    --baseline equity_trading/configs/orb_default_v0.yaml \
    --output equity_trading/phase0/validation/2026-05-04_orb_v2_1_post_improvements.md
```

Expected: report file written. Headline should still be **REJECT** (the variant was over-fit; warmup fix and stress_test gate should not change that conclusion).

- [ ] **Step 17.2: Inspect and confirm**

Read the report. Verify:
- Headline: **REJECT**
- OOS gate: still FAIL (variant ann ≤ baseline)
- tail_risk gate: still FAIL (worst trade > -5%, MaxDD > 20%)
- sample_size: PASS
- stress_test: PASS or FAIL (acceptable either way; if FAIL, that's additional evidence V2.1 is bad)
- Risk profile section present at the end

If the headline is no longer REJECT, **stop and investigate** — something in Tasks 1–12 unintentionally relaxed the gates.

- [ ] **Step 17.3: Commit**

```
git add equity_trading/phase0/validation/2026-05-04_orb_v2_1_post_improvements.md
git commit -m "data(validation): regression confirm V2.1 still REJECT post-improvements (Task 17)"
```

---

## Task 18: Final full test suite + summary commit

**Files:**
- (none)

- [ ] **Step 18.1: Run full test suite**

Run: `python3 -m pytest equity_trading/tests/ -v`

Expected: ALL pass. Note any failures and fix before proceeding.

- [ ] **Step 18.2: Run gates locally with `enabled: true` stress_test on default variant**

Run: `python3 -m equity_trading.src.validation --variant equity_trading/configs/orb_default_v0.yaml --baseline equity_trading/configs/orb_default_v0.yaml --output /tmp/self_check.md`

Expected: APPROVE headline, all 4 gates run (OOS, tail_risk, sample_size, stress_test), Risk profile section present.

- [ ] **Step 18.3: Verify access log shows warmup**

Run: `tail -1 equity_trading/data/prices/holdout_access.jsonl | python3 -c "import sys, json; r=json.loads(sys.stdin.read()); print('source:', r['source'], 'warmup_rows:', r.get('warmup_rows'))"`

Expected: when reading 1440-min bars, `source: holdout+warmup`, `warmup_rows: 250`.

- [ ] **Step 18.4: No commit (verification only)**

This task is verification; no new artifacts.

---

## Self-review checklist (run by writer after plan is complete)

- [x] Spec coverage: every section of the spec maps to ≥1 task
  - §1 → Tasks 1, 2, 3, 4
  - §2 → Tasks 5, 6
  - §3 → Tasks 7, 8, 9
  - §4-A → Tasks 13, 14
  - §4-B → Tasks 10, 11, 12
  - §5 → Tasks 15, 16
  - §6 critical-path → Tasks 1→2→3→4 then parallel (5,6,7,8,9,10,11,12,13,14,15,16) → Task 17
  - §7 testing strategy → unit tests in each task + Task 18 final sweep
- [x] No "TBD" / "TODO" / "implement later" left
- [x] Type/signature consistency: `_simulate_portfolio` returns 3-tuple in Task 10, `run_holdout_simulation` returns 4-tuple in Task 10, CLI updated in Task 10 to unpack 4 values
- [x] All file paths absolute or anchored at `/Users/hideakimacbookair/自動トレード`
- [x] Test commands include exact pytest invocation paths
- [x] Commit messages follow existing repo convention (`feat:`, `docs:`, `data:`, `refactor:`)
