"""Thin migration from the legacy codex-profile-sync bundle format.

The old bundle's portable pieces — the skills directory and the MCP servers
declared in config/common.toml — become workspace assets. Literal env values
turn into ``secret:env/NAME`` references. Codex-only named profiles are listed
as manual follow-ups and never copied. The old bundle is never modified.
"""

from __future__ import annotations

import shutil
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

import tomlkit

from .importers.base import empty_manifests, prepare_output
from .secrets import looks_like_secret


@dataclass(frozen=True)
class MigrationNote:
    kind: str
    rel: str
    note: str


@dataclass
class MigrationReport:
    bundle: Path
    output: Path
    notes: list[MigrationNote] = field(default_factory=list)

    def public_dict(self) -> dict:
        return {
            "schema_version": 1,
            "bundle": str(self.bundle),
            "output": str(self.output),
            "notes": [asdict(item) for item in self.notes],
        }


def _read_sync_toml(bundle: Path) -> dict:
    manifest = bundle / "sync.toml"
    if not manifest.is_file():
        raise ValueError(f"not a codex-profile-sync bundle (missing sync.toml): {bundle}")
    with manifest.open("rb") as handle:
        return tomllib.load(handle)


def _registry_from_config(bundle: Path, report: MigrationReport) -> dict[str, dict]:
    entries: dict[str, dict] = {}
    for relative in ("config/common.toml",):
        path = bundle / relative
        if not path.is_file():
            continue
        with path.open("rb") as handle:
            config = tomllib.load(handle)
        servers = config.get("mcp_servers", {})
        if not isinstance(servers, dict):
            continue
        for name, server in sorted(servers.items()):
            if name == "node_repl":
                report.notes.append(
                    MigrationNote("skipped", f"mcp:{name}", "Codex-owned embedded server")
                )
                continue
            if not isinstance(server, dict) or not isinstance(server.get("command"), str):
                report.notes.append(
                    MigrationNote("skipped", f"mcp:{name}", "unrecognized server shape")
                )
                continue
            entry: dict = {"command": server["command"]}
            args = server.get("args", [])
            if args and isinstance(args, list) and all(
                isinstance(item, str) for item in args
            ):
                entry["args"] = list(args)
            refs: dict[str, str] = {}
            for key, value in sorted((server.get("env") or {}).items()):
                if not isinstance(key, str) or not isinstance(value, str):
                    continue
                refs[key] = f"secret:env/{key}"
                if looks_like_secret(value):
                    report.notes.append(
                        MigrationNote(
                            "converted",
                            f"mcp:{name}.env.{key}",
                            "credential value became a secret:env reference",
                        )
                    )
            if refs:
                entry["env"] = refs
            entries[str(name)] = entry
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


def migrate_codex_profile_sync(bundle: Path, output: Path) -> MigrationReport:
    bundle = bundle.expanduser().absolute()
    if bundle.is_symlink():
        raise ValueError(f"bundle may not be a symlink: {bundle}")
    bundle = bundle.resolve()
    data = _read_sync_toml(bundle)
    destination = prepare_output(output)
    report = MigrationReport(bundle=bundle, output=destination)
    empty_manifests(destination)

    skills = data.get("skills", {})
    skills_enabled = bool(skills.get("enabled", False)) if isinstance(skills, dict) else False
    skills_rel = str(skills.get("directory", "skills")) if isinstance(skills, dict) else "skills"
    skills_dir = bundle / skills_rel
    if skills_enabled and skills_dir.is_dir():
        shutil.copytree(skills_dir, destination / "skills", dirs_exist_ok=True)
        report.notes.append(
            MigrationNote("copied", "skills", "skill directory migrated as-is")
        )
    else:
        report.notes.append(
            MigrationNote("skipped", "skills", "skills were disabled in the old bundle")
        )

    named_profiles = data.get("named_profiles", {})
    if isinstance(named_profiles, dict) and named_profiles.get("directory"):
        report.notes.append(
            MigrationNote(
                "manual",
                str(named_profiles.get("directory")),
                "Codex-only named profile configs are not portable assets; "
                "review them manually or drop them",
            )
        )

    entries = _registry_from_config(bundle, report)
    if entries:
        _write_registry(destination, entries)
        report.notes.append(
            MigrationNote("copied", "mcp/servers.toml", f"{len(entries)} server(s) converted")
        )

    manifest = destination / "workspace.toml"
    manifest.write_text(
        """schema_version = 1

[skills]
directory = "skills"
default_targets = ["codex", "claude", "dsh"]

[instructions]
common = "instructions/global.md"

[mcp]
registry = "mcp/servers.toml"

[extensions]
manifest = "extensions/manifest.toml"

[overlays]
platform_dir = "overlays/platform"
target_dir = "overlays/target"

[protect]
paths = []
""",
        encoding="utf-8",
    )
    report.notes.append(
        MigrationNote(
            "written",
            "workspace.toml",
            "draft workspace manifest; review and git-commit before applying",
        )
    )
    return report
