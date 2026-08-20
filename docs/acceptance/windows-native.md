# Windows native acceptance evidence

Status: **PASS with documented runtime and ACL limitations.**

Executed on 2026-08-20 in a native Windows user session. This is independent
of GitHub Actions and of the macOS acceptance record. The run started from
`main` at `0235d40`; the accepted fixes and this evidence are in the commit
that contains this document.

## Environment and isolation

- Windows registry product: Windows 10 Home China, DisplayVersion 25H2,
  build 26200.9168, x64 (the NT build is the authoritative version datum).
- PowerShell 7.6.4; CPython 3.12.10; skillferry 0.1.0.
- Node and `npx.cmd` were present. Codex CLI 0.146.0 was discoverable;
  Claude Code and DSH executables were not installed.
- The source was installed into a dedicated venv, first editable with the
  dev extras and then from the locally built wheel.
- Every rehearsal used an explicit fake home named `用户 验收 Home`, explicit
  Codex/Claude/DSH homes below it, and a separate `SKILLFERRY_STATE_DIR`
  named `独立 状态`. No real agent configuration directory was an apply target.
- The final rehearsal was run as the real Windows user, not as the Codex
  sandbox account. Generated config and ledger files were owned by that user.

## Native CLI rehearsal

The following was run from the installed wheel against a copy of
`examples/starter-workspace`, with the Windows MCP override set to
`command = "npx.cmd"`:

| Operation | Native result |
| --- | --- |
| `plan --platform windows` | exit 0; changes for Codex, Claude and DSH |
| `doctor` before apply | exit 2 (safe drift) |
| `apply --yes` | exit 0 |
| `doctor` after apply | exit 0, zero changes/conflicts |
| `export` | exit 0; shareable workspace created without expanding references |
| `import --from codex` then plan the draft | exit 0 after import marker fix |
| forced apply failure | exit 1 with rollback attempted; hashes of earlier Codex/Claude writes restored exactly |
| source file deletion then apply | managed copies deleted from shared and Claude skill roots |
| local edit to a managed MCP command | doctor/apply exit 3; no silent overwrite |
| final doctor | exit 0 |

The `npx.cmd` command was read back from all three native target shapes:
Codex `config.toml`, Claude `.claude.json`, and the DSH
`cordis.patch.yml` insert block.

## Windows-specific results

### CRLF

Codex `AGENTS.md`, Claude `CLAUDE.md`, DSH `AGENTS.md`, and the DSH
`cordis.patch.yml` were seeded with CRLF before apply. Byte-level readback
confirmed CRLF remained and no lone LF was introduced. A regression test now
covers all four files.

### Chinese and space-containing paths

The full plan/apply/doctor/export/import/rollback/deletion/conflict rehearsal
completed under `用户 验收 Home` and `工作区 Source`. Ledger JSON recorded the
resolved Unicode workspace path correctly.

### NTFS junctions and symlinks

Ordinary users can create NTFS junctions even when they lack
`SeCreateSymbolicLinkPrivilege`. Before this run, junctions were not detected
by `Path.is_symlink()`. The implementation now treats Windows reparse points
as link-like and refuses them at workspace, import/export, secret, adapter,
managed-root, target and state-ledger boundaries.

Three real-user NTFS junction tests passed: a workspace skill junction, a
legacy-migration junction, and a managed target-root junction. Two separate
symbolic-link tests skipped because this account received WinError 1314; the
skip is explicit and junction coverage remains fully exercised without
elevation.

### State directory and ACLs

With `SKILLFERRY_STATE_DIR` set, exactly one workspace ledger was created
below `<state-dir>/workspaces`; its workspace id/root matched the rehearsal
workspace. With the override removed for a read-only probe, platformdirs
resolved the default below the fake user's `AppData/Local/skillferry`; the
default directory was not written.

Native `Get-Acl` readback showed:

- the generated Codex config owner was the real Windows user and its ACL was
  inherited from the fake-home parent;
- the ledger owner was the real Windows user, with SYSTEM, Administrators and
  OWNER RIGHTS full-control entries;
- POSIX 0600 equivalence must not be claimed for agent config files. In this
  test workspace the inherited config ACL also granted the Codex sandbox group
  modify access. Windows confidentiality therefore depends on the ACL of the
  selected agent home, exactly as documented in the threat model.

## Repository gates

Final native results after the fixes:

```text
python -m pytest
82 passed, 2 skipped

python -m ruff check .
All checks passed!

python scripts/audit_public_tree.py .
Public-tree audit passed

python scripts/check_seed_skills_parity.py
Seed skill parity check passed.

python scripts/validate_workspace.py examples/starter-workspace
[OK] codex/windows
[OK] claude/windows
[OK] dsh/windows

python -m build
Successfully built skillferry-0.1.0.tar.gz and
skillferry-0.1.0-py3-none-any.whl
```

The wheel was force-reinstalled without dependencies into the isolated venv;
`python -m skillferry --version` returned `0.1.0`.

## Defects found and fixed during acceptance

1. Windows tests read UTF-8 skill files with the locale default (GBK), causing
   two false failures. Tests now specify UTF-8.
2. Symlink tests failed before the assertion when the account lacked Windows
   symlink privilege. They now skip only WinError 1314, while junction tests
   provide non-elevated topology coverage.
3. NTFS junctions bypassed symlink-only trust-boundary checks. A shared
   link-like path check now rejects Windows reparse points and has negative
   tests at source, migration and target boundaries.
4. Rules and DSH MCP reads used universal-newline translation, so CRLF was
   lost before newline detection. Raw newline reads plus native rendering now
   preserve CRLF byte-for-byte.
5. Re-importing an already managed Codex/Claude rules file retained
   SKILLFERRY marker delimiters, causing nested blocks on the next plan.
   Import now removes target ownership delimiters while retaining rule bodies.
6. The first post-push CI run exposed a Python 3.11-only test-helper issue:
   `Path.is_junction()` is unavailable there. Junction creation verification
   now checks the Windows reparse-point file attribute, matching the runtime
   implementation and retaining Python 3.11 support.

## Remaining limitations

- Claude Code and DSH were not installed, so this run validates their native
  on-disk configuration shapes but not process startup or client-side loading.
- The two privileged symbolic-link creation tests were not run elevated;
  they skipped explicitly. Non-elevated NTFS junction refusal passed.
- Windows agent config secrecy remains dependent on parent-directory ACLs;
  skillferry does not replace the operating system's ACL policy or act as a
  secret manager.
