"""CLI surface and exit-code semantics (0 sync / 1 error / 2 drift / 3 conflict)."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

from conftest import make_workspace

from skillferry.cli import main


def run(workspace: Path, home: Path, command: str, *extra: str) -> tuple[int, str]:
    argv = [
        command,
        "--workspace",
        str(workspace),
        "--home",
        str(home),
        "--dsh-home",
        str(home / ".dsh"),
        "--dsh-profile",
        "web",
        *extra,
    ]
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        code = main(argv)
    return code, buffer.getvalue()


def test_version_flag():
    import contextlib
    import io

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        try:
            main(["--version"])
        except SystemExit:
            pass
    assert "0.1.0" in buffer.getvalue()


def test_doctor_exit_codes(tmp_path, state_dir, fake_home, monkeypatch):
    ws = make_workspace(tmp_path)
    code, _ = run(ws, fake_home, "doctor")
    assert code == 2  # safe drift: changes pending
    code, _ = run(ws, fake_home, "apply", "--yes")
    assert code == 0
    code, output = run(ws, fake_home, "doctor")
    assert code == 0, output
    # local tamper -> conflict
    skill = fake_home / ".agents" / "skills" / "setup-skillferry" / "SKILL.md"
    skill.write_text(skill.read_text() + "\n# tampered\n", encoding="utf-8")
    code, _ = run(ws, fake_home, "doctor")
    assert code == 3
    # restore via overwrite
    code, _ = run(
        ws, fake_home, "apply", "--yes",
        "--resolve", "skill:codex:setup-skillferry:SKILL.md=overwrite",
        "--resolve", "skill:dsh:setup-skillferry:SKILL.md=overwrite",
    )
    assert code == 0
    code, _ = run(ws, fake_home, "doctor")
    assert code == 0


def test_plan_json_is_single_document_and_secret_free(tmp_path, state_dir, fake_home, monkeypatch):
    monkeypatch.setenv("DEMO_TOKEN", "ghp_" + "X" * 24)
    ws = make_workspace(tmp_path)
    (ws / "mcp" / "servers.toml").write_text(
        '[servers.time]\ncommand = "npx"\nargs = ["-y", "server-time"]\n'
        "[servers.time.env]\nTOKEN = \"secret:env/DEMO_TOKEN\"\n",
        encoding="utf-8",
    )
    code, output = run(ws, fake_home, "plan", "--json")
    assert code == 0
    payload = json.loads(output)
    assert payload["schema_version"] == 1
    assert "X" * 24 not in output


def test_apply_interactive_abort(tmp_path, state_dir, fake_home, monkeypatch):
    def refuse(_prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", refuse)
    ws = make_workspace(tmp_path)
    code, _ = run(ws, fake_home, "apply")  # EOF on stdin -> error exit
    assert code == 1
    assert not (fake_home / ".codex" / "config.toml").exists()


def test_init_creates_skeleton(tmp_path):
    destination = tmp_path / "init-ws"
    code = main(["init", str(destination)])
    assert code == 0
    assert (destination / "workspace.toml").is_file()
    assert (destination / "skills").is_dir()
    assert (destination / "overlays" / "platform" / "windows.toml").is_file()


def test_status_reports_ledger(tmp_path, state_dir, fake_home):
    ws = make_workspace(tmp_path)
    run(ws, fake_home, "apply", "--yes")
    code, output = run(ws, fake_home, "status")
    assert code == 0
    assert "codex" in output


def test_export_command(tmp_path, state_dir):
    ws = make_workspace(tmp_path)
    destination = tmp_path / "share"
    code = main(["export", "--workspace", str(ws), str(destination)])
    assert code == 0
    assert (destination / "workspace.toml").is_file()


def test_import_command_json(tmp_path, monkeypatch):
    codex = tmp_path / ".codex"
    skills = tmp_path / ".agents" / "skills"
    (codex / "sessions").mkdir(parents=True)
    skills.mkdir(parents=True)
    (codex / "config.toml").write_text("model = \"x\"\n", encoding="utf-8")
    output = tmp_path / "out"
    code = main(
        [
            "import",
            "--from",
            "codex",
            "--codex-home",
            str(codex),
            "--skills-home",
            str(skills),
            "--output",
            str(output),
            "--json",
        ]
    )
    assert code == 0
    assert (output / "workspace.toml").is_file()


def test_unknown_target_rejected(tmp_path, state_dir, fake_home):
    import pytest

    ws = make_workspace(tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        run(ws, fake_home, "plan", "--target", "gemini")
    assert excinfo.value.code == 2


def test_migrate_command(tmp_path):
    bundle = tmp_path / "bundle"
    (bundle / "config").mkdir(parents=True)
    (bundle / "sync.toml").write_text(
        "schema_version = 1\nprofile_id = \"p\"\n[config]\ncommon = \"config/common.toml\"\n",
        encoding="utf-8",
    )
    (bundle / "config" / "common.toml").write_text("", encoding="utf-8")
    output = tmp_path / "out"
    code = main(
        ["migrate", "--from", "codex-profile-sync", str(bundle), "--output", str(output)]
    )
    assert code == 0
    assert (output / "workspace.toml").is_file()
