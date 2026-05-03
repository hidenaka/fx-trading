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
