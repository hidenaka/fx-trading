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
