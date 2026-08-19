#!/usr/bin/env python3
"""Validate a workspace (schema, overlays, skills, MCP registry, extensions).

Usage: python scripts/validate_workspace.py <workspace-root> [--platform p] [--target t ...]
Exit code 0 when every requested target/platform pair validates.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from skillferry.models import SUPPORTED_PLATFORMS, SUPPORTED_TARGETS  # noqa: E402
from skillferry.workspace import WorkspaceError, validate_workspace  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--platform", choices=("auto", *SUPPORTED_PLATFORMS), default="auto")
    parser.add_argument(
        "--target", action="append", choices=SUPPORTED_TARGETS, default=list(SUPPORTED_TARGETS)
    )
    args = parser.parse_args()
    platform = (
        args.platform
        if args.platform != "auto"
        else None  # validate_workspace auto-detects when None
    )
    try:
        lines = validate_workspace(
            args.workspace, targets=tuple(args.target), platform=platform
        )
    except (WorkspaceError, OSError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
