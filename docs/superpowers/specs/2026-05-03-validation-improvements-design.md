# Validation Framework Improvements — Design Spec

- **Date**: 2026-05-03
- **Owner**: equity_trading bot maintainer
- **Status**: Approved (brainstorming) → ready for writing-plans
- **Scope**: 5 improvements driven by the 2026-05-03 review of `equity_trading/`. Addresses one confirmed bug (200d MA warmup missing in holdout) and four hardening items (catastrophic stop, stress windows, concentration disclosure, live-vs-backtest comparison).

---

## 1. Background

The 2026-05-03 review of the equity bot uncovered:

1. **Confirmed bug**: `data/prices/holdout/*_1440min.parquet` only contains the holdout window (501 days, 2024-05-01 → 2026-04-30). `OpeningRangeBreakoutStrategy.compute_entry_signal` requires a 200-day SMA on `daily["close"]`, which is NaN for the first ~200 trading days of holdout. With `daily_above_ma.fillna(False)`, ORB signals are silently suppressed for ~9 months of the 2-year holdout, distorting both variant and baseline absolute returns. This explains why the same period shows +24% in 7-yr replay but −12.80%/yr in holdout report.
2. **Concentration risk** is structural (5 ETFs all 3x leveraged US equity index, correlation ≈ 1 in stress), but not surfaced in validation output and only mentioned in passing in `RUNBOOK.md`.
3. **No 2022-style stress regime** in the current holdout (2024-05 → 2026-05 is bull-tilted).
4. **`tail_risk` gate already simulates** "−5% per-trade cap" informationally but does not allow it as a real strategy guard.
5. **No automated way to compare paper-trading results** to backtest expectations after deployment.

This spec defines five interlocking changes that fix (1) and harden (2)–(5).

---

## 2. Goals and non-goals

**Goals**:

- Eliminate the 200d MA warmup gap so holdout absolute returns reflect real strategy behaviour, not artificial signal suppression.
- Make catastrophic-stop a configurable, simulator-level guard.
- Add a stress-window gate that uses train data (does not consume holdout) so 2022-style drawdowns can be tested.
- Make concentration risk visible in every validation report, with a static disclosure document for context.
- Make live-vs-backtest divergence checkable from a single command, week by week.

**Non-goals**:

- No new strategies. Universe stays at TECL/TQQQ/TNA/UPRO/UDOW.
- No regime-conditioning or VIX overlays in this spec (called out in `strategy_research_review.md` as future work).
- No automated kill-switch or Slack alerts. Human reads the report and decides.
- No change to the holdout cutoff (2024-05-01). Existing reports stay comparable.
- No leverage/sizing changes. Stays 25% × 3 concurrent.

---

## 3. Architecture overview

```
data/prices/                                  # unchanged
  ├─ train/      *_5min.parquet, *_1440min.parquet
  └─ holdout/    *_5min.parquet, *_1440min.parquet
                              ▲
                              │
src/validation/data.py        │
  EvaluationContext.load_holdout_bars(symbol, tf)
    if tf == 1440:
      prepend last 250 daily bars from train/  ◀── §1 warmup
    else:
      return holdout/ as-is
                              │
src/validation/runner.py      │
  _collect_trades drops trades with entry_ts < holdout_start  ◀── §1
                              │
src/phase0/strategy_simulator.py
  simulate_strategy(..., catastrophic_stop_pct=None)          ◀── §2
                              │
src/validation/gates/
  oos.py / sample_size.py / tail_risk.py     (unchanged)
  stress_test.py                              ◀── §3 NEW
                              │
src/validation/risk_profile.py                ◀── §4-B NEW
src/validation/report.py
  appends Risk profile section using risk_profile.py
                              │
docs/risk_disclosure.md                       ◀── §4-A NEW
                              │
scripts/compare_live_vs_backtest.py           ◀── §5 NEW
  reads data/trades.sqlite + variant config
  writes phase0/live_vs_backtest_<date>.md
```

---

## 4. Section §1 — Warmup architecture (B: virtual warmup, daily-only, 250 trading days)

**Files**: `src/validation/data.py`, `src/validation/runner.py`, `tests/test_warmup.py` (new).

**`EvaluationContext`** gains:

```python
class EvaluationContext:
    WARMUP_DAYS_DAILY = 250  # 200d SMA + 50-day safety margin

    def load_holdout_bars(self, symbol: str, timeframe_minutes: int) -> pd.DataFrame:
        path_holdout = self.root / "holdout" / f"{symbol}_{timeframe_minutes}min.parquet"
        df_holdout = pd.read_parquet(path_holdout)

        if timeframe_minutes == 1440:
            df_warmup = self._load_warmup_daily(symbol)
            df = pd.concat([df_warmup, df_holdout]).sort_index()
            df = df[~df.index.duplicated(keep="last")]
            self._log_access(
                symbol=symbol,
                timeframe_minutes=timeframe_minutes,
                source="holdout+warmup",
                rows=len(df),
                warmup_rows=len(df_warmup),
            )
            return df

        # 5min: ATR(14) needs only 14 bars, no warmup necessary
        self._log_access(
            symbol=symbol,
            timeframe_minutes=timeframe_minutes,
            source="holdout",
            rows=len(df_holdout),
        )
        return df_holdout

    def _load_warmup_daily(self, symbol: str) -> pd.DataFrame:
        path_train = self.root / "train" / f"{symbol}_1440min.parquet"
        df = pd.read_parquet(path_train)
        return df.tail(self.WARMUP_DAYS_DAILY)
```

`_log_access` writes one record per call, with new `warmup_rows` field (existing JSONL parsers ignore unknown keys).

**`runner.py::_collect_trades`** gains a holdout-start filter:

```python
holdout_start = pd.Timestamp(cfg.gates["oos"]["holdout_start"], tz="UTC")
df = df[df["entry_ts"] >= holdout_start]
```

This drops any trade entered during the warmup prefix; only trades signaled inside the holdout window are scored.

**Manifest**: unchanged. The warmup data comes from `train/`, whose hashes are already in `manifest.json`. No new partition.

**Backwards compatibility**: 5min reads behave identically. Daily reads return more rows; consumers must accept that. `_collect_trades` filter ensures gate metrics are computed only on holdout-period trades, so the OOS gate result is comparable to pre-fix runs except the absolute return is no longer artificially negative.

**Tests** (`tests/test_warmup.py`):

- `EvaluationContext.load_holdout_bars(symbol, 1440)` returns a DataFrame whose first index is at least 250 trading days before `holdout_start`.
- `EvaluationContext.load_holdout_bars(symbol, 5)` returns identical bytes to the raw `holdout/*_5min.parquet` (no warmup).
- Access log JSONL contains an entry with `source == "holdout+warmup"` and `warmup_rows == 250`.
- `_collect_trades` drops a synthetic trade with `entry_ts == holdout_start - 1 day`, keeps one with `entry_ts == holdout_start`.
- 200d SMA on the returned daily series is non-NaN by `holdout_start`.

---

## 5. Section §2 — Catastrophic stop (B: simulator-level)

**Files**: `src/phase0/strategy_simulator.py`, `src/validation/runner.py`, `tests/test_catastrophic_stop.py` (new).

**Signature change** in `simulate_strategy` (and the parallel `simulate_single_trade`):

```python
def simulate_strategy(
    strategy, bars_5min, daily, atr_pct, params=None,
    stop_multiplier=1.5, target_multiplier=2.4,
    cost_pct=0.10, max_hold_bars=78,
    catastrophic_stop_pct: float | None = None,  # NEW
    return_trades=False,
) -> dict | tuple[dict, pd.DataFrame]:
    ...
    stop_price, target_price = strategy.compute_exit_levels(...)
    if catastrophic_stop_pct is not None:
        cat_floor = entry_price * (1 - catastrophic_stop_pct / 100.0)
        stop_price = max(stop_price, cat_floor)  # tighten only
```

The cap is applied **after** `compute_exit_levels` and only **tightens** the stop. It never widens. `target_price` is untouched.

**Variant config schema** (additive, optional):

```yaml
strategies:
  - class: OpeningRangeBreakoutStrategy
    symbols: [TECL, TQQQ, TNA]
    params:
      or_window_bars: 12
      stop_mult: 0.0
      target_mult: 1.0
      cost_pct: 0.10
      catastrophic_stop_pct: 5.0   # optional; absent or null means disabled
```

**`runner.py::_collect_trades`** propagates the param:

```python
params = dict(entry["params"])
cost = params.pop("cost_pct", 0.10)
cat_stop = params.pop("catastrophic_stop_pct", None)
_, trades = simulate_strategy(
    strategy=cls(), bars_5min=bars_5min, daily=daily, atr_pct=atr,
    params=params, cost_pct=cost,
    catastrophic_stop_pct=cat_stop,
    return_trades=True,
)
```

**Default**: absent (`None`). All existing variants behave unchanged.

**Tail risk gate**: the existing informational `_catastrophic_stop_worst` simulation in `tail_risk.py` stays as-is. With `catastrophic_stop_pct` set in config, the actual `worst_trade_pct` will already be ≥ −cap, so the simulation and reality coincide.

**Tests** (`tests/test_catastrophic_stop.py`):

- Synthetic 5min bars where bar low drops 10% from entry; with `catastrophic_stop_pct=5.0` the trade exits at −5% (minus cost), not −10%.
- `catastrophic_stop_pct=None` produces identical trades to a pre-change golden output.
- Target hits unchanged: bar high reaches target before low reaches cap → exit at target.
- LHM strategy with its native ±3% stops produces identical trades whether cap is 5.0 or None (regression).

---

## 6. Section §3 — `stress_test` gate (B: train-data window slicing)

**Files**: `src/validation/gates/stress_test.py` (new), `src/validation/runner.py`, `src/validation/cli.py`, `src/validation/report.py`, `tests/test_stress_gate.py` (new).

**Variant config schema** (additive, gate is opt-in):

```yaml
gates:
  oos:
    holdout_start: "2024-05-01"
    holdout_end: "2026-05-01"
    min_outperformance_pct: 0.0
  tail_risk:
    max_single_trade_loss_pct: 5.0
    max_portfolio_dd_pct: 20.0
    max_rolling_30d_loss_pct: 10.0
  sample_size:
    min_holdout_trades: 30
  stress_test:
    enabled: true                 # default false for back-compat
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

**`run_stress_test_gate`** signature:

```python
def run_stress_test_gate(
    *,
    cfg: VariantConfig,
    baseline_cfg: VariantConfig,
    train_root: Path,
    stress_windows: list[dict],
) -> GateResult:
    """For each window, slice train data, run variant + baseline through
    simulate_strategy + _simulate_portfolio, and check both:
    1. variant MaxDD ≤ window.max_dd_limit_pct AND worst trade ≤ -window.worst_trade_limit_pct
    2. variant MaxDD ≤ 1.3 * baseline MaxDD (excessive risk vs baseline)
    All windows must pass. Empty windows list → Status.WARN with 'no windows configured'.
    """
```

**Implementation**:

- Train data is read directly via `load_train_bars(train_root, symbol, timeframe_minutes, partition="train")`. No `EvaluationContext` (train access is unrestricted by design).
- Per-window slicing is in-memory: `bars_5min.loc[start:end]`, and for daily, slice from `start - 365 calendar days` (≈ 250 trading days, conservative buffer) to `end`. Train data is contiguous so no gap.
- For each window, run the existing `_collect_trades` logic and `_simulate_portfolio` with the variant's portfolio config.
- Aggregate per-window results into a single `GateResult` with `Status.FAIL` if any window fails, `Status.WARN` if no windows configured, `Status.PASS` otherwise.

**Report**: `report.py` renders a per-window table. Example:

```markdown
### Gate 4: Stress test ✅

| window | period | variant ann | variant DD | baseline DD | worst trade | result |
|---|---|---:|---:|---:|---:|:---:|
| covid_2020 | 2020-02-15 → 2020-05-15 | -8.4% | -22.1% | -19.8% | -4.9% | ✅ |
| hike_2022 | 2022-01-01 → 2023-04-01 | -2.1% | -18.7% | -17.4% | -4.3% | ✅ |
```

**Gate ordering**: stress_test runs after the existing three gates. If `enabled: false`, it is skipped (no entry in report).

**Tests** (`tests/test_stress_gate.py`):

- Synthetic bars rigged for −40% DD in window: with `max_dd_limit_pct=25.0` → FAIL.
- Same bars with `max_dd_limit_pct=50.0` → PASS.
- Two windows, one FAIL one PASS → overall FAIL with detail listing the failing window.
- Empty `windows` list → `Status.WARN`, `summary == "no windows configured"`.
- variant DD = 1.5× baseline DD → FAIL on the "excessive risk vs baseline" rule even when absolute DD is under window limit.

---

## 7. Section §4 — Concentration risk disclosure (C: static doc + auto report section)

### 7.1 §4-A static document

**File**: `equity_trading/docs/risk_disclosure.md` (new, ~150 lines).

Sections (each scaled to substance):

1. **Structural concentration** — Plain text + matrix figure: 5 symbols × 5 attributes (leverage, asset class, geography, factor tilt, decay). All five collapse to "3x · US equity index · long-tilt · daily-rebalanced". In a crash all positions go same direction.
2. **Historical correlation** — Compute once from train data: 5×5 daily-return correlation matrix and 5×5 5min-return correlation matrix. Embed both as markdown tables. Re-compute by running `python3 -m equity_trading.scripts.compute_correlation` (utility script — see §11).
3. **Volatility drag** — Math: `(1 + 3r)(1 - 3r) = 1 - 9r²`, so a 5% up + 5% down day costs 9.0% on the 3x ETF vs 0.25% on the 1x. Cite TQQQ 2022 example: NDX −33%, TQQQ −79%.
4. **PDT** — $25k floor, 3 day-trades / 5 business days. Current Scenario A (25%/pos × 3) makes 1–2 round-trips per day → $25k seed required for live.
5. **What the +13.75%/yr depends on** — Identify the months that drove the 7-yr return (2020-06, 2020-11, 2024-11 each contributed >$13k in the replay). Frame as "regime-dependent: the strategy harvests 3x ETF beta during sustained low-vol uptrends. In sideways or fast-moving markets it underperforms or loses."

`RUNBOOK.md` gets a one-line addition at the top:

> **Before any deployment, read `docs/risk_disclosure.md`.**

### 7.2 §4-B auto-section in validation report

**Files**: `src/validation/risk_profile.py` (new), `src/validation/report.py`.

**Computation** (`risk_profile.compute_risk_profile(trades, equity_curve)`):

1. **Symbol contribution**: requires per-trade `position_dollars`. Currently `runner.py::_simulate_portfolio` computes `equity * position_size_pct` internally but does not surface it on the trades DataFrame. **Sub-task**: extend `_simulate_portfolio` to attach `position_dollars` to its returned trades DataFrame (it already tracks the value in `open_pos`). Then `risk_profile` groups by symbol and sums `pnl_pct * position_dollars`, reports % of total absolute P&L.
2. **Pairwise correlation**: pivot `trades` to (entry_date, symbol) → daily return per symbol per day. Compute Pearson correlation matrix, fillna with 0 for days a symbol didn't trade.
3. **Stress overlap**: scan `equity_curve` and `trades` to find windows where ≥3 positions were open simultaneously; compute MaxDD inside those windows. Count days with all open positions losing.

**Rendering** (in `report.py`):

```markdown
## Risk profile

### Symbol contribution to P&L (holdout)
| symbol | trades | gross P&L $ | % of total | avg P&L % |
|---|---:|---:|---:|---:|
| TECL | 130 | +$8,420 | 41.0% | +0.32% |
...

### Pairwise daily-return correlation
|   | TECL | TQQQ | TNA | UPRO | UDOW |
|---|-----:|-----:|----:|-----:|-----:|
| TECL | 1.00 | 0.92 | 0.78 | 0.88 | 0.74 |
...

### Stress overlap
- 30-day rolling MaxDD when ≥3 positions open simultaneously: -12.4%
- Days with ≥3 open positions all losing same direction: 14 (5.6% of trading days)
```

**Tests** (`tests/test_risk_profile.py`):

- Synthetic 3-symbol × 10-trade DataFrame with known P&L → contribution table values exact.
- Correlation matrix is symmetric, diagonal == 1.0, off-diagonals in [-1, 1].
- Days with 3 simultaneous open positions counted correctly across timestamp boundaries (1-second overlap counts as overlap).
- `report.py` test asserts the new section header `## Risk profile` appears in the rendered report.

---

## 8. Section §5 — Live vs backtest comparison

**Files**: `equity_trading/scripts/compare_live_vs_backtest.py` (new), `tests/test_compare_live_vs_backtest.py` (new), `docs/RUNBOOK.md` (additive).

**CLI**:

```bash
python3 equity_trading/scripts/compare_live_vs_backtest.py \
    --variant equity_trading/configs/orb_default_v0.yaml \
    --db equity_trading/data/trades.sqlite \
    --since 2026-05-15 \
    --output equity_trading/phase0/live_vs_backtest_$(date +%Y-%m-%d).md
```

`--since` defaults to `cfg.gates["oos"]["holdout_end"] + 1 day`.

**Processing**:

1. Read `positions` table from SQLite, filter `exit_ts >= since`.
2. Group by `(strategy, symbol)`. Per group compute: n, WR, avg pnl%, total pnl$.
3. From `cfg.strategies`, identify expected `(strategy, symbol)` pairs and load **train** data via `load_train_bars` to compute the in-sample expected WR and avg pnl% for each (this is the "expected" baseline — using train data is fine, no holdout consumption).
4. Bootstrap (n=1000, seed=42 for reproducibility) the live samples to get 95% CI for WR and avg pnl%.
5. Render markdown comparing live CI vs expected point estimate. Decision rules per group:
    - `n < 30` → `INSUFFICIENT_SAMPLE`
    - `n ≥ 30` AND live avg pnl% 95% CI upper bound < expected avg pnl% → `DIVERGENCE_AVG`
    - `n ≥ 30` AND |live WR − expected WR| > 0.10 → `DIVERGENCE_WR`
    - else → `WITHIN_EXPECTATION`

**Operational doc** (`docs/RUNBOOK.md` addition):

```markdown
## Weekly live evaluation

Every Friday after EOD:
  python3 equity_trading/scripts/compare_live_vs_backtest.py \
      --variant equity_trading/configs/orb_default_v0.yaml

Read the report. If a (strategy, symbol) pair shows DIVERGENCE_* for two
consecutive weeks AND n ≥ 30, halt that pair (comment it out of the
variant config) and run `run_phase0_diagnostic.py` for that pair.
```

**Tests** (`tests/test_compare_live_vs_backtest.py`):

- Build a synthetic SQLite (50 trades, WR=0.55, avg=+0.18%); compare to expected (WR=0.54, avg=+0.22%) → output contains `WITHIN_EXPECTATION`.
- Bootstrap CI is reproducible across runs with `seed=42`.
- `--since` boundary is inclusive: a trade with `exit_ts == since 00:00:00 UTC` is included.
- `(strategy, symbol)` in SQLite but absent from variant config → warning row with marker `UNEXPECTED_PAIR`.
- `(strategy, symbol)` in config but n=0 in SQLite → row with `INSUFFICIENT_SAMPLE` and n=0.

**Out of scope**: Slack alerts, automated halt, multi-week consecutive-DIVERGENCE detector. Initial version is human-read-only.

---

## 9. Section §6 — Implementation order and critical path

```
[1] §1 warmup fix                                 ← blocker for everything
       │
       ▼
[2] re-run baseline (orb_default_v0) on holdout
       │
       ▼
[3] update RUNBOOK with corrected baseline numbers
       │
       ▼
       ├──→ [4a] §2 catastrophic_stop  ──┐
       ├──→ [4b] §3 stress_test gate   ──┤  (parallel; independent PRs)
       └──→ [4c] §4-B risk profile     ──┤
                                          ▼
                                       [5] regression: re-run V2.1 with all
                                           three; confirm REJECT unchanged
                                          ▼
       ┌──── always-parallel, independent of above ────┐
       │  §4-A docs/risk_disclosure.md                  │
       │  §5 compare_live_vs_backtest.py                │
       └────────────────────────────────────────────────┘
```

**Mandatory after step [3]**: open a PR titled "data: re-run baseline holdout post-warmup-fix" that adds the new validation report and updates the RUNBOOK projected return numbers. Without this, downstream gates compare against stale baseline metrics.

---

## 10. Section §7 — Test strategy

| Layer | Files | What it covers |
|---|---|---|
| Unit | `test_warmup.py`, `test_catastrophic_stop.py`, `test_stress_gate.py`, `test_risk_profile.py`, `test_compare_live_vs_backtest.py` | Each new piece of logic in isolation |
| Regression | existing `test_strategy_simulator.py`, `test_validation_runner.py`, `test_validation_report.py` | All pre-existing tests pass with `catastrophic_stop_pct=None` and `stress_test.enabled=false` |
| E2E (manual, run-once) | self-comparison run, V2.1 re-validate, capped-config validate | Confirms no integration regression |

Coverage target on **new** code: ≥90%. Run with:

```bash
cd /Users/hideakimacbookair/自動トレード
python3 -m pytest equity_trading/tests/ -v
```

TDD via the `superpowers:test-driven-development` skill: write each unit test first, watch it fail, write the minimum code to pass, refactor.

---

## 11. Resolved sub-tasks (folded out of open questions)

- **§4-A correlation values**: Implementation plan must include `equity_trading/scripts/compute_correlation.py` (small utility). Reads train daily and 5min parquets for TECL/TQQQ/TNA/UPRO/UDOW, prints two markdown correlation matrices to stdout. Output is pasted by hand into `risk_disclosure.md`.
- **§5 expected WR/EV source**: Computed on the fly inside `compare_live_vs_backtest.py` per invocation, from train data. No cache, no staleness. Runtime cost ≈ 25s for 5 strategy×symbol combos, acceptable for a weekly-run script.
- **RUNBOOK headline replacement**: After §1 lands and the post-warmup-fix baseline is re-run, the implementation plan must include a task that rewrites `RUNBOOK.md` lines 5–6 (想定リターン / Max DD) with the new holdout numbers, while preserving the 7-yr in-sample numbers as a separate "in-sample reference" line so the reader can see both.

---

## 12. Out of scope explicitly

- VIX overlay, Pre-FOMC reactivation, Pairs trading, Sector rotation — all called out in `strategy_research_review.md` but deferred.
- Walk-forward / CPCV — `stress_test` gate covers most of the practical concern with much less complexity.
- Half-Kelly sizing — premature given current sample sizes.
- Slack/email alerts.
- Live-trading kill switch driven by divergence script.

---

## 13. Acceptance criteria (one sentence each)

- §1: After warmup fix, `EvaluationContext.load_holdout_bars(symbol, 1440)` returns a series whose 200d SMA is non-NaN at the holdout_start boundary, and `_collect_trades` excludes any trade entered before holdout_start.
- §2: A variant with `catastrophic_stop_pct: 5.0` produces no trades worse than −5% (minus cost) on synthetic data engineered to cause −10% bar moves; same variant with `None` matches the pre-change baseline trade-for-trade.
- §3: `stress_test` gate is opt-in via `enabled: true`, runs the variant against each configured window, and FAILs if any window's MaxDD or worst-trade exceeds limits or DD > 1.3× baseline DD.
- §4: Every validation report ends with a `## Risk profile` section containing symbol contribution, correlation matrix, and stress overlap; `docs/risk_disclosure.md` exists and is linked from `RUNBOOK.md`.
- §5: `compare_live_vs_backtest.py` reads `data/trades.sqlite`, produces a markdown report with one row per (strategy, symbol), bootstrap-CI reproducible with `seed=42`, and a per-row decision tag from {INSUFFICIENT_SAMPLE, DIVERGENCE_AVG, DIVERGENCE_WR, WITHIN_EXPECTATION, UNEXPECTED_PAIR}.
