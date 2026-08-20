"""Shared pytest fixtures: fake homes, workspaces, isolated state dirs."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

STARTER = REPO_ROOT / "examples" / "starter-workspace"


def make_symlink_or_skip(link: Path, target: Path, *, target_is_directory: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as exc:
        if os.name == "nt" and exc.winerror == 1314:
            pytest.skip("Windows account lacks SeCreateSymbolicLinkPrivilege")
        raise


def make_junction(link: Path, target: Path) -> None:
    if os.name != "nt":
        pytest.skip("NTFS junctions are Windows-only")
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert link.is_junction()


@pytest.fixture()
def state_dir(tmp_path, monkeypatch):
    path = tmp_path / "state"
    monkeypatch.setenv("SKILLFERRY_STATE_DIR", str(path))
    return path


@pytest.fixture()
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("DSH_HOME", raising=False)
    monkeypatch.delenv("CLAUDE_HOME", raising=False)
    monkeypatch.delenv("DSH_PROFILE", raising=False)
    return home


def make_workspace(tmp_path: Path, *, name: str = "ws") -> Path:
    destination = tmp_path / name
    shutil.copytree(STARTER, destination)
    return destination


def make_home_kwargs(home: Path) -> dict:
    return {
        "home": str(home),
        "codex_home": str(home / ".codex"),
        "claude_home": str(home / ".claude"),
        "dsh_home": str(home / ".dsh"),
        "dsh_profile": "web",
    }


def plan_workspace(workspace: Path, home: Path, **extra):
    from skillferry.planner import build_plan

    return build_plan(workspace, **make_home_kwargs(home), **extra)


def apply_workspace(workspace: Path, home: Path, **extra):
    from skillferry.io_ops import apply_plan

    return apply_plan(plan_workspace(workspace, home, **extra))
