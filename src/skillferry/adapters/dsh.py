"""DeepSeek Harness (DSH) adapter.

Skills land in ``~/.agents/skills/<name>`` (the shared skill root DSH natively
auto-loads — verified on the author's macOS and Windows setups). MCP servers
become ``dsh-mcp-client`` plugin insert entries inside one marker-delimited
block of ``$DSH_HOME/profiles/<profile>/cordis.patch.yml``; everything outside
that block is preserved byte-for-byte, and a handwritten entry that would
collide with a generated ``mcp-<name>`` id is a conflict. Rules go to
``$DSH_HOME/AGENTS.md`` marker blocks.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..models import Change, TextWrite
from ..workspace import Extension, ServerSpec, WorkspaceError
from .base import Adapter, TargetEnv, mcp_entry_decision

BEGIN_MARKER = "# >>> BEGIN SKILLFERRY DSH MCP >>>"
END_MARKER = "# <<< END SKILLFERRY DSH MCP <<<"
PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
INSERT_ID_RE = re.compile(r"^    - id: (mcp-[A-Za-z0-9_-]+)\s*$")
SERVER_NAME_RE = re.compile(r"^\s+serverName: ([A-Za-z0-9_-]+)\s*$")
COMMAND_RE = re.compile(r'^\s+command: ("(?:[^"\\]|\\.)*")\s*$')
ARGS_RE = re.compile(r"^\s+args: (\[.*\])\s*$")
ENV_KEY_RE = re.compile(r'^\s+([A-Za-z_][A-Za-z0-9_]*): ("(?:[^"\\]|\\.)*")\s*$')


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _entry_lines(server: ServerSpec, resolved: dict[str, str]) -> list[str]:
    lines = [
        "- insert:",
        f"    - id: mcp-{server.name}",
        "      name: '@deepseek-ai/dsh-mcp-client'",
        "      config:",
        f"        serverName: {server.name}",
        "        transport: stdio",
        f"        command: {json.dumps(server.command)}",
        f"        args: {json.dumps(list(server.args))}",
    ]
    if resolved:
        lines.append("        env:")
        for key, value in sorted(resolved.items()):
            lines.append(f"          {key}: {json.dumps(value)}")
    lines.append("        failOnStartupError: false")
    return lines


def desired_block_text(
    servers: list[ServerSpec], resolved: dict[str, dict[str, str]]
) -> str:
    entries: list[str] = []
    for server in sorted(servers, key=lambda item: item.name):
        entries.extend(_entry_lines(server, resolved.get(server.name, {})))
    return "\n".join([BEGIN_MARKER, *entries, END_MARKER]) + "\n"


def _parse_current_block(text: str, known_names: set[str]) -> dict[str, dict[str, Any]] | None:
    """Parse the generated block shape; return None when it is unrecognizable."""
    entries: dict[str, dict[str, Any]] = {}
    current_name: str | None = None
    in_env = False
    for line in text.splitlines():
        match = INSERT_ID_RE.match(line)
        if match:
            # Sibling insert entries; each new id starts the next entry.
            current_name = match.group(1)
            in_env = False
            continue
        if current_name is None:
            continue
        stripped = line.strip()
        if stripped == "env:":
            in_env = True
            continue
        if in_env:
            env_match = ENV_KEY_RE.match(line)
            if env_match:
                entry = entries.setdefault(
                    current_name, {"command": None, "args": [], "env": {}, "server": None}
                )
                try:
                    entry["env"][env_match.group(1)] = json.loads(env_match.group(2))
                except json.JSONDecodeError:
                    return None
                continue
            in_env = False
        server_match = SERVER_NAME_RE.match(line)
        if server_match:
            entries.setdefault(
                current_name, {"command": None, "args": [], "env": {}, "server": None}
            )["server"] = server_match.group(1)
            continue
        command_match = COMMAND_RE.match(line)
        if command_match:
            try:
                value = json.loads(command_match.group(1))
            except json.JSONDecodeError:
                return None
            entries.setdefault(
                current_name, {"command": None, "args": [], "env": {}, "server": None}
            )["command"] = value
            continue
        args_match = ARGS_RE.match(line)
        if args_match:
            try:
                value = json.loads(args_match.group(1))
            except json.JSONDecodeError:
                return None
            entries.setdefault(
                current_name, {"command": None, "args": [], "env": {}, "server": None}
            )["args"] = list(value) if isinstance(value, list) else []
    for name in known_names:
        entry = entries.get(f"mcp-{name}")
        if entry is None or entry.get("server") != name or entry.get("command") is None:
            return None
    return entries


def _block_spans(lines: list[str]) -> tuple[int | None, int | None]:
    begin = [i for i, line in enumerate(lines) if line.rstrip("\r\n").strip() == BEGIN_MARKER]
    end = [i for i, line in enumerate(lines) if line.rstrip("\r\n").strip() == END_MARKER]
    if not begin and not end:
        return None, None
    if len(begin) != 1 or len(end) != 1 or begin[0] >= end[0]:
        raise WorkspaceError(
            "the DSH patch file must contain exactly one complete SKILLFERRY MCP block"
        )
    return begin[0], end[0]


def _preferred_newline(original: str, platform: str) -> str:
    first_lf = original.find("\n")
    if first_lf >= 0:
        return "\r\n" if first_lf > 0 and original[first_lf - 1] == "\r" else "\n"
    return "\r\n" if platform == "windows" else "\n"


def _with_newline(text: str, newline: str) -> str:
    return text.replace("\r\n", "\n").replace("\n", newline)


class DshAdapter(Adapter):
    name = "dsh"
    label = "DeepSeek Harness"
    plan_all_servers = True
    protected_names = (
        "settings.yaml",
        "sessions",
        "storages",
        "cordis.yml",
        "package.json",
        "pnpm-lock.yaml",
        "pnpm-workspace.yaml",
        "node_modules",
    )
    protected_mcp_servers = ("node_repl",)

    def skill_dir(self, env: TargetEnv) -> Path:
        raw = env.home / ".agents" / "skills"
        if raw.is_symlink():
            raise ValueError(f"skills target may not be a symlink: {raw}")
        return raw.resolve()

    def rules_file(self, env: TargetEnv) -> Path:
        return env.dsh_home / "AGENTS.md"

    def managed_roots(self, env: TargetEnv) -> list[Path]:
        return [env.dsh_home, env.home / ".agents"]

    def _patch_target(self, env: TargetEnv) -> Path:
        if not PROFILE_NAME_RE.fullmatch(env.dsh_profile):
            raise ValueError(
                "DSH profile must be one directory name of letters, digits, dot, "
                "underscore, or hyphen, starting with a letter or digit"
            )
        target = env.dsh_home / "profiles" / env.dsh_profile / "cordis.patch.yml"
        codex_home = (Path.home() / ".codex").resolve()
        if target.resolve() == codex_home or codex_home in target.resolve().parents:
            raise ValueError("refusing to target Codex-owned configuration")
        return target

    def rules_grade(self, strategy: str) -> tuple[str, tuple[str, ...]]:
        if strategy == "marker":
            return "native", ("marker-delimited blocks in $DSH_HOME/AGENTS.md",)
        if strategy == "include":
            return "degraded", ("@path import behavior in DSH AGENTS.md is unverified",)
        return "degraded", ("copy strategy replaces the whole AGENTS.md file",)

    def grade_mcp(self, server: ServerSpec) -> tuple[str, tuple[str, ...]]:
        if server.transport != "stdio":
            return "manual", (f"transport '{server.transport}' is not auto-rendered",)
        notes = ["inserted as dsh-mcp-client entries in the profile cordis.patch.yml"]
        if server.env:
            return "translated", ("secret resolved from local env", *notes)
        return "translated", tuple(notes)

    def grade_extension(self, extension: Extension) -> tuple[str, tuple[str, ...]]:
        return "manual", ("DSH plugin installs are user-owned",)

    def manual_mcp_instructions(self, server: ServerSpec) -> str:
        return (
            f"add an mcp-{server.name} entry to $DSH_HOME/profiles/<profile>/"
            f"cordis.patch.yml using '@deepseek-ai/dsh-mcp-client' "
            f"(transport {server.transport})"
        )

    def extension_instructions(self, extension: Extension) -> str:
        if extension.source_kind == "manual":
            return extension.instructions or "follow the extension's own install notes"
        if extension.source_kind == "marketplace":
            return f"install '{extension.name}' from {extension.repo} following DSH plugin docs"
        if extension.source_kind == "github":
            return f"fetch {extension.repo}@{extension.ref or 'HEAD'} and follow its install docs"
        return f"enable the local extension at {extension.path} per DSH plugin docs"

    def mcp_plan_all(
        self, ctx, servers: list[ServerSpec], next_state: dict[str, dict[str, Any]]
    ) -> None:
        from ..render.mcp import resolved_env  # local import avoids a cycle

        env: TargetEnv = ctx.env
        try:
            target = self._patch_target(env)
        except ValueError as exc:
            for server in servers:
                ctx.conflict(
                    "mcp", server.name, str(exc), str(exc), f"mcp:{ctx.target}:{server.name}"
                )
            return
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

        original = target.read_text(encoding="utf-8") if target.exists() else ""
        resolved_map: dict[str, dict[str, str]] = {}
        for server in servers:
            resolved = resolved_env(ctx, server)
            if resolved is None:
                return  # conflict already recorded
            resolved_map[server.name] = resolved
        desired = desired_block_text(servers, resolved_map)

        lines = original.splitlines(keepends=True)
        try:
            begin, end = _block_spans(lines)
        except WorkspaceError as exc:
            ctx.conflict("mcp", "all", str(target), str(exc), f"mcp:{ctx.target}:all")
            return
        newline = _preferred_newline(original, env.platform)
        rendered_block = _with_newline(desired, newline)

        if begin is not None:
            outside = lines[:begin] + lines[end + 1 :]
            merged = "".join(lines[:begin]) + rendered_block + "".join(lines[end + 1 :])
            current_block = "".join(lines[begin : end + 1])
        else:
            outside = lines
            current_block = ""
            separator = ""
            if original and not original.endswith(("\n", "\r")):
                separator += newline
            if original and not original.endswith((newline + newline, "\n\n", "\r\n\r\n")):
                separator += newline
            merged = original + separator + rendered_block

        for server in servers:
            collision = re.compile(rf"id:\s*mcp-{re.escape(server.name)}\b")
            for line in outside:
                if collision.search(line):
                    ctx.conflict(
                        "mcp",
                        server.name,
                        str(target),
                        f"a handwritten mcp-{server.name} entry exists outside the managed block",
                        f"mcp:{ctx.target}:{server.name}",
                    )
                    return

        known = {server.name for server in servers}
        parsed = _parse_current_block(current_block, known) if current_block else {}
        prior = ctx.previous.get("mcp", {})
        if current_block and parsed is None:
            decision = ctx.resolve(f"mcp:{ctx.target}:block")
            if decision != "overwrite":
                ctx.conflict(
                    "mcp",
                    "all",
                    str(target),
                    "managed DSH MCP block was hand-edited beyond the recognized shape",
                    f"mcp:{ctx.target}:block",
                )
                return

        kept_local = False
        for server in servers:
            entry = (parsed or {}).get(f"mcp-{server.name}")
            current_values: dict | None = None
            current_env: dict[str, str] = {}
            if entry is not None:
                current_values = {
                    "command": entry["command"],
                    "args": list(entry["args"]),
                }
                current_env = {
                    str(key): str(value) for key, value in entry["env"].items()
                }
            prior_entry = prior.get(server.name, {})
            action, next_entry = mcp_entry_decision(
                ctx,
                name=server.name,
                path=str(target),
                current_values=current_values,
                source_values={"command": server.command, "args": list(server.args)},
                current_env=current_env,
                resolved_env=resolved_map[server.name],
                env_refs=dict(server.env),
                prior=prior_entry,
                workspace_root=ctx.ws.root,
            )
            if action == "conflict":
                return
            if action == "adopt-local":
                kept_local = True
                next_state[server.name] = next_entry
                continue
            next_state[server.name] = next_entry

        if merged != original and not kept_local:
            label = "create" if not current_block else "update"
            ctx.plan.changes.append(Change("mcp", ctx.target, "all", label, str(target)))
            mode = target.stat().st_mode & 0o777 if target.exists() else 0o600
            ctx.apply.writes.append(
                TextWrite(target=target, text=merged, mode=mode, label="cordis.patch.yml")
            )
        elif merged != original:
            ctx.plan.warnings.append(
                f"mcp:{ctx.target}: DSH MCP block not written because one or more "
                "entries were kept local; re-run after resolving them"
            )
