"""Local-only ownership ledger for skillferry.

The ledger records, per workspace and per target, the hash of every file,
marker block, and MCP section that skillferry wrote. ``plan`` uses it to tell
"changed by the user since last apply" (conflict) from "stale managed content"
(safe update), and to adopt identical pre-existing content instead of
overwriting it. The ledger lives under the platform state directory and never
inside the workspace tree, so a public workspace repository stays clean.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

from platformdirs import user_state_path

STATE_SCHEMA = 1


class StateError(ValueError):
    pass


def state_root() -> Path:
    override = os.environ.get("SKILLFERRY_STATE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return user_state_path("skillferry", appauthor=False)


def workspace_id(workspace_root: Path) -> str:
    digest = hashlib.sha256(str(workspace_root.resolve()).encode("utf-8")).hexdigest()
    return f"ws-{digest[:16]}"


def ledger_file(workspace_id: str) -> Path:
    return state_root() / "workspaces" / f"{workspace_id}.json"


def backup_root(workspace_id: str) -> Path:
    return state_root() / "backups" / workspace_id


def empty_ledger(workspace_root: Path) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA,
        "workspace_id": workspace_id(workspace_root),
        "workspace_root": str(workspace_root.resolve()),
        "platform": None,
        "targets": {},
    }


def load_ledger(workspace_root: Path) -> dict[str, Any]:
    identifier = workspace_id(workspace_root)
    path = ledger_file(identifier)
    if not path.exists():
        return empty_ledger(workspace_root)
    if path.is_symlink():
        raise StateError(f"ledger may not be a symlink: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(f"cannot read ledger {path}: {exc}") from exc
    if (
        data.get("schema_version") != STATE_SCHEMA
        or data.get("workspace_id") != identifier
    ):
        raise StateError(f"ledger does not match this workspace: {path}")
    if not isinstance(data.get("targets"), dict):
        raise StateError(f"ledger targets must be an object: {path}")
    return data


def ledger_target(ledger: dict[str, Any], target: str) -> dict[str, dict[str, Any]]:
    entries = ledger["targets"].setdefault(target, {})
    if not isinstance(entries, dict):
        raise StateError(f"ledger target entry must be an object: {target}")
    return entries


def save_ledger(ledger: dict[str, Any]) -> Path:
    path = ledger_file(str(ledger["workspace_id"]))
    payload = (json.dumps(ledger, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(payload)
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
    return path


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bytes_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def text_hash(text: str) -> str:
    return bytes_hash(text.encode("utf-8"))


def executable(path: Path) -> bool:
    return bool(stat.S_IMODE(path.stat().st_mode) & 0o111)


def file_record(path: Path) -> dict[str, Any]:
    return {"hash": file_hash(path), "executable": executable(path)}
