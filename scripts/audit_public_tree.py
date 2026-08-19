#!/usr/bin/env python3
"""Fail when a public source tree contains likely private or secret material.

skillferry's public tree legitimately contains SKILL.md files (the seed
skills), so this auditor forbids runtime/credential filenames and secret
patterns instead of skill files. Run it before every commit and in CI:
``python scripts/audit_public_tree.py .``
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "build",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "state",
    "backups",
    "secrets",
}
SKIP_SELF_SUFFIX = "scripts/audit_public_tree.py"
FORBIDDEN_NAMES = {
    "auth.json",
    "history.jsonl",
    ".codex-global-state.json",
    ".credentials.json",
    "credentials.json",
    "workspace.local.toml",
    "sync.toml",
}
FORBIDDEN_SUFFIXES = (".sqlite", ".sqlite-shm", ".sqlite-wal", ".secret", ".key", ".pem")
PATTERNS = {
    "macOS user-specific absolute path": re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    "Windows user-specific absolute path": re.compile(r"[A-Za-z]:\\Users\\[A-Za-z0-9._-]+\\"),
    "email address": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "OpenAI-style API key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "GitHub personal token": re.compile(r"\bgh[oprsu]_[A-Za-z0-9]{20,}\b"),
    "GitHub fine-grained token": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    "bearer token": re.compile(r"\bBearer\s+[A-Za-z0-9._~-]{16,}\b", re.I),
    "private key material": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
}


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            yield path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, nargs="?", default=Path.cwd())
    parser.add_argument("--forbid", action="append", default=[], help="additional literal")
    args = parser.parse_args()
    root = args.root.resolve()
    findings: list[str] = []

    for path in iter_files(root):
        relative = path.relative_to(root)
        if relative.as_posix().endswith(SKIP_SELF_SUFFIX):
            continue
        if path.name in FORBIDDEN_NAMES:
            findings.append(f"{relative}: forbidden private/runtime filename")
        if path.name.endswith(FORBIDDEN_SUFFIXES):
            findings.append(f"{relative}: forbidden secret-suffix filename")
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{relative}: {label}")
        for literal in args.forbid:
            if literal and literal.casefold() in text.casefold():
                findings.append(f"{relative}: additional forbidden literal")

    if findings:
        print("Public-tree audit failed:", file=sys.stderr)
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        return 1
    print(f"Public-tree audit passed: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
