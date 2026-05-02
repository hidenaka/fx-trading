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
