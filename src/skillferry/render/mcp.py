"""MCP rendering dispatch.

Only ``stdio`` servers are rendered automatically; other transports are graded
``manual`` with per-adapter instructions. Environment values are secret
references: they are resolved only at apply time on the local machine, and a
missing source becomes a conflict before anything is written. Each adapter
owns its target format (TOML sections, JSON entries, or a YAML patch block);
adapters that render all servers into one file declare ``plan_all_servers``.
"""

from __future__ import annotations

from ..models import GradeReport
from ..secrets import resolve_secret
from ..workspace import ServerSpec, WorkspaceError
from . import RenderContext


def resolved_env(ctx: RenderContext, server: ServerSpec) -> dict[str, str] | None:
    """Expand secret references for the local machine; conflict on failure."""
    resolved: dict[str, str] = {}
    for key, reference in sorted(server.env.items()):
        try:
            resolved[key] = resolve_secret(
                reference,
                workspace_root=ctx.ws.root,
                expand=True,
                label=f"mcp:{server.name}:env.{key}",
            )
        except WorkspaceError as exc:
            ctx.conflict(
                "mcp",
                server.name,
                reference,
                str(exc),
                f"mcp:{ctx.target}:{server.name}",
            )
            return None
    return resolved


def plan_mcp(ctx: RenderContext) -> None:
    previous = ctx.previous.get("mcp", {})
    next_state: dict[str, dict[str, str]] = dict(previous)
    ctx.next_ledger["mcp"] = next_state

    eligible: list[ServerSpec] = []
    for name, server in sorted(ctx.servers.items()):
        if server.targets is not None and ctx.target not in server.targets:
            continue
        if server.name in ctx.adapter.protected_mcp_servers:
            ctx.conflict(
                "mcp",
                name,
                server.name,
                "server is protected on this target and will never be managed",
                f"mcp:{ctx.target}:{name}",
            )
            continue
        if server.transport != "stdio":
            grade, notes = ctx.adapter.grade_mcp(server)
            ctx.plan.grades.append(GradeReport("mcp", name, ctx.target, grade, notes))
            ctx.plan.manual_steps.setdefault(ctx.target, []).append(
                ctx.adapter.manual_mcp_instructions(server)
            )
            continue
        grade, notes = ctx.adapter.grade_mcp(server)
        ctx.plan.grades.append(GradeReport("mcp", name, ctx.target, grade, notes))
        eligible.append(server)

    if getattr(ctx.adapter, "plan_all_servers", False):
        if eligible:
            ctx.adapter.mcp_plan_all(ctx, eligible, next_state)
        return
    for server in eligible:
        ctx.adapter.mcp_plan_server(ctx, server, next_state)


def plan_extensions(ctx: RenderContext) -> None:
    previous = ctx.previous.get("extensions", {})
    next_state: dict[str, dict[str, str]] = dict(previous)
    ctx.next_ledger["extensions"] = next_state

    for name, extension in sorted(ctx.extensions.items()):
        if extension.targets is not None and ctx.target not in extension.targets:
            continue
        grade, notes = ctx.adapter.grade_extension(extension)
        ctx.plan.grades.append(GradeReport("extension", name, ctx.target, grade, notes))
        instructions = ctx.adapter.extension_instructions(extension)
        if instructions:
            ctx.plan.manual_steps.setdefault(ctx.target, []).append(
                f"{name}@{extension.version}: {instructions}"
            )
        prior = previous.get(name, {})
        if prior and prior.get("version") != extension.version:
            ctx.plan.warnings.append(
                f"extension:{ctx.target}:{name}: declared version changed "
                f"({prior.get('version')} -> {extension.version}); re-run the manual install"
            )
        next_state[name] = {"version": extension.version}
