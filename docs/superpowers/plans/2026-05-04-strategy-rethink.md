# Phase A Strategy Rethink — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Find a survivable variant of (ORB on TECL/TQQQ/TNA + LHM on UPRO/UDOW) by adding `catastrophic_stop_pct=5.0`, varying sizing, and adding an optional VIX-regime filter, then evaluate 6 candidates against an internal valid2 partition (2022-01 → 2024-04). The winning candidate gets one final holdout test.

**Architecture:** Virtual `train2`/`valid2` split inside the existing `train/` parquets (no new physical partition). Strategies gain an optional `vix_halve_threshold` param. A new `run_phase_a_search.py` script runs all 6 variants on `valid2` only and applies the four-axis threshold from spec §1. Holdout is read exactly once, only if a candidate passes the threshold.

**Tech Stack:** Python 3.12, pandas, pyyaml, pytest.

**Repo paths** (anchored at `/Users/hideakimacbookair/自動トレード/.worktrees/validation-improvements` — the active feature worktree on branch `feature/validation-improvements`):
- Source: `equity_trading/src/`
- Tests: `equity_trading/tests/`
- Configs: `equity_trading/configs/`
- Scripts: `equity_trading/scripts/`
- Reports: `equity_trading/phase0/`
- VIX cache: `equity_trading/data/prices/VIX_1day_2019-05-01_2026-05-01.parquet`

**Test command** (run from worktree root):
```
python3 -m pytest equity_trading/tests/<file>.py -v
```

**Predecessor branch state:** `feature/validation-improvements` already contains the warmup fix (commits 791e131, 01b295a, 217502a, 2264103, 1b54243). `simulate_strategy` already accepts `catastrophic_stop_pct`. `EvaluationContext` already prepends 250 daily warmup rows. `_collect_trades` already filters by `holdout_start`.

---

## Task 1: §3 internal_split module — load_train2 and load_valid2

**Files:**
- Create: `equity_trading/src/validation/internal_split.py`
- Create: `equity_trading/tests/test_internal_split.py`

- [ ] **Step 1.1: Write failing test**

Create `equity_trading/tests/test_internal_split.py`:

```python
"""Internal train2/valid2 split for Phase A variant search."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


def _write_daily(path: Path, start: str, end: str) -> None:
    ts = pd.date_range(start, end, freq="1D", tz="UTC")
    df = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5,
                        "volume": 1000}, index=ts)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)


def _write_5min(path: Path, start: str, end: str) -> None:
    ts = pd.date_range(start, end, freq="5min", tz="UTC")
    df = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5,
                        "volume": 1000}, index=ts)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)


def test_load_train2_daily_ends_at_2021_12_31(tmp_path):
    from equity_trading.src.validation.internal_split import load_train2_bars
    _write_daily(tmp_path / "train" / "TECL_1440min.parquet",
                  "2019-05-01", "2024-04-30")
    df = load_train2_bars(tmp_path, "TECL", timeframe_minutes=1440)
    assert df.index[-1] <= pd.Timestamp("2021-12-31", tz="UTC")
    assert df.index[0] == pd.Timestamp("2019-05-01", tz="UTC")


def test_load_train2_5min_ends_at_2021_12_31(tmp_path):
    from equity_trading.src.validation.internal_split import load_train2_bars
    _write_5min(tmp_path / "train" / "TECL_5min.parquet",
                 "2019-05-01", "2024-04-30")
    df = load_train2_bars(tmp_path, "TECL", timeframe_minutes=5)
    assert df.index[-1] <= pd.Timestamp("2021-12-31 23:59:59", tz="UTC")


def test_load_valid2_daily_prepends_warmup(tmp_path):
    from equity_trading.src.validation.internal_split import load_valid2_bars
    _write_daily(tmp_path / "train" / "TECL_1440min.parquet",
                  "2019-05-01", "2024-04-30")
    df = load_valid2_bars(tmp_path, "TECL", timeframe_minutes=1440)
    # warmup_start = VALID2_START - 365 calendar days = 2021-01-01
    assert df.index[0] <= pd.Timestamp("2021-01-02", tz="UTC")
    assert df.index[0] >= pd.Timestamp("2020-12-31", tz="UTC")
    assert df.index[-1] == pd.Timestamp("2024-04-30", tz="UTC")


def test_load_valid2_5min_no_warmup(tmp_path):
    from equity_trading.src.validation.internal_split import load_valid2_bars
    _write_5min(tmp_path / "train" / "TECL_5min.parquet",
                 "2019-05-01", "2024-04-30")
    df = load_valid2_bars(tmp_path, "TECL", timeframe_minutes=5)
    assert df.index[0] >= pd.Timestamp("2022-01-01", tz="UTC")
    assert df.index[-1] <= pd.Timestamp("2024-04-30 23:59:59", tz="UTC")
```

- [ ] **Step 1.2: Run tests to verify they fail**

Run: `python3 -m pytest equity_trading/tests/test_internal_split.py -v`

Expected: all 4 FAIL — `ModuleNotFoundError: No module named 'equity_trading.src.validation.internal_split'`.

- [ ] **Step 1.3: Implement module**

Create `equity_trading/src/validation/internal_split.py`:

```python
"""Internal train2/valid2 split for Phase A variant search.

train/ partition spans 2019-05-01 through 2024-04-30. We carve it conceptually:
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
    """train2 = train_full[:TRAIN2_END]. Same slicing for 5min and daily."""
    df = _read_train(root, symbol, timeframe_minutes)
    return df.loc[:TRAIN2_END]


def load_valid2_bars(root: Path | str, symbol: str, timeframe_minutes: int) -> pd.DataFrame:
    """valid2 = train_full[VALID2_START:VALID2_END]. Daily prepends 365-day
    calendar warmup so 200d SMA is non-NaN at VALID2_START."""
    df = _read_train(root, symbol, timeframe_minutes)
    if timeframe_minutes == 1440:
        warmup_start = pd.Timestamp(VALID2_START, tz="UTC") - pd.Timedelta(days=365)
        return df.loc[warmup_start:VALID2_END]
    return df.loc[VALID2_START:VALID2_END]


def _read_train(root: Path | str, symbol: str, timeframe_minutes: int) -> pd.DataFrame:
    path = Path(root) / "train" / f"{symbol}_{timeframe_minutes}min.parquet"
    return pd.read_parquet(path)
```

- [ ] **Step 1.4: Run tests to verify they pass**

Run: `python3 -m pytest equity_trading/tests/test_internal_split.py -v`

Expected: 4 passed.

- [ ] **Step 1.5: Commit**

```
git add equity_trading/src/validation/internal_split.py equity_trading/tests/test_internal_split.py
git commit -m "feat(validation): internal train2/valid2 split for Phase A search (Task 1)"
```

---

## Task 2: §3 runner._collect_trades_from_split

**Files:**
- Modify: `equity_trading/src/validation/runner.py` (additive function)
- Test: `equity_trading/tests/test_validation_runner.py` (extend)

- [ ] **Step 2.1: Write failing tests**

Append to `equity_trading/tests/test_validation_runner.py`:

```python
def test_collect_trades_from_split_rejects_unknown_partition(tmp_path):
    from equity_trading.src.validation.runner import _collect_trades_from_split
    from equity_trading.src.validation.config import VariantConfig
    cfg = VariantConfig(
        variant_id="t", description="",
        strategies=[{"class": "OpeningRangeBreakoutStrategy", "symbols": ["TECL"], "params": {}}],
        portfolio={"position_size_pct": 0.25, "max_concurrent": 3, "starting_equity_usd": 100000},
        gates={"oos": {"holdout_start": "2024-05-01", "holdout_end": "2026-05-01", "min_outperformance_pct": 0.0},
                "tail_risk": {"max_single_trade_loss_pct": 5.0, "max_portfolio_dd_pct": 20.0, "max_rolling_30d_loss_pct": 10.0},
                "sample_size": {"min_holdout_trades": 30}},
    )
    with pytest.raises(ValueError, match="Unknown partition"):
        _collect_trades_from_split(cfg, tmp_path, "invalid")


def test_collect_trades_from_split_excludes_pre_valid2_signals(monkeypatch, tmp_path):
    """A synthetic trade with entry_ts < VALID2_START must be dropped."""
    import equity_trading.src.validation.runner as R
    from equity_trading.src.validation.config import VariantConfig
    from equity_trading.src.validation.internal_split import VALID2_START

    valid2_start = pd.Timestamp(VALID2_START, tz="UTC")
    fake_trades = pd.DataFrame({
        "entry_ts": [valid2_start - pd.Timedelta(days=30),
                      valid2_start + pd.Timedelta(days=1),
                      valid2_start + pd.Timedelta(days=10)],
        "exit_ts":  [valid2_start - pd.Timedelta(days=29),
                      valid2_start + pd.Timedelta(days=1, hours=1),
                      valid2_start + pd.Timedelta(days=10, hours=1)],
        "entry_price": [100.0, 100.0, 100.0],
        "exit_price":  [101.0, 101.0, 101.0],
        "exit_type":   ["target", "target", "target"],
        "bars_held":   [12, 12, 12],
        "pnl_pct":     [0.01, 0.01, 0.01],
    })
    monkeypatch.setattr(R, "simulate_strategy",
                         lambda **kw: ({}, fake_trades))
    monkeypatch.setattr(R, "analyze_atr_distribution",
                         lambda b, period=14: {"median_pct": 0.2})
    # Stub the internal_split loaders so we don't need parquet files.
    import equity_trading.src.validation.internal_split as IS
    monkeypatch.setattr(IS, "load_valid2_bars", lambda r, s, timeframe_minutes: pd.DataFrame())

    cfg = VariantConfig(
        variant_id="t", description="",
        strategies=[{"class": "OpeningRangeBreakoutStrategy", "symbols": ["TECL"], "params": {}}],
        portfolio={"position_size_pct": 0.25, "max_concurrent": 3, "starting_equity_usd": 100000},
        gates={"oos": {"holdout_start": "2024-05-01", "holdout_end": "2026-05-01", "min_outperformance_pct": 0.0},
                "tail_risk": {"max_single_trade_loss_pct": 5.0, "max_portfolio_dd_pct": 20.0, "max_rolling_30d_loss_pct": 10.0},
                "sample_size": {"min_holdout_trades": 30}},
    )
    result = R._collect_trades_from_split(cfg, tmp_path, "valid2")
    assert len(result) == 2
    assert (result["entry_ts"] >= valid2_start).all()


def test_collect_trades_from_split_injects_vix_daily(monkeypatch, tmp_path):
    """vix_daily kwarg propagates into each strategy's params dict."""
    import equity_trading.src.validation.runner as R
    from equity_trading.src.validation.config import VariantConfig

    captured_params: list[dict] = []

    def _fake_simulate(**kwargs):
        captured_params.append(dict(kwargs["params"]))
        return ({}, pd.DataFrame(columns=["entry_ts", "exit_ts", "pnl_pct"]))

    monkeypatch.setattr(R, "simulate_strategy", _fake_simulate)
    monkeypatch.setattr(R, "analyze_atr_distribution",
                         lambda b, period=14: {"median_pct": 0.2})
    import equity_trading.src.validation.internal_split as IS
    monkeypatch.setattr(IS, "load_valid2_bars", lambda r, s, timeframe_minutes: pd.DataFrame())

    cfg = VariantConfig(
        variant_id="t", description="",
        strategies=[{"class": "OpeningRangeBreakoutStrategy", "symbols": ["TECL"], "params": {}}],
        portfolio={"position_size_pct": 0.25, "max_concurrent": 3, "starting_equity_usd": 100000},
        gates={"oos": {"holdout_start": "2024-05-01", "holdout_end": "2026-05-01", "min_outperformance_pct": 0.0},
                "tail_risk": {"max_single_trade_loss_pct": 5.0, "max_portfolio_dd_pct": 20.0, "max_rolling_30d_loss_pct": 10.0},
                "sample_size": {"min_holdout_trades": 30}},
    )
    fake_vix = pd.DataFrame({"close": [20.0]},
                             index=pd.date_range("2022-01-01", periods=1, freq="1D", tz="UTC"))
    R._collect_trades_from_split(cfg, tmp_path, "valid2", vix_daily=fake_vix)
    assert len(captured_params) == 1
    assert "_vix_daily" in captured_params[0]
    assert captured_params[0]["_vix_daily"] is fake_vix
```

- [ ] **Step 2.2: Run tests to verify they fail**

Run: `python3 -m pytest equity_trading/tests/test_validation_runner.py::test_collect_trades_from_split_rejects_unknown_partition equity_trading/tests/test_validation_runner.py::test_collect_trades_from_split_excludes_pre_valid2_signals equity_trading/tests/test_validation_runner.py::test_collect_trades_from_split_injects_vix_daily -v`

Expected: all 3 FAIL — `cannot import name '_collect_trades_from_split'`.

- [ ] **Step 2.3: Implement function**

In `equity_trading/src/validation/runner.py`, add at the end of the file:

```python
from equity_trading.src.validation.internal_split import (
    VALID2_START,
    load_train2_bars,
    load_valid2_bars,
)


def _collect_trades_from_split(
    cfg: VariantConfig,
    root,
    partition: str,
    *,
    vix_daily: pd.DataFrame | None = None,
) -> pd.DataFrame:
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

    out: list[pd.DataFrame] = []
    for entry in cfg.strategies:
        cls = cfg.resolve_strategy_class(entry["class"])
        for symbol in entry["symbols"]:
            bars_5min = load_bars(root, symbol, timeframe_minutes=5)
            daily = load_bars(root, symbol, timeframe_minutes=1440)
            atr = analyze_atr_distribution(bars_5min, period=14)["median_pct"] if len(bars_5min) > 0 else 0.0
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

- [ ] **Step 2.4: Run tests to verify they pass**

Run: `python3 -m pytest equity_trading/tests/test_validation_runner.py -v`

Expected: all tests in the file pass (existing 2 + new 3 = 5).

- [ ] **Step 2.5: Commit**

```
git add equity_trading/src/validation/runner.py equity_trading/tests/test_validation_runner.py
git commit -m "feat(validation): _collect_trades_from_split for Phase A search (Task 2)"
```

---

## Task 3: §4-A VIX-regime filter on ORB strategy

**Files:**
- Modify: `equity_trading/src/strategy/strategies/opening_range_breakout.py` (additive in `compute_entry_signal`)
- Test: `equity_trading/tests/test_strategy_opening_range_breakout.py` (extend)

- [ ] **Step 3.1: Write failing tests**

Append to `equity_trading/tests/test_strategy_opening_range_breakout.py`:

```python
def test_orb_vix_threshold_none_unchanged(_):  # _ = whatever fixture pattern is used
    """vix_halve_threshold=None (default) reproduces the pre-change signal stream."""
    pass  # placeholder — see Step 3.1 actual test below


def test_orb_vix_filter_suppresses_signals_on_high_vix_days():
    """With vix_halve_threshold=22.0, signals on synthetic high-VIX days are zero."""
    from equity_trading.src.strategy.strategies.opening_range_breakout import (
        OpeningRangeBreakoutStrategy,
    )
    import pandas as pd
    import numpy as np

    # 2 trading days × 78 bars (full RTH session) of 5-min data
    day1_idx = pd.date_range("2024-01-02 14:30", periods=78, freq="5min", tz="UTC")
    day2_idx = pd.date_range("2024-01-03 14:30", periods=78, freq="5min", tz="UTC")
    idx = day1_idx.union(day2_idx)
    # Construct prices that breakout cleanly after OR window on both days.
    closes = np.concatenate([
        np.linspace(100, 105, 78),  # day 1: rising → breakout
        np.linspace(100, 105, 78),  # day 2: rising → breakout
    ])
    bars = pd.DataFrame({
        "open": closes, "high": closes + 0.5, "low": closes - 0.5,
        "close": closes, "volume": [10000] * len(closes),
    }, index=idx)
    daily = pd.DataFrame({
        "close": [100.0] * 250 + [102.0, 103.0],
    }, index=pd.date_range("2023-04-01", periods=252, freq="1D", tz="UTC"))
    # Synthetic VIX: day 1 close = 30 (HIGH), day 2 close = 15 (LOW)
    vix = pd.DataFrame({
        "close": [30.0, 15.0],
    }, index=pd.to_datetime(["2024-01-02", "2024-01-03"], utc=True))

    s = OpeningRangeBreakoutStrategy()
    sig_unfiltered = s.compute_entry_signal(bars, daily, atr_pct=0.5, params={
        "or_window_bars": 12,
    })
    sig_filtered = s.compute_entry_signal(bars, daily, atr_pct=0.5, params={
        "or_window_bars": 12,
        "vix_halve_threshold": 22.0,
        "_vix_daily": vix,
    })
    # Map signals back to NY date to count by day.
    ny_dates = bars.index.tz_convert("America/New_York").date
    day1_idx_mask = pd.Series(ny_dates == ny_dates[0], index=bars.index)
    day2_idx_mask = pd.Series(ny_dates == ny_dates[-1], index=bars.index)
    # Day 1: VIX 30 > 22 → all signals suppressed
    assert sig_filtered[day1_idx_mask].sum() == 0
    # Day 2: VIX 15 < 22 → signal preserved
    assert sig_filtered[day2_idx_mask].sum() == sig_unfiltered[day2_idx_mask].sum()


def test_orb_vix_threshold_omitted_unchanged():
    """vix_halve_threshold not in params → identical to pre-change behavior."""
    from equity_trading.src.strategy.strategies.opening_range_breakout import (
        OpeningRangeBreakoutStrategy,
    )
    import pandas as pd
    import numpy as np
    idx = pd.date_range("2024-01-02 14:30", periods=78, freq="5min", tz="UTC")
    closes = np.linspace(100, 105, 78)
    bars = pd.DataFrame({
        "open": closes, "high": closes + 0.5, "low": closes - 0.5,
        "close": closes, "volume": [10000] * 78,
    }, index=idx)
    daily = pd.DataFrame({
        "close": [100.0] * 250 + [102.0],
    }, index=pd.date_range("2023-04-01", periods=251, freq="1D", tz="UTC"))
    s = OpeningRangeBreakoutStrategy()
    sig_a = s.compute_entry_signal(bars, daily, atr_pct=0.5, params={"or_window_bars": 12})
    sig_b = s.compute_entry_signal(bars, daily, atr_pct=0.5, params={
        "or_window_bars": 12,
        "vix_halve_threshold": 22.0,
        # _vix_daily intentionally absent
    })
    # No VIX data → silent no-op, signals identical
    assert (sig_a == sig_b).all()
```

Replace the first `def test_orb_vix_threshold_none_unchanged` placeholder (the one with `pass`) with actual content — the `test_orb_vix_threshold_omitted_unchanged` test above already covers the same intent. Delete the placeholder; keep only the two real tests.

- [ ] **Step 3.2: Run tests to verify they fail**

Run: `python3 -m pytest equity_trading/tests/test_strategy_opening_range_breakout.py::test_orb_vix_filter_suppresses_signals_on_high_vix_days equity_trading/tests/test_strategy_opening_range_breakout.py::test_orb_vix_threshold_omitted_unchanged -v`

Expected: `test_orb_vix_filter_suppresses_signals_on_high_vix_days` FAILS (suppression assertion: signal on day 1 is non-zero because VIX filter doesn't exist). `test_orb_vix_threshold_omitted_unchanged` PASSES (omitted param is currently silently ignored).

- [ ] **Step 3.3: Implement VIX filter**

Modify `equity_trading/src/strategy/strategies/opening_range_breakout.py::compute_entry_signal`. After the line `signal = first_breakout & daily_above_ma` (around line 60), add:

```python
        vix_halve_threshold = params.get("vix_halve_threshold")
        if vix_halve_threshold is not None and "_vix_daily" in params:
            vix = params["_vix_daily"]
            ny_date = pd.Series(
                bars_5min.index.tz_convert("America/New_York").date,
                index=bars_5min.index,
            )
            vix_dict = {ts.date(): float(c) for ts, c in vix["close"].items()}
            vix_high_mask = ny_date.map(vix_dict).fillna(0) > vix_halve_threshold
            signal = signal & ~vix_high_mask
```

The `.fillna(0)` ensures days without VIX data become "VIX = 0" (i.e. not high), so they pass through unchanged.

- [ ] **Step 3.4: Run tests to verify they pass**

Run: `python3 -m pytest equity_trading/tests/test_strategy_opening_range_breakout.py -v`

Expected: all tests pass (the existing 6 + the 2 new = 8).

- [ ] **Step 3.5: Commit**

```
git add equity_trading/src/strategy/strategies/opening_range_breakout.py equity_trading/tests/test_strategy_opening_range_breakout.py
git commit -m "feat(orb): optional vix_halve_threshold filter (Task 3)"
```

---

## Task 4: §4-A VIX-regime filter on LHM strategy

**Files:**
- Modify: `equity_trading/src/strategy/strategies/last_hour_momentum.py` (additive)
- Create: `equity_trading/tests/test_strategy_last_hour_momentum.py` (new — no existing test file)

- [ ] **Step 4.1: Write failing test**

Create `equity_trading/tests/test_strategy_last_hour_momentum.py`:

```python
"""LastHourMomentumStrategy tests."""
from __future__ import annotations

import numpy as np
import pandas as pd

from equity_trading.src.strategy.strategies.last_hour_momentum import (
    LastHourMomentumStrategy,
)


def _bars_with_bullish_yesterday_close():
    """Two NY days. Day 0 (yesterday): last 30-min strongly up.
    Day 1 (today): bar 0 is the signal candidate."""
    day0_idx = pd.date_range("2024-01-02 14:30", periods=78, freq="5min", tz="UTC")
    day1_idx = pd.date_range("2024-01-03 14:30", periods=78, freq="5min", tz="UTC")
    idx = day0_idx.append(day1_idx)
    closes = np.concatenate([
        np.linspace(100, 100, 72),       # day 0 bars 0..71 flat
        np.linspace(100, 105, 6),        # day 0 bars 72..77 up 5%
        np.full(78, 105.0),              # day 1 flat
    ])
    return pd.DataFrame({
        "open": closes, "high": closes + 0.1, "low": closes - 0.1,
        "close": closes, "volume": [10000] * len(closes),
    }, index=idx)


def test_lhm_signals_at_today_bar_0_when_yesterday_bullish():
    bars = _bars_with_bullish_yesterday_close()
    daily = pd.DataFrame({"close": [100.0]},
                          index=pd.date_range("2024-01-01", periods=1, freq="1D", tz="UTC"))
    s = LastHourMomentumStrategy()
    sig = s.compute_entry_signal(bars, daily, atr_pct=0.2, params={"threshold": 0.001})
    # signal exists somewhere on day 1
    day1_mask = bars.index >= pd.Timestamp("2024-01-03 14:30", tz="UTC")
    assert sig[day1_mask].any()


def test_lhm_vix_filter_suppresses_high_vix_day():
    bars = _bars_with_bullish_yesterday_close()
    daily = pd.DataFrame({"close": [100.0]},
                          index=pd.date_range("2024-01-01", periods=1, freq="1D", tz="UTC"))
    # VIX on the signal day (Jan 3 NY) = 30 (HIGH); on Jan 2 = 15
    vix = pd.DataFrame({"close": [15.0, 30.0]},
                        index=pd.to_datetime(["2024-01-02", "2024-01-03"], utc=True))
    s = LastHourMomentumStrategy()
    sig_unfiltered = s.compute_entry_signal(bars, daily, atr_pct=0.2,
                                              params={"threshold": 0.001})
    sig_filtered = s.compute_entry_signal(bars, daily, atr_pct=0.2, params={
        "threshold": 0.001,
        "vix_halve_threshold": 22.0,
        "_vix_daily": vix,
    })
    day1_mask = bars.index >= pd.Timestamp("2024-01-03 14:30", tz="UTC")
    assert sig_unfiltered[day1_mask].any()
    assert sig_filtered[day1_mask].sum() == 0


def test_lhm_vix_threshold_omitted_unchanged():
    bars = _bars_with_bullish_yesterday_close()
    daily = pd.DataFrame({"close": [100.0]},
                          index=pd.date_range("2024-01-01", periods=1, freq="1D", tz="UTC"))
    s = LastHourMomentumStrategy()
    sig_a = s.compute_entry_signal(bars, daily, atr_pct=0.2, params={"threshold": 0.001})
    sig_b = s.compute_entry_signal(bars, daily, atr_pct=0.2, params={
        "threshold": 0.001,
        "vix_halve_threshold": 22.0,
        # _vix_daily intentionally absent
    })
    assert (sig_a == sig_b).all()
```

- [ ] **Step 4.2: Run tests to verify failures**

Run: `python3 -m pytest equity_trading/tests/test_strategy_last_hour_momentum.py -v`

Expected: `test_lhm_signals_at_today_bar_0_when_yesterday_bullish` PASSES (existing behavior). `test_lhm_vix_filter_suppresses_high_vix_day` FAILS (no filter exists yet — the count is 1+, not 0). `test_lhm_vix_threshold_omitted_unchanged` PASSES (omitted param ignored).

- [ ] **Step 4.3: Implement VIX filter**

Modify `equity_trading/src/strategy/strategies/last_hour_momentum.py::compute_entry_signal`. After the line `signal = is_signal_bar & is_bullish_yesterday` (around line 61), add:

```python
        vix_halve_threshold = params.get("vix_halve_threshold")
        if vix_halve_threshold is not None and "_vix_daily" in params:
            vix = params["_vix_daily"]
            vix_dict = {ts.date(): float(c) for ts, c in vix["close"].items()}
            vix_high_mask = ny_date.map(vix_dict).fillna(0) > vix_halve_threshold
            signal = signal & ~vix_high_mask
```

(`ny_date` is already defined earlier in the function at line ~30.)

- [ ] **Step 4.4: Run tests to verify they pass**

Run: `python3 -m pytest equity_trading/tests/test_strategy_last_hour_momentum.py -v`

Expected: 3 passed.

- [ ] **Step 4.5: Commit**

```
git add equity_trading/src/strategy/strategies/last_hour_momentum.py equity_trading/tests/test_strategy_last_hour_momentum.py
git commit -m "feat(lhm): optional vix_halve_threshold filter + initial test file (Task 4)"
```

---

## Task 5: §4-B Phase A variant configs

**Files:**
- Create: `equity_trading/configs/phase_a/v0_capped.yaml`
- Create: `equity_trading/configs/phase_a/v0_capped_size12.yaml`
- Create: `equity_trading/configs/phase_a/v0_capped_concur1.yaml`
- Create: `equity_trading/configs/phase_a/v0_capped_vix22.yaml`
- Create: `equity_trading/configs/phase_a/v0_capped_size12_vix22.yaml`
- Create: `equity_trading/configs/phase_a/v0_capped_concur1_vix22.yaml`
- Create: `equity_trading/tests/test_phase_a_configs.py`

- [ ] **Step 5.1: Write failing test**

Create `equity_trading/tests/test_phase_a_configs.py`:

```python
"""Phase A search variant configs."""
from __future__ import annotations

from pathlib import Path

import pytest

from equity_trading.src.validation.config import load_variant_config

CONFIGS_DIR = Path(__file__).resolve().parents[1] / "configs" / "phase_a"
EXPECTED_FILES = {
    "v0_capped.yaml",
    "v0_capped_size12.yaml",
    "v0_capped_concur1.yaml",
    "v0_capped_vix22.yaml",
    "v0_capped_size12_vix22.yaml",
    "v0_capped_concur1_vix22.yaml",
}


def test_phase_a_dir_contains_six_files():
    files = {p.name for p in CONFIGS_DIR.glob("*.yaml")}
    assert files == EXPECTED_FILES


@pytest.mark.parametrize("filename", sorted(EXPECTED_FILES))
def test_phase_a_yaml_loads(filename):
    cfg = load_variant_config(CONFIGS_DIR / filename)
    assert cfg.parent_baseline == "orb_default_v0"
    assert cfg.variant_id == f"orb_default_v0_{filename.replace('v0_', '').replace('.yaml', '')}"


@pytest.mark.parametrize("filename", sorted(EXPECTED_FILES))
def test_phase_a_yaml_has_catastrophic_stop_5(filename):
    cfg = load_variant_config(CONFIGS_DIR / filename)
    for entry in cfg.strategies:
        assert entry["params"].get("catastrophic_stop_pct") == 5.0, (
            f"{filename} strategy {entry['class']} missing catastrophic_stop_pct=5.0"
        )


@pytest.mark.parametrize("filename,size,concur", [
    ("v0_capped.yaml", 0.25, 3),
    ("v0_capped_size12.yaml", 0.125, 3),
    ("v0_capped_concur1.yaml", 0.25, 1),
    ("v0_capped_vix22.yaml", 0.25, 3),
    ("v0_capped_size12_vix22.yaml", 0.125, 3),
    ("v0_capped_concur1_vix22.yaml", 0.25, 1),
])
def test_phase_a_yaml_sizing(filename, size, concur):
    cfg = load_variant_config(CONFIGS_DIR / filename)
    assert cfg.portfolio["position_size_pct"] == size
    assert cfg.portfolio["max_concurrent"] == concur


@pytest.mark.parametrize("filename,vix_threshold", [
    ("v0_capped.yaml", None),
    ("v0_capped_size12.yaml", None),
    ("v0_capped_concur1.yaml", None),
    ("v0_capped_vix22.yaml", 22.0),
    ("v0_capped_size12_vix22.yaml", 22.0),
    ("v0_capped_concur1_vix22.yaml", 22.0),
])
def test_phase_a_yaml_vix(filename, vix_threshold):
    cfg = load_variant_config(CONFIGS_DIR / filename)
    for entry in cfg.strategies:
        assert entry["params"].get("vix_halve_threshold") == vix_threshold, (
            f"{filename} {entry['class']} expected vix_halve_threshold={vix_threshold}"
        )
```

- [ ] **Step 5.2: Run tests to verify failures**

Run: `python3 -m pytest equity_trading/tests/test_phase_a_configs.py -v`

Expected: all FAIL — directory does not exist or has no files.

- [ ] **Step 5.3: Create configs/phase_a/ directory and 6 yamls**

Create `equity_trading/configs/phase_a/v0_capped.yaml`:

```yaml
variant_id: orb_default_v0_capped
description: |
  Phase A search candidate: catastrophic_stop_pct=5.0, sizing=25%×3, vix=none.
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
  - class: LastHourMomentumStrategy
    symbols: [UPRO, UDOW]
    params:
      threshold: 0.003
      _max_hold_bars: 60
      cost_pct: 0.10
      catastrophic_stop_pct: 5.0
portfolio:
  position_size_pct: 0.25
  max_concurrent: 3
  starting_equity_usd: 100000
gates:
  oos: { holdout_start: "2024-05-01", holdout_end: "2026-05-01", min_outperformance_pct: 0.0 }
  tail_risk: { max_single_trade_loss_pct: 5.0, max_portfolio_dd_pct: 20.0, max_rolling_30d_loss_pct: 10.0 }
  sample_size: { min_holdout_trades: 30 }
```

Create `equity_trading/configs/phase_a/v0_capped_size12.yaml` — same as `v0_capped.yaml` but with `position_size_pct: 0.125` and `variant_id: orb_default_v0_capped_size12` and the description updated to `sizing=12.5%×3, vix=none`.

Create `equity_trading/configs/phase_a/v0_capped_concur1.yaml` — same as `v0_capped.yaml` but with `max_concurrent: 1` and `variant_id: orb_default_v0_capped_concur1` and description `sizing=25%×1, vix=none`.

Create `equity_trading/configs/phase_a/v0_capped_vix22.yaml` — same as `v0_capped.yaml` but every `params` block also includes `vix_halve_threshold: 22.0`. `variant_id: orb_default_v0_capped_vix22`. Description `sizing=25%×3, vix=22`.

Create `equity_trading/configs/phase_a/v0_capped_size12_vix22.yaml` — combination of `_size12` (position_size_pct: 0.125) and `_vix22` (vix_halve_threshold: 22.0 on every strategy). `variant_id: orb_default_v0_capped_size12_vix22`. Description `sizing=12.5%×3, vix=22`.

Create `equity_trading/configs/phase_a/v0_capped_concur1_vix22.yaml` — combination of `_concur1` (max_concurrent: 1) and `_vix22`. `variant_id: orb_default_v0_capped_concur1_vix22`. Description `sizing=25%×1, vix=22`.

- [ ] **Step 5.4: Run tests to verify they pass**

Run: `python3 -m pytest equity_trading/tests/test_phase_a_configs.py -v`

Expected: all parametrized tests pass (1 + 6 + 6 + 6 + 6 = 25 tests).

- [ ] **Step 5.5: Commit**

```
git add equity_trading/configs/phase_a/ equity_trading/tests/test_phase_a_configs.py
git commit -m "feat(phase_a): 6 variant configs for Phase A search (Task 5)"
```

---

## Task 6: §5 Phase A search runner

**Files:**
- Create: `equity_trading/scripts/run_phase_a_search.py`
- Create: `equity_trading/tests/test_run_phase_a_search.py`

- [ ] **Step 6.1: Write failing tests**

Create `equity_trading/tests/test_run_phase_a_search.py`:

```python
"""Phase A search runner."""
from __future__ import annotations

import pandas as pd
import pytest


def test_eval_threshold_all_pass():
    from equity_trading.scripts.run_phase_a_search import _eval_threshold
    summary = {"annualized_pct": 0.5, "max_dd_pct": -10.0, "sharpe": 0.1}
    assert _eval_threshold(summary, worst_trade_pct=-3.0) == []


def test_eval_threshold_ann_fail():
    from equity_trading.scripts.run_phase_a_search import _eval_threshold
    summary = {"annualized_pct": -5.0, "max_dd_pct": -10.0, "sharpe": 0.0}
    assert "ann" in _eval_threshold(summary, worst_trade_pct=-3.0)


def test_eval_threshold_dd_fail():
    from equity_trading.scripts.run_phase_a_search import _eval_threshold
    summary = {"annualized_pct": 0.0, "max_dd_pct": -25.0, "sharpe": 0.0}
    assert "MaxDD" in _eval_threshold(summary, worst_trade_pct=-3.0)


def test_eval_threshold_worst_fail():
    from equity_trading.scripts.run_phase_a_search import _eval_threshold
    summary = {"annualized_pct": 0.0, "max_dd_pct": -10.0, "sharpe": 0.0}
    assert "worst" in _eval_threshold(summary, worst_trade_pct=-7.0)


def test_eval_threshold_sharpe_fail():
    from equity_trading.scripts.run_phase_a_search import _eval_threshold
    summary = {"annualized_pct": 0.0, "max_dd_pct": -10.0, "sharpe": -0.5}
    assert "Sharpe" in _eval_threshold(summary, worst_trade_pct=-3.0)


def test_render_md_no_candidate_passes():
    from equity_trading.scripts.run_phase_a_search import _render_md
    rows = [
        {"variant_id": "v_a", "ann": -5.0, "dd": -22.0, "worst": -6.0, "sharpe": -0.4,
         "n": 100, "fails": ["ann", "MaxDD", "worst", "Sharpe"]},
    ]
    md = _render_md(rows)
    assert "## No candidate passes" in md
    assert "v_a" in md


def test_render_md_top_by_ann():
    from equity_trading.scripts.run_phase_a_search import _render_md
    rows = [
        {"variant_id": "v_a", "ann": -1.0, "dd": -10.0, "worst": -3.0, "sharpe": -0.1,
         "n": 100, "fails": []},
        {"variant_id": "v_b", "ann": +0.5, "dd": -8.0, "worst": -3.5, "sharpe": +0.05,
         "n": 90, "fails": []},
    ]
    md = _render_md(rows)
    assert "## Top by ann return" in md
    assert "v_b" in md  # v_b has higher ann


def test_search_does_not_read_holdout(tmp_path, monkeypatch):
    """Phase A search must not call EvaluationContext.load_holdout_bars or
    instantiate EvaluationContext."""
    import equity_trading.src.validation.data as D

    holdout_calls: list = []

    class _ForbiddenCtx:
        def __init__(self, *a, **kw):
            holdout_calls.append("init")
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def load_holdout_bars(self, *a, **kw):
            holdout_calls.append("load")

    monkeypatch.setattr(D, "EvaluationContext", _ForbiddenCtx)

    # Stub load_train2/valid2 + simulate to avoid needing real data
    import equity_trading.src.validation.internal_split as IS
    monkeypatch.setattr(IS, "load_train2_bars", lambda r, s, timeframe_minutes: pd.DataFrame())
    monkeypatch.setattr(IS, "load_valid2_bars", lambda r, s, timeframe_minutes: pd.DataFrame())

    # Build minimal phase_a dir with one yaml
    pa = tmp_path / "phase_a"
    pa.mkdir()
    (pa / "v_test.yaml").write_text(
        "variant_id: v_test\n"
        "description: ''\n"
        "strategies:\n"
        "  - class: OpeningRangeBreakoutStrategy\n"
        "    symbols: [TECL]\n"
        "    params: { or_window_bars: 12, stop_mult: 0.0, target_mult: 1.0,\n"
        "              cost_pct: 0.10, catastrophic_stop_pct: 5.0 }\n"
        "portfolio: { position_size_pct: 0.25, max_concurrent: 3, starting_equity_usd: 100000 }\n"
        "gates:\n"
        "  oos: { holdout_start: '2024-05-01', holdout_end: '2026-05-01', min_outperformance_pct: 0.0 }\n"
        "  tail_risk: { max_single_trade_loss_pct: 5.0, max_portfolio_dd_pct: 20.0, max_rolling_30d_loss_pct: 10.0 }\n"
        "  sample_size: { min_holdout_trades: 30 }\n"
    )
    out = tmp_path / "out.md"
    # Stub VIX read so the runner doesn't need a real parquet
    fake_vix = pd.DataFrame({"close": [20.0]},
                             index=pd.date_range("2022-01-01", periods=1, freq="1D", tz="UTC"))

    from equity_trading.scripts.run_phase_a_search import run_search
    run_search(configs_dir=pa, data_root=tmp_path, output=out, vix_daily=fake_vix)
    assert holdout_calls == [], f"Phase A search touched holdout: {holdout_calls}"
```

- [ ] **Step 6.2: Run tests to verify they fail**

Run: `python3 -m pytest equity_trading/tests/test_run_phase_a_search.py -v`

Expected: all FAIL — `ModuleNotFoundError: No module named 'equity_trading.scripts.run_phase_a_search'`.

- [ ] **Step 6.3: Implement script**

Create `equity_trading/scripts/run_phase_a_search.py`:

```python
"""Phase A variant search.

Reads configs/phase_a/*.yaml, simulates each on internal valid2
(2022-01-01 → 2024-04-30), applies the four-axis threshold from spec §1,
and writes a markdown report ranking the candidates by ann return.

This script reads ONLY train data via internal_split. It must not
read holdout — a guard test (test_search_does_not_read_holdout) enforces this.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import pandas as pd

from equity_trading.src.validation.config import load_variant_config
from equity_trading.src.validation.runner import (
    _collect_trades_from_split,
    _simulate_portfolio,
)


def _eval_threshold(summary: dict, worst_trade_pct: float) -> list[str]:
    fails: list[str] = []
    if summary["annualized_pct"] < -3.0:
        fails.append("ann")
    if abs(summary["max_dd_pct"]) > 20.0:
        fails.append("MaxDD")
    if abs(worst_trade_pct) > 5.0:
        fails.append("worst")
    if summary["sharpe"] < -0.3:
        fails.append("Sharpe")
    return fails


def _render_md(rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append("# Phase A search — internal valid (2022-01-01 → 2024-04-30)\n")
    lines.append("**Threshold (Q2 A)**: ann ≥ -3%/yr, MaxDD ≤ 20%, "
                  "worst trade ≤ 5%, Sharpe ≥ -0.3\n")
    lines.append("| variant | ann | MaxDD | worst | Sharpe | n trades | passes? |")
    lines.append("|---|---:|---:|---:|---:|---:|:---:|")
    for r in rows:
        passes = "✅" if not r["fails"] else "❌ " + "/".join(r["fails"])
        lines.append(
            f"| {r['variant_id']} | {r['ann']:+.2f}% | {r['dd']:+.2f}% | "
            f"{r['worst']:+.2f}% | {r['sharpe']:+.2f} | {r['n']} | {passes} |"
        )
    lines.append("")
    passing = [r for r in rows if not r["fails"]]
    if not passing:
        lines.append("## No candidate passes")
        lines.append("")
        lines.append("Phase A step 1 (6 candidates) yielded no passing variant. "
                      "Escalate to step 2 (12 candidates) by adding `target_mult ∈ {1.0, 1.5}` "
                      "to the search dimensions, or to step 3 (24 candidates, +daily_halt_pct), "
                      "or to Phase B (new strategies / universe) per "
                      "`docs/superpowers/specs/2026-05-04-strategy-rethink-design.md` §8.")
    else:
        winner = max(passing, key=lambda r: r["ann"])
        lines.append(f"## Top by ann return (passing only): **{winner['variant_id']}** "
                      f"({winner['ann']:+.2f}%/yr)")
        lines.append("")
        lines.append("→ Run holdout test:")
        lines.append("```")
        lines.append("python3 -m equity_trading.src.validation \\")
        lines.append(f"    --variant equity_trading/configs/phase_a/"
                      f"{winner['variant_id'].replace('orb_default_v0_', 'v0_')}.yaml \\")
        lines.append("    --baseline equity_trading/configs/orb_default_v0.yaml \\")
        lines.append("    --output equity_trading/phase0/validation/"
                      f"<date>_phase_a_winner_holdout.md")
        lines.append("```")
    return "\n".join(lines) + "\n"


def run_search(*, configs_dir: Path, data_root: Path, output: Path,
                vix_daily: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for cfg_path in sorted(Path(configs_dir).glob("*.yaml")):
        cfg = load_variant_config(cfg_path)
        trades = _collect_trades_from_split(cfg, data_root, "valid2", vix_daily=vix_daily)
        summary, _eq, _accepted = _simulate_portfolio_safe(
            trades, starting_equity=cfg.portfolio["starting_equity_usd"],
            position_size_pct=cfg.portfolio["position_size_pct"],
            max_concurrent=cfg.portfolio["max_concurrent"],
        )
        worst = float(trades["pnl_pct"].min() * 100) if len(trades) > 0 else 0.0
        fails = _eval_threshold(summary, worst)
        rows.append({
            "variant_id": cfg.variant_id,
            "ann": summary["annualized_pct"],
            "dd": summary["max_dd_pct"],
            "worst": worst,
            "sharpe": summary["sharpe"],
            "n": len(trades),
            "fails": fails,
        })
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(_render_md(rows))
    return rows


def _simulate_portfolio_safe(trades, starting_equity, position_size_pct, max_concurrent):
    """Wrapper that tolerates either the existing 2-tuple or future 3-tuple
    return shape from runner._simulate_portfolio (forward-compat with the
    deferred predecessor task that adds position_dollars surfacing)."""
    result = _simulate_portfolio(
        trades=trades, starting_equity=starting_equity,
        position_size_pct=position_size_pct, max_concurrent=max_concurrent,
    )
    if len(result) == 2:
        summary, eq = result
        return summary, eq, pd.DataFrame()
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--configs-dir", type=Path,
                    default=Path("equity_trading/configs/phase_a"))
    p.add_argument("--data-root", type=Path,
                    default=Path("equity_trading/data/prices"))
    p.add_argument("--output", type=Path, required=True)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    vix_path = args.data_root / "VIX_1day_2019-05-01_2026-05-01.parquet"
    vix_daily = pd.read_parquet(vix_path) if vix_path.exists() else pd.DataFrame(
        {"close": []}, index=pd.DatetimeIndex([], tz="UTC"))
    run_search(configs_dir=args.configs_dir, data_root=args.data_root,
                output=args.output, vix_daily=vix_daily)
    print(f"[saved] {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6.4: Run tests to verify they pass**

Run: `python3 -m pytest equity_trading/tests/test_run_phase_a_search.py -v`

Expected: 8 passed.

- [ ] **Step 6.5: Commit**

```
git add equity_trading/scripts/run_phase_a_search.py equity_trading/tests/test_run_phase_a_search.py
git commit -m "feat(scripts): Phase A variant search runner with holdout-leak guard (Task 6)"
```

---

## Task 7: Execute Phase A search and capture results

**Files:**
- Create: `equity_trading/phase0/phase_a_search_2026-05-04.md` (output)

- [ ] **Step 7.1: Run Phase A search on real data**

From `/Users/hideakimacbookair/自動トレード/.worktrees/validation-improvements`:

```
python3 equity_trading/scripts/run_phase_a_search.py \
    --output equity_trading/phase0/phase_a_search_2026-05-04.md
```

Expected: console prints `[saved] equity_trading/phase0/phase_a_search_2026-05-04.md`. Exit 0.

- [ ] **Step 7.2: Read and summarise the report**

Read `equity_trading/phase0/phase_a_search_2026-05-04.md`. Capture:
- The 6×6 results table verbatim
- Whether the report contains `## Top by ann return (passing only)` (≥1 candidate passed) or `## No candidate passes` (zero passers)
- If passing: the winner's variant_id and its ann/dd/worst/sharpe values

- [ ] **Step 7.3: Commit the report**

```
git add equity_trading/phase0/phase_a_search_2026-05-04.md
git commit -m "data(phase_a): capture step-1 search results on internal valid2 (Task 7)"
```

---

## Task 8: (Conditional) Holdout test of winning candidate

**Trigger condition:** Task 7 produced `## Top by ann return (passing only)` in the report.

**Files:**
- Create: `equity_trading/phase0/validation/2026-05-04_phase_a_winner_holdout.md` (output)

- [ ] **Step 8.1: Run holdout validation on the winner**

Replace `<WINNER_FILENAME>` below with the filename from Task 7's "Top by ann return" line (e.g. `v0_capped_concur1_vix22.yaml`):

```
python3 -m equity_trading.src.validation \
    --variant equity_trading/configs/phase_a/<WINNER_FILENAME> \
    --baseline equity_trading/configs/orb_default_v0.yaml \
    --output equity_trading/phase0/validation/2026-05-04_phase_a_winner_holdout.md
```

Expected: report file written. Headline is one of `APPROVE`, `REVIEW`, or `REJECT`.

- [ ] **Step 8.2: Inspect the report**

Read `equity_trading/phase0/validation/2026-05-04_phase_a_winner_holdout.md`. Note:
- Headline (APPROVE / REVIEW / REJECT)
- OOS gate: variant ann, baseline ann, diff
- Tail risk gate: worst trade, MaxDD, 30d rolling
- Sample size gate: trade count

- [ ] **Step 8.3: Commit the report**

```
git add equity_trading/phase0/validation/2026-05-04_phase_a_winner_holdout.md
git commit -m "data(validation): Phase A winner holdout test (Task 8)"
```

- [ ] **Step 8.4: Decide outcome**

If headline is APPROVE: this is the deploy candidate. Move to Phase A completion (Task 9).
If headline is REVIEW: read the warnings; small tail-risk-gate WARN may be acceptable; large WARN means escalate.
If headline is REJECT: the variant was over-fit on valid2 too; escalate to step 2 (12 candidates with target_mult dimension) or step 3 (24 candidates with daily_halt_pct dimension), or to Phase B brainstorm if step 3 also fails. Document the decision in the report's "Decision Log" section.

---

## Task 9: Update RUNBOOK with Phase A outcome

**Files:**
- Modify: `equity_trading/docs/RUNBOOK.md`

- [ ] **Step 9.1: Append Phase A section**

In `equity_trading/docs/RUNBOOK.md`, after the existing header block, add:

```markdown
## 2026-05-04 Phase A search outcome

Post-warmup-fix baseline (orb_default_v0) holdout was -22.60%/yr / -42.02% MaxDD,
prompting Phase A variant search per
`docs/superpowers/specs/2026-05-04-strategy-rethink-design.md`.

**Step 1 (6 candidates) result**: see
`equity_trading/phase0/phase_a_search_2026-05-04.md`.

**Holdout test of winner** (only if a candidate passed valid2 threshold): see
`equity_trading/phase0/validation/2026-05-04_phase_a_winner_holdout.md`.

**Deploy candidate** (only if holdout APPROVE): <WINNER_VARIANT_ID>.
**If no deploy candidate**: Phase A step 2/3 or Phase B brainstorm pending.
```

Replace `<WINNER_VARIANT_ID>` with the actual winner if Task 8 produced APPROVE; otherwise replace it with `none — see decision log`.

- [ ] **Step 9.2: Commit**

```
git add equity_trading/docs/RUNBOOK.md
git commit -m "docs(RUNBOOK): record Phase A outcome and pointers (Task 9)"
```

---

## Task 10: Final regression sweep

**Files:**
- (none)

- [ ] **Step 10.1: Run full test suite**

```
python3 -m pytest equity_trading/tests/ -v
```

Expected: all tests pass. Note any failures and resolve before marking Phase A complete.

- [ ] **Step 10.2: Verify branch state**

```
git log --oneline feature/validation-improvements ^main | head -20
```

Expected: a contiguous chain of Task-1 through Task-9 commits on top of `main`.

- [ ] **Step 10.3: No commit (verification only)**

This task is a sweep; no new artifacts.

---

## Self-review checklist

- [x] **Spec coverage**:
  - §3 internal_split → Tasks 1, 2
  - §4-A VIX filter → Tasks 3, 4
  - §4-B 6 yaml configs → Task 5
  - §5 search runner → Task 6
  - §6 implementation order matches Tasks 1→2→3→4→5→6→7→8→9→10
  - §7 test strategy → unit tests in each task + Task 10 final sweep
- [x] **No "TBD" / "TODO" / "implement later"** in code-bearing steps
- [x] **Type/signature consistency**: `_collect_trades_from_split` defined in Task 2, used in Task 6 (`run_search` calls it). `_eval_threshold` defined in Task 6 (with `worst_trade_pct` second arg), tested same shape in Task 6. `vix_halve_threshold` param key consistent across Tasks 3, 4, 5, 6. `_vix_daily` param key consistent.
- [x] **All file paths absolute or worktree-anchored** at `/Users/hideakimacbookair/自動トレード/.worktrees/validation-improvements`
- [x] **Test commands include exact pytest invocations**
- [x] **Commit messages follow convention**: `feat:`, `data:`, `docs:`, `test:` prefixes consistent with repo history
- [x] **Holdout-once invariant codified**: Task 6 includes `test_search_does_not_read_holdout`; Task 8 is the single holdout read; intermediate tasks (1–7) never call `EvaluationContext.load_holdout_bars`
- [x] **Conditional task gating**: Task 8 trigger condition (Task 7 produced "## Top by ann return") is explicit. If Task 7 produced "## No candidate passes", Task 8 is skipped and Task 9 documents the no-candidate outcome.
