"""Build a full SyncPlan: grades, changes, conflicts, and apply operations."""

from __future__ import annotations

import sys
from pathlib import Path

from .adapters.base import TargetEnv, resolve_target_env
from .adapters.registry import get_adapter
from .models import SUPPORTED_PLATFORMS, SUPPORTED_TARGETS, SyncPlan, TargetApply
from .render import RenderContext
from .render.mcp import plan_extensions, plan_mcp
from .render.rules import plan_rules
from .render.skills import plan_skills
from .state import ledger_target, load_ledger
from .workspace import (
    WorkspaceError,
    _validate_protect_declarations,
    load_extensions,
    load_mcp_registry,
    load_skills,
    load_workspace,
)


def detect_platform(requested: str) -> str:
    if requested != "auto":
        if requested not in SUPPORTED_PLATFORMS:
            raise WorkspaceError(f"unsupported platform: {requested}")
        return requested
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    raise WorkspaceError(f"cannot map host platform {sys.platform!r}")


def _check_protect(
    plan: SyncPlan, apply: TargetApply, env: TargetEnv, declared: tuple[str, ...]
) -> None:
    """Any operation target covered by [protect] or an adapter-protected name
    becomes a conflict instead of a write."""
    adapter = get_adapter(apply.target)
    for op_path in [copy.target for copy in apply.copies] + [
        write.target for write in apply.writes
    ] + [delete.target for delete in apply.deletes]:
        for entry in declared:
            candidate = (env.home / entry).resolve()
            if op_path.resolve() == candidate or candidate in op_path.resolve().parents:
                plan.conflicts.append(
                    _conflict_protect(apply.target, op_path, f"[protect] path: {entry}")
                )
                continue
            if "/" not in entry and entry in op_path.parts:
                plan.conflicts.append(
                    _conflict_protect(apply.target, op_path, f"[protect] name: {entry}")
                )
        for name in adapter.protected_names:
            if name in op_path.parts:
                plan.conflicts.append(
                    _conflict_protect(apply.target, op_path, f"protected on this target: {name}")
                )


def _conflict_protect(target: str, path: Path, reason: str):
    from .models import Conflict

    return Conflict("protect", target, str(path), str(path), reason, f"protect:{target}")


def build_plan(
    workspace_root: Path,
    *,
    requested_platform: str = "auto",
    targets: tuple[str, ...] | None = None,
    hostname: str | None = None,
    home: str | None = None,
    codex_home: str | None = None,
    claude_home: str | None = None,
    dsh_home: str | None = None,
    dsh_profile: str | None = None,
    resolutions: dict[str, str] | None = None,
    allow_local: bool = True,
) -> SyncPlan:
    workspace_root = workspace_root.expanduser().absolute()
    platform = detect_platform(requested_platform)
    selected = tuple(targets) if targets else SUPPORTED_TARGETS
    unknown = sorted(set(selected) - set(SUPPORTED_TARGETS))
    if unknown:
        raise WorkspaceError(f"unsupported targets: {unknown}")
    env = resolve_target_env(
        platform=platform,
        home=home,
        codex_home=codex_home,
        claude_home=claude_home,
        dsh_home=dsh_home,
        dsh_profile=dsh_profile,
    )
    plan = SyncPlan(
        workspace_root=workspace_root,
        platform=platform,
        targets=selected,
        homes={
            "codex": env.codex_home,
            "claude": env.claude_home,
            "dsh": env.dsh_home,
        },
    )
    ledger = load_ledger(workspace_root)

    for target in selected:
        adapter = get_adapter(target)
        ws = load_workspace(
            workspace_root,
            target=target,
            platform=platform,
            hostname=hostname,
            allow_local=allow_local,
        )
        _validate_protect_declarations(ws)
        skills = load_skills(ws)
        servers = load_mcp_registry(ws)
        extensions = load_extensions(ws)
        apply = TargetApply(target=target, roots=adapter.managed_roots(env))
        ctx = RenderContext(
            ws=ws,
            adapter=adapter,
            env=env,
            target=target,
            plan=plan,
            apply=apply,
            skills=skills,
            servers=servers,
            extensions=extensions,
            previous=ledger_target(ledger, target),
            resolutions=resolutions or {},
        )
        plan_skills(ctx)
        plan_rules(ctx)
        plan_mcp(ctx)
        plan_extensions(ctx)
        apply.ledger = ctx.next_ledger
        _check_protect(plan, apply, env, ws.protect.paths)
        plan.applies[target] = apply

    plan.changes.sort(key=lambda item: (item.target, item.kind, item.name, item.path))
    plan.conflicts.sort(
        key=lambda item: (item.target, item.kind, item.name, item.path)
    )
    plan.grades.sort(key=lambda item: (item.kind, item.name, item.target))
    return plan
