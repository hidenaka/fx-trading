# Validation Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-command validation framework that runs OOS / tail-risk / sample-size gates against a strategy variant config and produces a markdown report; physically separate train/holdout data so a strategy cannot accidentally optimize on the test set.

**Architecture:** Add `equity_trading/src/validation/` module (config loader, EvaluationContext, 3 gates, report writer, CLI). Split existing flat `data/prices/*.parquet` into `data/prices/full/` (backward compat) plus generated `train/` (≤ 2024-05-01) and `holdout/` (> 2024-05-01) views. Strategies/portfolio refactor to read variant YAML. Headline judgment derives from gate statuses (PASS/FAIL/WARN).

**Tech Stack:** Python 3.12, pandas, pyarrow, pyyaml, jsonschema, pytest. Reuses existing `equity_trading.src.phase0.strategy_simulator`, `equity_trading.src.strategy.strategies.*`.

**Spec:** `docs/superpowers/specs/2026-05-03-validation-framework-design.md`

---

## File Map

### New
```
equity_trading/src/validation/
├── __init__.py
├── config.py                          # YAML loader, schema
├── manifest.py                        # data manifest hashing
├── data.py                            # EvaluationContext
├── report.py                          # markdown writer
├── cli.py                             # python -m equity_trading.validation.validate
├── __main__.py                        # entry point glue
└── gates/
    ├── __init__.py
    ├── base.py                        # GateResult, Status, Outcome
    ├── sample_size.py
    ├── tail_risk.py
    └── oos.py

equity_trading/configs/
├── orb_default_v0.yaml                # baseline (legacy ORB exits)
└── orb_tight_v2_1.yaml                # variant (new ORB exits)

equity_trading/scripts/
└── split_train_holdout.py             # one-time data partition

equity_trading/tests/
├── test_validation_base.py
├── test_validation_config.py
├── test_validation_manifest.py
├── test_validation_data.py
├── test_validation_report.py
├── test_validation_cli.py
├── test_gate_sample_size.py
├── test_gate_tail_risk.py
├── test_gate_oos.py
└── test_validation_e2e.py
```

### Modified
- `equity_trading/src/data/price_fetcher.py` — add `partition` kwarg
- `equity_trading/scripts/run_portfolio_ensemble.py` — read variant config
- `equity_trading/docs/RUNBOOK.md` — add validation section

### Generated (after Task 5 runs once)
```
equity_trading/data/prices/
├── full/   <- existing flat files moved here (backward compat)
├── train/  <- bars where ts <= 2024-05-01
├── holdout/<- bars where ts > 2024-05-01
└── manifest.json
```

---

## Task 1: GateResult + Status enum

**Files:**
- Create: `equity_trading/src/validation/__init__.py` (empty)
- Create: `equity_trading/src/validation/gates/__init__.py` (empty)
- Create: `equity_trading/src/validation/gates/base.py`
- Test: `equity_trading/tests/test_validation_base.py`

- [ ] **Step 1: Write failing test**

`equity_trading/tests/test_validation_base.py`:

```python
"""Status enum + GateResult dataclass tests."""
from __future__ import annotations

import pytest

from equity_trading.src.validation.gates.base import GateResult, Status


def test_status_enum_has_three_levels():
    assert Status.PASS.value == "PASS"
    assert Status.WARN.value == "WARN"
    assert Status.FAIL.value == "FAIL"


def test_gate_result_constructs_with_required_fields():
    r = GateResult(
        name="oos",
        status=Status.PASS,
        summary="variant +12.5% vs baseline +8.3%",
        detail_md="### OOS\nfoo bar",
        metrics={"variant_ann": 12.5, "baseline_ann": 8.3},
    )
    assert r.name == "oos"
    assert r.status == Status.PASS
    assert "variant" in r.summary
    assert "###" in r.detail_md
    assert r.metrics["variant_ann"] == 12.5


def test_gate_result_metrics_defaults_to_empty_dict():
    r = GateResult(name="x", status=Status.PASS, summary="ok", detail_md="")
    assert r.metrics == {}


def test_gate_result_status_icon():
    """Each status maps to a markdown icon for the report."""
    assert Status.PASS.icon == "✅"
    assert Status.WARN.icon == "⚠️"
    assert Status.FAIL.icon == "❌"
```

- [ ] **Step 2: Run to confirm fail**

```
python3 -m pytest equity_trading/tests/test_validation_base.py -v
```

Expected: `ModuleNotFoundError: No module named 'equity_trading.src.validation'`

- [ ] **Step 3: Implement minimal code**

`equity_trading/src/validation/__init__.py`:
```python
```

`equity_trading/src/validation/gates/__init__.py`:
```python
```

`equity_trading/src/validation/gates/base.py`:
```python
"""Gate result types shared by all validation gates."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Status(Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"

    @property
    def icon(self) -> str:
        return {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[self.value]


@dataclass
class GateResult:
    name: str
    status: Status
    summary: str
    detail_md: str
    metrics: dict = field(default_factory=dict)
```

- [ ] **Step 4: Run tests to confirm pass**

```
python3 -m pytest equity_trading/tests/test_validation_base.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```
git add equity_trading/src/validation/__init__.py \
        equity_trading/src/validation/gates/__init__.py \
        equity_trading/src/validation/gates/base.py \
        equity_trading/tests/test_validation_base.py
git commit -m "feat(validation): add GateResult + Status enum (Task 1)"
```

---

## Task 2: Variant config YAML loader

**Files:**
- Create: `equity_trading/src/validation/config.py`
- Create: `equity_trading/configs/_example_minimal.yaml` (used in tests)
- Test: `equity_trading/tests/test_validation_config.py`

- [ ] **Step 1: Write failing test**

`equity_trading/tests/test_validation_config.py`:

```python
"""Variant config loader tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from equity_trading.src.validation.config import VariantConfig, load_variant_config


REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_config(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "v.yaml"
    p.write_text(body)
    return p


def test_load_minimal_config(tmp_path):
    body = """
variant_id: test_v0
description: minimal
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
"""
    p = _write_config(tmp_path, body)
    cfg = load_variant_config(p)
    assert cfg.variant_id == "test_v0"
    assert cfg.strategies[0]["class"] == "OpeningRangeBreakoutStrategy"
    assert cfg.strategies[0]["symbols"] == ["TECL"]
    assert cfg.gates["oos"]["holdout_start"] == "2024-05-01"
    assert cfg.gates["sample_size"]["min_holdout_trades"] == 30


def test_load_rejects_missing_variant_id(tmp_path):
    body = """
description: missing variant_id
strategies: []
portfolio:
  position_size_pct: 0.25
  max_concurrent: 3
  starting_equity_usd: 100000
gates: {}
"""
    p = _write_config(tmp_path, body)
    with pytest.raises(ValueError, match="variant_id"):
        load_variant_config(p)


def test_load_rejects_unknown_strategy_class(tmp_path):
    body = """
variant_id: bad
description: ""
strategies:
  - class: NonExistentStrategy
    symbols: [TECL]
    params: {}
portfolio:
  position_size_pct: 0.25
  max_concurrent: 3
  starting_equity_usd: 100000
gates:
  oos: {holdout_start: "2024-05-01", holdout_end: "2026-05-01", min_outperformance_pct: 0.0}
  tail_risk: {max_single_trade_loss_pct: 5.0, max_portfolio_dd_pct: 20.0, max_rolling_30d_loss_pct: 10.0}
  sample_size: {min_holdout_trades: 30}
"""
    p = _write_config(tmp_path, body)
    with pytest.raises(ValueError, match="NonExistentStrategy"):
        load_variant_config(p)


def test_resolve_strategy_class_returns_real_class(tmp_path):
    body = """
variant_id: test
description: ""
strategies:
  - class: OpeningRangeBreakoutStrategy
    symbols: [TECL]
    params: {or_window_bars: 12, stop_mult: 0.0, target_mult: 1.0, cost_pct: 0.10}
portfolio: {position_size_pct: 0.25, max_concurrent: 3, starting_equity_usd: 100000}
gates:
  oos: {holdout_start: "2024-05-01", holdout_end: "2026-05-01", min_outperformance_pct: 0.0}
  tail_risk: {max_single_trade_loss_pct: 5.0, max_portfolio_dd_pct: 20.0, max_rolling_30d_loss_pct: 10.0}
  sample_size: {min_holdout_trades: 30}
"""
    p = _write_config(tmp_path, body)
    cfg = load_variant_config(p)
    klass = cfg.resolve_strategy_class(cfg.strategies[0]["class"])
    from equity_trading.src.strategy.strategies.opening_range_breakout import OpeningRangeBreakoutStrategy
    assert klass is OpeningRangeBreakoutStrategy
```

- [ ] **Step 2: Run to confirm fail**

```
python3 -m pytest equity_trading/tests/test_validation_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'equity_trading.src.validation.config'`

- [ ] **Step 3: Implement config loader**

`equity_trading/src/validation/config.py`:

```python
"""Variant config YAML loader and schema validator.

A variant config is the single source of truth for strategy parameters,
portfolio sizing, and gate thresholds. Eliminates dual-namespace bugs
(stop_mult vs stop_multiplier) by being the only place values are defined.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from equity_trading.src.strategy.strategies.gap_fill import GapFillStrategy
from equity_trading.src.strategy.strategies.last_hour_momentum import LastHourMomentumStrategy
from equity_trading.src.strategy.strategies.opening_range_breakout import OpeningRangeBreakoutStrategy
from equity_trading.src.strategy.strategies.pre_fomc import PreFOMCDriftStrategy

# Whitelist of strategy classes resolvable from config. Adding a new
# strategy requires explicit listing here — prevents typo-driven loads.
STRATEGY_REGISTRY = {
    "OpeningRangeBreakoutStrategy": OpeningRangeBreakoutStrategy,
    "LastHourMomentumStrategy": LastHourMomentumStrategy,
    "GapFillStrategy": GapFillStrategy,
    "PreFOMCDriftStrategy": PreFOMCDriftStrategy,
}

REQUIRED_TOP_KEYS = {"variant_id", "strategies", "portfolio", "gates"}
REQUIRED_GATES = {"oos", "tail_risk", "sample_size"}


@dataclass
class VariantConfig:
    variant_id: str
    description: str
    strategies: list[dict[str, Any]]
    portfolio: dict[str, Any]
    gates: dict[str, dict[str, Any]]
    parent_baseline: str | None = None
    source_path: Path | None = None

    def resolve_strategy_class(self, class_name: str):
        if class_name not in STRATEGY_REGISTRY:
            raise ValueError(f"Unknown strategy class: {class_name!r}. Known: {list(STRATEGY_REGISTRY)}")
        return STRATEGY_REGISTRY[class_name]


def load_variant_config(path: Path | str) -> VariantConfig:
    path = Path(path)
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: config must be a YAML mapping")
    missing = REQUIRED_TOP_KEYS - raw.keys()
    if missing:
        raise ValueError(f"{path}: missing required keys: {sorted(missing)}")
    for s in raw["strategies"]:
        cls_name = s.get("class")
        if cls_name not in STRATEGY_REGISTRY:
            raise ValueError(f"{path}: unknown strategy class {cls_name!r}")
    gate_keys = set(raw["gates"].keys())
    if not REQUIRED_GATES.issubset(gate_keys):
        raise ValueError(f"{path}: gates must include {REQUIRED_GATES}, got {gate_keys}")
    return VariantConfig(
        variant_id=raw["variant_id"],
        description=raw.get("description", ""),
        strategies=raw["strategies"],
        portfolio=raw["portfolio"],
        gates=raw["gates"],
        parent_baseline=raw.get("parent_baseline"),
        source_path=path,
    )
```

- [ ] **Step 4: Run tests to confirm pass**

```
python3 -m pytest equity_trading/tests/test_validation_config.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```
git add equity_trading/src/validation/config.py \
        equity_trading/tests/test_validation_config.py
git commit -m "feat(validation): add variant config YAML loader (Task 2)"
```

---

## Task 3: Data manifest module

**Files:**
- Create: `equity_trading/src/validation/manifest.py`
- Test: `equity_trading/tests/test_validation_manifest.py`

- [ ] **Step 1: Write failing test**

`equity_trading/tests/test_validation_manifest.py`:

```python
"""Manifest hash + verification tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from equity_trading.src.validation.manifest import (
    Manifest,
    ManifestMismatchError,
    compute_manifest,
    verify_manifest,
)


def _make_data_tree(tmp_path: Path) -> Path:
    root = tmp_path / "prices"
    (root / "train").mkdir(parents=True)
    (root / "holdout").mkdir(parents=True)
    (root / "train" / "TECL_5min.parquet").write_bytes(b"train_TECL")
    (root / "train" / "TQQQ_5min.parquet").write_bytes(b"train_TQQQ")
    (root / "holdout" / "TECL_5min.parquet").write_bytes(b"holdout_TECL")
    return root


def test_compute_manifest_records_files_and_hashes(tmp_path):
    root = _make_data_tree(tmp_path)
    m = compute_manifest(root, holdout_cutoff="2024-05-01")
    assert m.cutoff_date == "2024-05-01"
    assert "train/TECL_5min.parquet" in m.file_hashes
    assert "holdout/TECL_5min.parquet" in m.file_hashes
    # SHA256 of b"train_TECL"
    import hashlib
    assert m.file_hashes["train/TECL_5min.parquet"] == hashlib.sha256(b"train_TECL").hexdigest()


def test_manifest_round_trip_via_json(tmp_path):
    root = _make_data_tree(tmp_path)
    m = compute_manifest(root, holdout_cutoff="2024-05-01")
    out = root / "manifest.json"
    m.write(out)
    loaded = Manifest.read(out)
    assert loaded.cutoff_date == m.cutoff_date
    assert loaded.file_hashes == m.file_hashes


def test_verify_manifest_pass_when_unchanged(tmp_path):
    root = _make_data_tree(tmp_path)
    m = compute_manifest(root, holdout_cutoff="2024-05-01")
    m.write(root / "manifest.json")
    # Should not raise
    verify_manifest(root)


def test_verify_manifest_raises_when_file_modified(tmp_path):
    root = _make_data_tree(tmp_path)
    m = compute_manifest(root, holdout_cutoff="2024-05-01")
    m.write(root / "manifest.json")
    # Tamper
    (root / "holdout" / "TECL_5min.parquet").write_bytes(b"TAMPERED")
    with pytest.raises(ManifestMismatchError, match="holdout/TECL_5min.parquet"):
        verify_manifest(root)


def test_verify_manifest_raises_when_file_added(tmp_path):
    root = _make_data_tree(tmp_path)
    m = compute_manifest(root, holdout_cutoff="2024-05-01")
    m.write(root / "manifest.json")
    (root / "holdout" / "NEW.parquet").write_bytes(b"surprise")
    with pytest.raises(ManifestMismatchError, match="NEW.parquet"):
        verify_manifest(root)
```

- [ ] **Step 2: Run to confirm fail**

```
python3 -m pytest equity_trading/tests/test_validation_manifest.py -v
```

Expected: `ModuleNotFoundError: No module named 'equity_trading.src.validation.manifest'`

- [ ] **Step 3: Implement manifest module**

`equity_trading/src/validation/manifest.py`:

```python
"""Data manifest: SHA256 of every parquet under data/prices/{train,holdout}.

The manifest is committed to git. validate CLI startup verifies hashes
match — if any file was modified or added, the run is rejected.
This catches accidental data overwrite, partial fetches, etc.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path


class ManifestMismatchError(RuntimeError):
    """Raised when on-disk parquet files don't match the recorded manifest."""


@dataclass
class Manifest:
    cutoff_date: str   # ISO date, e.g. "2024-05-01" — boundary between train and holdout
    file_hashes: dict[str, str] = field(default_factory=dict)

    @classmethod
    def read(cls, path: Path | str) -> "Manifest":
        path = Path(path)
        d = json.loads(path.read_text())
        return cls(cutoff_date=d["cutoff_date"], file_hashes=d["file_hashes"])

    def write(self, path: Path | str) -> None:
        path = Path(path)
        path.write_text(json.dumps(
            {"cutoff_date": self.cutoff_date, "file_hashes": self.file_hashes},
            indent=2, sort_keys=True,
        ))


def _hash_file(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def _list_parquet_relpaths(root: Path) -> list[str]:
    out: list[str] = []
    for sub in ("train", "holdout"):
        sub_dir = root / sub
        if not sub_dir.exists():
            continue
        for p in sorted(sub_dir.rglob("*.parquet")):
            out.append(str(p.relative_to(root)))
    return out


def compute_manifest(root: Path | str, holdout_cutoff: str) -> Manifest:
    root = Path(root)
    hashes: dict[str, str] = {}
    for rel in _list_parquet_relpaths(root):
        hashes[rel] = _hash_file(root / rel)
    return Manifest(cutoff_date=holdout_cutoff, file_hashes=hashes)


def verify_manifest(root: Path | str) -> None:
    """Raise ManifestMismatchError if any file is missing, added, or hash-different."""
    root = Path(root)
    saved = Manifest.read(root / "manifest.json")
    on_disk = {rel: _hash_file(root / rel) for rel in _list_parquet_relpaths(root)}
    saved_keys = set(saved.file_hashes)
    disk_keys = set(on_disk)
    extra = disk_keys - saved_keys
    missing = saved_keys - disk_keys
    if extra:
        raise ManifestMismatchError(f"unexpected files on disk: {sorted(extra)}")
    if missing:
        raise ManifestMismatchError(f"manifest files missing from disk: {sorted(missing)}")
    for rel, h in saved.file_hashes.items():
        if on_disk[rel] != h:
            raise ManifestMismatchError(f"hash changed for {rel}")
```

- [ ] **Step 4: Run tests**

```
python3 -m pytest equity_trading/tests/test_validation_manifest.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```
git add equity_trading/src/validation/manifest.py \
        equity_trading/tests/test_validation_manifest.py
git commit -m "feat(validation): add data manifest with hash verification (Task 3)"
```

---

## Task 4: EvaluationContext + access log

**Files:**
- Create: `equity_trading/src/validation/data.py`
- Test: `equity_trading/tests/test_validation_data.py`

- [ ] **Step 1: Write failing test**

`equity_trading/tests/test_validation_data.py`:

```python
"""EvaluationContext access tests."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from equity_trading.src.validation.data import (
    EvaluationContext,
    HoldoutAccessError,
    load_train_bars,
)


def _write_parquet(path: Path, ts_start: str, n: int = 10) -> None:
    ts = pd.date_range(ts_start, periods=n, freq="5min", tz="UTC")
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1}, index=ts)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)


def _setup_data_root(tmp_path: Path) -> Path:
    root = tmp_path / "prices"
    _write_parquet(root / "train" / "TECL_5min.parquet", "2023-01-01")
    _write_parquet(root / "holdout" / "TECL_5min.parquet", "2025-01-01")
    return root


def test_load_train_bars_reads_train_partition(tmp_path):
    root = _setup_data_root(tmp_path)
    df = load_train_bars(root, "TECL", timeframe_minutes=5)
    assert len(df) == 10
    assert df.index[0].year == 2023


def test_evaluation_context_can_load_holdout(tmp_path):
    root = _setup_data_root(tmp_path)
    log_path = tmp_path / "holdout_access.jsonl"
    with EvaluationContext(
        root=root, variant_id="v_test", reason="gate:oos",
        access_log_path=log_path,
    ) as ctx:
        df = ctx.load_holdout_bars("TECL", timeframe_minutes=5)
    assert len(df) == 10
    assert df.index[0].year == 2025
    # access logged
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["variant_id"] == "v_test"
    assert record["reason"] == "gate:oos"
    assert record["symbol"] == "TECL"
    assert record["timeframe_minutes"] == 5


def test_holdout_access_outside_evaluation_context_raises(tmp_path):
    root = _setup_data_root(tmp_path)
    # Trying to read holdout parquet directly (without EvaluationContext) is the
    # convention we enforce by NOT exposing a load_holdout function. Instead
    # only train is publicly accessible:
    with pytest.raises(HoldoutAccessError):
        load_train_bars(root, "TECL", timeframe_minutes=5, partition="holdout")


def test_evaluation_context_appends_to_access_log(tmp_path):
    root = _setup_data_root(tmp_path)
    log_path = tmp_path / "log.jsonl"
    log_path.write_text(json.dumps({"variant_id": "old", "reason": "x", "symbol": "Y", "timeframe_minutes": 5, "ts_utc": "old"}) + "\n")
    with EvaluationContext(root=root, variant_id="v", reason="r", access_log_path=log_path) as ctx:
        ctx.load_holdout_bars("TECL", timeframe_minutes=5)
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 2  # appended, did not overwrite
```

- [ ] **Step 2: Run to confirm fail**

```
python3 -m pytest equity_trading/tests/test_validation_data.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement EvaluationContext**

`equity_trading/src/validation/data.py`:

```python
"""Train/holdout data access with explicit holdout audit trail.

Train data is freely accessible via load_train_bars. Holdout data is
only readable inside an EvaluationContext, which appends a record to
holdout_access.jsonl on every read. This makes "I accidentally trained
on the holdout" physically impossible from properly written code.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import pandas as pd


class HoldoutAccessError(RuntimeError):
    """Raised when code attempts to read holdout data without EvaluationContext."""


def _parquet_filename(symbol: str, timeframe_minutes: int) -> str:
    return f"{symbol}_{timeframe_minutes}min.parquet"


def load_train_bars(
    root: Path | str,
    symbol: str,
    timeframe_minutes: int,
    partition: Literal["train", "holdout"] = "train",
) -> pd.DataFrame:
    """Load bars from the train partition. partition='holdout' is rejected
    here — use EvaluationContext for that path.
    """
    if partition != "train":
        raise HoldoutAccessError(
            "Direct access to non-train partition is forbidden. "
            "Use EvaluationContext to read holdout data."
        )
    root = Path(root)
    path = root / "train" / _parquet_filename(symbol, timeframe_minutes)
    return pd.read_parquet(path)


class EvaluationContext:
    """Context manager that grants holdout-read permission while logging access.

    Usage:
        with EvaluationContext(root, variant_id, reason="gate:oos") as ctx:
            df = ctx.load_holdout_bars("TECL", timeframe_minutes=5)
    """

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
        return False  # don't suppress exceptions

    def load_holdout_bars(self, symbol: str, timeframe_minutes: int) -> pd.DataFrame:
        path = self.root / "holdout" / _parquet_filename(symbol, timeframe_minutes)
        df = pd.read_parquet(path)
        record = {
            "variant_id": self.variant_id,
            "reason": self.reason,
            "symbol": symbol,
            "timeframe_minutes": timeframe_minutes,
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "rows": len(df),
        }
        self.access_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.access_log_path.open("a") as f:
            f.write(json.dumps(record) + "\n")
        return df
```

- [ ] **Step 4: Run tests**

```
python3 -m pytest equity_trading/tests/test_validation_data.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```
git add equity_trading/src/validation/data.py \
        equity_trading/tests/test_validation_data.py
git commit -m "feat(validation): add EvaluationContext + holdout access log (Task 4)"
```

---

## Task 5: Data partition script

**Files:**
- Create: `equity_trading/scripts/split_train_holdout.py`
- Test: `equity_trading/tests/test_split_train_holdout.py`

- [ ] **Step 1: Write failing test**

`equity_trading/tests/test_split_train_holdout.py`:

```python
"""Test the partition script splits parquet by date correctly."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest


def _make_full_parquet(root: Path, symbol: str, tf: int) -> None:
    src = root / "full"
    src.mkdir(parents=True, exist_ok=True)
    ts = pd.date_range("2023-01-01", "2025-12-31", freq=f"{tf}min", tz="UTC")
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1}, index=ts)
    df.to_parquet(src / f"{symbol}_{tf}min.parquet")


def test_split_creates_train_and_holdout_partitions(tmp_path):
    _make_full_parquet(tmp_path, "TECL", 5)
    _make_full_parquet(tmp_path, "TECL", 1440)

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from equity_trading.scripts.split_train_holdout import split_partitions

    split_partitions(data_root=tmp_path, holdout_cutoff="2024-05-01",
                     symbols=["TECL"], timeframes=[5, 1440])

    train_5 = pd.read_parquet(tmp_path / "train" / "TECL_5min.parquet")
    holdout_5 = pd.read_parquet(tmp_path / "holdout" / "TECL_5min.parquet")
    assert train_5.index.max() < pd.Timestamp("2024-05-01", tz="UTC")
    assert holdout_5.index.min() >= pd.Timestamp("2024-05-01", tz="UTC")
    assert len(train_5) + len(holdout_5) > 0
    # manifest written
    assert (tmp_path / "manifest.json").exists()
```

- [ ] **Step 2: Run to confirm fail**

```
python3 -m pytest equity_trading/tests/test_split_train_holdout.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement split script**

`equity_trading/scripts/split_train_holdout.py`:

```python
"""One-time data partition: split data/prices/full/SYMBOL_*min.parquet
into train/ (ts < cutoff) and holdout/ (ts >= cutoff), then compute manifest.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from equity_trading.src.validation.manifest import compute_manifest


def split_partitions(
    data_root: Path | str,
    holdout_cutoff: str,
    symbols: Sequence[str],
    timeframes: Sequence[int],
) -> None:
    data_root = Path(data_root)
    cutoff = pd.Timestamp(holdout_cutoff, tz="UTC")
    train_dir = data_root / "train"
    holdout_dir = data_root / "holdout"
    train_dir.mkdir(parents=True, exist_ok=True)
    holdout_dir.mkdir(parents=True, exist_ok=True)

    for symbol in symbols:
        for tf in timeframes:
            src = data_root / "full" / f"{symbol}_{tf}min.parquet"
            if not src.exists():
                print(f"[skip] {src} not found")
                continue
            df = pd.read_parquet(src)
            train_df = df[df.index < cutoff]
            holdout_df = df[df.index >= cutoff]
            train_df.to_parquet(train_dir / f"{symbol}_{tf}min.parquet")
            holdout_df.to_parquet(holdout_dir / f"{symbol}_{tf}min.parquet")
            print(f"[ok] {symbol} {tf}min: train n={len(train_df)}, holdout n={len(holdout_df)}")

    m = compute_manifest(data_root, holdout_cutoff=holdout_cutoff)
    m.write(data_root / "manifest.json")
    print(f"[saved] manifest.json with {len(m.file_hashes)} entries")


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    data_root = project_root / "data" / "prices"
    full_dir = data_root / "full"
    if not full_dir.exists():
        print(f"[ERROR] {full_dir} does not exist. Move existing parquet files there first:")
        print(f"  mkdir -p {full_dir}")
        print(f"  mv {data_root}/*.parquet {full_dir}/")
        return 1
    symbols = ["TECL", "TQQQ", "TNA", "UPRO", "UDOW"]
    timeframes = [5, 1440]
    split_partitions(data_root=data_root, holdout_cutoff="2024-05-01",
                     symbols=symbols, timeframes=timeframes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run unit tests**

```
python3 -m pytest equity_trading/tests/test_split_train_holdout.py -v
```

Expected: `1 passed`

- [ ] **Step 5: Manually run the partition on real data**

```
mkdir -p equity_trading/data/prices/full
# Move existing flat parquet files (NOT directories) to full/
find equity_trading/data/prices -maxdepth 1 -name "*.parquet" -exec mv {} equity_trading/data/prices/full/ \;
python3 equity_trading/scripts/split_train_holdout.py
```

Expected output:
```
[ok] TECL 5min: train n=..., holdout n=...
[ok] TECL 1440min: ...
...
[saved] manifest.json with 10 entries
```

Note: existing flat files like `TECL_5min_2019-05-01_2026-05-01.parquet` first need to be coalesced into `full/TECL_5min.parquet`. Add a quick coalesce step manually before running the script if needed:

```bash
python3 -c "
import pandas as pd, glob
from pathlib import Path
src = Path('equity_trading/data/prices/full')
for sym in ['TECL', 'TQQQ', 'TNA', 'UPRO', 'UDOW']:
    for tf in [5, 1440]:
        files = sorted(src.glob(f'{sym}_{tf}min_*.parquet'))
        if not files:
            continue
        dfs = [pd.read_parquet(f) for f in files]
        merged = pd.concat(dfs).sort_index()
        merged = merged[~merged.index.duplicated(keep='first')]
        out = src / f'{sym}_{tf}min.parquet'
        merged.to_parquet(out)
        print(f'{sym} {tf}min: {len(merged)} bars -> {out}')
"
python3 equity_trading/scripts/split_train_holdout.py
```

- [ ] **Step 6: Commit**

```
git add equity_trading/scripts/split_train_holdout.py \
        equity_trading/tests/test_split_train_holdout.py
git add equity_trading/data/prices/manifest.json
git add equity_trading/data/prices/train/ equity_trading/data/prices/holdout/
git commit -m "feat(validation): split price data into train/holdout (Task 5)"
```

---

## Task 6: PriceFetcher partition awareness

**Files:**
- Modify: `equity_trading/src/data/price_fetcher.py`
- Test: `equity_trading/tests/test_price_fetcher_partition.py` (new file, leave existing tests untouched)

- [ ] **Step 1: Read existing `equity_trading/src/data/price_fetcher.py`**

(Implementer reads the file to find the `cache_dir` usage point and the fetch method body. Look for the line that does `cache_path = self.cache_dir / filename` or similar.)

- [ ] **Step 2: Write failing test**

`equity_trading/tests/test_price_fetcher_partition.py`:

```python
"""PriceFetcher with partition kwarg routes reads to train/ vs holdout/."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from equity_trading.src.data.price_fetcher import PriceFetcher
from equity_trading.src.validation.data import HoldoutAccessError


class _StubBroker:
    """Avoids hitting Alpaca; returns empty DataFrame on fetch."""
    def fetch_bars(self, *args, **kwargs):
        return pd.DataFrame()


def _seed_partition(tmp_path: Path, partition: str, symbol: str, tf: int) -> None:
    p = tmp_path / partition
    p.mkdir(parents=True, exist_ok=True)
    ts = pd.date_range("2023-01-01", periods=10, freq=f"{tf}min", tz="UTC")
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1}, index=ts)
    df.to_parquet(p / f"{symbol}_{tf}min.parquet")


def test_pricefetcher_partition_train_loads_train_data(tmp_path):
    _seed_partition(tmp_path, "train", "TECL", 5)
    fetcher = PriceFetcher(broker=_StubBroker(), cache_dir=tmp_path, partition="train")
    df = fetcher.fetch(symbol="TECL", start=pd.Timestamp("2023-01-01", tz="UTC"),
                       end=pd.Timestamp("2024-01-01", tz="UTC"), timeframe_minutes=5)
    assert len(df) > 0


def test_pricefetcher_partition_train_rejects_holdout_dates(tmp_path):
    """When partition='train', requesting dates after cutoff should not fetch from holdout."""
    _seed_partition(tmp_path, "train", "TECL", 5)
    _seed_partition(tmp_path, "holdout", "TECL", 5)
    fetcher = PriceFetcher(broker=_StubBroker(), cache_dir=tmp_path, partition="train")
    # The fetcher in train mode never reads holdout/ — even if file exists there
    # (this test relies on the train-mode parquet only containing train rows)
    df = fetcher.fetch(symbol="TECL", start=pd.Timestamp("2023-01-01", tz="UTC"),
                       end=pd.Timestamp("2025-12-31", tz="UTC"), timeframe_minutes=5)
    # All rows must be from train partition (date < 2024-05-01 in real data;
    # in this seed, train rows are 2023-01-01)
    assert df.index.max() < pd.Timestamp("2024-05-01", tz="UTC")


def test_pricefetcher_default_partition_is_full_for_back_compat(tmp_path):
    """No partition arg means use cache_dir directly (legacy flat layout)."""
    # Seed flat directly
    ts = pd.date_range("2023-01-01", periods=10, freq="5min", tz="UTC")
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1}, index=ts)
    flat = tmp_path / "full"
    flat.mkdir(parents=True)
    df.to_parquet(flat / "TECL_5min.parquet")
    # Default partition == "full" — keeps existing behavior intact
    fetcher = PriceFetcher(broker=_StubBroker(), cache_dir=tmp_path)
    df_out = fetcher.fetch(symbol="TECL", start=pd.Timestamp("2023-01-01", tz="UTC"),
                            end=pd.Timestamp("2024-01-01", tz="UTC"), timeframe_minutes=5)
    assert len(df_out) > 0
```

- [ ] **Step 3: Run to confirm fail**

```
python3 -m pytest equity_trading/tests/test_price_fetcher_partition.py -v
```

Expected: 3 failures or `TypeError: PriceFetcher.__init__() got an unexpected keyword argument 'partition'`.

- [ ] **Step 4: Modify PriceFetcher**

In `equity_trading/src/data/price_fetcher.py`, locate the `__init__` and the cache directory usage. Add a `partition` kwarg:

```python
# In __init__:
def __init__(
    self, *,
    broker,
    cache_dir: Path,
    partition: str = "full",  # NEW: "full" (back compat) | "train" | "holdout"
):
    self.broker = broker
    self.cache_dir = Path(cache_dir)
    self.partition = partition

# Add a helper:
def _partition_dir(self) -> Path:
    return self.cache_dir / self.partition

# In fetch(), replace `self.cache_dir / filename` with `self._partition_dir() / filename`
```

(The exact diff depends on the current file structure — locate the cache path resolution and route through `_partition_dir`. Do NOT change Alpaca fetch fallback behavior.)

- [ ] **Step 5: Run new + existing tests**

```
python3 -m pytest equity_trading/tests/test_price_fetcher.py equity_trading/tests/test_price_fetcher_partition.py -v
```

Expected: existing test_price_fetcher tests still pass (back compat), new partition tests pass. All green.

- [ ] **Step 6: Commit**

```
git add equity_trading/src/data/price_fetcher.py \
        equity_trading/tests/test_price_fetcher_partition.py
git commit -m "feat(validation): PriceFetcher partition kwarg (Task 6)"
```

---

## Task 7: Gate 3 — sample size

**Files:**
- Create: `equity_trading/src/validation/gates/sample_size.py`
- Test: `equity_trading/tests/test_gate_sample_size.py`

- [ ] **Step 1: Write failing test**

`equity_trading/tests/test_gate_sample_size.py`:

```python
"""Sample-size gate."""
from __future__ import annotations

import pandas as pd

from equity_trading.src.validation.gates.base import Status
from equity_trading.src.validation.gates.sample_size import run_sample_size_gate


def _trades(n: int) -> pd.DataFrame:
    ts = pd.date_range("2024-06-01", periods=n, freq="1D", tz="UTC")
    return pd.DataFrame({
        "entry_ts": ts,
        "exit_ts": ts + pd.Timedelta(hours=2),
        "pnl_pct": [0.005] * n,
        "symbol": ["TECL"] * n,
    })


def test_sample_size_pass_when_n_well_above_min():
    res = run_sample_size_gate(holdout_trades=_trades(60), min_holdout_trades=30)
    assert res.status == Status.PASS
    assert "60" in res.summary
    assert res.metrics["n"] == 60


def test_sample_size_warn_in_borderline_band():
    res = run_sample_size_gate(holdout_trades=_trades(35), min_holdout_trades=30)
    assert res.status == Status.WARN  # 35 < 30 * 1.5


def test_sample_size_fail_below_minimum():
    res = run_sample_size_gate(holdout_trades=_trades(20), min_holdout_trades=30)
    assert res.status == Status.FAIL
    assert "20" in res.summary
```

- [ ] **Step 2: Run to confirm fail**

```
python3 -m pytest equity_trading/tests/test_gate_sample_size.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement gate**

`equity_trading/src/validation/gates/sample_size.py`:

```python
"""Gate 3: sample size — too few holdout trades = no statistical power."""
from __future__ import annotations

import pandas as pd

from equity_trading.src.validation.gates.base import GateResult, Status


def run_sample_size_gate(
    holdout_trades: pd.DataFrame,
    min_holdout_trades: int,
) -> GateResult:
    n = len(holdout_trades)
    if n < min_holdout_trades:
        status = Status.FAIL
        summary = f"n={n} < min={min_holdout_trades}: insufficient sample"
    elif n < min_holdout_trades * 1.5:
        status = Status.WARN
        summary = f"n={n} just above min={min_holdout_trades}: borderline power"
    else:
        status = Status.PASS
        summary = f"n={n} >= 1.5*min={int(min_holdout_trades*1.5)}: adequate"
    detail = (
        f"### Gate 3: Sample size {status.icon}\n\n"
        f"- holdout trades: **{n}**\n"
        f"- threshold: **{min_holdout_trades}** (FAIL below, WARN below 1.5x)\n"
        f"- {summary}\n"
    )
    return GateResult(name="sample_size", status=status, summary=summary,
                       detail_md=detail, metrics={"n": n, "min": min_holdout_trades})
```

- [ ] **Step 4: Run tests**

```
python3 -m pytest equity_trading/tests/test_gate_sample_size.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```
git add equity_trading/src/validation/gates/sample_size.py \
        equity_trading/tests/test_gate_sample_size.py
git commit -m "feat(validation): Gate 3 sample size (Task 7)"
```

---

## Task 8: Gate 2 — tail risk

**Files:**
- Create: `equity_trading/src/validation/gates/tail_risk.py`
- Test: `equity_trading/tests/test_gate_tail_risk.py`

- [ ] **Step 1: Write failing test**

`equity_trading/tests/test_gate_tail_risk.py`:

```python
"""Tail-risk gate: per-trade loss + portfolio MaxDD + rolling 30d."""
from __future__ import annotations

import pandas as pd

from equity_trading.src.validation.gates.base import Status
from equity_trading.src.validation.gates.tail_risk import run_tail_risk_gate


def _equity_curve(values: list[float], start_date: str = "2024-06-01") -> pd.DataFrame:
    ts = pd.date_range(start_date, periods=len(values), freq="1D", tz="UTC")
    return pd.DataFrame({"ts": ts, "equity": values})


def _trades(pnls: list[float]) -> pd.DataFrame:
    ts = pd.date_range("2024-06-01", periods=len(pnls), freq="1D", tz="UTC")
    return pd.DataFrame({
        "entry_ts": ts, "exit_ts": ts + pd.Timedelta(hours=2),
        "pnl_pct": pnls, "symbol": ["TECL"] * len(pnls),
    })


def test_tail_risk_pass_when_all_within_thresholds():
    eq = _equity_curve([100_000, 101_000, 100_500, 102_000])
    trades = _trades([0.01, -0.005, 0.015])
    res = run_tail_risk_gate(
        equity_curve=eq, trades=trades,
        max_single_trade_loss_pct=5.0,
        max_portfolio_dd_pct=20.0,
        max_rolling_30d_loss_pct=10.0,
    )
    assert res.status == Status.PASS


def test_tail_risk_fail_on_single_trade_loss():
    eq = _equity_curve([100_000, 95_000])
    trades = _trades([0.01, -0.06])  # -6% > 5% limit
    res = run_tail_risk_gate(
        equity_curve=eq, trades=trades,
        max_single_trade_loss_pct=5.0,
        max_portfolio_dd_pct=20.0,
        max_rolling_30d_loss_pct=10.0,
    )
    assert res.status == Status.FAIL
    assert "single trade" in res.summary.lower() or "trade" in res.summary.lower()


def test_tail_risk_fail_on_portfolio_dd():
    # 100k -> 78k = -22% drawdown
    eq = _equity_curve([100_000, 78_000])
    trades = _trades([-0.04])
    res = run_tail_risk_gate(
        equity_curve=eq, trades=trades,
        max_single_trade_loss_pct=5.0,
        max_portfolio_dd_pct=20.0,
        max_rolling_30d_loss_pct=10.0,
    )
    assert res.status == Status.FAIL
    assert "drawdown" in res.summary.lower() or "dd" in res.summary.lower()


def test_tail_risk_warn_on_rolling_30d():
    # Single 30-day window with -12% drop
    days = 60
    values = [100_000.0] * days
    for i in range(15, 30):  # mid drop
        values[i] = 88_000
    eq = _equity_curve(values)
    res = run_tail_risk_gate(
        equity_curve=eq, trades=_trades([0.0]),
        max_single_trade_loss_pct=5.0,
        max_portfolio_dd_pct=20.0,  # not triggered: 12% < 20%
        max_rolling_30d_loss_pct=10.0,
    )
    assert res.status == Status.WARN


def test_tail_risk_reports_catastrophic_stop_simulation():
    """When trades have one big loss, report what a 5% catastrophic cap would do."""
    eq = _equity_curve([100_000, 90_000])
    # One -10% trade — would be capped to -5% with catastrophic stop
    trades = _trades([-0.10])
    res = run_tail_risk_gate(
        equity_curve=eq, trades=trades,
        max_single_trade_loss_pct=5.0,
        max_portfolio_dd_pct=20.0,
        max_rolling_30d_loss_pct=10.0,
    )
    assert "catastrophic" in res.detail_md.lower() or "5%" in res.detail_md
    assert res.metrics.get("catastrophic_stop_worst_pct") is not None
```

- [ ] **Step 2: Run to confirm fail**

```
python3 -m pytest equity_trading/tests/test_gate_tail_risk.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement gate**

`equity_trading/src/validation/gates/tail_risk.py`:

```python
"""Gate 2: tail-risk — single-trade, portfolio DD, rolling 30d."""
from __future__ import annotations

import pandas as pd

from equity_trading.src.validation.gates.base import GateResult, Status


def _max_drawdown_pct(equity: pd.Series) -> float:
    running_max = equity.cummax()
    dd = (equity - running_max) / running_max
    return float(abs(dd.min() * 100)) if len(dd) > 0 else 0.0


def _max_rolling_loss_pct(eq_df: pd.DataFrame, window_days: int) -> float:
    """Worst (peak - trough) % within any rolling window of length window_days."""
    if len(eq_df) < 2:
        return 0.0
    eq = eq_df.set_index("ts")["equity"]
    eq = eq.sort_index()
    worst = 0.0
    for i, ts in enumerate(eq.index):
        end = ts + pd.Timedelta(days=window_days)
        window = eq[(eq.index >= ts) & (eq.index <= end)]
        if len(window) < 2:
            continue
        peak = window.iloc[0]
        trough = window.min()
        loss = (peak - trough) / peak * 100 if peak > 0 else 0.0
        worst = max(worst, loss)
    return float(worst)


def _catastrophic_stop_worst(trades: pd.DataFrame, cap_pct: float = 5.0) -> float:
    """If a 5% hard stop were applied, what's the worst trade pnl_pct?"""
    if len(trades) == 0:
        return 0.0
    capped = trades["pnl_pct"].apply(lambda p: max(p, -cap_pct / 100))
    return float(capped.min() * 100)


def run_tail_risk_gate(
    *,
    equity_curve: pd.DataFrame,           # columns: ts, equity
    trades: pd.DataFrame,                 # columns: entry_ts, exit_ts, pnl_pct, symbol
    max_single_trade_loss_pct: float,
    max_portfolio_dd_pct: float,
    max_rolling_30d_loss_pct: float,
) -> GateResult:
    worst_trade_pct = float(trades["pnl_pct"].min() * 100) if len(trades) > 0 else 0.0
    portfolio_dd_pct = _max_drawdown_pct(equity_curve["equity"])
    rolling_30d_loss_pct = _max_rolling_loss_pct(equity_curve, window_days=30)
    cat_stop_worst = _catastrophic_stop_worst(trades, cap_pct=5.0)

    failures: list[str] = []
    warnings: list[str] = []

    if abs(worst_trade_pct) > max_single_trade_loss_pct:
        failures.append(
            f"worst single trade {worst_trade_pct:.2f}% exceeds limit -{max_single_trade_loss_pct:.1f}%"
        )
    if portfolio_dd_pct > max_portfolio_dd_pct:
        failures.append(
            f"portfolio drawdown {portfolio_dd_pct:.2f}% exceeds limit {max_portfolio_dd_pct:.1f}%"
        )
    if rolling_30d_loss_pct > max_rolling_30d_loss_pct:
        warnings.append(
            f"30-day rolling loss {rolling_30d_loss_pct:.2f}% exceeds {max_rolling_30d_loss_pct:.1f}%"
        )

    if failures:
        status = Status.FAIL
        summary = "; ".join(failures)
    elif warnings:
        status = Status.WARN
        summary = "; ".join(warnings)
    else:
        status = Status.PASS
        summary = (
            f"worst trade {worst_trade_pct:.2f}%, MaxDD {portfolio_dd_pct:.2f}%, "
            f"30d rolling {rolling_30d_loss_pct:.2f}% — all within limits"
        )

    detail = (
        f"### Gate 2: Tail risk {status.icon}\n\n"
        f"- worst single trade: **{worst_trade_pct:.2f}%** (limit -{max_single_trade_loss_pct:.1f}%)\n"
        f"- portfolio MaxDD: **{portfolio_dd_pct:.2f}%** (limit {max_portfolio_dd_pct:.1f}%)\n"
        f"- 30-day rolling loss: **{rolling_30d_loss_pct:.2f}%** (limit {max_rolling_30d_loss_pct:.1f}%)\n"
        f"\n#### Catastrophic stop simulation (-5% cap on every trade)\n"
        f"- worst trade if cap were applied: **{cat_stop_worst:.2f}%**\n"
        f"- This is informational only. To apply, add a `catastrophic_stop_pct: 5.0` "
        f"override in the variant config and re-validate.\n"
    )
    return GateResult(name="tail_risk", status=status, summary=summary, detail_md=detail,
                       metrics={
                           "worst_trade_pct": worst_trade_pct,
                           "portfolio_dd_pct": portfolio_dd_pct,
                           "rolling_30d_loss_pct": rolling_30d_loss_pct,
                           "catastrophic_stop_worst_pct": cat_stop_worst,
                       })
```

- [ ] **Step 4: Run tests**

```
python3 -m pytest equity_trading/tests/test_gate_tail_risk.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```
git add equity_trading/src/validation/gates/tail_risk.py \
        equity_trading/tests/test_gate_tail_risk.py
git commit -m "feat(validation): Gate 2 tail risk + catastrophic-stop sim (Task 8)"
```

---

## Task 9: Gate 1 — out-of-sample (OOS)

**Files:**
- Create: `equity_trading/src/validation/gates/oos.py`
- Test: `equity_trading/tests/test_gate_oos.py`

- [ ] **Step 1: Write failing test**

`equity_trading/tests/test_gate_oos.py`:

```python
"""OOS gate: variant must beat baseline on holdout."""
from __future__ import annotations

import pandas as pd

from equity_trading.src.validation.gates.base import Status
from equity_trading.src.validation.gates.oos import run_oos_gate


def _result(ann_pct: float, dd_pct: float, sharpe: float) -> dict:
    return {"annualized_pct": ann_pct, "max_dd_pct": dd_pct, "sharpe": sharpe}


def test_oos_pass_when_variant_beats_baseline():
    res = run_oos_gate(
        variant_holdout=_result(15.0, -10.0, 1.2),
        baseline_holdout=_result(8.0, -12.0, 0.8),
        min_outperformance_pct=0.0,
    )
    assert res.status == Status.PASS
    assert "15.0" in res.summary or "15.00" in res.summary


def test_oos_fail_when_variant_underperforms():
    res = run_oos_gate(
        variant_holdout=_result(5.0, -10.0, 0.5),
        baseline_holdout=_result(8.0, -12.0, 0.8),
        min_outperformance_pct=0.0,
    )
    assert res.status == Status.FAIL


def test_oos_fail_when_variant_dd_120pct_worse_than_baseline():
    res = run_oos_gate(
        variant_holdout=_result(20.0, -25.0, 1.5),  # 25% DD vs baseline 18%
        baseline_holdout=_result(15.0, -18.0, 1.0),  # 18 * 1.2 = 21.6, 25 > 21.6
        min_outperformance_pct=0.0,
    )
    assert res.status == Status.FAIL
    assert "drawdown" in res.summary.lower() or "dd" in res.summary.lower()


def test_oos_warn_when_returns_better_but_sharpe_worse():
    res = run_oos_gate(
        variant_holdout=_result(20.0, -10.0, 0.7),
        baseline_holdout=_result(15.0, -10.0, 1.0),
        min_outperformance_pct=0.0,
    )
    assert res.status == Status.WARN
```

- [ ] **Step 2: Run to confirm fail**

```
python3 -m pytest equity_trading/tests/test_gate_oos.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement gate**

`equity_trading/src/validation/gates/oos.py`:

```python
"""Gate 1: out-of-sample — variant must beat baseline on holdout."""
from __future__ import annotations

from equity_trading.src.validation.gates.base import GateResult, Status


def run_oos_gate(
    *,
    variant_holdout: dict,    # {annualized_pct, max_dd_pct, sharpe}
    baseline_holdout: dict,
    min_outperformance_pct: float,
) -> GateResult:
    v_ann = variant_holdout["annualized_pct"]
    b_ann = baseline_holdout["annualized_pct"]
    v_dd = abs(variant_holdout["max_dd_pct"])
    b_dd = abs(baseline_holdout["max_dd_pct"])
    v_sharpe = variant_holdout["sharpe"]
    b_sharpe = baseline_holdout["sharpe"]

    fails: list[str] = []
    warns: list[str] = []

    return_diff = v_ann - b_ann
    if return_diff < min_outperformance_pct:
        fails.append(
            f"variant ann {v_ann:.2f}% < baseline ann {b_ann:.2f}% + threshold {min_outperformance_pct:.2f}%"
        )
    if v_dd > b_dd * 1.2:
        fails.append(
            f"variant drawdown {v_dd:.2f}% > 1.2x baseline DD {b_dd:.2f}% (excessive risk)"
        )
    if not fails and v_sharpe < b_sharpe:
        warns.append(
            f"variant Sharpe {v_sharpe:.2f} < baseline Sharpe {b_sharpe:.2f} "
            f"(returns up but risk-adjusted worse)"
        )

    if fails:
        status = Status.FAIL
        summary = "; ".join(fails)
    elif warns:
        status = Status.WARN
        summary = "; ".join(warns)
    else:
        status = Status.PASS
        summary = (
            f"variant ann {v_ann:.2f}% vs baseline {b_ann:.2f}% "
            f"(+{return_diff:.2f}pp), Sharpe {v_sharpe:.2f} vs {b_sharpe:.2f}"
        )

    detail = (
        f"### Gate 1: OOS holdout {status.icon}\n\n"
        f"| metric | variant | baseline | diff |\n"
        f"|---|---:|---:|---:|\n"
        f"| Annual return | {v_ann:+.2f}% | {b_ann:+.2f}% | {return_diff:+.2f}pp |\n"
        f"| Max drawdown | -{v_dd:.2f}% | -{b_dd:.2f}% | {-v_dd-(-b_dd):+.2f}pp |\n"
        f"| Sharpe | {v_sharpe:.2f} | {b_sharpe:.2f} | {v_sharpe-b_sharpe:+.2f} |\n"
        f"\n{summary}\n"
    )
    return GateResult(name="oos", status=status, summary=summary, detail_md=detail,
                       metrics={
                           "variant_ann": v_ann, "baseline_ann": b_ann,
                           "variant_dd": v_dd, "baseline_dd": b_dd,
                           "variant_sharpe": v_sharpe, "baseline_sharpe": b_sharpe,
                       })
```

- [ ] **Step 4: Run tests**

```
python3 -m pytest equity_trading/tests/test_gate_oos.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```
git add equity_trading/src/validation/gates/oos.py \
        equity_trading/tests/test_gate_oos.py
git commit -m "feat(validation): Gate 1 OOS comparison (Task 9)"
```

---

## Task 10: Markdown report writer

**Files:**
- Create: `equity_trading/src/validation/report.py`
- Test: `equity_trading/tests/test_validation_report.py`

- [ ] **Step 1: Write failing test**

`equity_trading/tests/test_validation_report.py`:

```python
"""Markdown report writer."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from equity_trading.src.validation.gates.base import GateResult, Status
from equity_trading.src.validation.report import (
    Headline,
    derive_headline,
    write_validation_report,
)


def _g(name: str, status: Status, summary: str = "ok", detail: str = "") -> GateResult:
    return GateResult(name=name, status=status, summary=summary,
                       detail_md=detail or f"### {name} {status.icon}\n\n{summary}")


def test_derive_headline_approve_when_all_pass():
    gates = [_g("oos", Status.PASS), _g("tail_risk", Status.PASS), _g("sample_size", Status.PASS)]
    assert derive_headline(gates) == Headline.APPROVE


def test_derive_headline_review_when_any_warn():
    gates = [_g("oos", Status.PASS), _g("tail_risk", Status.WARN), _g("sample_size", Status.PASS)]
    assert derive_headline(gates) == Headline.REVIEW


def test_derive_headline_reject_when_required_fail():
    gates = [_g("oos", Status.FAIL), _g("tail_risk", Status.PASS), _g("sample_size", Status.PASS)]
    assert derive_headline(gates) == Headline.REJECT


def test_write_validation_report(tmp_path):
    gates = [
        _g("oos", Status.PASS, "variant beats baseline"),
        _g("tail_risk", Status.WARN, "30d rolling 12%"),
        _g("sample_size", Status.PASS, "n=120"),
    ]
    out = tmp_path / "report.md"
    write_validation_report(
        path=out,
        variant_id="orb_tight_v2_1",
        baseline_id="orb_default_v0",
        gates=gates,
        git_sha="abc123",
        manifest_hash="def456",
        holdout_window=("2024-05-01", "2026-05-01"),
        generated_at=datetime(2026, 5, 3, 14, 32, tzinfo=timezone.utc),
    )
    text = out.read_text()
    assert "orb_tight_v2_1" in text
    assert "orb_default_v0" in text
    assert "abc123" in text
    assert "REVIEW" in text
    assert "OOS" in text or "oos" in text
    assert "tail_risk" in text or "Tail" in text
```

- [ ] **Step 2: Run to confirm fail**

```
python3 -m pytest equity_trading/tests/test_validation_report.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement report writer**

`equity_trading/src/validation/report.py`:

```python
"""Validation report writer (markdown)."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Iterable

from equity_trading.src.validation.gates.base import GateResult, Status

REQUIRED_GATES = {"oos", "tail_risk", "sample_size"}


class Headline(Enum):
    APPROVE = "APPROVE"
    REVIEW = "REVIEW"
    REJECT = "REJECT"

    @property
    def icon(self) -> str:
        return {"APPROVE": "✅", "REVIEW": "⚠️", "REJECT": "❌"}[self.value]


def derive_headline(gates: Iterable[GateResult]) -> Headline:
    gates = list(gates)
    required = [g for g in gates if g.name in REQUIRED_GATES]
    if any(g.status == Status.FAIL for g in required):
        return Headline.REJECT
    if any(g.status == Status.WARN for g in gates):
        return Headline.REVIEW
    return Headline.APPROVE


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
) -> None:
    headline = derive_headline(gates)
    lines: list[str] = []
    lines.append(f"# Validation Report: {variant_id}\n")
    lines.append(f"- **Variant**: `{variant_id}`")
    lines.append(f"- **Baseline**: `{baseline_id}`")
    lines.append(f"- **Generated**: {generated_at.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"- **Git SHA**: `{git_sha}`")
    lines.append(f"- **Data manifest hash**: `{manifest_hash}`")
    lines.append(f"- **Holdout window**: {holdout_window[0]} → {holdout_window[1]}")
    lines.append("")
    lines.append(f"## Headline: {headline.icon} **{headline.value}**\n")
    for g in gates:
        if g.name in REQUIRED_GATES and g.status == Status.FAIL:
            lines.append(f"- ❌ Required gate `{g.name}` failed: {g.summary}")
        elif g.status == Status.WARN:
            lines.append(f"- ⚠️ `{g.name}`: {g.summary}")
    lines.append("")
    lines.append("## Gate Results\n")
    for g in gates:
        lines.append(g.detail_md)
        lines.append("")
    lines.append("## Reproducibility\n")
    lines.append("```")
    lines.append(f"git checkout {git_sha}")
    lines.append("python3 -m equity_trading.validation.validate \\")
    lines.append(f"    --variant configs/{variant_id}.yaml \\")
    lines.append(f"    --baseline configs/{baseline_id}.yaml")
    lines.append("```")
    lines.append("")
    lines.append("## Decision Log\n")
    lines.append("(Fill in: APPROVED / REJECTED / reasoning)")
    lines.append("")
    Path(path).write_text("\n".join(lines))
```

- [ ] **Step 4: Run tests**

```
python3 -m pytest equity_trading/tests/test_validation_report.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```
git add equity_trading/src/validation/report.py \
        equity_trading/tests/test_validation_report.py
git commit -m "feat(validation): markdown report writer + headline (Task 10)"
```

---

## Task 11: CLI entry point

**Files:**
- Create: `equity_trading/src/validation/cli.py`
- Create: `equity_trading/src/validation/__main__.py`
- Test: `equity_trading/tests/test_validation_cli.py`

- [ ] **Step 1: Write failing test**

`equity_trading/tests/test_validation_cli.py`:

```python
"""CLI entry point smoke test."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from equity_trading.src.validation import cli


def _seed_variant_yaml(path: Path, variant_id: str) -> Path:
    body = f"""
variant_id: {variant_id}
description: cli test
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
"""
    path.write_text(body)
    return path


def test_cli_parses_args_and_loads_configs(tmp_path):
    v = _seed_variant_yaml(tmp_path / "v.yaml", "test_v1")
    b = _seed_variant_yaml(tmp_path / "b.yaml", "test_b0")
    args = cli.parse_args(["--variant", str(v), "--baseline", str(b),
                            "--output", str(tmp_path / "out.md"),
                            "--data-root", str(tmp_path / "fake_data")])
    assert args.variant == v
    assert args.baseline == b


def test_cli_main_returns_nonzero_when_data_missing(tmp_path):
    v = _seed_variant_yaml(tmp_path / "v.yaml", "test_v1")
    b = _seed_variant_yaml(tmp_path / "b.yaml", "test_b0")
    rc = cli.main([
        "--variant", str(v), "--baseline", str(b),
        "--output", str(tmp_path / "out.md"),
        "--data-root", str(tmp_path / "no_data"),
    ])
    assert rc != 0  # data missing → fail
```

- [ ] **Step 2: Run to confirm fail**

```
python3 -m pytest equity_trading/tests/test_validation_cli.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement CLI**

`equity_trading/src/validation/cli.py`:

```python
"""CLI: python3 -m equity_trading.validation.validate \\
        --variant configs/<id>.yaml \\
        --baseline configs/<id>.yaml \\
        --output phase0/validation/<id>.md
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from equity_trading.src.validation.config import load_variant_config
from equity_trading.src.validation.data import EvaluationContext
from equity_trading.src.validation.gates.oos import run_oos_gate
from equity_trading.src.validation.gates.sample_size import run_sample_size_gate
from equity_trading.src.validation.gates.tail_risk import run_tail_risk_gate
from equity_trading.src.validation.manifest import verify_manifest
from equity_trading.src.validation.report import write_validation_report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validation framework")
    p.add_argument("--variant", type=Path, required=True)
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--data-root", type=Path,
                    default=Path("equity_trading/data/prices"))
    return p.parse_args(argv)


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True,
        ).strip()
    except Exception:
        return "unknown"


def _manifest_hash(data_root: Path) -> str:
    mp = data_root / "manifest.json"
    if not mp.exists():
        return "no-manifest"
    import hashlib
    return hashlib.sha256(mp.read_bytes()).hexdigest()[:12]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.data_root.exists():
        print(f"[ERROR] data root not found: {args.data_root}", file=sys.stderr)
        return 2
    try:
        verify_manifest(args.data_root)
    except Exception as exc:
        print(f"[ERROR] manifest verification failed: {exc}", file=sys.stderr)
        return 2

    variant = load_variant_config(args.variant)
    baseline = load_variant_config(args.baseline)

    # Run portfolio simulations on holdout data for both variant and baseline.
    # The actual portfolio runner is plugged in via Task 12. For now we accept
    # that the CLI errors with a stub if the runner is not yet wired — Task 12
    # implements the wiring.
    try:
        from equity_trading.src.validation.runner import run_holdout_simulation
    except ImportError:
        print("[ERROR] portfolio runner not available (Task 12 prerequisite). "
              "Wire equity_trading.src.validation.runner first.", file=sys.stderr)
        return 3

    with EvaluationContext(
        root=args.data_root, variant_id=variant.variant_id,
        reason="cli:validate",
    ) as ctx:
        v_summary, v_trades, v_equity = run_holdout_simulation(variant, ctx)
        b_summary, b_trades, b_equity = run_holdout_simulation(baseline, ctx)

    gates = []
    gates.append(run_oos_gate(
        variant_holdout=v_summary,
        baseline_holdout=b_summary,
        min_outperformance_pct=variant.gates["oos"]["min_outperformance_pct"],
    ))
    gates.append(run_tail_risk_gate(
        equity_curve=v_equity, trades=v_trades,
        max_single_trade_loss_pct=variant.gates["tail_risk"]["max_single_trade_loss_pct"],
        max_portfolio_dd_pct=variant.gates["tail_risk"]["max_portfolio_dd_pct"],
        max_rolling_30d_loss_pct=variant.gates["tail_risk"]["max_rolling_30d_loss_pct"],
    ))
    gates.append(run_sample_size_gate(
        holdout_trades=v_trades,
        min_holdout_trades=variant.gates["sample_size"]["min_holdout_trades"],
    ))

    write_validation_report(
        path=args.output, variant_id=variant.variant_id, baseline_id=baseline.variant_id,
        gates=gates, git_sha=_git_sha(), manifest_hash=_manifest_hash(args.data_root),
        holdout_window=(variant.gates["oos"]["holdout_start"], variant.gates["oos"]["holdout_end"]),
        generated_at=datetime.now(timezone.utc),
    )
    print(f"[saved] {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`equity_trading/src/validation/__main__.py`:

```python
"""python3 -m equity_trading.validation entry."""
from __future__ import annotations

import sys

from equity_trading.src.validation.cli import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run smoke tests**

```
python3 -m pytest equity_trading/tests/test_validation_cli.py -v
```

Expected: `2 passed` (the second one returns nonzero due to missing data, which is what we test for).

- [ ] **Step 5: Commit**

```
git add equity_trading/src/validation/cli.py \
        equity_trading/src/validation/__main__.py \
        equity_trading/tests/test_validation_cli.py
git commit -m "feat(validation): CLI entry point (Task 11)"
```

---

## Task 12: Refactor portfolio runner to consume variant config

**Files:**
- Create: `equity_trading/src/validation/runner.py`
- Modify: `equity_trading/scripts/run_portfolio_ensemble.py`
- Test: `equity_trading/tests/test_validation_runner.py`

- [ ] **Step 1: Write failing test**

`equity_trading/tests/test_validation_runner.py`:

```python
"""Portfolio runner that consumes variant config + EvaluationContext."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from equity_trading.src.validation.config import load_variant_config
from equity_trading.src.validation.data import EvaluationContext
from equity_trading.src.validation.runner import run_holdout_simulation


def _seed_data(root: Path) -> None:
    for sym in ["TECL"]:
        for tf in [5, 1440]:
            ts = pd.date_range("2024-05-02 14:30", "2026-05-01 21:00", freq=f"{tf}min", tz="UTC")
            df = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5,
                                "volume": 1000}, index=ts)
            (root / "holdout").mkdir(parents=True, exist_ok=True)
            df.to_parquet(root / "holdout" / f"{sym}_{tf}min.parquet")


def _seed_variant(path: Path) -> Path:
    body = """
variant_id: t
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
  oos: {holdout_start: "2024-05-01", holdout_end: "2026-05-01", min_outperformance_pct: 0.0}
  tail_risk: {max_single_trade_loss_pct: 5.0, max_portfolio_dd_pct: 20.0, max_rolling_30d_loss_pct: 10.0}
  sample_size: {min_holdout_trades: 30}
"""
    path.write_text(body)
    return path


def test_run_holdout_simulation_returns_summary_trades_equity(tmp_path):
    _seed_data(tmp_path)
    cfg = load_variant_config(_seed_variant(tmp_path / "v.yaml"))
    with EvaluationContext(root=tmp_path, variant_id="t", reason="test") as ctx:
        summary, trades, equity = run_holdout_simulation(cfg, ctx)
    assert "annualized_pct" in summary
    assert "max_dd_pct" in summary
    assert "sharpe" in summary
    assert isinstance(trades, pd.DataFrame)
    assert isinstance(equity, pd.DataFrame)
    assert "ts" in equity.columns and "equity" in equity.columns
```

- [ ] **Step 2: Run to confirm fail**

```
python3 -m pytest equity_trading/tests/test_validation_runner.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement runner**

`equity_trading/src/validation/runner.py`:

```python
"""Portfolio runner: consumes a VariantConfig + EvaluationContext, returns
(summary, trades, equity_curve). Re-uses simulate_strategy from phase0.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from equity_trading.src.phase0.atr_analyzer import analyze_atr_distribution
from equity_trading.src.phase0.strategy_simulator import simulate_strategy
from equity_trading.src.validation.config import VariantConfig
from equity_trading.src.validation.data import EvaluationContext


def _collect_trades(cfg: VariantConfig, ctx: EvaluationContext) -> pd.DataFrame:
    out: list[pd.DataFrame] = []
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
    df = df.drop_duplicates(subset=["symbol", "entry_ts"], keep="first")
    return df.sort_values("entry_ts").reset_index(drop=True)


def _simulate_portfolio(
    trades: pd.DataFrame, starting_equity: float,
    position_size_pct: float, max_concurrent: int,
) -> tuple[dict, pd.DataFrame]:
    if len(trades) == 0:
        return {"annualized_pct": 0.0, "max_dd_pct": 0.0, "sharpe": 0.0,
                "final_equity": starting_equity}, pd.DataFrame(columns=["ts", "equity"])
    equity = starting_equity
    open_pos: list[dict] = []
    eq_curve = [(trades["entry_ts"].iloc[0] - pd.Timedelta(seconds=1), equity)]
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
        open_pos.append({"symbol": t["symbol"], "exit_ts": t["exit_ts"],
                          "dollars": equity * position_size_pct, "pnl_pct": t["pnl_pct"]})
    final_close = trades["exit_ts"].max() + pd.Timedelta(seconds=1)
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
    return summary, eq_df


def run_holdout_simulation(
    cfg: VariantConfig, ctx: EvaluationContext,
) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    trades = _collect_trades(cfg, ctx)
    summary, equity_curve = _simulate_portfolio(
        trades=trades,
        starting_equity=cfg.portfolio["starting_equity_usd"],
        position_size_pct=cfg.portfolio["position_size_pct"],
        max_concurrent=cfg.portfolio["max_concurrent"],
    )
    return summary, trades, equity_curve
```

- [ ] **Step 4: Run tests**

```
python3 -m pytest equity_trading/tests/test_validation_runner.py -v
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```
git add equity_trading/src/validation/runner.py \
        equity_trading/tests/test_validation_runner.py
git commit -m "feat(validation): config-driven holdout portfolio runner (Task 12)"
```

---

## Task 13: End-to-end demo + first real validation reports

**Files:**
- Create: `equity_trading/configs/orb_default_v0.yaml`
- Create: `equity_trading/configs/orb_tight_v2_1.yaml`
- Test: `equity_trading/tests/test_validation_e2e.py`

- [ ] **Step 1: Create variant configs**

`equity_trading/configs/orb_default_v0.yaml`:

```yaml
variant_id: orb_default_v0
description: |
  Legacy ORB exits (stop=OR_low, target=OR_high+1R) + LHM ensemble.
  Used as the baseline against which v2.1 is measured.
strategies:
  - class: OpeningRangeBreakoutStrategy
    symbols: [TECL, TQQQ, TNA]
    params:
      or_window_bars: 12
      stop_mult: 0.0
      target_mult: 1.0
      cost_pct: 0.10
  - class: LastHourMomentumStrategy
    symbols: [UPRO, UDOW]
    params:
      threshold: 0.003
      _max_hold_bars: 60
      cost_pct: 0.10
portfolio:
  position_size_pct: 0.25
  max_concurrent: 3
  starting_equity_usd: 100000
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
```

`equity_trading/configs/orb_tight_v2_1.yaml`:

```yaml
variant_id: orb_tight_v2_1
description: |
  ORB exits tightened to stop=OR_low+0.25R, target=OR_high+2R based on
  a 7-yr in-sample sweep of (stop_mult, target_mult). This config is the
  unit being validated on the holdout.
parent_baseline: orb_default_v0
strategies:
  - class: OpeningRangeBreakoutStrategy
    symbols: [TECL, TQQQ, TNA]
    params:
      or_window_bars: 12
      stop_mult: 0.25
      target_mult: 2.0
      cost_pct: 0.10
  - class: LastHourMomentumStrategy
    symbols: [UPRO, UDOW]
    params:
      threshold: 0.003
      _max_hold_bars: 60
      cost_pct: 0.10
portfolio:
  position_size_pct: 0.25
  max_concurrent: 3
  starting_equity_usd: 100000
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
```

- [ ] **Step 2: Write E2E test**

`equity_trading/tests/test_validation_e2e.py`:

```python
"""End-to-end: load both configs, run validate CLI on real holdout data."""
from __future__ import annotations

from pathlib import Path

import pytest

from equity_trading.src.validation import cli

REPO = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO / "equity_trading" / "data" / "prices"
HOLDOUT_DIR = DATA_ROOT / "holdout"


@pytest.mark.skipif(not HOLDOUT_DIR.exists(), reason="holdout data not yet partitioned (Task 5 not run)")
def test_e2e_orb_v2_1_vs_v0(tmp_path):
    out = tmp_path / "report.md"
    rc = cli.main([
        "--variant", str(REPO / "equity_trading/configs/orb_tight_v2_1.yaml"),
        "--baseline", str(REPO / "equity_trading/configs/orb_default_v0.yaml"),
        "--output", str(out),
        "--data-root", str(DATA_ROOT),
    ])
    assert rc == 0
    text = out.read_text()
    # Headline must be one of the three
    assert any(h in text for h in ["APPROVE", "REVIEW", "REJECT"])
    # All three required gates must appear
    for gate in ["OOS", "Tail", "Sample"]:
        assert gate in text or gate.lower() in text
```

- [ ] **Step 3: Run E2E test (auto-skips if data not partitioned yet)**

```
python3 -m pytest equity_trading/tests/test_validation_e2e.py -v
```

Expected: PASS or skip-with-reason.

- [ ] **Step 4: Manually run the validation and inspect**

```
mkdir -p equity_trading/phase0/validation
python3 -m equity_trading.validation \
    --variant equity_trading/configs/orb_tight_v2_1.yaml \
    --baseline equity_trading/configs/orb_default_v0.yaml \
    --output equity_trading/phase0/validation/2026-05-03_orb_v2_1.md
```

Expected: report file written. Open it. Verify:
- Headline shows APPROVE / REVIEW / REJECT
- All 3 required gate sections present
- Reproducibility manifest with git SHA + manifest hash
- Decision Log section is empty (for human to fill)

- [ ] **Step 5: Commit**

```
git add equity_trading/configs/orb_default_v0.yaml \
        equity_trading/configs/orb_tight_v2_1.yaml \
        equity_trading/tests/test_validation_e2e.py \
        equity_trading/phase0/validation/2026-05-03_orb_v2_1.md
git commit -m "feat(validation): E2E demo — orb_tight_v2_1 holdout report (Task 13)"
```

---

## Task 14: RUNBOOK update — validation procedure

**Files:**
- Modify: `equity_trading/docs/RUNBOOK.md`

- [ ] **Step 1: Read existing RUNBOOK to find a sensible insertion point**

```
grep -n "## " equity_trading/docs/RUNBOOK.md
```

Insert the new section right after the `## What this bot does` section (before the validation hits / projections).

- [ ] **Step 2: Add a "Strategy change validation" section**

Add this section to `equity_trading/docs/RUNBOOK.md` (after `## What this bot does`):

```markdown
## Strategy change validation (敏腕 v3 framework)

Before deploying any strategy variant change to paper trading, run the
validation framework:

```
python3 -m equity_trading.validation \\
    --variant equity_trading/configs/<new_variant>.yaml \\
    --baseline equity_trading/configs/<current_baseline>.yaml \\
    --output equity_trading/phase0/validation/$(date +%Y-%m-%d)_<variant_id>.md
```

The framework:
1. Verifies `data/prices/manifest.json` matches on-disk parquets (rejects start otherwise)
2. Reads variant + baseline strategy configs (YAML, single source of truth)
3. Loads `data/prices/holdout/` via `EvaluationContext` (every read is logged to `holdout_access.jsonl`)
4. Runs portfolio simulation on holdout for both variant and baseline
5. Runs three required gates: OOS comparison, tail risk, sample size
6. Writes a markdown report with PASS/FAIL/WARN per gate and a headline (APPROVE / REVIEW / REJECT)

Required gate thresholds (from variant config):
- **OOS**: variant annualized return must be ≥ baseline; variant drawdown must be ≤ 1.2x baseline
- **Tail risk**: worst single trade ≤ 5% loss, portfolio MaxDD ≤ 20%, 30-day rolling ≤ 10%
- **Sample size**: ≥ 30 trades on holdout

A REJECT result blocks deployment. Iterate on `data/prices/train/` only;
**never modify code based on holdout observations** (that is the curve-fit
trap this framework prevents).

After deployment, the holdout is "burned" — accumulate new paper-trade
data and refresh the holdout cutoff before the next variant test.
```

- [ ] **Step 3: Verify markdown renders cleanly**

```
git diff equity_trading/docs/RUNBOOK.md
```

(Visually check the diff is well-formed.)

- [ ] **Step 4: Commit**

```
git add equity_trading/docs/RUNBOOK.md
git commit -m "docs(validation): add strategy-change validation procedure to RUNBOOK (Task 14)"
```

---

## Task 15: Retrofit existing run_portfolio_ensemble.py to read variant config

**Files:**
- Modify: `equity_trading/scripts/run_portfolio_ensemble.py`
- Test: `equity_trading/tests/test_run_portfolio_ensemble_config.py`

This addresses spec acceptance criterion §12.6. The script keeps its current
behavior (7-yr in-sample analysis writing `phase0/portfolio_ensemble_long.md`)
but now sources its strategy list from a YAML config instead of the hardcoded
`SELECTED` literal.

- [ ] **Step 1: Read existing `equity_trading/scripts/run_portfolio_ensemble.py`** to locate the `SELECTED = [...]` block (around lines 41-55) and the `collect_all_trades` function that reads it.

- [ ] **Step 2: Write failing test**

`equity_trading/tests/test_run_portfolio_ensemble_config.py`:

```python
"""run_portfolio_ensemble retrofit: SELECTED replaced by config-driven loader."""
from __future__ import annotations

from pathlib import Path

from equity_trading.scripts.run_portfolio_ensemble import selected_from_config


def _seed_yaml(p: Path) -> Path:
    p.write_text("""
variant_id: legacy_orb_lhm
description: legacy
strategies:
  - class: OpeningRangeBreakoutStrategy
    symbols: [TECL, TQQQ]
    params: {or_window_bars: 12, stop_mult: 0.0, target_mult: 1.0, cost_pct: 0.10}
  - class: LastHourMomentumStrategy
    symbols: [UPRO]
    params: {threshold: 0.003, _max_hold_bars: 60, cost_pct: 0.10}
portfolio: {position_size_pct: 0.25, max_concurrent: 3, starting_equity_usd: 100000}
gates:
  oos: {holdout_start: "2024-05-01", holdout_end: "2026-05-01", min_outperformance_pct: 0.0}
  tail_risk: {max_single_trade_loss_pct: 5.0, max_portfolio_dd_pct: 20.0, max_rolling_30d_loss_pct: 10.0}
  sample_size: {min_holdout_trades: 30}
""")
    return p


def test_selected_from_config_returns_5_tuples(tmp_path):
    sel = selected_from_config(_seed_yaml(tmp_path / "c.yaml"))
    assert len(sel) == 3  # 2 ORB + 1 LHM
    for entry in sel:
        assert len(entry) == 5  # (cls, sym, params, label, cost)
    cls0, sym0, params0, label0, cost0 = sel[0]
    from equity_trading.src.strategy.strategies.opening_range_breakout import OpeningRangeBreakoutStrategy
    assert cls0 is OpeningRangeBreakoutStrategy
    assert sym0 == "TECL"
    assert params0["or_window_bars"] == 12
    assert label0 == "OpeningRangeBreakoutStrategy_TECL"
    assert cost0 == 0.10
```

- [ ] **Step 3: Run to confirm fail**

```
python3 -m pytest equity_trading/tests/test_run_portfolio_ensemble_config.py -v
```

Expected: `ImportError: cannot import name 'selected_from_config'`.

- [ ] **Step 4: Modify `run_portfolio_ensemble.py`**

In `equity_trading/scripts/run_portfolio_ensemble.py`:

1. Add import at the top of the script:
   ```python
   from equity_trading.src.validation.config import load_variant_config
   ```

2. Replace the entire `SELECTED = [...]` literal (around lines 52-60) with:
   ```python
   def selected_from_config(config_path):
       """Load (cls, symbol, params, label, cost_pct) tuples from a variant YAML.
   
       Replaces the hardcoded SELECTED literal — strategy params now live only
       in YAML configs, eliminating dual-namespace drift.
       """
       cfg = load_variant_config(config_path)
       out = []
       for entry in cfg.strategies:
           cls = cfg.resolve_strategy_class(entry["class"])
           for sym in entry["symbols"]:
               params = dict(entry["params"])
               cost = params.pop("cost_pct", 0.10)
               label = f"{cls.__name__}_{sym}"
               out.append((cls, sym, params, label, cost))
       return out
   
   # Default config used by main() — equivalent to old hardcoded list.
   DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "orb_default_v0.yaml"
   SELECTED = selected_from_config(DEFAULT_CONFIG_PATH)
   ```

3. Add a `--config` arg to `main()`:
   ```python
   def main() -> int:
       import argparse
       parser = argparse.ArgumentParser()
       parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
       args = parser.parse_args()
       global SELECTED
       SELECTED = selected_from_config(args.config)
       # ... rest of main unchanged
   ```

- [ ] **Step 5: Run new test + existing tests**

```
python3 -m pytest equity_trading/tests/test_run_portfolio_ensemble_config.py -v
python3 -m pytest equity_trading/tests/ --tb=short
```

Expected: new test passes; existing 230+ tests still pass (the script's behavior with default config is identical to the old hardcoded SELECTED).

- [ ] **Step 6: Smoke-test the script itself runs**

```
python3 equity_trading/scripts/run_portfolio_ensemble.py --config equity_trading/configs/orb_default_v0.yaml
```

Expected: same output as before (trades collected, scenarios A/B/C printed, `phase0/portfolio_ensemble_long.md` updated). No errors.

- [ ] **Step 7: Commit**

```
git add equity_trading/scripts/run_portfolio_ensemble.py \
        equity_trading/tests/test_run_portfolio_ensemble_config.py
git commit -m "refactor(validation): run_portfolio_ensemble reads variant config (Task 15)"
```

---

## Final verification

After all 15 tasks:

- [ ] **Run the entire test suite**

```
python3 -m pytest equity_trading/tests/ --tb=short
```

Expected: all tests pass (existing 230 + ~14 new from this plan).

- [ ] **Manually run the demo validation one more time**

```
python3 -m equity_trading.validation \
    --variant equity_trading/configs/orb_tight_v2_1.yaml \
    --baseline equity_trading/configs/orb_default_v0.yaml \
    --output /tmp/final_check.md
cat /tmp/final_check.md
```

Sanity-check the report has all sections (headline, 3 gates, reproducibility, decision log).

- [ ] **Audit holdout access log**

```
cat equity_trading/data/prices/holdout_access.jsonl
```

Expected: every read of holdout data has a JSON record with variant_id, reason, timestamp. If empty, the framework didn't actually read holdout (bug).

- [ ] **Confirm acceptance criteria from spec**

| § | Criterion | Verified by |
|---|-----------|------------|
| 12.1 | CLI runs and outputs markdown | Manual demo (above) |
| 12.2 | Report contains 3 gates + headline | E2E test |
| 12.3 | Holdout direct access raises | Task 4 unit test |
| 12.4 | Manifest tampering detected | Task 3 unit test |
| 12.5 | All tests pass | pytest run (above) |
| 12.6 | Portfolio runner config-driven | Task 15 (existing script) + Task 12 (new runner) |
| 12.7 | RUNBOOK has validation section | Task 14 commit |

If all 7 are ✓, the framework v1 is complete.
