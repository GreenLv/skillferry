"""Legacy codex-profile-sync bundle migration."""

from __future__ import annotations

from pathlib import Path

import pytest

from skillferry.migrate import migrate_codex_profile_sync

FAKE_TOKEN = "ghp_" + "X" * 24


def build_bundle(root: Path) -> Path:
    bundle = root / "bundle"
    (bundle / "config").mkdir(parents=True)
    (bundle / "skills" / "demo-skill").mkdir(parents=True)
    (bundle / "skills" / "demo-skill" / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: demo\n---\n# demo\n", encoding="utf-8"
    )
    (bundle / "sync.toml").write_text(
        "schema_version = 1\n"
        'profile_id = "portable-codex"\n'
        "[config]\ncommon = \"config/common.toml\"\n"
        "[skills]\ndirectory = \"skills\"\nenabled = true\n"
        "[named_profiles]\ndirectory = \"profiles\"\n",
        encoding="utf-8",
    )
    (bundle / "config" / "common.toml").write_text(
        "[mcp_servers.github]\ncommand = \"npx\"\nargs = [\"-y\", \"server-github\"]\n"
        "[mcp_servers.github.env]\n"
        "GITHUB_PERSONAL_ACCESS_TOKEN = \"" + FAKE_TOKEN + "\"\n",
        encoding="utf-8",
    )
    return bundle


def test_migrate_creates_draft_workspace(tmp_path):
    bundle = build_bundle(tmp_path)
    output = tmp_path / "out"
    report = migrate_codex_profile_sync(bundle, output)
    assert (output / "workspace.toml").is_file()
    assert (output / "skills" / "demo-skill" / "SKILL.md").is_file()
    registry = (output / "mcp" / "servers.toml").read_text(encoding="utf-8")
    assert "secret:env/GITHUB_PERSONAL_ACCESS_TOKEN" in registry
    assert FAKE_TOKEN not in registry
    kinds = {note.kind for note in report.notes}
    assert "converted" in kinds
    assert "manual" in kinds  # named profiles note


def test_migrate_never_touches_bundle(tmp_path):
    bundle = build_bundle(tmp_path)
    before = {
        path.relative_to(bundle).as_posix(): path.read_bytes()
        for path in bundle.rglob("*")
        if path.is_file()
    }
    migrate_codex_profile_sync(bundle, tmp_path / "out")
    after = {
        path.relative_to(bundle).as_posix(): path.read_bytes()
        for path in bundle.rglob("*")
        if path.is_file()
    }
    assert before == after


def test_migrate_rejects_symlink_inside_skills(tmp_path):
    bundle = build_bundle(tmp_path)
    outside = tmp_path / "private.txt"
    outside.write_text("private", encoding="utf-8")
    (bundle / "skills" / "demo-skill" / "linked.txt").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        migrate_codex_profile_sync(bundle, tmp_path / "out")


def test_migrate_requires_sync_toml(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    import pytest

    with pytest.raises(ValueError, match="sync.toml"):
        migrate_codex_profile_sync(empty, tmp_path / "out")
