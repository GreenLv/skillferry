# Threat model

skillferry moves **capability definitions**, never secrets and never machine
state. This document lists the assets, the trust boundaries, the threats the
design refuses, and what is explicitly out of scope.

## Assets and trust boundaries

| Layer | Content | Stored where | Sensitivity |
| --- | --- | --- | --- |
| Public engine (this repo) | code, docs, seed skills, starter example | Git / PyPI | public |
| Workspace | `workspace.toml`, skills, instructions, MCP templates, extension manifest, overlays | user's own Git repository | user choice — the schema makes the *safe default* enforceable |
| Local machine state | resolved secrets, ownership ledger, backups | `SKILLFERRY_STATE_DIR` (platform state dir, 0700/0600) and the agents' own config homes | private, never exported |

The **only** place resolved secret values ever appear is the local runtime
config files the agents themselves read (e.g. `~/.codex/config.toml`), with
restrictive permissions and redacted backups.

## Threats the design refuses

1. **Secrets entering the workspace.** `workspace.toml`/`mcp/servers.toml`
   env values must match `secret:env/NAME` or `secret:file/PATH`; anything
   else fails schema validation before any plan is built
   (`src/skillferry/workspace.py`, negative tests in `tests/test_workspace.py`).
   Imported and migrated skill trees are inspected before copying; detected
   credential content, runtime-state filenames, opaque binaries, and symlinks
   are refused rather than labeled portable.
2. **Secrets leaking through exports.** `export --shareable` scans every
   copied file for credential-shaped content and forbids symlinks; it refuses
   to export opaque binaries it cannot inspect, refuses on any finding, and
   never expands a reference
   (`src/skillferry/secrets.py`, `tests/test_export_audit.py`).
3. **Secrets leaking through reports/logs.** `plan --json`/`doctor --json`
   emit only references; rendered values never reach `public_dict()`
   (`test_env_secret_lands_only_in_local_config`).
4. **Secrets leaking through backups.** Backups are stored 0600 under the
   local state dir, and every text backup gets a credential-redacted copy for
   human inspection while the raw copy preserves exact rollback
   (`src/skillferry/io_ops.py`, `test_backups_redact_secrets`).
5. **Silent overwrites.** Every managed path is hash-tracked in the local
   ownership ledger. Unregistered local content, locally modified managed
   content, and handwritten entries colliding with generated ones are
   conflicts (exit 3) — resolved only by an explicit
   `--resolve ...=adopt|overwrite|keep-local`.
6. **Machine-state takeover.** `[protect]` plus per-adapter protected names
   (auth, history, sessions, sqlite, caches, embedded servers such as
   Codex's `node_repl`) are never managed; schema rejects mis-declarations
   (`tests/test_workspace.py`, `test_protected_mcp_server_never_managed`).
7. **Path-based attacks.** Symlinks are rejected in workspaces, in target
   parents, and at every write; absolute paths and `..` are rejected in the
   schema; import and legacy migration reject symlinks before copying; apply
   operations are confined to declared managed roots
   (`src/skillferry/io_ops.py`, `tests/test_plan_apply.py`).
8. **Accidental publication of local overrides.** `workspace.local.toml` is
   gitignored, excluded from exports, and its filename is forbidden by
   `scripts/audit_public_tree.py`.
9. **Partial multi-target failure.** Apply rolls back per target group; a
   failure in one target restores everything already written
   (`test_rollback_restores_targets_on_failure`).

## Threats acknowledged, not fully mitigated (v1)

- **Supply chain of workspace content.** skillferry applies what the
  workspace declares. A malicious workspace can point MCP at arbitrary local
  commands. Mitigation: the portability grades and `plan` preview are
  mandatory reading; future versions will add signing/lockfile provenance
  (roadmap B).
- **Local attacker with the user's account.** skillferry assumes the OS
  account boundary. It does not re-encrypt resolved secrets at rest beyond
  file permissions; it is not a secret manager.
- **Claude Code's `~/.claude.json` is a single user-owned JSON file.**
  skillferry preserves every key it does not manage but rewrites the file
  with normalized formatting (stated honestly in the grade notes;
  `tests` assert other keys survive). Backup + redacted copy cover recovery.
- **Windows ACL semantics.** POSIX mode bits do not map onto Windows; on
  Windows, secrets land in config files with default ACLs. Windows-native
  acceptance is tracked separately
  ([docs/acceptance/windows-native.md](acceptance/windows-native.md)) and is
  not inferred from macOS or CI results.

## Out of scope

Session/memory sync, credential storage/rotation, network distribution of
secrets, SSH targets (v1.x), and agent runtime state (trust, marketplace,
history) are explicitly not features; `[protect]` enforces the boundary.
