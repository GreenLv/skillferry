"""Import from an existing Codex setup into a draft workspace."""

from __future__ import annotations

import os
import tomllib
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


def _registry_entries(mcp_servers: dict, report: ImportReport) -> dict[str, dict]:
    entries: dict[str, dict] = {}
    for name, server in sorted(mcp_servers.items()):
        if name == "node_repl":
            report.findings.append(
                Finding(
                    f"config.toml [mcp_servers.{name}]",
                    "LOCAL-ONLY",
                    "Codex-owned embedded server",
                    "skipped",
                )
            )
            continue
        if not isinstance(server, dict) or not isinstance(server.get("command"), str):
            report.findings.append(
                Finding(
                    f"config.toml [mcp_servers.{name}]",
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
                        f"config.toml [mcp_servers.{name}]",
                        "UNKNOWN",
                        "args must be a list of strings",
                        "listed",
                    )
                )
                continue
            entry["args"] = list(args)
        env = server.get("env", {})
        refs: dict[str, str] = {}
        for key, value in sorted(env.items() if isinstance(env, dict) else []):
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            refs[key] = f"secret:env/{key}"
            if looks_like_secret(value):
                report.findings.append(
                    Finding(
                        f"config.toml [mcp_servers.{name}].env.{key}",
                        "SENSITIVE",
                        "credential value converted to a secret:env reference",
                        "converted",
                    )
                )
            else:
                report.findings.append(
                    Finding(
                        f"config.toml [mcp_servers.{name}].env.{key}",
                        "PORTABLE",
                        "env value moved to a secret:env reference",
                        "converted",
                    )
                )
        if refs:
            entry["env"] = refs
        entries[name] = entry
    return entries


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


def import_codex(
    *,
    output: Path,
    codex_home: Path | None = None,
    skills_home: Path | None = None,
) -> ImportReport:
    home = Path.home()
    configured = os.environ.get("CODEX_HOME")
    codex = (
        codex_home
        or (Path(configured).expanduser() if configured else home / ".codex")
    ).expanduser()
    if codex.is_symlink():
        raise ValueError(f"codex home may not be a symlink: {codex}")
    codex = codex.resolve()
    skills = (skills_home or home / ".agents" / "skills").expanduser()
    if skills.is_symlink():
        raise ValueError(f"skills root may not be a symlink: {skills}")
    skills = skills.resolve()

    destination = prepare_output(output)
    report = ImportReport(source=f"codex:{codex}", output=destination)
    empty_manifests(destination)

    if skills.is_dir():
        for child in sorted(skills.iterdir()):
            if child.is_dir() and (child / "SKILL.md").is_file():
                copy_tree(child, destination / "skills" / child.name, label=str(child))
                report.findings.append(
                    Finding(f"skills/{child.name}", "PORTABLE", "skill directory", "copied")
                )

    config_path = codex / "config.toml"
    if config_path.is_file() and not config_path.is_symlink():
        try:
            with config_path.open("rb") as handle:
                config = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            report.findings.append(
                Finding("config.toml", "UNKNOWN", f"cannot parse: {exc}", "listed")
            )
            config = {}
        mcp_servers = config.get("mcp_servers", {})
        if isinstance(mcp_servers, dict) and mcp_servers:
            entries = _registry_entries(mcp_servers, report)
            _write_registry(destination, entries)
            report.findings.append(
                Finding(
                    "mcp/servers.toml",
                    "PORTABLE",
                    f"registry written with {len(entries)} server(s)",
                    "copied",
                )
            )

    agents_md = codex / "AGENTS.md"
    if agents_md.is_file() and not agents_md.is_symlink():
        text = agents_md.read_text(encoding="utf-8")
        findings = scan_text(text, label="AGENTS.md")
        if findings:
            report.findings.append(
                Finding(
                    "AGENTS.md",
                    "SENSITIVE",
                    f"credential-looking content found ({findings[0]}); not copied",
                    "skipped",
                )
            )
        else:
            (destination / "instructions" / "global.md").write_text(text, encoding="utf-8")
            report.findings.append(
                Finding("instructions/global.md", "PORTABLE", "AGENTS.md content", "copied")
            )

    for child in sorted(codex.iterdir()):
        if child.name in ("config.toml", "AGENTS.md", ".git"):
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
