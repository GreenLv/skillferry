"""Render workspace assets into each agent's native formats.

The render layer never writes to disk itself; it fills ``SyncPlan`` with
changes, conflicts, grades, and concrete operations per target. Adaptors own
the target-specific formats; this package owns the shared ownership ledger
semantics (create / update / adopt / conflict / delete).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..models import Conflict

if TYPE_CHECKING:
    from ..adapters.base import Adapter, TargetEnv
    from ..models import SyncPlan, TargetApply
    from ..workspace import Extension, ServerSpec, Skill, Workspace


@dataclass
class RenderContext:
    """Everything one target's render pass needs."""

    ws: Workspace
    adapter: Adapter
    env: TargetEnv
    target: str
    plan: SyncPlan
    apply: TargetApply
    skills: dict[str, Skill]
    servers: dict[str, ServerSpec]
    extensions: dict[str, Extension]
    previous: dict[str, Any] = field(default_factory=dict)
    next_ledger: dict[str, Any] = field(default_factory=dict)
    resolutions: dict[str, str] = field(default_factory=dict)

    def conflict(self, kind: str, name: str, path: str, reason: str, resolution_id: str) -> None:
        self.plan.conflicts.append(
            Conflict(
                kind=kind,
                target=self.target,
                name=name,
                path=path,
                reason=reason,
                resolution_id=resolution_id,
            )
        )

    def resolve(self, resolution_id: str, *, default: str = "conflict") -> str:
        """Map a pending conflict id to adopt / overwrite / keep-local / conflict."""
        decision = self.resolutions.get(resolution_id, default)
        if decision in ("adopt", "keep-local"):
            return "adopt"
        if decision == "overwrite":
            return "overwrite"
        return "conflict"


def effective_targets(skill: Skill, ws: Workspace) -> tuple[str, ...]:
    return skill.targets if skill.targets is not None else ws.skills.default_targets
