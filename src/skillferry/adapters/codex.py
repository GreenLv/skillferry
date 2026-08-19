"""Codex adapter.

Skills land in ``~/.agents/skills/<name>`` (the shared, agent-neutral skill
root that Codex natively discovers — verified on both macOS and Windows by the
author's codex-sync setup). MCP servers are rendered as native
``[mcp_servers.<name>]`` tables inside ``~/.codex/config.toml`` via tomlkit,
and global rules become marker-delimited blocks in ``~/.codex/AGENTS.md``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import tomlkit

from ..models import Change, TextWrite
from ..workspace import Extension, ServerSpec
from .base import Adapter, TargetEnv, mcp_entry_decision


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class CodexAdapter(Adapter):
    name = "codex"
    label = "Codex"
    plan_all_servers = True
    protected_names = (
        "auth.json",
        "history.jsonl",
        "sessions",
        "logs",
        "cache",
        "desktop",
        "marketplace",
        "trust",
        "projects",
        "plugins",
        "state",
        "node_modules",
    )
    protected_mcp_servers = ("node_repl",)

    def skill_dir(self, env: TargetEnv) -> Path:
        raw = env.home / ".agents" / "skills"
        if raw.is_symlink():
            raise ValueError(f"skills target may not be a symlink: {raw}")
        return raw.resolve()

    def rules_file(self, env: TargetEnv) -> Path:
        return env.codex_home / "AGENTS.md"

    def managed_roots(self, env: TargetEnv) -> list[Path]:
        return [env.codex_home, env.home / ".agents"]

    def rules_grade(self, strategy: str) -> tuple[str, tuple[str, ...]]:
        if strategy == "marker":
            return "native", ("marker-delimited blocks in AGENTS.md",)
        if strategy == "include":
            return "translated", ("rendered as @path imports in AGENTS.md",)
        return "degraded", ("copy strategy replaces the whole AGENTS.md file",)

    def grade_mcp(self, server: ServerSpec) -> tuple[str, tuple[str, ...]]:
        if server.transport != "stdio":
            return "manual", (f"transport '{server.transport}' is not auto-rendered",)
        notes = ["managed as [mcp_servers.<name>] in ~/.codex/config.toml"]
        if server.env:
            return "translated", ("secret resolved from local env", *notes)
        return "native", tuple(notes)

    def grade_extension(self, extension: Extension) -> tuple[str, tuple[str, ...]]:
        return "manual", ("Codex plugin/marketplace installs are user-owned",)

    def manual_mcp_instructions(self, server: ServerSpec) -> str:
        return (
            f"codex mcp add {server.name} -- {server.command} "
            f"{' '.join(server.args)} (transport {server.transport})"
        )

    def extension_instructions(self, extension: Extension) -> str:
        if extension.source_kind == "manual":
            return extension.instructions or "follow the extension's own install notes"
        if extension.source_kind == "marketplace":
            return f"install '{extension.name}' from {extension.repo} in the Codex marketplace"
        if extension.source_kind == "github":
            return f"fetch {extension.repo}@{extension.ref or 'HEAD'} and follow its install docs"
        return f"enable the local extension at {extension.path} per Codex plugin docs"

    def mcp_plan_all(
        self, ctx, servers: list[ServerSpec], next_state: dict[str, dict[str, Any]]
    ) -> None:
        """Render every eligible server into one config.toml document.

        Sections are owned per server (values hash + env-reference hash); a
        conflicted server keeps its current section untouched while the other
        servers still render, so one bad entry never blocks the file.
        """
        from ..render.mcp import resolved_env  # local import avoids a cycle

        env: TargetEnv = ctx.env
        target = env.codex_home / "config.toml"
        original = target.read_text(encoding="utf-8") if target.exists() else ""
        if target.is_symlink() or (target.exists() and not target.is_file()):
            for server in servers:
                ctx.conflict(
                    "mcp",
                    server.name,
                    str(target),
                    "target config is a symlink or non-file",
                    f"mcp:{ctx.target}:{server.name}",
                )
            return
        try:
            document = tomlkit.parse(original) if original.strip() else tomlkit.document()
        except ValueError as exc:
            for server in servers:
                ctx.conflict(
                    "mcp",
                    server.name,
                    str(target),
                    f"cannot parse config.toml: {exc}",
                    f"mcp:{ctx.target}:{server.name}",
                )
            return

        prior_all = ctx.previous.get("mcp", {})
        # name -> (command, args_json, env_json)
        sections_to_set: dict[str, tuple[str, str, str]] = {}

        for server in servers:
            resolved = resolved_env(ctx, server)
            if resolved is None:
                continue  # conflict already recorded; section stays untouched

            mcp_servers = document.get("mcp_servers")
            current_values: dict | None = None
            current_env: dict[str, str] = {}
            if isinstance(mcp_servers, dict) and server.name in mcp_servers:
                entry = mcp_servers[server.name]
                if not isinstance(entry, dict):
                    ctx.conflict(
                        "mcp",
                        server.name,
                        str(target),
                        "mcp_servers entry is not a table",
                        f"mcp:{ctx.target}:{server.name}",
                    )
                    continue
                plain = {key: value.unwrap() for key, value in entry.items()}
                command = plain.get("command")
                args = plain.get("args", [])
                if command is not None:
                    current_values = {"command": command, "args": list(args)}
                raw_env = plain.get("env", {})
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
                source_values={"command": server.command, "args": list(server.args)},
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
            sections_to_set[server.name] = (
                server.command,
                json.dumps(list(server.args), sort_keys=True),
                json.dumps(dict(sorted(resolved.items())), sort_keys=True),
            )
            next_state[server.name] = next_entry

        if not sections_to_set:
            return
        for name, (command, args_json, env_json) in sorted(sections_to_set.items()):
            if not isinstance(document.get("mcp_servers"), dict):
                document["mcp_servers"] = tomlkit.table()
            section = tomlkit.table()
            section["command"] = command
            args_list = json.loads(args_json)
            if args_list:
                args_array = tomlkit.array()
                for item in args_list:
                    args_array.append(item)
                section["args"] = args_array
            env_map = json.loads(env_json)
            if env_map:
                env_table = tomlkit.table()
                for key, value in sorted(env_map.items()):
                    env_table[key] = value
                section["env"] = env_table
            document["mcp_servers"][name] = section
        rendered = tomlkit.dumps(document)
        if rendered == original:
            return
        ctx.plan.changes.append(
            Change(
                "mcp",
                ctx.target,
                ", ".join(sorted(sections_to_set)),
                "create" if not original else "update",
                str(target),
            )
        )
        ctx.apply.writes.append(
            TextWrite(target=target, text=rendered, mode=0o600, label="config.toml")
        )
