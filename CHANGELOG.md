# Changelog

All notable changes to skillferry are documented here, newest first.

## Unreleased

### Docs

- Added a documentation index for the `docs/` tree
  ([docs/README.md](docs/README.md)) and Chinese translations of the core
  documents ([docs/zh-CN/](docs/zh-CN/), `CONTRIBUTING.zh-CN.md`,
  `SECURITY.zh-CN.md`).
- READMEs gained tables of contents, a grade glossary, and a documentation
  map; the Chinese README was resynced with the English one.

## 0.1.0 — 2026-08-19

First release: the portable agent-workspace core (roadmap stage A).

### Added

- `workspace.toml` schema v1: skills, instructions (marker/copy/include),
  MCP registry (secret-reference-only env), extension manifest, orthogonal
  overlays (`base < target < platform < host < local`), `[protect]`
  declarations, with schema-level rejection of literal secrets, path
  traversal, symlinks, and protect mis-declarations.
- Adapters for Codex, Claude Code, and DeepSeek Harness with
  evidence-backed portability grades
  (`native / translated / degraded / manual / unsupported`).
- CLI: `init`, `import --from codex|claude`
  (PORTABLE / LOCAL-ONLY / SENSITIVE / UNKNOWN classification),
  `plan`, `apply` (with `--resolve id=adopt|overwrite|keep-local`),
  `doctor` (exit codes 0/1/2/3), `status`, `export --shareable`,
  `migrate --from codex-profile-sync`.
- Hash-based ownership ledger: create/update/adopt/delete semantics,
  source-change vs local-edit distinction, conflict blocking, per-target
  rollback, raw + redacted backups.
- Seed skills `setup-skillferry` and `release-checklist`, and the runnable
  `examples/starter-workspace` (parity-checked in CI).
- Public-tree auditor (`scripts/audit_public_tree.py`) and workspace
  validator (`scripts/validate_workspace.py`).
- Test suite (68 tests) and CI matrix: 3 OS × Python 3.11–3.13 plus a
  release workflow.
- Documentation: bilingual README, THREAT_MODEL, AGENT_MATRIX,
  PORTABILITY_CONTRACT, COMPARISON, MIGRATION, and the macOS native
  acceptance record.

### Fixed

- Hardened multiline secret scanning, imported-skill inspection, opaque-binary
  rejection, and legacy migration against symlink traversal.
- Made rollback restore partial writes in the failing target group and preserve
  deleted files, with redacted views generated from the actual backup bytes.
- Persisted ledger-only `adopt` / `keep-local` resolutions.
- Reconciled whole-skill and MCP-server removals across Codex, Claude Code, and
  DeepSeek Harness without deleting locally modified owned content silently.
- Expanded the regression suite from 68 to 79 tests.
