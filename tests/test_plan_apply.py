"""End-to-end plan/apply/doctor behavior across the three targets in a fake home."""

from __future__ import annotations

import json

import pytest
from conftest import apply_workspace, make_junction, make_workspace, plan_workspace

from skillferry.io_ops import ApplyError, apply_plan
from skillferry.models import SyncPlan, TargetApply, TextWrite


def test_apply_creates_all_three_target_shapes(tmp_path, state_dir, fake_home):
    ws = make_workspace(tmp_path)
    plan = plan_workspace(ws, fake_home)
    assert not plan.conflicts
    backup = apply_workspace(ws, fake_home)
    assert backup.is_dir()

    # Codex: config.toml section + AGENTS.md marker block + shared skill root
    config = (fake_home / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert '[mcp_servers.time]' in config and 'command = "npx"' in config
    agents = (fake_home / ".codex" / "AGENTS.md").read_text(encoding="utf-8")
    assert "<!-- BEGIN SKILLFERRY RULES global -->" in agents
    assert (fake_home / ".agents" / "skills" / "release-checklist" / "SKILL.md").is_file()

    # Claude: user-level .claude.json + CLAUDE.md + own skill dir
    claude_json = json.loads((fake_home / ".claude" / ".claude.json").read_text())
    assert claude_json["mcpServers"]["time"]["command"] == "npx"
    assert "SKILLFERRY RULES" in (fake_home / ".claude" / "CLAUDE.md").read_text()
    assert (fake_home / ".claude" / "skills" / "setup-skillferry" / "SKILL.md").is_file()

    # DSH: cordis.patch.yml insert block + AGENTS.md + shared skill root
    patch = (fake_home / ".dsh" / "profiles" / "web" / "cordis.patch.yml").read_text()
    assert "# >>> BEGIN SKILLFERRY DSH MCP >>>" in patch
    assert "id: mcp-time" in patch
    assert "serverName: time" in patch
    dsh_agents = (fake_home / ".dsh" / "AGENTS.md").read_text()
    assert "SKILLFERRY RULES" in dsh_agents


def test_apply_then_doctor_is_clean(tmp_path, state_dir, fake_home):
    ws = make_workspace(tmp_path)
    apply_workspace(ws, fake_home)
    plan = plan_workspace(ws, fake_home)
    assert plan.changes == []
    assert plan.conflicts == []


def test_second_apply_is_idempotent(tmp_path, state_dir, fake_home):
    ws = make_workspace(tmp_path)
    apply_workspace(ws, fake_home)
    before = (fake_home / ".codex" / "config.toml").read_bytes()
    apply_workspace(ws, fake_home)
    after = (fake_home / ".codex" / "config.toml").read_bytes()
    assert before == after


def test_source_change_is_update_not_conflict(tmp_path, state_dir, fake_home):
    ws = make_workspace(tmp_path)
    apply_workspace(ws, fake_home)
    registry = (ws / "mcp" / "servers.toml").read_text(encoding="utf-8")
    (ws / "mcp" / "servers.toml").write_text(
        registry.replace('"@modelcontextprotocol/server-time"',
                         '"@modelcontextprotocol/server-time", "--debug"'),
        encoding="utf-8",
    )
    plan = plan_workspace(ws, fake_home)
    assert not plan.conflicts
    assert any(c.action == "update" and c.kind == "mcp" for c in plan.changes)


def test_local_edit_is_conflict(tmp_path, state_dir, fake_home):
    ws = make_workspace(tmp_path)
    apply_workspace(ws, fake_home)
    config = fake_home / ".codex" / "config.toml"
    config.write_text(
        config.read_text().replace('command = "npx"', 'command = "hand-edited"'),
        encoding="utf-8",
    )
    plan = plan_workspace(ws, fake_home)
    assert any(c.kind == "mcp" and c.target == "codex" for c in plan.conflicts)


def test_unregistered_file_conflict_and_overwrite(tmp_path, state_dir, fake_home):
    ws = make_workspace(tmp_path)
    skill = fake_home / ".agents" / "skills" / "setup-skillferry" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: setup-skillferry\ndescription: local\n---\n", encoding="utf-8")
    plan = plan_workspace(ws, fake_home)
    conflicts = [c for c in plan.conflicts if c.kind == "skill"]
    assert conflicts
    resolutions = {
        "skill:codex:setup-skillferry:SKILL.md": "overwrite",
        "skill:dsh:setup-skillferry:SKILL.md": "overwrite",
    }
    plan = plan_workspace(ws, fake_home, resolutions=resolutions)
    assert not [c for c in plan.conflicts if "setup-skillferry" in c.name]
    apply_workspace(ws, fake_home, resolutions=resolutions)
    text = skill.read_text(encoding="utf-8")
    assert "Install, verify, and re-apply" in text


def test_adopt_keeps_local_content(tmp_path, state_dir, fake_home):
    ws = make_workspace(tmp_path)
    skill = fake_home / ".agents" / "skills" / "setup-skillferry" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    local = "---\nname: setup-skillferry\ndescription: my local version\n---\n# mine\n"
    skill.write_text(local, encoding="utf-8")
    apply_workspace(
        ws, fake_home,
        resolutions={
            "skill:codex:setup-skillferry:SKILL.md": "adopt",
            "skill:dsh:setup-skillferry:SKILL.md": "adopt",
        },
    )
    assert skill.read_text(encoding="utf-8") == local
    plan = plan_workspace(ws, fake_home)
    # adopted content is now the registered baseline; further source changes
    # will still show as changes, not conflicts.
    assert not plan.conflicts


def test_source_deletion_removes_managed_file(tmp_path, state_dir, fake_home):
    ws = make_workspace(tmp_path)
    apply_workspace(ws, fake_home)
    target = (
        fake_home / ".agents" / "skills" / "release-checklist"
        / "references" / "release-gates.md"
    )
    assert target.is_file()
    (ws / "skills" / "release-checklist" / "references" / "release-gates.md").unlink()
    plan = plan_workspace(ws, fake_home)
    assert any(
        c.action == "delete" and "release-gates.md" in c.path for c in plan.changes
    )
    apply_workspace(ws, fake_home)
    assert not target.exists()


def test_source_skill_removal_uninstalls_whole_managed_skill(
    tmp_path, state_dir, fake_home
):
    import shutil

    ws = make_workspace(tmp_path)
    apply_workspace(ws, fake_home)
    shutil.rmtree(ws / "skills" / "release-checklist")
    plan = plan_workspace(ws, fake_home)
    assert any(
        change.kind == "skill"
        and change.name == "release-checklist"
        and change.action == "delete"
        for change in plan.changes
    )
    apply_plan(plan)
    assert not (fake_home / ".agents" / "skills" / "release-checklist" / "SKILL.md").exists()
    assert not (fake_home / ".claude" / "skills" / "release-checklist" / "SKILL.md").exists()


def test_source_mcp_removal_deletes_all_owned_target_entries(
    tmp_path, state_dir, fake_home
):
    ws = make_workspace(tmp_path)
    apply_workspace(ws, fake_home)
    (ws / "mcp" / "servers.toml").write_text("[servers]\n", encoding="utf-8")
    plan = plan_workspace(ws, fake_home)
    assert not plan.conflicts
    assert {change.target for change in plan.changes if change.kind == "mcp"} == {
        "codex",
        "claude",
        "dsh",
    }
    apply_plan(plan)
    assert "mcp_servers.time" not in (
        fake_home / ".codex" / "config.toml"
    ).read_text(encoding="utf-8")
    claude = json.loads((fake_home / ".claude" / ".claude.json").read_text())
    assert "time" not in claude["mcpServers"]
    dsh = (fake_home / ".dsh" / "profiles" / "web" / "cordis.patch.yml").read_text()
    assert "mcp-time" not in dsh


def test_source_mcp_removal_conflicts_with_local_modification(
    tmp_path, state_dir, fake_home
):
    ws = make_workspace(tmp_path)
    apply_workspace(ws, fake_home)
    config = fake_home / ".codex" / "config.toml"
    config.write_text(
        config.read_text().replace('command = "npx"', 'command = "local-edit"'),
        encoding="utf-8",
    )
    (ws / "mcp" / "servers.toml").write_text("[servers]\n", encoding="utf-8")
    plan = plan_workspace(ws, fake_home, targets=("codex",))
    assert any(
        conflict.kind == "mcp" and "source removal" in conflict.reason
        for conflict in plan.conflicts
    )


def test_missing_secret_env_is_conflict(tmp_path, state_dir, fake_home, monkeypatch):
    monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
    ws = make_workspace(tmp_path)
    (ws / "mcp" / "servers.toml").write_text(
        '[servers.time]\ncommand = "npx"\nargs = ["-y", "server-time"]\n'
        "[servers.time.env]\nTOKEN = \"secret:env/GITHUB_PERSONAL_ACCESS_TOKEN\"\n",
        encoding="utf-8",
    )
    plan = plan_workspace(ws, fake_home)
    assert any("is not set" in c.reason for c in plan.conflicts)


def test_env_secret_lands_only_in_local_config(tmp_path, state_dir, fake_home, monkeypatch):
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ghp_" + "X" * 24)
    ws = make_workspace(tmp_path)
    (ws / "mcp" / "servers.toml").write_text(
        '[servers.time]\ncommand = "npx"\nargs = ["-y", "server-time"]\n'
        "[servers.time.env]\nTOKEN = \"secret:env/GITHUB_PERSONAL_ACCESS_TOKEN\"\n",
        encoding="utf-8",
    )
    plan = plan_workspace(ws, fake_home)
    assert not plan.conflicts
    payload = plan.public_dict()
    assert "X" * 24 not in json.dumps(payload)
    apply_workspace(ws, fake_home)
    config = (fake_home / ".codex" / "config.toml").read_text()
    assert "ghp_" + "X" * 24 in config  # local runtime file only
    # the workspace source keeps the reference
    assert "X" * 24 not in (ws / "mcp" / "servers.toml").read_text()


def test_protected_mcp_server_never_managed(tmp_path, state_dir, fake_home):
    ws = make_workspace(tmp_path)
    (ws / "mcp" / "servers.toml").write_text(
        '[servers.node_repl]\ncommand = "node"\nargs = ["repl"]\n', encoding="utf-8"
    )
    plan = plan_workspace(ws, fake_home)
    assert any("protected" in c.reason for c in plan.conflicts)
    assert not any(c.kind == "mcp" and c.action != "none" for c in plan.changes)


def test_dsh_handwritten_collision_conflicts(tmp_path, state_dir, fake_home):
    ws = make_workspace(tmp_path)
    patch_dir = fake_home / ".dsh" / "profiles" / "web"
    patch_dir.mkdir(parents=True)
    (patch_dir / "cordis.patch.yml").write_text(
        "- insert:\n    - id: mcp-time\n      name: handwritten\n", encoding="utf-8"
    )
    plan = plan_workspace(ws, fake_home)
    assert any(
        "handwritten" in c.reason and c.target == "dsh" for c in plan.conflicts
    )


def test_rules_unmanaged_content_preserved(tmp_path, state_dir, fake_home):
    ws = make_workspace(tmp_path)
    agents = fake_home / ".codex" / "AGENTS.md"
    agents.parent.mkdir(parents=True)
    agents.write_text("# My personal rules\n- keep this line\n", encoding="utf-8")
    apply_workspace(ws, fake_home)
    text = agents.read_text(encoding="utf-8")
    assert text.startswith("# My personal rules\n- keep this line\n")
    assert "SKILLFERRY RULES" in text


def test_rules_marker_blocks_roundtrip_update(tmp_path, state_dir, fake_home):
    ws = make_workspace(tmp_path)
    apply_workspace(ws, fake_home)
    instructions = ws / "instructions" / "global.md"
    instructions.write_text(instructions.read_text() + "\n- new rule\n", encoding="utf-8")
    plan = plan_workspace(ws, fake_home)
    assert any(c.kind == "rules" and c.action == "update" for c in plan.changes)
    assert not plan.conflicts
    apply_workspace(ws, fake_home)
    assert "- new rule" in (fake_home / ".codex" / "AGENTS.md").read_text()


def test_rollback_restores_targets_on_failure(tmp_path, state_dir, fake_home):
    ws = make_workspace(tmp_path)
    apply_workspace(ws, fake_home)
    before_config = (fake_home / ".codex" / "config.toml").read_bytes()
    before_agents = (fake_home / ".codex" / "AGENTS.md").read_bytes()
    # Make the dsh patch target path unwritable-ish by replacing the profiles
    # dir with a regular file so the dsh write fails after codex/claude wrote.
    profiles = fake_home / ".dsh" / "profiles"
    import shutil

    shutil.rmtree(profiles)
    profiles.write_text("not a dir", encoding="utf-8")
    (ws / "mcp" / "servers.toml").write_text(
        '[servers.time]\ncommand = "npx"\nargs = ["-y", "server-time", "--changed"]\n',
        encoding="utf-8",
    )
    with pytest.raises(Exception, match="rollback"):
        apply_workspace(ws, fake_home)
    assert (fake_home / ".codex" / "config.toml").read_bytes() == before_config
    assert (fake_home / ".codex" / "AGENTS.md").read_bytes() == before_agents


def test_rollback_restores_partial_writes_in_failing_target(tmp_path, state_dir):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    managed = tmp_path / "managed"
    managed.mkdir()
    first = managed / "first.txt"
    first.write_text("old", encoding="utf-8")
    blocker = managed / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    target_apply = TargetApply(
        target="codex",
        roots=[managed],
        writes=[
            TextWrite(first, "new", 0o600, "first"),
            TextWrite(blocker / "second.txt", "new", 0o600, "second"),
        ],
    )
    plan = SyncPlan(
        workspace_root=workspace,
        platform="macos",
        targets=("codex",),
        homes={"codex": managed},
        applies={"codex": target_apply},
    )
    with pytest.raises(ApplyError, match="rollback"):
        apply_plan(plan)
    assert first.read_text(encoding="utf-8") == "old"


def test_backups_redact_secrets(tmp_path, state_dir, fake_home, monkeypatch):
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ghp_" + "X" * 24)
    ws = make_workspace(tmp_path)
    (ws / "mcp" / "servers.toml").write_text(
        '[servers.time]\ncommand = "npx"\nargs = ["-y", "server-time"]\n'
        "[servers.time.env]\nTOKEN = \"secret:env/GITHUB_PERSONAL_ACCESS_TOKEN\"\n",
        encoding="utf-8",
    )
    apply_workspace(ws, fake_home)
    # update apply to force backups of existing config.toml
    (ws / "mcp" / "servers.toml").write_text(
        '[servers.time]\ncommand = "npx"\nargs = ["-y", "server-time", "--v2"]\n'
        "[servers.time.env]\nTOKEN = \"secret:env/GITHUB_PERSONAL_ACCESS_TOKEN\"\n",
        encoding="utf-8",
    )
    apply_workspace(ws, fake_home)
    backups = list(state_dir.rglob("config.toml"))
    assert backups, "config.toml backup expected"
    raw = backups[-1]
    assert "ghp_" + "X" * 24 in raw.read_text()
    redacted = raw.with_name(raw.name + ".redacted")
    assert redacted.is_file()
    assert "X" * 24 not in redacted.read_text()
    assert "<redacted>" in redacted.read_text()
    assert "--v2" not in redacted.read_text()


def test_windows_plan_renders_windows_home(tmp_path, state_dir, fake_home):
    ws = make_workspace(tmp_path)
    plan = plan_workspace(ws, fake_home, requested_platform="windows")
    assert plan.platform == "windows"
    assert all(
        str(fake_home) in change.path for change in plan.changes
    )


def test_windows_junction_managed_root_rejected(tmp_path, state_dir, fake_home):
    ws = make_workspace(tmp_path)
    outside = tmp_path / "outside-skills"
    outside.mkdir()
    agents = fake_home / ".agents"
    agents.mkdir()
    make_junction(agents / "skills", outside)
    with pytest.raises(ValueError, match="junction"):
        plan_workspace(ws, fake_home, requested_platform="windows", targets=("codex",))
    assert list(outside.iterdir()) == []


def test_windows_crlf_rules_and_dsh_patch_preserved(tmp_path, state_dir, fake_home):
    ws = make_workspace(tmp_path)
    paths = (
        fake_home / ".codex" / "AGENTS.md",
        fake_home / ".claude" / "CLAUDE.md",
        fake_home / ".dsh" / "AGENTS.md",
        fake_home / ".dsh" / "profiles" / "web" / "cordis.patch.yml",
    )
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"# existing\r\n")

    apply_workspace(ws, fake_home, requested_platform="windows")

    for path in paths:
        rendered = path.read_bytes()
        assert b"\r\n" in rendered
        assert b"\n" not in rendered.replace(b"\r\n", b"")


def test_claude_json_other_keys_preserved(tmp_path, state_dir, fake_home):
    ws = make_workspace(tmp_path)
    claude_home = fake_home / ".claude"
    claude_home.mkdir(parents=True)
    (claude_home / ".claude.json").write_text(
        json.dumps({"hasCompletedOnboarding": True, "mcpServers": {}}) + "\n",
        encoding="utf-8",
    )
    apply_workspace(ws, fake_home)
    document = json.loads((claude_home / ".claude.json").read_text())
    assert document["hasCompletedOnboarding"] is True
    assert document["mcpServers"]["time"]["command"] == "npx"
