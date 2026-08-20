"""Adapter contract: every rendering target implements this interface.

An adapter declares *where* each asset type lands, the grade (and evidence
notes) each asset receives, and how MCP servers are rendered into the target's
native format. Grades must be backed by the capability evidence in
docs/AGENT_MATRIX.md — an adapter never claims ``native`` for an untested
behavior.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..models import GradeReport
from ..workspace import Extension, ServerSpec, Skill

if TYPE_CHECKING:
    from ..render import RenderContext


@dataclass(frozen=True)
class TargetEnv:
    platform: str
    home: Path
    codex_home: Path
    claude_home: Path
    dsh_home: Path
    dsh_profile: str


def _pick(override: str | None, env_name: str, default: Path, label: str) -> Path:
    if override:
        candidate = Path(override).expanduser()
    elif os.environ.get(env_name):
        candidate = Path(os.environ[env_name]).expanduser()
    else:
        candidate = default
    if candidate.is_symlink():
        raise ValueError(f"{label} may not be a symlink: {candidate}")
    return candidate.resolve()


def resolve_target_env(
    *,
    platform: str,
    home: str | None = None,
    codex_home: str | None = None,
    claude_home: str | None = None,
    dsh_home: str | None = None,
    dsh_profile: str | None = None,
) -> TargetEnv:
    base = Path(home).expanduser().resolve() if home else Path.home()
    codex = _pick(codex_home, "CODEX_HOME", base / ".codex", "codex home")
    claude = _pick(claude_home, "CLAUDE_HOME", base / ".claude", "claude home")
    dsh = _pick(dsh_home, "DSH_HOME", base / ".dsh", "dsh home")
    profile = dsh_profile or os.environ.get("DSH_PROFILE") or "web"
    return TargetEnv(
        platform=platform,
        home=base,
        codex_home=codex,
        claude_home=claude,
        dsh_home=dsh,
        dsh_profile=profile,
    )


class Adapter(ABC):
    name: str
    label: str
    protected_names: tuple[str, ...] = ()
    protected_mcp_servers: tuple[str, ...] = ()

    @abstractmethod
    def skill_dir(self, env: TargetEnv) -> Path | None: ...

    @abstractmethod
    def rules_file(self, env: TargetEnv) -> Path | None: ...

    @abstractmethod
    def managed_roots(self, env: TargetEnv) -> list[Path]: ...

    def grade_skill(self, skill: Skill) -> GradeReport:
        return GradeReport("skill", skill.name, self.name, "native", ())

    @abstractmethod
    def rules_grade(self, strategy: str) -> tuple[str, tuple[str, ...]]: ...

    @abstractmethod
    def grade_mcp(self, server: ServerSpec) -> tuple[str, tuple[str, ...]]: ...

    @abstractmethod
    def grade_extension(self, extension: Extension) -> tuple[str, tuple[str, ...]]: ...

    def mcp_plan_server(
        self, ctx: RenderContext, server: ServerSpec, next_state: dict[str, dict[str, Any]]
    ) -> None:
        """Plan one stdio server. Adapters that render all servers into one
        file override ``mcp_plan_all`` instead and declare ``plan_all_servers``."""
        raise NotImplementedError(
            f"{self.name} adapter implements neither mcp_plan_server nor mcp_plan_all"
        )

    @abstractmethod
    def manual_mcp_instructions(self, server: ServerSpec) -> str: ...

    @abstractmethod
    def extension_instructions(self, extension: Extension) -> str: ...


def hash_decision(
    ctx: RenderContext,
    *,
    resolution_id: str,
    current_hash: str | None,
    source_hash: str,
    prior_hash: str | None,
    kind: str,
    name: str,
    path: str,
) -> tuple[str, str | None]:
    """Shared ownership decision for a hash-tracked asset.

    Returns ``(action, next_hash)`` with action in
    ``create / update / adopt / none / adopt-local / conflict``. Conflicts are
    appended to the plan unless a ``--resolve`` decision overrides them.
    """
    if current_hash is None:
        return "create", source_hash
    if current_hash == source_hash:
        return ("adopt" if prior_hash is None else "none"), source_hash
    if prior_hash is None:
        decision = ctx.resolve(resolution_id)
        if decision == "overwrite":
            return "update", source_hash
        if decision == "adopt":
            return "adopt-local", current_hash
        ctx.conflict(kind, name, path, "refusing to overwrite an unregistered entry", resolution_id)
        return "conflict", None
    if current_hash != prior_hash:
        decision = ctx.resolve(resolution_id)
        if decision == "overwrite":
            return "update", source_hash
        if decision == "adopt":
            return "adopt-local", current_hash
        ctx.conflict(kind, name, path, "managed entry was modified locally", resolution_id)
        return "conflict", None
    return "update", source_hash


def mcp_entry_decision(
    ctx: RenderContext,
    *,
    name: str,
    path: str,
    current_values: dict | None,
    source_values: dict,
    current_env: dict,
    resolved_env: dict,
    env_refs: dict,
    prior: dict,
    workspace_root,
) -> tuple[str, dict]:
    """Ownership decision for one MCP entry.

    The ledger stores plain non-secret ``values`` and ``env_refs`` so a source
    change (new key, new command) is distinguishable from a local edit: the
    previous refs are re-resolved locally and compared against the local
    values. Returns ``(action, next_entry)`` with action in
    ``create / update / adopt / none / adopt-local / conflict``.
    """
    from ..secrets import resolve_secret
    from ..workspace import WorkspaceError

    next_entry = {"values": source_values, "env_refs": dict(env_refs)}
    if current_values is None:
        return "create", next_entry
    if current_values == source_values and current_env == resolved_env:
        return ("adopt" if not prior else "none"), next_entry
    if not prior:
        decision = ctx.resolve(f"mcp:{ctx.target}:{name}")
        if decision == "overwrite":
            return "update", next_entry
        if decision == "adopt":
            return "adopt-local", _adopted_entry(current_values, current_env)
        ctx.conflict(
            "mcp", name, path, "refusing to overwrite an unregistered entry",
            f"mcp:{ctx.target}:{name}",
        )
        return "conflict", {}
    if prior.get("adopted"):
        local_matches_prior = False
    elif not prior.get("env_refs"):
        local_matches_prior = current_values == prior.get("values") and current_env == {}
    else:
        try:
            prior_env = {
                key: resolve_secret(
                    reference,
                    workspace_root=workspace_root,
                    expand=True,
                    label=f"mcp:{name}:env.{key}",
                )
                for key, reference in prior["env_refs"].items()
            }
        except WorkspaceError as exc:
            ctx.conflict(
                "mcp",
                name,
                path,
                f"cannot verify local env against the previous apply: {exc}",
                f"mcp:{ctx.target}:{name}",
            )
            return "conflict", {}
        local_matches_prior = (
            current_values == prior.get("values") and current_env == prior_env
        )
    if not local_matches_prior:
        decision = ctx.resolve(f"mcp:{ctx.target}:{name}")
        if decision == "overwrite":
            return "update", next_entry
        if decision == "adopt":
            return "adopt-local", _adopted_entry(current_values, current_env)
        ctx.conflict(
            "mcp", name, path, "managed entry was modified locally",
            f"mcp:{ctx.target}:{name}",
        )
        return "conflict", {}
    return "update", next_entry


def mcp_removal_decision(
    ctx: RenderContext,
    *,
    name: str,
    path: str,
    current_values: dict | None,
    current_env: dict,
    prior: dict,
    workspace_root: Path,
) -> str:
    """Decide whether a previously owned, now-removed MCP entry is safe to delete."""
    from ..secrets import resolve_secret
    from ..workspace import WorkspaceError

    if current_values is None:
        return "absent"
    if prior.get("adopted"):
        return "keep"
    try:
        prior_env = {
            key: resolve_secret(
                reference,
                workspace_root=workspace_root,
                expand=True,
                label=f"mcp:{name}:env.{key}",
            )
            for key, reference in prior.get("env_refs", {}).items()
        }
    except WorkspaceError as exc:
        ctx.conflict(
            "mcp",
            name,
            path,
            f"cannot verify removed entry against the previous apply: {exc}",
            f"mcp:{ctx.target}:{name}",
        )
        return "conflict"
    if current_values == prior.get("values") and current_env == prior_env:
        return "delete"
    decision = ctx.resolve(f"mcp:{ctx.target}:{name}")
    if decision == "overwrite":
        return "delete"
    if decision == "adopt":
        return "keep"
    ctx.conflict(
        "mcp",
        name,
        path,
        "managed entry changed before source removal",
        f"mcp:{ctx.target}:{name}",
    )
    return "conflict"


def _adopted_entry(current_values: dict, current_env: dict) -> dict:
    return {
        "values": current_values,
        "env_refs": {},
        "adopted": True,
        "env_count": len(current_env),
    }
