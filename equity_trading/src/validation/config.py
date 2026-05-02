"""Variant config YAML loader and schema validator.

A variant config is the single source of truth for strategy parameters,
portfolio sizing, and gate thresholds. Eliminates dual-namespace bugs
(stop_mult vs stop_multiplier) by being the only place values are defined.
"""
from __future__ import annotations

from dataclasses import dataclass
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
    if not isinstance(raw["strategies"], list):
        raise ValueError(f"{path}: 'strategies' must be a list, got {type(raw['strategies']).__name__}")
    if not isinstance(raw["gates"], dict):
        raise ValueError(f"{path}: 'gates' must be a mapping, got {type(raw['gates']).__name__}")
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
