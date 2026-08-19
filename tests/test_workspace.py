"""workspace.toml schema: parsing, overlays, protection, asset validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import make_workspace

from skillferry.workspace import (
    WorkspaceError,
    load_extensions,
    load_mcp_registry,
    load_skills,
    load_workspace,
    validate_workspace,
)


def load(ws: Path, target: str = "codex", platform: str = "macos", **extra):
    return load_workspace(ws, target=target, platform=platform, **extra)


def test_valid_starter_workspace(tmp_path):
    ws = make_workspace(tmp_path)
    lines = validate_workspace(ws)
    assert len(lines) == 3
    for line in lines:
        assert "2 skill(s)" in line and "1 MCP server(s)" in line


def test_schema_version_must_be_one(tmp_path):
    ws = make_workspace(tmp_path)
    (ws / "workspace.toml").write_text("schema_version = 2\n", encoding="utf-8")
    with pytest.raises(WorkspaceError, match="schema_version"):
        load(ws)


def test_literal_secret_in_registry_rejected(tmp_path):
    ws = make_workspace(tmp_path)
    registry = ws / "mcp" / "servers.toml"
    registry.write_text(
        '[servers.bad]\ncommand = "x"\n[servers.bad.env]\nTOKEN = "'
        + ("ghp_" + "X" * 24)
        + '"\n',
        encoding="utf-8",
    )
    with pytest.raises(WorkspaceError, match="secret:env"):
        load_mcp_registry(load(ws))


def test_secret_file_reference_accepted(tmp_path):
    ws = make_workspace(tmp_path)
    (ws / "secrets").mkdir()
    (ws / "secrets" / "token.txt").write_text("x", encoding="utf-8")
    registry = ws / "mcp" / "servers.toml"
    registry.write_text(
        '[servers.ok]\ncommand = "x"\n[servers.ok.env]\nTOKEN = "secret:file/secrets/token.txt"\n',
        encoding="utf-8",
    )
    spec = load_mcp_registry(load(ws))["ok"]
    assert spec.env["TOKEN"] == "secret:file/secrets/token.txt"


def test_path_traversal_rejected(tmp_path):
    ws = make_workspace(tmp_path)
    (ws / "workspace.toml").write_text(
        'schema_version = 1\n[skills]\ndirectory = "../escape"\n', encoding="utf-8"
    )
    with pytest.raises(WorkspaceError, match="inside the workspace"):
        load(ws)


def _rewrite_protect(ws: Path, paths: list[str]) -> None:
    import json

    base = (ws / "workspace.toml").read_text(encoding="utf-8")
    head = base.split("[protect]")[0]
    (ws / "workspace.toml").write_text(
        head + "[protect]\npaths = " + json.dumps(paths) + "\n", encoding="utf-8"
    )


def test_protect_misdeclaration_rejected(tmp_path):
    ws = make_workspace(tmp_path)
    _rewrite_protect(ws, ["skills"])
    with pytest.raises(WorkspaceError, match=r"\[protect\] mis-declaration"):
        validate_workspace(ws)


def test_protect_absolute_path_rejected(tmp_path):
    ws = make_workspace(tmp_path)
    _rewrite_protect(ws, ["/etc/passwd"])
    with pytest.raises(WorkspaceError, match="relative"):
        load(ws)


def test_overlay_merge_and_provenance(tmp_path):
    ws = make_workspace(tmp_path)
    (ws / "overlays" / "target" / "codex.toml").write_text(
        '[skills]\ndefault_targets = ["codex"]\n', encoding="utf-8"
    )
    (ws / "overlays" / "platform" / "macos.toml").write_text(
        '[skills]\ndefault_targets = ["codex", "dsh"]\n', encoding="utf-8"
    )
    loaded = load(ws, target="codex", platform="macos")
    # platform overlay wins over target overlay; lists replace wholesale.
    assert loaded.skills.default_targets == ("codex", "dsh")
    assert "overlays/platform/macos.toml" in loaded.provenance["skills.default_targets"]


def test_unknown_overlay_key_rejected(tmp_path):
    ws = make_workspace(tmp_path)
    (ws / "overlays" / "target" / "codex.toml").write_text(
        "bogus = 1\n", encoding="utf-8"
    )
    with pytest.raises(WorkspaceError, match="unsupported keys"):
        load(ws)


def test_local_override_applied_last(tmp_path):
    ws = make_workspace(tmp_path)
    (ws / "overlays" / "platform" / "macos.toml").write_text(
        '[skills]\ndefault_targets = ["codex"]\n', encoding="utf-8"
    )
    (ws / "workspace.local.toml").write_text(
        '[skills]\ndefault_targets = ["dsh"]\n', encoding="utf-8"
    )
    assert load(ws).skills.default_targets == ("dsh",)
    assert load(ws, allow_local=False).skills.default_targets == ("codex",)


def test_skill_frontmatter_and_targets(tmp_path):
    ws = make_workspace(tmp_path)
    skills = load_skills(load(ws))
    assert set(skills) == {"setup-skillferry", "release-checklist"}
    assert skills["release-checklist"].targets == ("codex", "claude", "dsh")
    assert skills["release-checklist"].version == "0.1.0"


def test_skill_name_mismatch_rejected(tmp_path):
    ws = make_workspace(tmp_path)
    path = ws / "skills" / "setup-skillferry" / "SKILL.md"
    path.write_text(
        "---\nname: other-name\ndescription: x\n---\n", encoding="utf-8"
    )
    with pytest.raises(WorkspaceError, match="does not match folder"):
        load_skills(load(ws))


def test_skill_symlink_rejected(tmp_path):
    ws = make_workspace(tmp_path)
    target = ws / "skills" / "setup-skillferry"
    (ws / "skills" / "linked").symlink_to(target)
    with pytest.raises(WorkspaceError, match="symlink"):
        load_skills(load(ws))


def test_mcp_targets_restriction(tmp_path):
    ws = make_workspace(tmp_path)
    registry = ws / "mcp" / "servers.toml"
    registry.write_text(
        '[servers.time]\ncommand = "npx"\nargs = ["-y", "@modelcontextprotocol/server-time"]\n'
        'targets = ["codex"]\n',
        encoding="utf-8",
    )
    spec = load_mcp_registry(load(ws, target="codex"))["time"]
    assert spec.targets == ("codex",)


def test_mcp_platform_override(tmp_path):
    ws = make_workspace(tmp_path)
    registry = ws / "mcp" / "servers.toml"
    registry.write_text(
        '[servers.time]\ncommand = "npx"\nargs = ["-y", "server-time"]\n'
        "[servers.time.platform.windows]\ncommand = \"npx.cmd\"\n",
        encoding="utf-8",
    )
    macos_spec = load_mcp_registry(load(ws, platform="macos"))["time"]
    windows_spec = load_mcp_registry(load(ws, platform="windows"))["time"]
    assert macos_spec.command == "npx"
    assert windows_spec.command == "npx.cmd"


def test_extension_manifest_validation(tmp_path):
    ws = make_workspace(tmp_path)
    manifest = ws / "extensions" / "manifest.toml"
    manifest.write_text(
        '[extensions.demo]\nversion = "1.2.3"\n[extensions.demo.source]\n'
        'kind = "manual"\ninstructions = "do it by hand"\n',
        encoding="utf-8",
    )
    extensions = load_extensions(load(ws))
    assert extensions["demo"].version == "1.2.3"
    assert extensions["demo"].instructions == "do it by hand"


def test_extension_missing_version_rejected(tmp_path):
    ws = make_workspace(tmp_path)
    manifest = ws / "extensions" / "manifest.toml"
    manifest.write_text(
        '[extensions.demo]\n[extensions.demo.source]\nkind = "manual"\ninstructions = "x"\n',
        encoding="utf-8",
    )
    with pytest.raises(WorkspaceError, match="version"):
        load_extensions(load(ws))


def test_mcp_overlay_partial_merge(tmp_path):
    ws = make_workspace(tmp_path)
    (ws / "overlays" / "target" / "codex.toml").write_text(
        '[mcp.servers.time]\ncommand = "npx"\nargs = ["-y", "server-time", "--extra"]\n',
        encoding="utf-8",
    )
    spec = load_mcp_registry(load(ws, target="codex"))["time"]
    assert spec.args == ("-y", "server-time", "--extra")
