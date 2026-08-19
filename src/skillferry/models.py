"""Shared plan/change model types.

Grades are the portability contract: every rendered asset receives one of
``native / translated / degraded / manual / unsupported`` plus notes that say
what was lost or what the user must do by hand.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

Action = Literal["create", "update", "delete", "adopt"]
Grade = Literal["native", "translated", "degraded", "manual", "unsupported"]
Kind = Literal["skill", "rules", "mcp", "extension"]

SUPPORTED_TARGETS = ("codex", "claude", "dsh")
SUPPORTED_PLATFORMS = ("macos", "windows", "linux")


@dataclass(frozen=True)
class Change:
    kind: Kind
    target: str
    name: str
    action: Action
    path: str


@dataclass(frozen=True)
class Conflict:
    kind: Kind
    target: str
    name: str
    path: str
    reason: str
    resolution_id: str


@dataclass(frozen=True)
class GradeReport:
    kind: Kind
    name: str
    target: str
    grade: Grade
    notes: tuple[str, ...]


@dataclass(frozen=True)
class FileCopy:
    source: Path
    target: Path
    mode: int | None = None  # None keeps the source mode


@dataclass(frozen=True)
class TextWrite:
    target: Path
    text: str
    mode: int
    label: str  # short name used for the backup path and logs
    redact_backup: bool = True


@dataclass(frozen=True)
class FileDelete:
    target: Path


@dataclass
class TargetApply:
    """All disk operations plus the next ownership ledger for one target."""

    target: str
    roots: list[Path] = field(default_factory=list)
    copies: list[FileCopy] = field(default_factory=list)
    writes: list[TextWrite] = field(default_factory=list)
    deletes: list[FileDelete] = field(default_factory=list)
    ledger: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class SyncPlan:
    workspace_root: Path
    platform: str
    targets: tuple[str, ...]
    homes: dict[str, Path]
    changes: list[Change] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    grades: list[GradeReport] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    manual_steps: dict[str, list[str]] = field(default_factory=dict)
    applies: dict[str, TargetApply] = field(default_factory=dict)

    def public_dict(self) -> dict[str, Any]:
        """JSON-safe plan summary; never contains resolved secret values."""
        return {
            "schema_version": 1,
            "platform": self.platform,
            "workspace_root": str(self.workspace_root),
            "targets": list(self.targets),
            "homes": {target: str(path) for target, path in self.homes.items()},
            "grades": [asdict(item) for item in self.grades],
            "changes": [asdict(item) for item in self.changes],
            "conflicts": [asdict(item) for item in self.conflicts],
            "warnings": list(self.warnings),
            "manual_steps": {
                key: list(value) for key, value in self.manual_steps.items()
            },
        }
