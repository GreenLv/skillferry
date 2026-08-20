"""export --shareable and the public-tree auditor never leak secrets."""

from __future__ import annotations

import subprocess
import sys

import pytest
from conftest import REPO_ROOT, make_workspace

from skillferry.cli import _export_shareable

FAKE_TOKEN = "ghp_" + "X" * 24


def test_export_preserves_references_and_copies_assets(tmp_path):
    ws = make_workspace(tmp_path)
    destination = tmp_path / "share"
    _export_shareable(ws, destination, [])
    assert (destination / "workspace.toml").is_file()
    assert (destination / "skills" / "release-checklist" / "SKILL.md").is_file()
    assert not (destination / "workspace.local.toml").exists()


def test_export_refuses_secret_content(tmp_path):
    ws = make_workspace(tmp_path)
    (ws / "skills" / "release-checklist" / "SKILL.md").write_text(
        "---\nname: release-checklist\ndescription: x\n---\n"
        "leaked token: " + FAKE_TOKEN + "\n",
        encoding="utf-8",
    )
    destination = tmp_path / "share"
    with pytest.raises(Exception, match="refused"):
        _export_shareable(ws, destination, [])
    assert not destination.exists()


def test_export_refuses_forbidden_literal(tmp_path):
    ws = make_workspace(tmp_path)
    (ws / "instructions" / "global.md").write_text(
        "company-confidential phrase here\n", encoding="utf-8"
    )
    destination = tmp_path / "share"
    with pytest.raises(Exception, match="refused"):
        _export_shareable(ws, destination, ["company-confidential"])
    assert not destination.exists()


def test_export_refuses_sensitive_assignment_after_first_line(tmp_path):
    ws = make_workspace(tmp_path)
    (ws / "instructions" / "global.md").write_text(
        "# heading\npassword = hunter2\n", encoding="utf-8"
    )
    destination = tmp_path / "share"
    with pytest.raises(Exception, match="refused"):
        _export_shareable(ws, destination, [])
    assert not destination.exists()


def test_export_refuses_opaque_binary(tmp_path):
    ws = make_workspace(tmp_path)
    asset = ws / "skills" / "release-checklist" / "assets" / "opaque.bin"
    asset.parent.mkdir()
    asset.write_bytes(b"\xffopaque")
    destination = tmp_path / "share"
    with pytest.raises(Exception, match="refused"):
        _export_shareable(ws, destination, [])
    assert not destination.exists()


def test_export_skips_runtime_state(tmp_path):
    ws = make_workspace(tmp_path)
    (ws / "state").mkdir()
    (ws / "state" / "ledger.json").write_text("{}", encoding="utf-8")
    (ws / "auth.json").write_text("{}", encoding="utf-8")
    destination = tmp_path / "share"
    _export_shareable(ws, destination, [])
    assert not (destination / "state").exists()
    assert not (destination / "auth.json").exists()


def test_audit_public_tree_passes_repo_tree(tmp_path):
    # Copy the repo (excluding .git) and run the auditor on the copy.
    import shutil

    copy = tmp_path / "repo"
    shutil.copytree(
        REPO_ROOT,
        copy,
        ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache"),
    )
    result = subprocess.run(
        [sys.executable, str(copy / "scripts" / "audit_public_tree.py"), str(copy)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_audit_public_tree_fails_on_token(tmp_path):
    import shutil

    copy = tmp_path / "repo"
    shutil.copytree(
        REPO_ROOT,
        copy,
        ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache"),
    )
    (copy / "leak.md").write_text(FAKE_TOKEN, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(copy / "scripts" / "audit_public_tree.py"), str(copy)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "leak.md" in result.stderr


def test_audit_public_tree_fails_on_opaque_binary(tmp_path):
    import shutil

    copy = tmp_path / "repo"
    shutil.copytree(
        REPO_ROOT,
        copy,
        ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache"),
    )
    (copy / "opaque.bin").write_bytes(b"\xff" + FAKE_TOKEN.encode())
    result = subprocess.run(
        [sys.executable, str(copy / "scripts" / "audit_public_tree.py"), str(copy)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "opaque.bin" in result.stderr


def test_audit_public_tree_allows_skill_files(tmp_path):
    import shutil

    copy = tmp_path / "repo"
    shutil.copytree(
        REPO_ROOT,
        copy,
        ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache"),
    )
    assert (copy / "skills" / "release-checklist" / "SKILL.md").is_file()
    result = subprocess.run(
        [sys.executable, str(copy / "scripts" / "audit_public_tree.py"), str(copy)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
