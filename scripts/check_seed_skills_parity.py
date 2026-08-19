#!/usr/bin/env python3
"""Keep the starter workspace's embedded seed skills in parity with skills/.

The repository root skills/ directory is the canonical copy of the seed
skills; examples/starter-workspace embeds them so the demo workspace runs
standalone. Any drift between the two fails CI.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

SEED_SKILLS = ("setup-skillferry", "release-checklist")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            result[path.relative_to(root).as_posix()] = sha256(path)
    return result


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    problems: list[str] = []
    for name in SEED_SKILLS:
        canonical = repo_root / "skills" / name
        embedded = repo_root / "examples" / "starter-workspace" / "skills" / name
        if not canonical.is_dir():
            problems.append(f"{canonical.relative_to(repo_root)}: missing canonical skill")
            continue
        if not embedded.is_dir():
            problems.append(f"{embedded.relative_to(repo_root)}: missing embedded copy")
            continue
        source = inventory(canonical)
        target = inventory(embedded)
        missing = sorted(set(source) - set(target))
        extra = sorted(set(target) - set(source))
        changed = sorted(path for path in set(source) & set(target) if source[path] != target[path])
        if missing or extra or changed:
            problems.append(
                f"{name}: drift detected "
                f"(missing={missing}, extra={extra}, changed={changed}); "
                "re-copy the canonical skill into the starter workspace"
            )
    if problems:
        print("Seed skill parity check failed:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print("Seed skill parity check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
