"""Secret references and secret scanning.

The workspace schema only admits ``secret:env/NAME`` or ``secret:file/PATH``
as environment values for MCP servers (see workspace.py). This module parses,
validates, and — only at apply time on the local machine — resolves those
references. Reports, logs, JSON output, and ``export --shareable`` only ever
see the reference, never the resolved value.
"""

from __future__ import annotations

import os
import re
from pathlib import Path, PurePosixPath

from .workspace import WorkspaceError

SECRET_REF_RE = re.compile(r"^secret:(env|file)/(.+)$", re.DOTALL)
ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Patterns used to detect likely secrets in text before exporting or reporting.
SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "api_key",
    "apikey",
    "token",
    "credential",
    "private_key",
)
SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "OpenAI-style API key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "GitHub personal token": re.compile(r"\bgh[oprsu]_[A-Za-z0-9]{20,}\b"),
    "GitHub fine-grained token": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    "bearer token": re.compile(r"\bBearer\s+[A-Za-z0-9._~-]{16,}\b", re.I),
    "private key material": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "long base64-ish blob": re.compile(
        r"\b[A-Za-z0-9+/]{40,}={0,2}\b"
    ),
}


def parse_secret_ref(value: str) -> tuple[str, str] | None:
    match = SECRET_REF_RE.fullmatch(value.strip())
    if not match:
        return None
    return match.group(1), match.group(2)


def is_secret_ref(value: str) -> bool:
    return parse_secret_ref(value) is not None


def validate_secret_ref(value: str, *, workspace_root: Path, label: str) -> tuple[str, str]:
    """Return ``(kind, spec)`` for a valid reference or raise WorkspaceError."""
    parsed = parse_secret_ref(value)
    if parsed is None:
        raise WorkspaceError(
            f"{label}: env values must be 'secret:env/NAME' or "
            f"'secret:file/PATH' references; got {value!r}"
        )
    kind, spec = parsed
    if not spec:
        raise WorkspaceError(f"{label}: empty secret reference")
    if kind == "env":
        if not ENV_NAME_RE.fullmatch(spec):
            raise WorkspaceError(f"{label}: invalid environment variable name {spec!r}")
    else:
        pure = PurePosixPath(spec)
        if pure.is_absolute():
            return kind, spec
        if ".." in pure.parts or not pure.parts:
            raise WorkspaceError(f"{label}: file reference may not traverse parents: {spec!r}")
        relative = workspace_root.joinpath(*pure.parts)
        _refuse_symlink_traversal(workspace_root, relative, label)
    return kind, spec


def _refuse_symlink_traversal(root: Path, path: Path, label: str) -> None:
    current = root
    for part in path.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            raise WorkspaceError(f"{label}: reference traverses a symlink: {path}")


def resolve_secret(
    value: str,
    *,
    workspace_root: Path,
    environ: dict[str, str] | None = None,
    expand: bool,
    label: str,
) -> str:
    """Resolve a reference.

    With ``expand=False`` the original reference is returned unchanged (used by
    reports and export). With ``expand=True`` the local value is read; missing
    sources raise WorkspaceError so ``plan``/``apply`` can surface a conflict
    instead of writing an empty secret.
    """
    kind, spec = validate_secret_ref(value, workspace_root=workspace_root, label=label)
    if not expand:
        return value.strip()
    env = os.environ if environ is None else environ
    if kind == "env":
        if spec not in env:
            raise WorkspaceError(
                f"{label}: environment variable {spec} is not set on this machine"
            )
        return env[spec]
    path = Path(spec) if PurePosixPath(spec).is_absolute() else workspace_root / spec
    if path.is_symlink() or not path.is_file():
        raise WorkspaceError(f"{label}: secret file is missing or unsafe: {path}")
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise WorkspaceError(f"{label}: cannot read secret file {path}: {exc}") from exc


def looks_like_secret(value: str) -> bool:
    if not value:
        return False
    if is_secret_ref(value):
        return False
    return any(pattern.search(value) for pattern in SECRET_PATTERNS.values())


def scan_text(text: str, *, label: str) -> list[str]:
    """Return human-readable findings for likely secrets in ``text``."""
    findings: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(line):
                findings.append(f"{label}:{line_no}: {name}")
    for part in SENSITIVE_KEY_PARTS:
        # Catch ``key = <non-reference value>`` style assignments.
        for match in re.finditer(rf"^\s*[\w.-]*{part}[\w.-]*\s*[=:]\s*(\S.*)$", text, re.I):
            value = match.group(1).strip().strip("\"'")
            if value and not is_secret_ref(value):
                findings.append(
                    f"{label}:{match.start()}: sensitive key '{part}' with literal value"
                )
                break
    return findings


def redact_text(text: str) -> str:
    """Line-based redaction of credential-like assignments for human-readable backups.

    The result is not guaranteed to parse; raw backups are stored separately
    for exact rollback. This copy exists so a human can inspect a backup
    without handling live secrets.
    """
    output: list[str] = []
    assignment = re.compile(r'^(\s*)("[A-Za-z0-9_.-]+"|[A-Za-z0-9_.-]+)(\s*[:=])(.*)$')
    for line in text.splitlines():
        match = assignment.match(line)
        if match:
            key = match.group(2).strip('"')
            if any(part in key.lower() for part in SENSITIVE_KEY_PARTS):
                line = f"{match.group(1)}{match.group(2)}{match.group(3)} <redacted>"
        output.append(line)
    return "\n".join(output).rstrip("\n") + "\n"
