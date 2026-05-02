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
