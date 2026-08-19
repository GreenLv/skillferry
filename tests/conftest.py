"""Shared pytest fixtures: fake homes, workspaces, isolated state dirs."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

STARTER = REPO_ROOT / "examples" / "starter-workspace"


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
