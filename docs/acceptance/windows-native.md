# Windows native acceptance evidence

Status: **NOT YET EXECUTED — pending a Windows-native run.**

Per the repository's acceptance policy, Windows acceptance is an
independent record and may never be inferred from macOS results or from CI
greenness (`windows-latest` CI asserts shapes and behavior, not the native
runtime experience).

## Why this record exists empty

The plan (SKILLFERRY_PLAN §6 step 7) requires Windows-native evidence to be
recorded separately. At the time of the initial macOS acceptance
(2026-08-19) no Windows machine was part of this execution round, so this
file is the standing checklist and must be filled in before any claim of
Windows support beyond "CI-tested".

## Windows-specific acceptance checklist (to execute on a real Windows machine)

1. Install: `pipx install skillferry`; record `skillferry --version`.
2. Rehearse the same five beats as macOS with a fake home (all homes
   overridden), recording transcripts into a new dated section below.
3. Verify these Windows-specific behaviors:
   - Windows newline handling in `~/.claude/CLAUDE.md`, `AGENTS.md`, and the
     DSH `cordis.patch.yml` (CRLF preservation — the renderer preserves the
     file's preferred newline).
   - A username/path containing non-ASCII characters (e.g. a Chinese
     username): full rehearsal against that home must succeed.
   - `npx.cmd`/`.cmd` MCP commands: declared via
     `[servers.<name>.platform.windows]` override; verify the override wins.
   - File permission semantics: record that POSIX mode bits are not
     applicable and that secrets in local config files rely on the user's
     ACL — the documented degradation boundary.
   - `[protect]` + symlink/junction refusal behavior on NTFS junctions.
4. Run `pytest`, `ruff`, `scripts/audit_public_tree.py .` on Windows
   natively and record outputs.
5. Confirm the local state ledger path resolves under
   `SKILLFERRY_STATE_DIR` defaults (platformdirs) without elevation.

## Render-rehearsal (macOS, NOT native evidence)

For reference only: `plan --platform windows` against a fake home renders
Windows-shaped paths and is covered by CI tests
(`test_windows_plan_renders_windows_home`). This does **not** constitute
Windows-native acceptance.
