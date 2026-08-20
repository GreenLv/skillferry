"""Claude Code adapter.

Skills land in ``~/.claude/skills/<name>`` (Claude Code's documented personal
skills directory; see docs/AGENT_MATRIX.md). MCP servers are merged into the
user-level ``~/.claude.json`` ``mcpServers`` table — every other key in that
file is preserved, and the whole file is rewritten with normalized JSON
formatting (noted honestly in the grade). Rules go to ``~/.claude/CLAUDE.md``.
Project-level ``.mcp.json`` is intentionally not managed in v1.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models import Change, TextWrite
from ..workspace import Extension, ServerSpec
from .base import Adapter, TargetEnv, mcp_entry_decision, mcp_removal_decision


class ClaudeAdapter(Adapter):
    name = "claude"
    label = "Claude Code"
    plan_all_servers = True
    protected_names = (
        "config.json",
        "settings.json",
        "history.jsonl",
        ".credentials.json",
        "stats-cache.json",
        "projects",
        "sessions",
        "shell-snapshots",
        "ide",
        "plugins",
        "debug",
        "usage-data",
        "telemetry",
        "backups",
        "cache",
    )
    protected_mcp_servers = ("node_repl",)

    def skill_dir(self, env: TargetEnv) -> Path:
        raw = env.claude_home / "skills"
        if raw.is_symlink():
            raise ValueError(f"skills target may not be a symlink: {raw}")
        return raw.resolve()

    def rules_file(self, env: TargetEnv) -> Path:
        return env.claude_home / "CLAUDE.md"

    def managed_roots(self, env: TargetEnv) -> list[Path]:
        return [env.claude_home]

    def rules_grade(self, strategy: str) -> tuple[str, tuple[str, ...]]:
        if strategy == "marker":
            return "translated", (
                "CLAUDE.md has no managed-block concept; block appended verbatim",
            )
        if strategy == "include":
            return "translated", ("rendered as @path imports in CLAUDE.md",)
        return "degraded", ("copy strategy replaces the whole CLAUDE.md file",)

    def grade_mcp(self, server: ServerSpec) -> tuple[str, tuple[str, ...]]:
        if server.transport != "stdio":
            return "manual", (f"transport '{server.transport}' is not auto-rendered",)
        notes = [
            "user-level ~/.claude.json mcpServers; project .mcp.json is not managed by v1",
            "~/.claude.json is rewritten with normalized JSON formatting "
            "(all other keys preserved)",
        ]
        if server.env:
            return "translated", ("secret resolved from local env", *notes)
        return "translated", tuple(notes)

    def grade_extension(self, extension: Extension) -> tuple[str, tuple[str, ...]]:
        return "manual", ("Claude plugin installs are user-owned",)

    def manual_mcp_instructions(self, server: ServerSpec) -> str:
        return (
            f"claude mcp add {server.name} --scope user -- {server.command} "
            f"{' '.join(server.args)} (transport {server.transport})"
        )

    def extension_instructions(self, extension: Extension) -> str:
        if extension.source_kind == "manual":
            return extension.instructions or "follow the extension's own install notes"
        if extension.source_kind == "marketplace":
            return f"install '{extension.name}' from {extension.repo} via /plugin in Claude Code"
        if extension.source_kind == "github":
            return f"fetch {extension.repo}@{extension.ref or 'HEAD'} and follow its install docs"
        return f"enable the local extension at {extension.path} per Claude plugin docs"

    def mcp_plan_all(
        self, ctx, servers: list[ServerSpec], next_state: dict[str, dict[str, Any]]
    ) -> None:
        """Render every eligible server into one ``~/.claude.json`` document.

        Only the ``mcpServers`` keys we manage are touched; every other key in
        the document is preserved. A conflicted server keeps its current entry
        while the rest still render.
        """
        from ..render.mcp import resolved_env  # local import avoids a cycle

        env: TargetEnv = ctx.env
        target = env.claude_home / ".claude.json"
        if target.is_symlink() or (target.exists() and not target.is_file()):
            for server in servers:
                ctx.conflict(
                    "mcp",
                    server.name,
                    str(target),
                    "target is a symlink or non-file",
                    f"mcp:{ctx.target}:{server.name}",
                )
            return
        if target.exists():
            try:
                document = json.loads(target.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                for server in servers:
                    ctx.conflict(
                        "mcp",
                        server.name,
                        str(target),
                        f"cannot parse .claude.json: {exc}",
                        f"mcp:{ctx.target}:{server.name}",
                    )
                return
        else:
            document = {}
        if not isinstance(document, dict):
            for server in servers:
                ctx.conflict(
                    "mcp",
                    server.name,
                    str(target),
                    ".claude.json root is not an object",
                    f"mcp:{ctx.target}:{server.name}",
                )
            return
        servers_table = document.get("mcpServers", {})
        if not isinstance(servers_table, dict):
            for server in servers:
                ctx.conflict(
                    "mcp",
                    server.name,
                    str(target),
                    ".claude.json mcpServers is not an object",
                    f"mcp:{ctx.target}:{server.name}",
                )
            return
        original = target.read_text(encoding="utf-8") if target.exists() else ""

        prior_all = ctx.previous.get("mcp", {})
        entries_to_set: dict[str, dict[str, Any]] = {}
        entries_to_delete: list[str] = []
        for server in servers:
            resolved = resolved_env(ctx, server)
            if resolved is None:
                continue
            desired_entry: dict[str, Any] = {"type": "stdio", "command": server.command}
            if server.args:
                desired_entry["args"] = list(server.args)
            if resolved:
                desired_entry["env"] = dict(resolved)

            current = servers_table.get(server.name)
            current_values: dict | None = None
            current_env: dict[str, str] = {}
            if isinstance(current, dict):
                if current.get("command") is not None:
                    current_values = {
                        "type": current.get("type", "stdio"),
                        "command": current.get("command"),
                        "args": current.get("args", []),
                    }
                raw_env = current.get("env", {})
                if isinstance(raw_env, dict):
                    current_env = {
                        str(key): str(value) for key, value in raw_env.items()
                    }

            prior = prior_all.get(server.name, {})
            action, next_entry = mcp_entry_decision(
                ctx,
                name=server.name,
                path=str(target),
                current_values=current_values,
                source_values={
                    "type": "stdio",
                    "command": server.command,
                    "args": list(server.args),
                },
                current_env=current_env,
                resolved_env=resolved,
                env_refs=dict(server.env),
                prior=prior,
                workspace_root=ctx.ws.root,
            )
            if action == "conflict":
                continue
            if action == "adopt-local":
                next_state[server.name] = next_entry
                continue
            entries_to_set[server.name] = desired_entry
            next_state[server.name] = next_entry

        desired_names = {server.name for server in servers}
        for name in sorted(set(prior_all) - desired_names):
            current = servers_table.get(name)
            current_values: dict | None = None
            current_env: dict[str, str] = {}
            if current is not None and not isinstance(current, dict):
                ctx.conflict(
                    "mcp",
                    name,
                    str(target),
                    "managed mcpServers entry is no longer an object",
                    f"mcp:{ctx.target}:{name}",
                )
                continue
            if isinstance(current, dict):
                if current.get("command") is not None:
                    current_values = {
                        "type": current.get("type", "stdio"),
                        "command": current.get("command"),
                        "args": current.get("args", []),
                    }
                raw_env = current.get("env", {})
                if isinstance(raw_env, dict):
                    current_env = {str(key): str(value) for key, value in raw_env.items()}
            action = mcp_removal_decision(
                ctx,
                name=name,
                path=str(target),
                current_values=current_values,
                current_env=current_env,
                prior=prior_all[name],
                workspace_root=ctx.ws.root,
            )
            if action == "delete":
                del servers_table[name]
                entries_to_delete.append(name)
                next_state.pop(name, None)
            elif action in ("absent", "keep"):
                next_state.pop(name, None)

        if not entries_to_set and not entries_to_delete:
            return
        for name, entry in sorted(entries_to_set.items()):
            servers_table[name] = entry
        document["mcpServers"] = servers_table
        rendered = json.dumps(document, indent=2, sort_keys=False) + "\n"
        if rendered == original:
            return
        ctx.plan.changes.append(
            Change(
                "mcp",
                ctx.target,
                ", ".join(sorted(set(entries_to_set) | set(entries_to_delete))),
                "create" if not original else "update",
                str(target),
            )
        )
        ctx.apply.writes.append(
            TextWrite(target=target, text=rendered, mode=0o600, label="claude.json")
        )
