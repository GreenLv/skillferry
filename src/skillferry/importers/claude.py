"""Import from an existing Claude Code setup into a draft workspace."""

from __future__ import annotations

import json
from pathlib import Path

import tomlkit

from ..secrets import looks_like_secret, scan_text
from .base import (
    Finding,
    ImportReport,
    classify_name,
    copy_tree,
    empty_manifests,
    prepare_output,
    workspace_manifest_text,
)


def _write_registry(destination: Path, entries: dict[str, dict]) -> None:
    document = tomlkit.document()
    servers = tomlkit.table()
    for name, entry in entries.items():
        table = tomlkit.table()
        table["command"] = entry["command"]
        if entry.get("args"):
            args = tomlkit.array()
            for item in entry["args"]:
                args.append(item)
            table["args"] = args
        if entry.get("env"):
            env = tomlkit.table()
            for key, ref in sorted(entry["env"].items()):
                env[key] = ref
            table["env"] = env
        servers[name] = table
    document["servers"] = servers
    (destination / "mcp" / "servers.toml").write_text(tomlkit.dumps(document), encoding="utf-8")


def _registry_entries(claude_json: Path, report: ImportReport) -> dict[str, dict]:
    try:
        document = json.loads(claude_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report.findings.append(
            Finding(".claude.json", "UNKNOWN", f"cannot parse: {exc}", "listed")
        )
        return {}
    if not isinstance(document, dict):
        report.findings.append(
            Finding(".claude.json", "UNKNOWN", "root is not an object", "listed")
        )
        return {}
    servers_table = document.get("mcpServers", {})
    if not isinstance(servers_table, dict):
        report.findings.append(
            Finding(".claude.json", "UNKNOWN", "mcpServers is not an object", "listed")
        )
        return {}
    entries: dict[str, dict] = {}
    for name, server in sorted(servers_table.items()):
        if not isinstance(server, dict) or not isinstance(server.get("command"), str):
            report.findings.append(
                Finding(
                    f".claude.json mcpServers.{name}",
                    "UNKNOWN",
                    "entry is not a recognizable stdio server",
                    "listed",
                )
            )
            continue
        entry: dict = {"command": server["command"]}
        args = server.get("args", [])
        if args:
            if not isinstance(args, list) or not all(
                isinstance(item, str) for item in args
            ):
                report.findings.append(
                    Finding(
                        f".claude.json mcpServers.{name}",
                        "UNKNOWN",
                        "args must be a list of strings",
                        "listed",
                    )
                )
                continue
            entry["args"] = list(args)
        env = server.get("env", {})
        refs: dict[str, str] = {}
        if isinstance(env, dict):
            for key, value in sorted(env.items()):
                if not isinstance(key, str) or not isinstance(value, str):
                    continue
                refs[key] = f"secret:env/{key}"
                if looks_like_secret(value):
                    report.findings.append(
                        Finding(
                            f".claude.json mcpServers.{name}.env.{key}",
                            "SENSITIVE",
                            "credential value converted to a secret:env reference",
                            "converted",
                        )
                    )
                else:
                    report.findings.append(
                        Finding(
                            f".claude.json mcpServers.{name}.env.{key}",
                            "PORTABLE",
                            "env value moved to a secret:env reference",
                            "converted",
                        )
                    )
        if refs:
            entry["env"] = refs
        if server.get("headers"):
            report.findings.append(
                Finding(
                    f".claude.json mcpServers.{name}.headers",
                    "SENSITIVE",
                    "headers often carry credentials; omitted from the draft, review manually",
                    "skipped",
                )
            )
        entries[str(name)] = entry
    return entries


def import_claude(*, output: Path, claude_home: Path | None = None) -> ImportReport:
    home = Path.home()
    claude = (claude_home or home / ".claude").expanduser()
    if claude.is_symlink():
        raise ValueError(f"claude home may not be a symlink: {claude}")
    claude = claude.resolve()

    destination = prepare_output(output)
    report = ImportReport(source=f"claude:{claude}", output=destination)
    empty_manifests(destination)

    skills = claude / "skills"
    if skills.is_dir():
        for child in sorted(skills.iterdir()):
            if child.is_dir() and (child / "SKILL.md").is_file():
                copy_tree(child, destination / "skills" / child.name, label=str(child))
                report.findings.append(
                    Finding(f"skills/{child.name}", "PORTABLE", "skill directory", "copied")
                )

    claude_md = claude / "CLAUDE.md"
    if claude_md.is_file() and not claude_md.is_symlink():
        text = claude_md.read_text(encoding="utf-8")
        findings = scan_text(text, label="CLAUDE.md")
        if findings:
            report.findings.append(
                Finding(
                    "CLAUDE.md",
                    "SENSITIVE",
                    f"credential-looking content found ({findings[0]}); not copied",
                    "skipped",
                )
            )
        else:
            (destination / "instructions" / "global.md").write_text(text, encoding="utf-8")
            report.findings.append(
                Finding("instructions/global.md", "PORTABLE", "CLAUDE.md content", "copied")
            )

    claude_json = claude / ".claude.json"
    if claude_json.is_file() and not claude_json.is_symlink():
        entries = _registry_entries(claude_json, report)
        if entries:
            _write_registry(destination, entries)
            report.findings.append(
                Finding(
                    "mcp/servers.toml",
                    "PORTABLE",
                    f"registry written with {len(entries)} server(s)",
                    "copied",
                )
            )

    for child in sorted(claude.iterdir()):
        if child.name in ("CLAUDE.md", ".claude.json", "skills", ".git"):
            continue
        classification = classify_name(child.name)
        if classification == "UNKNOWN":
            report.findings.append(
                Finding(child.name, "UNKNOWN", "not classified; review manually", "listed")
            )
        else:
            report.findings.append(
                Finding(child.name, classification, "left untouched", "skipped")
            )

    (destination / "workspace.toml").write_text(workspace_manifest_text(), encoding="utf-8")
    return report
