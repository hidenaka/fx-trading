# Phase A Strategy Rethink — Design Spec

- **Date**: 2026-05-04
- **Owner**: equity_trading bot maintainer
- **Status**: Approved (brainstorming) → ready for writing-plans
- **Trigger**: Post-warmup-fix baseline holdout (2024-05-01 → 2026-05-01) returned **−22.60%/yr / −42.02% MaxDD / worst trade −7.73% / 1136 trades** on `orb_default_v0`. Tail-risk gate REJECTs. Original spec `2026-05-03-validation-improvements-design.md` was implemented through Task 3, then critical path was halted to redesign the strategy.
- **Predecessors**: `2026-05-03-validation-improvements-design.md` (warmup fix already merged on `feature/validation-improvements` as commits 791e131 + 01b295a + 217502a + 2264103 + 1b54243).

---

## 1. Background

Re-running the baseline `orb_default_v0` (ORB on TECL/TQQQ/TNA + LHM on UPRO/UDOW, 25%×3) on the post-warmup-fix holdout reveals the strategy is broken in the 2024-05 → 2026-05 regime: −22.60%/yr with −42% drawdown. The 7-yr in-sample number of +13.75%/yr was driven by 5 high-vol months (2020-06, 2020-07, 2020-11, 2020-12, 2024-11) contributing >$79k of the $118k profit. Outside those months, the system bleeds.

The user picked option **E** (hybrid) from the Q1 fork: first attempt to fix the existing structure with parameter rework (Phase A), and only escalate to new strategies / universe changes (Phase B) if Phase A cannot find a survivable configuration.

This spec covers Phase A only. Phase B is its own brainstorm + spec when triggered.

---

## 2. Goals and non-goals

**Phase A goal**: find a variant of (ORB on TECL/TQQQ/TNA + LHM on UPRO/UDOW) — same strategies, same universe — that clears the **survival threshold** on internal validation:

- annualized return ≥ −3%/yr
- portfolio MaxDD ≤ 20%
- worst single trade ≤ 5%
- Sharpe ≥ −0.3

…on `valid2 = train.loc[2022-01-01 : 2024-04-30]` (28 months including the 2022 hike cycle). The top-by-ann variant clearing all four is then validated against the **holdout** (2024-05-01 → 2026-05-01) **once**.

**Non-goals (deferred to Phase B if triggered)**:

- New strategies (pre-FOMC, pairs trade, Heston-Korajczyk-Sadka intraday momentum, Turn-of-Month).
- Universe changes (drop 3x leverage, add non-US, add fixed income).
- ML / regime classifiers beyond the simple VIX threshold filter.
- Half-Kelly or other dynamic sizing.
- Walk-forward / CPCV cross-validation.

**Holdout discipline**: Phase A reads the holdout exactly once — only when a candidate passes the threshold on valid2. Search and tuning happen on train data alone.

---

## 3. Architecture overview

```
data/prices/                                    # physical layout unchanged
  ├─ train/      (5 yrs: 2019-05 → 2024-04)
  └─ holdout/    (2 yrs: 2024-05 → 2026-05) — read once at the end

Virtual sub-split (code only, no new files on disk):
  train2  = train.loc[2019-05 → 2021-12]   # exploration / fitting
  valid2  = train.loc[2022-01 → 2024-04]   # internal validation, includes 2022 hike
                       │
src/validation/internal_split.py                  ← NEW
  load_train2_bars(root, symbol, tf)
  load_valid2_bars(root, symbol, tf)              # daily prepends 365-day warmup
                       │
src/validation/runner.py                          ← MODIFY (additive)
  _collect_trades_from_split(cfg, root, partition)
                       │
src/strategy/strategies/opening_range_breakout.py ← MODIFY (additive, optional param)
src/strategy/strategies/last_hour_momentum.py     ← MODIFY (additive, optional param)
  vix_halve_threshold param: signals on days with VIX_close > threshold are skipped
                       │
configs/phase_a/                                  ← NEW dir
  v0_capped.yaml                       sizing 25%×3, vix=none, cat_stop=5
  v0_capped_size12.yaml                sizing 12.5%×3, vix=none, cat_stop=5
  v0_capped_concur1.yaml               sizing 25%×1, vix=none, cat_stop=5
  v0_capped_vix22.yaml                 sizing 25%×3, vix=22,   cat_stop=5
  v0_capped_size12_vix22.yaml          sizing 12.5%×3, vix=22, cat_stop=5
  v0_capped_concur1_vix22.yaml         sizing 25%×1, vix=22,   cat_stop=5
                       │
scripts/run_phase_a_search.py                     ← NEW
  Reads all phase_a/*.yaml, runs each on valid2,
  applies survival threshold, picks top-by-ann passing variant.
  Output: phase0/phase_a_search_<date>.md
                       │
existing CLI (unchanged): src/validation/__main__.py
  Final test of winning variant against holdout (1 read)
                       │
phase0/validation/<date>_phase_a_winner_holdout.md
```

No change to: `data.py`, `config.py`, `gates/*`, `report.py`, `manifest.py`, `cli.py` (other than the existing entry point being reused for the final holdout test).

---

## 4. Section §3 — internal_split module

**File**: `equity_trading/src/validation/internal_split.py` (new).

```python
"""Internal train2/valid2 split for Phase A variant search.

train/ partition spans 2019-05-01 → 2024-04-30. We carve it conceptually:
  train2 = 2019-05-01 → 2021-12-31  (~32 months, exploration / fit)
  valid2 = 2022-01-01 → 2024-04-30  (~28 months, internal validation,
                                      includes 2022 hike cycle)

Daily indicators (200d SMA) need warmup. valid2 reads daily from
(VALID2_START - 365 calendar days) so 200d SMA is non-NaN at VALID2_START.
5-min bars need no warmup (ATR(14) fills in 14 bars).
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd

TRAIN2_END = "2021-12-31"
VALID2_START = "2022-01-01"
VALID2_END = "2024-04-30"
WARMUP_DAYS_DAILY = 250


def load_train2_bars(root: Path | str, symbol: str, timeframe_minutes: int) -> pd.DataFrame:
    df = _read_train(root, symbol, timeframe_minutes)
    return df.loc[:TRAIN2_END]


def load_valid2_bars(root: Path | str, symbol: str, timeframe_minutes: int) -> pd.DataFrame:
    df = _read_train(root, symbol, timeframe_minutes)
    if timeframe_minutes == 1440:
        warmup_start = pd.Timestamp(VALID2_START, tz="UTC") - pd.Timedelta(days=365)
        return df.loc[warmup_start:VALID2_END]
    return df.loc[VALID2_START:VALID2_END]


def _read_train(root: Path | str, symbol: str, timeframe_minutes: int) -> pd.DataFrame:
    path = Path(root) / "train" / f"{symbol}_{timeframe_minutes}min.parquet"
    return pd.read_parquet(path)
```

`runner.py` gains an additive function (existing `_collect_trades` is untouched, so the holdout path keeps working unchanged):

```python
def _collect_trades_from_split(cfg, root, partition, *, vix_daily=None):
    """partition: 'train2' or 'valid2'. Reads from train/ via internal_split.
    Filters trades whose entry_ts falls outside the partition window so
    warmup-period signals are not counted. vix_daily, if provided, is
    injected into each strategy's params as '_vix_daily' (consumed by
    strategies with vix_halve_threshold set)."""
    if partition == "train2":
        load_bars = load_train2_bars
        window_start = pd.Timestamp("2019-05-01", tz="UTC")
    elif partition == "valid2":
        load_bars = load_valid2_bars
        window_start = pd.Timestamp(VALID2_START, tz="UTC")
    else:
        raise ValueError(f"Unknown partition: {partition!r}")
    out = []
    for entry in cfg.strategies:
        cls = cfg.resolve_strategy_class(entry["class"])
        for symbol in entry["symbols"]:
            bars_5min = load_bars(root, symbol, timeframe_minutes=5)
            daily = load_bars(root, symbol, timeframe_minutes=1440)
            atr = analyze_atr_distribution(bars_5min, period=14)["median_pct"]
            params = dict(entry["params"])
            params["_daily"] = daily
            if vix_daily is not None:
                params["_vix_daily"] = vix_daily
            cost = params.pop("cost_pct", 0.10)
            cat_stop = params.pop("catastrophic_stop_pct", None)
            _, trades = simulate_strategy(
                strategy=cls(), bars_5min=bars_5min, daily=daily, atr_pct=atr,
                params=params, cost_pct=cost,
                catastrophic_stop_pct=cat_stop, return_trades=True,
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
    df = df[df["entry_ts"] >= window_start]
    df = df.drop_duplicates(subset=["symbol", "entry_ts"], keep="first")
    return df.sort_values("entry_ts").reset_index(drop=True)
```

The function passes `catastrophic_stop_pct` through identically to the holdout path that Task 6 of the predecessor plan defines. (Predecessor plan was halted, but the simulator-level `catastrophic_stop_pct` parameter was already merged in commits 791e131 series; here we depend only on the existing API.)

**Tests** (`tests/test_internal_split.py`):

- `load_train2_bars(root, "TECL", 5)` returns rows whose last index ≤ TRAIN2_END.
- `load_train2_bars(root, "TECL", 1440)` last index ≤ TRAIN2_END.
- `load_valid2_bars(root, "TECL", 1440)` first index is at least 250 trading days before VALID2_START (warmup).
- `load_valid2_bars(root, "TECL", 5)` first index ≥ VALID2_START (no warmup).
- `_collect_trades_from_split(cfg, root, "valid2")` excludes a synthetic trade with `entry_ts == VALID2_START - 1 day`, keeps one with `entry_ts == VALID2_START`.
- `_collect_trades_from_split(cfg, root, "invalid")` raises `ValueError`.
- `_collect_trades_from_split(cfg, root, "valid2", vix_daily=df_vix)` causes each strategy's `params` to include `_vix_daily` at simulate-time (verified by capturing the params via a fake `simulate_strategy`).

---

## 5. Section §4-A — VIX-regime filter

**Files**: `src/strategy/strategies/opening_range_breakout.py`, `src/strategy/strategies/last_hour_momentum.py`.

Both strategies gain an optional `vix_halve_threshold` parameter. Despite the name (kept for descriptive clarity), the implementation **skips entry signals on days where the daily VIX close exceeds the threshold**. Skip is operationally simpler than dynamic position-size halving (the simulator works with uniform position sizes) and has comparable tail-risk reduction.

For ORB, append after the existing `signal = first_breakout & daily_above_ma`:

```python
vix_halve_threshold = params.get("vix_halve_threshold")
if vix_halve_threshold is not None and "_vix_daily" in params:
    vix = params["_vix_daily"]
    ny_date = pd.Series(
        bars_5min.index.tz_convert("America/New_York").date,
        index=bars_5min.index,
    )
    vix_dict = {d.date(): v for d, v in vix["close"].items()}
    vix_high_mask = ny_date.map(vix_dict) > vix_halve_threshold
    signal = signal & ~vix_high_mask.fillna(False)
```

LHM same pattern after its `signal = is_signal_bar & is_bullish_yesterday`.

`_vix_daily` parameter is already a convention in `run_portfolio_ensemble.py` (passed via `augmented["_vix_daily"]`). The Phase A search runner injects it from `data/prices/VIX_1day_2019-05-01_2026-05-01.parquet` (file already exists).

**Tests** (extension to existing `test_strategy_opening_range_breakout.py` and `test_strategy_last_hour_momentum.py`):

- `vix_halve_threshold=None` (default) → output identical to current implementation (regression).
- `vix_halve_threshold=22.0` + synthetic VIX with three high-VIX days (close > 22) → signals on those three days are zero, others unchanged.
- `vix_halve_threshold=22.0` + missing `_vix_daily` in params → silent no-op (no error). Documented behavior so the strategy can run on data that pre-dates VIX cache.

---

## 6. Section §4-B — Phase A variant configs

**Directory**: `equity_trading/configs/phase_a/` (new). Six YAML files, each derived from `orb_default_v0.yaml` with `catastrophic_stop_pct: 5.0` added to every strategy's `params` and one of three sizing × one of two VIX-filter dimensions:

| filename | position_size_pct × max_concurrent | vix_halve_threshold |
|---|:---:|:---:|
| `v0_capped.yaml` | 0.25 × 3 | none |
| `v0_capped_size12.yaml` | 0.125 × 3 | none |
| `v0_capped_concur1.yaml` | 0.25 × 1 | none |
| `v0_capped_vix22.yaml` | 0.25 × 3 | 22 |
| `v0_capped_size12_vix22.yaml` | 0.125 × 3 | 22 |
| `v0_capped_concur1_vix22.yaml` | 0.25 × 1 | 22 |

Each YAML carries `parent_baseline: orb_default_v0` and `variant_id` matching the filename stem. All six retain the existing `gates` block from `orb_default_v0.yaml` so the holdout test (when reached) uses the same gate thresholds.

Concrete example (`v0_capped_size12_vix22.yaml`):

```yaml
variant_id: orb_default_v0_capped_size12_vix22
description: |
  Phase A search candidate: catastrophic_stop_pct=5.0, sizing=12.5%×3,
  vix_halve_threshold=22.0. Searches for survivable variant under the
  Q2(A) threshold on internal valid2 (2022-01 → 2024-04).
parent_baseline: orb_default_v0
strategies:
  - class: OpeningRangeBreakoutStrategy
    symbols: [TECL, TQQQ, TNA]
    params:
      or_window_bars: 12
      stop_mult: 0.0
      target_mult: 1.0
      cost_pct: 0.10
      catastrophic_stop_pct: 5.0
      vix_halve_threshold: 22.0
  - class: LastHourMomentumStrategy
    symbols: [UPRO, UDOW]
    params:
      threshold: 0.003
      _max_hold_bars: 60
      cost_pct: 0.10
      catastrophic_stop_pct: 5.0
      vix_halve_threshold: 22.0
portfolio:
  position_size_pct: 0.125
  max_concurrent: 3
  starting_equity_usd: 100000
gates:
  oos: { holdout_start: "2024-05-01", holdout_end: "2026-05-01", min_outperformance_pct: 0.0 }
  tail_risk: { max_single_trade_loss_pct: 5.0, max_portfolio_dd_pct: 20.0, max_rolling_30d_loss_pct: 10.0 }
  sample_size: { min_holdout_trades: 30 }
```

**Tests** (`tests/test_phase_a_configs.py`):

- `glob("configs/phase_a/*.yaml")` returns exactly 6 files matching the table above.
- All 6 load via `load_variant_config` without error.
- All 6 have `catastrophic_stop_pct == 5.0` on every strategy entry.
- All 6 have `parent_baseline == "orb_default_v0"`.
- `variant_id` matches filename stem for each.

---

## 7. Section §5 — Phase A search runner

**File**: `equity_trading/scripts/run_phase_a_search.py` (new).

**CLI**:

```bash
python3 equity_trading/scripts/run_phase_a_search.py \
    --configs-dir equity_trading/configs/phase_a/ \
    --data-root equity_trading/data/prices \
    --output equity_trading/phase0/phase_a_search_$(date +%Y-%m-%d).md
```

**Pipeline**:

1. `Path(configs_dir).glob("*.yaml")` → 6 paths. For each, `load_variant_config`.
2. Load VIX daily once: `pd.read_parquet(data_root / "VIX_1day_2019-05-01_2026-05-01.parquet")`. Hold as a local `vix_daily`.
3. For each variant: `_collect_trades_from_split(cfg, data_root, "valid2", vix_daily=vix_daily)` → trades. The function injects `_vix_daily` into each strategy's params before calling `simulate_strategy`. Then `_simulate_portfolio(trades, starting=cfg.portfolio.starting_equity_usd, size=cfg.portfolio.position_size_pct, concur=cfg.portfolio.max_concurrent)` → summary.
4. Compute also `worst_trade_pct = trades["pnl_pct"].min() * 100`.
5. Apply `_eval_threshold(summary, worst_trade_pct)` → list of failing axes.
6. Render markdown:

```markdown
# Phase A search — internal valid (2022-01-01 → 2024-04-30)

**Threshold (Q2 A)**: ann ≥ -3%/yr, MaxDD ≤ 20%, worst trade ≤ 5%, Sharpe ≥ -0.3

| variant | ann | MaxDD | worst | Sharpe | n trades | passes? |
|---|---:|---:|---:|---:|---:|:---:|
| v0_capped | … | … | … | … | … | ❌/✅ |
…

## Top by ann return (passing only): **<variant_id>** (+X.X%/yr)

→ Run holdout test:
\`\`\`
python3 -m equity_trading.src.validation \
    --variant equity_trading/configs/phase_a/<winner>.yaml \
    --baseline equity_trading/configs/orb_default_v0.yaml \
    --output equity_trading/phase0/validation/<date>_phase_a_winner_holdout.md
\`\`\`
```

If zero variants pass, render `## No candidate passes` and a paragraph pointing to escalation step 2 (per §8 below).

**Threshold function**:

```python
def _eval_threshold(summary: dict, worst_trade_pct: float) -> list[str]:
    fails = []
    if summary["annualized_pct"] < -3.0:
        fails.append("ann")
    if abs(summary["max_dd_pct"]) > 20.0:
        fails.append("MaxDD")
    if abs(worst_trade_pct) > 5.0:
        fails.append("worst")
    if summary["sharpe"] < -0.3:
        fails.append("Sharpe")
    return fails
```

**Tests** (`tests/test_run_phase_a_search.py`):

- `_eval_threshold` boundary cases for each of the 4 axes (just above / just below limit).
- All-pass synthetic summary → empty fails list.
- All-fail synthetic summary → all four labels in fails.
- End-to-end smoke: with synthetic `configs/phase_a/` containing 1 yaml + synthetic train data → script runs to completion, produces non-empty markdown with either "## Top by ann return" or "## No candidate passes" header.
- **Holdout-leak guard**: monkeypatch `EvaluationContext` and `EvaluationContext.load_holdout_bars` to raise; run search; expect zero raise. Codifies "Phase A search must not read holdout."

---

## 8. Section §6 — Implementation order and escalation

```
[1] §3 internal_split.py + load_train2/valid2 + _collect_trades_from_split
       │
       ▼
[2] §4-A VIX-regime filter for ORB and LHM
       │
       ▼
[3] §4-B 6 yaml configs in configs/phase_a/
       │
       ▼
[4] §5 run_phase_a_search.py + _eval_threshold
       │
       ▼
[5] EXECUTE: run_phase_a_search → phase0/phase_a_search_<date>.md
       │
       ▼
[6] decision:
    ≥1 candidate passes threshold on valid2?
         │
    yes ───→ [7a] top-by-ann holdout-validate (1 read)
         │            │
         │       gate REJECT?
         │       no ──── deploy candidate confirmed
         │       yes ─── treat as Phase A failure → escalate
         │
    no  ───→ [7b] expand to step 2 (12 candidates):
                   add target_mult ∈ {1.0, 1.5} dimension
                   re-run [5]
                   │
                   if still no pass → step 3 (24 candidates):
                   add daily_halt_pct ∈ {2.0, 1.0} dimension
                   re-run [5]
                   │
                   if still no pass → Phase B brainstorm (separate spec)
```

**holdout-once invariant**: The holdout is read exactly once across the entire Phase A pipeline — at step [7a]. Steps [1]–[6], [7b] expansions, and any internal valid re-runs use only train data.

**Phase B trigger**: only when step 3 (24 candidates) produces zero passing variants. At that point the universe (5 × 3x leveraged US equity ETFs) is empirically shown not to generalize; new strategies / universe expansion is the only remaining lever. Phase B requires its own brainstorm + spec.

---

## 9. Section §7 — Test strategy

| File | Coverage | New / Existing |
|---|---|---|
| `tests/test_internal_split.py` | §3 module | new |
| `tests/test_strategy_opening_range_breakout.py` | §4-A VIX filter on ORB | extend existing |
| `tests/test_strategy_last_hour_momentum.py` | §4-A VIX filter on LHM | extend existing |
| `tests/test_phase_a_configs.py` | §4-B six yaml configs | new |
| `tests/test_run_phase_a_search.py` | §5 search runner + holdout-leak guard | new |

**Regression**: existing tests for ORB / LHM / `simulate_strategy` / `_collect_trades` / `validation_runner` / `validation_report` must keep passing with no edits. The VIX param is optional (default `None`), the new `_collect_trades_from_split` is additive, no existing API changes.

**Coverage target**: ≥ 90% on new code.

**Holdout-leak codification**: the `test_phase_a_search_does_not_read_holdout` monkeypatch test is the single most important safety net for Phase A. It must remain green for all subsequent Phase A iterations (steps 7b expansions).

**Run command**:

```bash
cd /Users/hideakimacbookair/自動トレード
python3 -m pytest equity_trading/tests/ -v
```

Followed by the manual E2E:

```bash
cd /Users/hideakimacbookair/自動トレード/.worktrees/validation-improvements
python3 equity_trading/scripts/run_phase_a_search.py \
    --output equity_trading/phase0/phase_a_search_$(date +%Y-%m-%d).md
```

---

## 10. Out of scope (explicit)

- New strategies (any of: pre-FOMC, pairs, HKS intraday momentum, TOM).
- Universe expansion beyond TECL/TQQQ/TNA/UPRO/UDOW.
- Dynamic position sizing (fractional Kelly, vol-targeting).
- ML / regime classifiers beyond VIX threshold.
- Walk-forward, CPCV, deflated Sharpe.
- Slack / email alerts on divergence.
- The remaining tasks from the predecessor spec `2026-05-03-validation-improvements-design.md` (catastrophic_stop integration in simulator was completed; stress_test gate, risk_profile, compare_live_vs_backtest are deferred to post-Phase-A — they are still useful but not on the critical path to "is the bot deployable").

---

## 11. Acceptance criteria (one sentence each)

- §3: `load_train2_bars` and `load_valid2_bars` return the documented date ranges; `_collect_trades_from_split` with `partition="valid2"` excludes any trade entered before `VALID2_START`.
- §4-A: ORB and LHM with `vix_halve_threshold=22.0` produce zero signals on synthetic high-VIX days; with `vix_halve_threshold=None` (or omitted) produce identical signals to the pre-change implementation.
- §4-B: `configs/phase_a/` contains exactly the 6 listed YAMLs; all load successfully and all carry `catastrophic_stop_pct: 5.0` on every strategy.
- §5: `run_phase_a_search.py` produces a markdown report ranking the 6 variants on valid2, applies the four-axis threshold, and either declares `## Top by ann return: <variant_id>` (passing case) or `## No candidate passes` (failing case); a unit test enforces it never calls `EvaluationContext.load_holdout_bars`.
- Pipeline: Phase A succeeds when one variant clears the threshold on valid2 AND survives the existing OOS + tail_risk + sample_size gates on the holdout. If step 3 (24 candidates) still produces zero passers, Phase A is declared insufficient and Phase B is triggered.

---

## 12. Predecessor compatibility

The warmup fix (commits 791e131 + 01b295a + 217502a + 2264103 + 1b54243 on `feature/validation-improvements`) is required for this spec. `_collect_trades` already filters by `holdout_start`; `EvaluationContext` already prepends 250 daily warmup rows; `simulate_strategy` already accepts `catastrophic_stop_pct`. This spec depends on those merged changes and is built on the same branch.

The deferred items from the predecessor spec (`stress_test` gate, `risk_profile` auto-section, `compare_live_vs_backtest` script, `risk_disclosure.md`) remain valuable and can be picked up in parallel or after Phase A produces a deploy candidate. They are **not** required to determine whether Phase A succeeds.
