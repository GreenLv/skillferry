"""Import classification: PORTABLE / LOCAL-ONLY / SENSITIVE / UNKNOWN."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skillferry.importers.claude import import_claude
from skillferry.importers.codex import import_codex

FAKE_TOKEN = "ghp_" + "X" * 24


def build_codex_home(root: Path) -> tuple[Path, Path]:
    codex = root / ".codex"
    skills = root / ".agents" / "skills"
    (codex / "sessions").mkdir(parents=True)
    skills.mkdir(parents=True)
    (codex / "config.toml").write_text(
        'model = "gpt-5.2"\n'
        "[mcp_servers.node_repl]\ntype = \"local\"\n"
        "[mcp_servers.github]\ncommand = \"npx\"\nargs = [\"-y\", \"server-github\"]\n"
        "[mcp_servers.github.env]\n"
        "GITHUB_PERSONAL_ACCESS_TOKEN = \"" + FAKE_TOKEN + "\"\n",
        encoding="utf-8",
    )
    (codex / "AGENTS.md").write_text("# portable rules\n", encoding="utf-8")
    (codex / "auth.json").write_text("{}", encoding="utf-8")
    (codex / "sessions" / "rollout.json").write_text("{}", encoding="utf-8")
    (skills / "demo-skill").mkdir()
    (skills / "demo-skill" / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: demo\n---\n# demo\n", encoding="utf-8"
    )
    return codex, skills


def test_import_codex_classifies(tmp_path):
    codex, skills = build_codex_home(tmp_path / "src")
    output = tmp_path / "out"
    report = import_codex(output=output, codex_home=codex, skills_home=skills)
    by_rel = {finding.rel: finding for finding in report.findings}
    assert by_rel["skills/demo-skill"].classification == "PORTABLE"
    assert (
        "SENSITIVE"
        == by_rel[
            "config.toml [mcp_servers.github].env.GITHUB_PERSONAL_ACCESS_TOKEN"
        ].classification
    )
    assert by_rel["config.toml [mcp_servers.node_repl]"].classification == "LOCAL-ONLY"
    assert by_rel["auth.json"].classification == "SENSITIVE"
    assert by_rel["sessions"].classification == "LOCAL-ONLY"
    assert (output / "skills" / "demo-skill" / "SKILL.md").is_file()
    assert not (output / "auth.json").exists()


def test_import_codex_token_becomes_reference(tmp_path):
    codex, skills = build_codex_home(tmp_path / "src")
    output = tmp_path / "out"
    import_codex(output=output, codex_home=codex, skills_home=skills)
    registry = (output / "mcp" / "servers.toml").read_text(encoding="utf-8")
    assert 'secret:env/GITHUB_PERSONAL_ACCESS_TOKEN' in registry
    assert FAKE_TOKEN not in registry


def test_import_codex_skips_skill_with_sensitive_content(tmp_path):
    codex, skills = build_codex_home(tmp_path / "src")
    skill_md = skills / "demo-skill" / "SKILL.md"
    skill_md.write_text(skill_md.read_text() + "\npassword = hunter2\n", encoding="utf-8")
    output = tmp_path / "out"
    report = import_codex(output=output, codex_home=codex, skills_home=skills)
    finding = next(item for item in report.findings if item.rel == "skills/demo-skill")
    assert finding.classification == "SENSITIVE"
    assert finding.action == "skipped"
    assert not (output / "skills" / "demo-skill").exists()


def test_import_codex_nonempty_destination_rejected(tmp_path):
    codex, skills = build_codex_home(tmp_path / "src")
    output = tmp_path / "out"
    output.mkdir()
    (output / "x").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="not empty"):
        import_codex(output=output, codex_home=codex, skills_home=skills)


def test_import_claude_classifies(tmp_path):
    claude = tmp_path / ".claude"
    (claude / "skills" / "demo-skill").mkdir(parents=True)
    (claude / "skills" / "demo-skill" / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: demo\n---\n# demo\n", encoding="utf-8"
    )
    (claude / "CLAUDE.md").write_text("# rules\n", encoding="utf-8")
    (claude / ".claude.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "github": {
                        "command": "npx",
                        "args": ["-y", "server-github"],
                        "env": {"GITHUB_TOKEN": FAKE_TOKEN},
                        "headers": {"Authorization": "Bearer secret"},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (claude / ".credentials.json").write_text("{}", encoding="utf-8")
    (claude / "history.jsonl").write_text("{}", encoding="utf-8")
    output = tmp_path / "out"
    report = import_claude(output=output, claude_home=claude)
    by_rel = {finding.rel: finding for finding in report.findings}
    assert by_rel["skills/demo-skill"].classification == "PORTABLE"
    assert by_rel["instructions/global.md"].classification == "PORTABLE"
    assert "SENSITIVE" == by_rel[".claude.json mcpServers.github.env.GITHUB_TOKEN"].classification
    assert by_rel[".claude.json mcpServers.github.headers"].classification == "SENSITIVE"
    assert by_rel[".credentials.json"].classification == "SENSITIVE"
    assert by_rel["history.jsonl"].classification == "SENSITIVE"
    registry = (output / "mcp" / "servers.toml").read_text(encoding="utf-8")
    assert 'secret:env/GITHUB_TOKEN' in registry
    assert "Bearer secret" not in registry
