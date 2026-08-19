"""Render global instructions into each target's rules file.

Three strategies (workspace ``instructions.strategy``):

- ``marker`` (default): insert/replace ``SKILLFERRY`` marker-delimited blocks,
  preserving every unmanaged byte; ownership is per block.
- ``include``: the same blocks, but each body is one ``@path`` import line
  pointing at the workspace source file.
- ``copy``: the whole target file is owned and replaced by the concatenated
  instruction sources; any unregistered local content is a conflict.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from ..models import Change, GradeReport, TextWrite
from ..secrets import scan_text
from ..state import text_hash
from ..workspace import WorkspaceError
from . import RenderContext

BEGIN_PREFIX = "<!-- BEGIN SKILLFERRY RULES "
END_PREFIX = "<!-- END SKILLFERRY RULES "
MARKER_RE = re.compile(r"<!--\s*(?:BEGIN|END)\s+SKILLFERRY\s+RULES\s+([A-Za-z0-9_.-]+)\s*-->")


class BlockSpan(NamedTuple):
    name: str
    start: int
    end: int
    lines: tuple[str, ...]


def normalize_text(text: str) -> str:
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def parse_blocks(text: str) -> dict[str, BlockSpan]:
    lines = normalize_text(text).splitlines()
    spans: dict[str, BlockSpan] = {}
    active: tuple[str, int] | None = None
    for index, line in enumerate(lines):
        match = MARKER_RE.fullmatch(line.strip())
        if not match:
            continue
        name = match.group(1)
        begin = line.strip().startswith(BEGIN_PREFIX)
        end = line.strip().startswith(END_PREFIX)
        if begin:
            if active is not None:
                raise WorkspaceError(f"nested SKILLFERRY rules block on line {index + 1}")
            if name in spans:
                raise WorkspaceError(f"duplicate SKILLFERRY rules block: {name}")
            active = (name, index)
        elif end:
            if active is None:
                raise WorkspaceError(f"SKILLFERRY rules block end without start: {name}")
            if active[0] != name:
                raise WorkspaceError(
                    f"mismatched SKILLFERRY rules block end: expected {active[0]}, got {name}"
                )
            start = active[1]
            spans[name] = BlockSpan(name, start, index, tuple(lines[start : index + 1]))
            active = None
    if active is not None:
        raise WorkspaceError(f"unterminated SKILLFERRY rules block: {active[0]}")
    return spans


def unmanaged_text(text: str) -> str:
    lines = normalize_text(text).splitlines()
    spans = parse_blocks(text)
    managed = {
        index
        for span in spans.values()
        for index in range(span.start, span.end + 1)
    }
    return "\n".join(line for index, line in enumerate(lines) if index not in managed)


def render_block(name: str, body: str) -> list[str]:
    return [f"{BEGIN_PREFIX}{name} -->", *body.splitlines(), f"{END_PREFIX}{name} -->"]


def _sources(ctx: RenderContext) -> dict[str, Path]:
    sources: dict[str, Path] = {}
    if ctx.ws.instructions.common is not None:
        sources["global"] = ctx.ws.instructions.common
    sources.update(ctx.ws.instructions.blocks)
    return sources


def _secret_conflicts(ctx: RenderContext, sources: dict[str, Path]) -> None:
    for name, path in sorted(sources.items()):
        try:
            findings = scan_text(path.read_text(encoding="utf-8"), label=str(path))
        except (OSError, UnicodeError) as exc:
            ctx.conflict(
                "rules", name, str(path), f"cannot read instruction source: {exc}",
                f"rules:{ctx.target}:{name}",
            )
            continue
        for finding in findings:
            ctx.conflict(
                "rules", name, str(path), f"credential-looking content: {finding}",
                f"rules:{ctx.target}:{name}",
            )


def _marker_merge(ctx: RenderContext, sources: dict[str, Path], *, include: bool) -> None:
    target_file = ctx.adapter.rules_file(ctx.env)
    if target_file is None:
        return
    original = read_text(target_file)
    try:
        spans = parse_blocks(original)
    except WorkspaceError as exc:
        ctx.conflict("rules", "all", str(target_file), str(exc), f"rules:{ctx.target}:all")
        return
    original_unmanaged = unmanaged_text(original)

    bodies: dict[str, str] = {}
    for name, path in sorted(sources.items()):
        try:
            raw = normalize_text(path.read_text(encoding="utf-8")).strip()
        except (OSError, UnicodeError) as exc:
            ctx.conflict(
                "rules", name, str(path), f"cannot read instruction source: {exc}",
                f"rules:{ctx.target}:{name}",
            )
            continue
        if include:
            bodies[name] = f"@{path.resolve()}"
        else:
            bodies[name] = raw
        if not raw and not include:
            ctx.plan.warnings.append(
                f"rules:{ctx.target}: instruction source is empty: {path}"
            )

    desired_names = set(bodies)
    lines = normalize_text(original).splitlines()
    output: list[str] = []
    cursor = 0
    for span in sorted(spans.values(), key=lambda item: item.start):
        output.extend(lines[cursor : span.start])
        if span.name in desired_names:
            output.extend(render_block(span.name, bodies[span.name]))
        cursor = span.end + 1
    output.extend(lines[cursor:])
    for name in sorted(desired_names):
        if name in spans:
            continue
        output.extend(render_block(name, bodies[name]))

    desired = "\n".join(output).rstrip("\n")
    if desired:
        desired += "\n"
    if unmanaged_text(desired) != original_unmanaged:
        ctx.conflict(
            "rules",
            "all",
            str(target_file),
            "merge would alter unmanaged rules content",
            f"rules:{ctx.target}:all",
        )
        return

    next_state: dict[str, dict[str, str]] = {}
    for name in desired_names:
        next_state[name] = {
            "block_sha256": text_hash("\n".join(render_block(name, bodies[name])) + "\n"),
            "unmanaged_sha256": text_hash(original_unmanaged),
        }
    ctx.next_ledger["rules"] = next_state

    if desired != original:
        label = "create" if not original else "update"
        ctx.plan.changes.append(Change("rules", ctx.target, "all", label, str(target_file)))
        ctx.apply.writes.append(
            TextWrite(target=target_file, text=desired, mode=0o644, label="rules.md")
        )


def _copy_merge(ctx: RenderContext, sources: dict[str, Path]) -> None:
    target_file = ctx.adapter.rules_file(ctx.env)
    if target_file is None:
        return
    original = read_text(target_file)
    sections: list[str] = []
    for name, path in sorted(sources.items()):
        try:
            sections.append(normalize_text(path.read_text(encoding="utf-8")).strip())
        except (OSError, UnicodeError) as exc:
            ctx.conflict(
                "rules", name, str(path), f"cannot read instruction source: {exc}",
                f"rules:{ctx.target}:{name}",
            )
            continue
    desired = "\n\n".join(section for section in sections if section).rstrip("\n") + "\n"

    previous = ctx.previous.get("rules", {})
    prior = previous.get("file_hash")
    current = text_hash(original)
    desired_hash = text_hash(desired)
    resolution_id = f"rules:{ctx.target}:file"
    if original == desired:
        ctx.next_ledger["rules"] = {"file_hash": desired_hash}
        return
    if original and prior is None:
        decision = ctx.resolve(resolution_id)
        if decision == "overwrite":
            pass
        elif decision == "adopt":
            ctx.next_ledger["rules"] = {"file_hash": current}
            return
        else:
            ctx.conflict(
                "rules",
                "all",
                str(target_file),
                "refusing to replace an unregistered rules file",
                resolution_id,
            )
            return
    if original and prior is not None and current != prior:
        decision = ctx.resolve(resolution_id)
        if decision == "overwrite":
            pass
        elif decision == "adopt":
            ctx.next_ledger["rules"] = {"file_hash": current}
            return
        else:
            ctx.conflict(
                "rules",
                "all",
                str(target_file),
                "managed rules file was modified locally",
                resolution_id,
            )
            return
    ctx.next_ledger["rules"] = {"file_hash": desired_hash}
    label = "create" if not original else "update"
    ctx.plan.changes.append(Change("rules", ctx.target, "all", label, str(target_file)))
    ctx.apply.writes.append(
        TextWrite(target=target_file, text=desired, mode=0o644, label="rules.md")
    )


def plan_rules(ctx: RenderContext) -> None:
    strategy = ctx.ws.instructions.strategy
    target_file = ctx.adapter.rules_file(ctx.env)
    grade, notes = ctx.adapter.rules_grade(strategy)
    if target_file is None:
        grade = "unsupported"
        notes = ("no rules file for this target",)
    ctx.plan.grades.append(GradeReport("rules", "global", ctx.target, grade, notes))
    if target_file is None:
        return

    sources = _sources(ctx)
    if not sources:
        return
    _secret_conflicts(ctx, sources)
    if any(c.kind == "rules" and c.target == ctx.target for c in ctx.plan.conflicts):
        return
    if strategy == "copy":
        _copy_merge(ctx, sources)
    else:
        _marker_merge(ctx, sources, include=strategy == "include")
