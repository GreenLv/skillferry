"""Atomic application with per-target rollback and recoverable backups.

Every write goes through a temp-file + ``os.replace``, targets must be regular
files inside declared managed roots (symlinks are refused), and each changed
file is backed up first — raw for exact rollback and, for text targets, an
additional credential-redacted copy for safe human inspection. A failure rolls
back the failing target group and every previously applied target group.
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
import tempfile
from pathlib import Path

from .models import SyncPlan, TargetApply
from .paths import is_linklike
from .secrets import redact_text
from .state import backup_root, load_ledger, save_ledger, workspace_id


class ApplyError(RuntimeError):
    pass


def _atomic_write(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, mode)
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _safe_target(path: Path, roots: list[Path]) -> None:
    for root in roots:
        try:
            relative = path.relative_to(root)
            break
        except ValueError:
            continue
    else:
        raise ApplyError(f"target escapes every managed root: {path}")
    if is_linklike(root):
        raise ApplyError(f"managed root is a symlink or junction: {root}")
    current = root
    for part in relative.parts[:-1]:
        current = current / part
        if is_linklike(current):
            raise ApplyError(f"target parent is a symlink or junction: {current}")
    if is_linklike(path):
        raise ApplyError(f"target is a symlink or junction: {path}")
    if path.exists() and not path.is_file():
        raise ApplyError(f"target is not a regular file: {path}")


def _existing_targets(apply: TargetApply) -> list[Path]:
    paths = [copy.target for copy in apply.copies]
    paths += [write.target for write in apply.writes]
    paths += [delete.target for delete in apply.deletes]
    return [path for path in paths if path.exists()]


def _backup_group(apply: TargetApply, backup_dir: Path) -> dict[Path, Path]:
    """Back up every existing target; returns target -> raw backup path."""
    backups: dict[Path, Path] = {}
    for target in _existing_targets(apply):
        relative: Path | None = None
        for root in apply.roots:
            try:
                relative = target.relative_to(root)
                break
            except ValueError:
                continue
        if relative is None:
            relative = Path(target.name)
        destination = backup_dir / apply.target / relative.as_posix().replace("/", "__")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, destination)
        backups[target] = destination
    for write in apply.writes:
        if not write.redact_backup or write.target not in backups:
            continue
        try:
            original = backups[write.target].read_text(encoding="utf-8")
            redacted = redact_text(original)
        except (OSError, UnicodeError, ValueError):
            continue
        redacted_path = backups[write.target].with_name(
            backups[write.target].name + ".redacted"
        )
        redacted_path.write_text(redacted, encoding="utf-8")
        os.chmod(redacted_path, 0o600)
    return backups


def _apply_group(apply: TargetApply) -> None:
    for copy in apply.copies:
        _safe_target(copy.target, apply.roots)
        mode = copy.mode if copy.mode is not None else (
            copy.source.stat().st_mode & 0o777
        )
        _atomic_write(copy.target, copy.source.read_bytes(), mode)
    for write in apply.writes:
        _safe_target(write.target, apply.roots)
        _atomic_write(write.target, write.text.encode("utf-8"), write.mode)
    for delete in apply.deletes:
        _safe_target(delete.target, apply.roots)
        if delete.target.exists():
            delete.target.unlink()


def _rollback_group(
    apply: TargetApply, backups: dict[Path, Path], created: set[Path]
) -> None:
    for target in reversed(
        [copy.target for copy in apply.copies]
        + [write.target for write in apply.writes]
        + [delete.target for delete in apply.deletes]
    ):
        try:
            if target in backups:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backups[target], target)
            elif target in created and target.exists():
                target.unlink()
        except OSError:
            pass


def apply_plan(plan: SyncPlan) -> Path:
    if plan.conflicts:
        raise ApplyError("refusing to apply a plan with conflicts")
    identifier = workspace_id(plan.workspace_root)
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%S%fZ")
    backup_dir = backup_root(identifier) / stamp
    backup_dir.mkdir(parents=True, mode=0o700)
    os.chmod(backup_dir.parent.parent, 0o700)
    os.chmod(backup_dir.parent, 0o700)

    previous = load_ledger(plan.workspace_root)
    groups: dict[str, tuple[TargetApply, dict[Path, Path], set[Path]]] = {}
    applied: list[str] = []
    active: str | None = None

    for target in plan.targets:
        apply = plan.applies.get(target)
        if apply is None:
            continue
        for path in _existing_targets(apply) + [c.target for c in apply.copies] + [
            w.target for w in apply.writes
        ] + [d.target for d in apply.deletes]:
            _safe_target(path, apply.roots)
        backups = _backup_group(apply, backup_dir)
        created = {
            path
            for path in [c.target for c in apply.copies]
            + [w.target for w in apply.writes]
            if not path.exists()
        }
        groups[target] = (apply, backups, created)

    try:
        for target in plan.targets:
            if target not in groups:
                continue
            active = target
            apply, _, _ = groups[target]
            _apply_group(apply)
            applied.append(target)
            active = None
        ledger = previous
        ledger["platform"] = plan.platform
        for target in plan.targets:
            if target in plan.applies:
                ledger["targets"][target] = plan.applies[target].ledger
        save_ledger(ledger)
    except Exception as exc:
        if active is not None and active in groups:
            apply, backups, created = groups[active]
            _rollback_group(apply, backups, created)
        for target in reversed(applied):
            apply, backups, created = groups[target]
            _rollback_group(apply, backups, created)
        raise ApplyError(f"apply failed and rollback was attempted: {exc}") from exc
    return backup_dir
