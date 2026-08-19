"""Import classification: PORTABLE / LOCAL-ONLY / SENSITIVE / UNKNOWN.

Importers read an existing agent's local state and draft a target-neutral
workspace: portable assets are copied, secrets are converted to
``secret:env/NAME`` references and never copied, machine-local state is
skipped, and everything unrecognized is listed for human review.
"""

from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path

CLASSIFICATIONS = ("PORTABLE", "LOCAL-ONLY", "SENSITIVE", "UNKNOWN")

RUNTIME_NAMES = (
    "sessions",
    "logs",
    "cache",
    "state",
    "backups",
    "projects",
    "desktop",
    "marketplace",
    "trust",
    "plugins",
    "node_modules",
    ".git",
    "debug",
    "ide",
    "telemetry",
    "usage-data",
    "stats-cache.json",
    "shell-snapshots",
)
SENSITIVE_NAMES = ("auth.json", ".credentials.json", "credentials.json", "history.jsonl")
IGNORED_NAMES = {".DS_Store", "Thumbs.db", ".gitkeep"}


@dataclass(frozen=True)
class Finding:
    rel: str
    classification: str
    note: str
    action: str  # copied | converted | skipped | listed


@dataclass
class ImportReport:
    source: str
    output: Path
    findings: list[Finding] = field(default_factory=list)

    def public_dict(self) -> dict:
        return {
            "schema_version": 1,
            "source": self.source,
            "output": str(self.output),
            "findings": [asdict(item) for item in self.findings],
        }


def prepare_output(path: Path) -> Path:
    path = path.expanduser().absolute()
    if path.is_symlink():
        raise ValueError(f"destination may not be a symlink: {path}")
    path = path.resolve()
    if path.exists() and any(path.iterdir()):
        raise ValueError(f"destination is not empty: {path}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def copy_tree(source: Path, destination: Path, *, label: str) -> None:
    if source.is_symlink():
        raise ValueError(f"{label} may not be a symlink: {source}")
    for entry in source.rglob("*"):
        if entry.is_symlink():
            raise ValueError(f"{label} contains a symlink: {entry}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)


def classify_name(name: str) -> str:
    if name in SENSITIVE_NAMES:
        return "SENSITIVE"
    if name in RUNTIME_NAMES:
        return "LOCAL-ONLY"
    if name.endswith((".sqlite", ".sqlite-shm", ".sqlite-wal", ".db")):
        return "LOCAL-ONLY"
    return "UNKNOWN"


def workspace_manifest_text() -> str:
    return """schema_version = 1

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
"""


def empty_manifests(output: Path) -> None:
    (output / "instructions").mkdir(parents=True, exist_ok=True)
    (output / "instructions" / "global.md").write_text(
        "# Portable instructions\n"
        "\n"
        "# Rules written here are rendered into each agent's global instructions\n"
        "# file by `skillferry apply` (marker-delimited blocks by default).\n",
        encoding="utf-8",
    )
    (output / "mcp").mkdir(parents=True, exist_ok=True)
    (output / "mcp" / "servers.toml").write_text(
        "# Non-secret MCP connection templates.\n"
        "# env values must be secret:env/NAME or secret:file/PATH references.\n"
        "\n"
        "[servers]\n",
        encoding="utf-8",
    )
    (output / "extensions").mkdir(parents=True, exist_ok=True)
    (output / "extensions" / "manifest.toml").write_text(
        "# Expected-state extension declarations (source + pinned version).\n"
        "\n"
        "[extensions]\n",
        encoding="utf-8",
    )
    (output / "overlays" / "platform").mkdir(parents=True, exist_ok=True)
    (output / "overlays" / "target").mkdir(parents=True, exist_ok=True)
    for platform in ("macos", "windows", "linux"):
        (output / "overlays" / "platform" / f"{platform}.toml").write_text(
            f"# Platform-specific overrides for {platform}.\n", encoding="utf-8"
        )
    for target in ("codex", "claude", "dsh"):
        (output / "overlays" / "target" / f"{target}.toml").write_text(
            f"# Target-specific overrides for {target}.\n", encoding="utf-8"
        )
    (output / "skills").mkdir(parents=True, exist_ok=True)
    (output / "skills" / ".gitkeep").write_text("", encoding="utf-8")
    (output / ".gitignore").write_text(
        "workspace.local.toml\nstate/\nbackups/\nsecrets/\n*.secret\n.DS_Store\n",
        encoding="utf-8",
    )
