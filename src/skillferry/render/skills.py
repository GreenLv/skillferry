"""Render workspace skills into a target's skill directory.

Ownership rules (per file): identical unregistered content is adopted, missing
files are created, ledger-registered files are updated only when the local
copy still matches the ledger, and any other local content is a conflict —
never silently overwritten. Symlinks and non-regular files are conflicts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import Change, FileCopy, FileDelete, GradeReport
from ..paths import is_linklike
from ..state import file_record
from . import RenderContext, effective_targets


def _target_record(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    if is_linklike(path) or not path.is_file():
        return {"unsafe": True}
    return file_record(path)


def _same(record_a: dict[str, Any] | None, record_b: dict[str, Any]) -> bool:
    if not record_a or record_a.get("unsafe"):
        return False
    return all(record_a.get(key) == value for key, value in record_b.items())


def plan_skills(ctx: RenderContext) -> None:
    target = ctx.target
    skill_dir = ctx.adapter.skill_dir(ctx.env)
    if skill_dir is None:
        for skill in ctx.skills.values():
            if target not in effective_targets(skill, ctx.ws):
                continue
            ctx.plan.grades.append(
                GradeReport("skill", skill.name, target, "unsupported", ("no skill directory",))
            )
        return

    previous = ctx.previous.get("skills", {})
    next_state: dict[str, Any] = {name: dict(records) for name, records in previous.items()}
    active_names: set[str] = set()

    for name, skill in sorted(ctx.skills.items()):
        if target not in effective_targets(skill, ctx.ws):
            continue
        active_names.add(name)
        ctx.plan.grades.append(ctx.adapter.grade_skill(skill))
        prior = previous.get(name, {})
        target_dir = skill_dir / name
        entry: dict[str, Any] = dict(prior)

        for relative, source in sorted(skill.files.items()):
            destination = target_dir / relative
            target_record = _target_record(destination)
            source_record = file_record(source)
            resolution_id = f"skill:{target}:{name}:{relative}"
            if target_record and target_record.get("unsafe"):
                ctx.conflict(
                    "skill",
                    name,
                    str(destination),
                    "target is a symlink or non-file entry",
                    resolution_id,
                )
            elif target_record is None:
                ctx.plan.changes.append(Change("skill", target, name, "create", str(destination)))
                ctx.apply.copies.append(FileCopy(source=source, target=destination))
                entry[relative] = source_record
            elif _same(target_record, source_record):
                if relative not in prior:
                    ctx.plan.changes.append(
                        Change("skill", target, name, "adopt", str(destination))
                    )
                entry[relative] = source_record
            elif relative not in prior:
                decision = ctx.resolve(resolution_id)
                if decision == "overwrite":
                    ctx.plan.changes.append(
                        Change("skill", target, name, "update", str(destination))
                    )
                    ctx.apply.copies.append(FileCopy(source=source, target=destination))
                    entry[relative] = source_record
                elif decision == "adopt":
                    entry[relative] = target_record
                else:
                    ctx.conflict(
                        "skill",
                        name,
                        str(destination),
                        "refusing to overwrite an unregistered file",
                        resolution_id,
                    )
            elif not _same(target_record, prior[relative]):
                decision = ctx.resolve(resolution_id)
                if decision == "overwrite":
                    ctx.plan.changes.append(
                        Change("skill", target, name, "update", str(destination))
                    )
                    ctx.apply.copies.append(FileCopy(source=source, target=destination))
                    entry[relative] = source_record
                elif decision == "adopt":
                    entry[relative] = target_record
                else:
                    ctx.conflict(
                        "skill",
                        name,
                        str(destination),
                        "managed file was modified locally",
                        resolution_id,
                    )
            else:
                ctx.plan.changes.append(Change("skill", target, name, "update", str(destination)))
                ctx.apply.copies.append(FileCopy(source=source, target=destination))
                entry[relative] = source_record

        for relative, old_record in sorted(prior.items()):
            if relative in skill.files:
                continue
            destination = target_dir / relative
            target_record = _target_record(destination)
            resolution_id = f"skill:{target}:{name}:{relative}"
            if target_record is None:
                entry.pop(relative, None)
                continue
            if target_record.get("unsafe"):
                ctx.conflict(
                    "skill",
                    name,
                    str(destination),
                    "managed target became a symlink or non-file",
                    resolution_id,
                )
            elif not _same(target_record, old_record):
                decision = ctx.resolve(resolution_id)
                if decision == "overwrite":
                    ctx.plan.changes.append(
                        Change("skill", target, name, "delete", str(destination))
                    )
                    ctx.apply.deletes.append(FileDelete(target=destination))
                    entry.pop(relative, None)
                elif decision == "adopt":
                    entry.pop(relative, None)
                else:
                    ctx.conflict(
                        "skill",
                        name,
                        str(destination),
                        "managed file changed before source deletion",
                        resolution_id,
                    )
            else:
                ctx.plan.changes.append(
                    Change("skill", target, name, "delete", str(destination))
                )
                ctx.apply.deletes.append(FileDelete(target=destination))
                entry.pop(relative, None)

        if entry:
            next_state[name] = entry
        else:
            next_state.pop(name, None)

    # Reconcile skills that disappeared entirely or no longer target this
    # adapter. Per-file ownership checks still protect local modifications.
    for name, prior in sorted(previous.items()):
        if name in active_names:
            continue
        entry: dict[str, Any] = dict(prior)
        target_dir = skill_dir / name
        for relative, old_record in sorted(prior.items()):
            destination = target_dir / relative
            target_record = _target_record(destination)
            resolution_id = f"skill:{target}:{name}:{relative}"
            if target_record is None:
                entry.pop(relative, None)
                continue
            if target_record.get("unsafe"):
                ctx.conflict(
                    "skill",
                    name,
                    str(destination),
                    "managed target became a symlink or non-file",
                    resolution_id,
                )
                continue
            if not _same(target_record, old_record):
                decision = ctx.resolve(resolution_id)
                if decision == "overwrite":
                    ctx.plan.changes.append(
                        Change("skill", target, name, "delete", str(destination))
                    )
                    ctx.apply.deletes.append(FileDelete(target=destination))
                    entry.pop(relative, None)
                elif decision == "adopt":
                    # The source no longer owns this path; keep it locally and
                    # release it from the ledger.
                    entry.pop(relative, None)
                else:
                    ctx.conflict(
                        "skill",
                        name,
                        str(destination),
                        "managed file changed before source skill removal",
                        resolution_id,
                    )
                continue
            ctx.plan.changes.append(
                Change("skill", target, name, "delete", str(destination))
            )
            ctx.apply.deletes.append(FileDelete(target=destination))
            entry.pop(relative, None)
        if entry:
            next_state[name] = entry
        else:
            next_state.pop(name, None)

    ctx.next_ledger["skills"] = next_state
