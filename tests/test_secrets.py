"""Secret reference parsing, resolution, scanning, and redaction."""

from __future__ import annotations

import pytest

from skillferry.secrets import (
    is_secret_ref,
    looks_like_secret,
    redact_text,
    resolve_secret,
    scan_text,
    validate_secret_ref,
)
from skillferry.workspace import WorkspaceError

FAKE_TOKEN = "ghp_" + "X" * 24
SK_TOKEN = "sk-" + "y" * 28


def test_parse_env_ref():
    assert is_secret_ref("secret:env/GITHUB_TOKEN")
    assert is_secret_ref("secret:file/secrets/token.txt")
    assert not is_secret_ref(FAKE_TOKEN)
    assert not is_secret_ref("secret:env/")


def test_validate_env_ref_name(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    with pytest.raises(WorkspaceError, match="variable name"):
        validate_secret_ref("secret:env/1BAD", workspace_root=ws, label="x")


def test_validate_file_ref_traversal(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    with pytest.raises(WorkspaceError, match="traverse"):
        validate_secret_ref("secret:file/../etc/passwd", workspace_root=ws, label="x")


def test_resolve_env_expand_and_keep(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("MY_TOKEN", "value-123")
    assert (
        resolve_secret("secret:env/MY_TOKEN", workspace_root=ws, expand=False, label="x")
        == "secret:env/MY_TOKEN"
    )
    assert (
        resolve_secret("secret:env/MY_TOKEN", workspace_root=ws, expand=True, label="x")
        == "value-123"
    )
    monkeypatch.delenv("MY_TOKEN")
    with pytest.raises(WorkspaceError, match="not set"):
        resolve_secret("secret:env/MY_TOKEN", workspace_root=ws, expand=True, label="x")


def test_resolve_file_ref(tmp_path):
    ws = tmp_path / "ws"
    (ws / "secrets").mkdir(parents=True)
    (ws / "secrets" / "token.txt").write_text("  file-value-123  \n", encoding="utf-8")
    value = resolve_secret(
        "secret:file/secrets/token.txt", workspace_root=ws, expand=True, label="x"
    )
    assert value == "file-value-123"


def test_looks_like_secret():
    assert looks_like_secret(FAKE_TOKEN)
    assert looks_like_secret(SK_TOKEN)
    assert not looks_like_secret("secret:env/GITHUB_TOKEN")
    assert not looks_like_secret("npx")


def test_scan_text_finds_credentials():
    findings = scan_text('TOKEN = "' + FAKE_TOKEN + '"\nok = 1\n', label="f")
    assert any("TOKEN" in f or "GitHub" in f for f in findings)


def test_redact_text_masks_toml_json_yaml_keys():
    text = (
        'TOKEN = "a"\n'
        '"GITHUB_TOKEN": "b"\n'
        "  password: c\n"
        "plain = 1\n"
    )
    redacted = redact_text(text)
    assert "TOKEN = <redacted>" in redacted
    assert '"GITHUB_TOKEN": <redacted>' in redacted
    assert "password: <redacted>" in redacted
    assert "plain = 1" in redacted
