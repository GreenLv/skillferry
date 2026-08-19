"""skillferry CLI: init / import / plan / apply / doctor / status / export / migrate.

Exit codes (doctor semantics carry the contract):
0 = in sync · 1 = error · 2 = safe-to-apply drift · 3 = conflict needs a human.

The tool performs zero network requests; every command is local.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .adapters.base import resolve_target_env
from .importers.base import empty_manifests, workspace_manifest_text
from .importers.claude import import_claude
from .importers.codex import import_codex
from .io_ops import ApplyError, apply_plan
from .migrate import migrate_codex_profile_sync
from .planner import build_plan
from .secrets import scan_text
from .state import load_ledger
from .workspace import WorkspaceError

EXIT_ERROR = 1
EXIT_DRIFT = 2
EXIT_CONFLICT = 3

EXPORT_SKIP_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "build",
    "dist",
    "state",
    "backups",
    "secrets",
    "workspace.local.toml",
    "auth.json",
    "history.jsonl",
    ".credentials.json",
    ".DS_Store",
    "Thumbs.db",
}


def _workspace_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace", type=Path, default=Path.cwd(), help="workspace root (default: cwd)"
    )


def _sync_arguments(parser: argparse.ArgumentParser) -> None:
    _workspace_argument(parser)
    parser.add_argument(
        "--platform", choices=("auto", "macos", "windows", "linux"), default="auto"
    )
    parser.add_argument("--target", action="append", choices=("codex", "claude", "dsh"))
    parser.add_argument("--home", type=Path, help="override the base home directory")
    parser.add_argument("--codex-home", type=Path, help="override CODEX_HOME")
    parser.add_argument("--claude-home", type=Path, help="override the Claude home")
    parser.add_argument("--dsh-home", type=Path, help="override $DSH_HOME")
    parser.add_argument("--dsh-profile", help="DSH profile name (default: web)")
    parser.add_argument("--json", action="store_true", dest="as_json")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skillferry")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="create a workspace skeleton")
    init_parser.add_argument("workspace_dir", type=Path)

    import_parser = subparsers.add_parser(
        "import", help="draft a workspace from an existing agent setup"
    )
    import_parser.add_argument("--from", required=True, choices=("codex", "claude"), dest="source")
    import_parser.add_argument("--output", type=Path, required=True)
    import_parser.add_argument("--home", type=Path, help="override the base home directory")
    import_parser.add_argument("--codex-home", type=Path, help="override CODEX_HOME")
    import_parser.add_argument("--claude-home", type=Path, help="override the Claude home")
    import_parser.add_argument("--skills-home", type=Path, help="override ~/.agents/skills")
    import_parser.add_argument("--json", action="store_true", dest="as_json")

    for name in ("plan", "apply", "doctor", "status"):
        sub = subparsers.add_parser(name, help=f"{name} the workspace")
        _sync_arguments(sub)
        if name == "apply":
            sub.add_argument("--yes", action="store_true", help="skip confirmation")
            sub.add_argument(
                "--resolve",
                action="append",
                default=[],
                metavar="ID=DECISION",
                help="resolve a conflict: <id>=adopt|overwrite|keep-local (repeatable)",
            )

    export_parser = subparsers.add_parser(
        "export", help="copy the workspace without ever expanding secrets"
    )
    _workspace_argument(export_parser)
    export_parser.add_argument("destination", type=Path)
    export_parser.add_argument("--forbid", action="append", default=[])

    migrate_parser = subparsers.add_parser(
        "migrate", help="convert a legacy codex-profile-sync bundle"
    )
    migrate_parser.add_argument(
        "--from", required=True, choices=("codex-profile-sync",), dest="source"
    )
    migrate_parser.add_argument("bundle", type=Path)
    migrate_parser.add_argument("--output", type=Path, required=True)
    migrate_parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _init_workspace(path: Path) -> None:
    path = path.expanduser().absolute()
    if path.is_symlink():
        raise WorkspaceError(f"destination may not be a symlink: {path}")
    path = path.resolve()
    if path.exists() and any(path.iterdir()):
        raise WorkspaceError(f"destination is not empty: {path}")
    path.mkdir(parents=True, exist_ok=True)
    empty_manifests(path)
    (path / "workspace.toml").write_text(workspace_manifest_text(), encoding="utf-8")


def _print_plan(plan, *, as_json: bool, extra: dict | None = None) -> None:
    if as_json:
        payload = plan.public_dict()
        if extra:
            payload.update(extra)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"Workspace: {plan.workspace_root}")
    print(f"Platform: {plan.platform}   Targets: {', '.join(plan.targets)}")
    if plan.grades:
        print("\nPortability grades:")
        current: tuple[str, str] | None = None
        for grade in plan.grades:
            key = (grade.kind, grade.name)
            if key != current:
                print(f"  {grade.kind.upper()} {grade.name}")
                current = key
            notes = "   " + "; ".join(grade.notes) if grade.notes else ""
            print(f"    {grade.target:6} {grade.grade}{notes}")
    if plan.changes:
        print("\nChanges:")
        for change in plan.changes:
            print(
                f"  {change.action:7} {change.kind:9} {change.target:6} "
                f"{change.name:24} {change.path}"
            )
    else:
        print("\nChanges: none")
    if plan.conflicts:
        print("\nConflicts:")
        for conflict in plan.conflicts:
            print(
                f"  {conflict.kind:7} {conflict.target:6} {conflict.name:24} "
                f"{conflict.path}\n      {conflict.reason}\n      resolve: "
                f"--resolve {conflict.resolution_id}=adopt|overwrite|keep-local"
            )
    if plan.manual_steps:
        print("\nManual steps:")
        for target, steps in sorted(plan.manual_steps.items()):
            for step in steps:
                print(f"  [{target}] {step}")
    for warning in plan.warnings:
        print(f"Warning: {warning}")
    if extra:
        print("\n" + "\n".join(f"{key}: {value}" for key, value in extra.items()))


def _parse_resolutions(raw: Sequence[str]) -> dict[str, str]:
    resolutions: dict[str, str] = {}
    for item in raw:
        if "=" not in item:
            raise WorkspaceError(f"--resolve must be <id>=<decision>: {item!r}")
        identifier, decision = item.split("=", 1)
        if decision not in ("adopt", "overwrite", "keep-local"):
            raise WorkspaceError(
                f"decision must be adopt|overwrite|keep-local: {decision!r}"
            )
        resolutions[identifier] = decision
    return resolutions


def _build_from_args(args, *, resolutions: dict[str, str] | None = None):
    return build_plan(
        args.workspace,
        requested_platform=args.platform,
        targets=tuple(args.target) if args.target else None,
        home=str(args.home) if args.home else None,
        codex_home=str(args.codex_home) if args.codex_home else None,
        claude_home=str(args.claude_home) if args.claude_home else None,
        dsh_home=str(args.dsh_home) if args.dsh_home else None,
        dsh_profile=args.dsh_profile,
        resolutions=resolutions,
    )


def _probe_binary(name: str) -> dict:
    binary = shutil.which(name)
    info = {"available": bool(binary), "path": binary, "version": None}
    if not binary:
        return info
    try:
        result = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, check=False, timeout=10
        )
        output = (result.stdout or result.stderr).strip().splitlines()
        info["version"] = output[0] if output else "unknown"
    except (OSError, subprocess.SubprocessError):
        info["version"] = "unavailable"
    return info


def _export_shareable(workspace: Path, destination: Path, forbid: list[str]) -> None:
    workspace = workspace.expanduser().resolve()
    if not (workspace / "workspace.toml").is_file():
        raise WorkspaceError(f"not a skillferry workspace: {workspace}")
    destination = destination.expanduser().absolute()
    if destination.exists() and any(destination.iterdir()):
        raise WorkspaceError(f"export destination is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    try:
        findings: list[str] = []
        copied = 0
        for source in sorted(workspace.rglob("*")):
            relative = source.relative_to(workspace)
            if any(part in EXPORT_SKIP_NAMES for part in relative.parts):
                continue
            if source.name.endswith((".sqlite", ".sqlite-shm", ".sqlite-wal")):
                continue
            if source.is_symlink():
                findings.append(f"{relative}: symlinks are not exported")
                continue
            if not source.is_file():
                continue
            try:
                text = source.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for finding in scan_text(text, label=str(relative)):
                findings.append(finding)
            for literal in forbid:
                if literal and literal.casefold() in text.casefold():
                    findings.append(f"{relative}: forbidden literal present")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied += 1
        if findings:
            shutil.rmtree(destination, ignore_errors=True)
            print("Export refused: secret or forbidden content found:", file=sys.stderr)
            for finding in findings:
                print(f"  {finding}", file=sys.stderr)
            raise WorkspaceError("export refused: public tree would contain secrets")
        print(f"Exported {copied} file(s) to {destination}")
        print("No secret references were expanded; no secrets were copied.")
    except BaseException:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "init":
            _init_workspace(args.workspace_dir)
            print(f"Created workspace skeleton: {args.workspace_dir.expanduser().resolve()}")
            print("No Git repository or remote was created.")
            return 0

        if args.command == "import":
            if args.source == "codex":
                report = import_codex(
                    output=args.output,
                    codex_home=args.codex_home
                    or (args.home / ".codex" if args.home else None),
                    skills_home=args.skills_home
                    or (args.home / ".agents" / "skills" if args.home else None),
                )
            else:
                report = import_claude(
                    output=args.output,
                    claude_home=args.claude_home
                    or (args.home / ".claude" if args.home else None),
                )
            if args.as_json:
                print(json.dumps(report.public_dict(), indent=2, sort_keys=True))
            else:
                for finding in report.findings:
                    print(
                        f"  {finding.classification:10} {finding.rel:56} {finding.note}"
                    )
                print(f"\nDraft workspace written to {report.output}")
                print("Review the draft, then git-commit it before running `skillferry apply`.")
            return 0

        if args.command == "export":
            _export_shareable(args.workspace, args.destination, args.forbid)
            return 0

        if args.command == "migrate":
            report = migrate_codex_profile_sync(args.bundle, args.output)
            if args.as_json:
                print(json.dumps(report.public_dict(), indent=2, sort_keys=True))
            else:
                for note in report.notes:
                    print(f"  {note.kind:8} {note.rel:40} {note.note}")
                print(f"\nDraft workspace written to {report.output}")
            return 0

        resolutions = (
            _parse_resolutions(args.resolve) if getattr(args, "resolve", None) else {}
        )
        plan = _build_from_args(args, resolutions=resolutions)

        if args.command == "plan":
            _print_plan(plan, as_json=args.as_json)
            return EXIT_CONFLICT if plan.conflicts else 0

        if args.command == "doctor":
            env = resolve_target_env(
                platform=plan.platform,
                home=str(args.home) if args.home else None,
                codex_home=str(args.codex_home) if args.codex_home else None,
                claude_home=str(args.claude_home) if args.claude_home else None,
                dsh_home=str(args.dsh_home) if args.dsh_home else None,
                dsh_profile=args.dsh_profile,
            )
            binaries = {
                target: _probe_binary(target) for target in plan.targets
            }
            for target in plan.targets:
                home_path = plan.homes.get(target)
                if home_path and not home_path.exists():
                    binaries[target]["home_exists"] = False
                    plan.warnings.append(
                        f"{target}: home directory does not exist yet: {home_path}"
                    )
            _print_plan(plan, as_json=args.as_json, extra={"binaries": binaries, "env": {
                "dsh_profile": env.dsh_profile,
            }})
            if plan.conflicts:
                return EXIT_CONFLICT
            return EXIT_DRIFT if plan.changes else 0

        if args.command == "status":
            ledger = load_ledger(plan.workspace_root)
            if args.as_json:
                payload = plan.public_dict()
                payload["ledger"] = {
                    "platform": ledger.get("platform"),
                    "targets": sorted(ledger.get("targets", {})),
                }
                print(json.dumps(payload, indent=2, sort_keys=True))
            else:
                _print_plan(plan, as_json=False)
                print(f"Ledger platform: {ledger.get('platform') or 'never applied'}")
                print(
                    f"Ledger targets: {', '.join(sorted(ledger.get('targets', {}))) or 'none'}"
                )
            return 0

        if args.command == "apply":
            _print_plan(plan, as_json=args.as_json)
            if plan.conflicts:
                return EXIT_CONFLICT
            if not plan.changes:
                print("Nothing to apply: the workspace is already in sync.")
                return 0
            if not args.yes:
                try:
                    answer = input("Apply these changes? [y/N] ")
                except EOFError:
                    return EXIT_ERROR
                if answer.strip().lower() not in {"y", "yes"}:
                    print("Aborted.")
                    return EXIT_ERROR
            backup = apply_plan(plan)
            if not args.as_json:
                print(f"Applied successfully. Recoverable backups: {backup}")
            return 0
    except (WorkspaceError, ApplyError, OSError, ValueError) as exc:
        if getattr(args, "as_json", False):
            print(json.dumps({"schema_version": 1, "error": str(exc)}, indent=2))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_ERROR
