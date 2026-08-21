# Changelog

[简体中文](CHANGELOG.zh-CN.md)

All notable public releases are documented here, newest first. Each version
opens with its highest-impact changes, followed by implementation details and
a compact validation note. `0.1.0` is the latest published release.

## Unreleased

### Documentation

- Reorganized the bilingual README around the product problem, core promises,
  release status, and evidence boundaries.
- Added a Chinese changelog and synchronized the documentation index,
  portability matrix, comparison, threat model, and release record.
- Corrected the documented `export` command: the shareable export is
  `skillferry export <destination>`, not a `--shareable` flag, which never
  existed in the CLI.
- Kept the current documentation follow-up separate from the already-published
  `v0.1.0` tag; no runtime behavior changes are included here.

## 0.1.0 — 2026-08-20

First public release of the portable agent-workspace core (roadmap stage A).

### Highlights

- A target-neutral `workspace.toml` describes skills, global instructions, MCP
  templates, extensions, overlays, and protected paths once; adapters render
  it for Codex, Claude Code, and DeepSeek Harness.
- `plan` reports evidence-backed `native`, `translated`, `degraded`, `manual`,
  or `unsupported` grades instead of treating every target as lossless.
- Secret references stay in the workspace while resolved values remain local;
  the shareable `export` refuses credential-shaped content and never expands a
  reference.
- Hash-based ownership, explicit conflict resolution, backups, redacted views,
  and per-target rollback prevent silent overwrites.

### Changes

- Added schema v1 validation for skills, instructions (`marker`/`copy`/`include`),
  MCP registries, extension manifests, orthogonal overlays
  (`base < target < platform < host < local`), and `[protect]` declarations.
  Literal secrets, path traversal, symlinks, Windows junctions/reparse points,
  opaque binaries, and protected-state mis-declarations are rejected.
- Added the CLI workflow: `init`, `import --from codex|claude`, `plan`, `apply`,
  `doctor`, `status`, the shareable `export`, and
  `migrate --from codex-profile-sync`.
- Added Codex, Claude Code, and DeepSeek Harness adapters, the
  `setup-skillferry` and `release-checklist` seed skills, and the runnable
  `examples/starter-workspace`.
- Added the public-tree auditor, workspace validator, bilingual README and
  core-document translations, portability contract, threat model, capability
  matrix, comparison, migration guide, and platform acceptance records.
- Hardened multiline secret scanning, imported-skill inspection, legacy
  migration, rollback of partial writes, redacted backup generation, and
  source-change versus local-edit reconciliation.
- Pinned `hatchling<1.32` so distributions retain `Metadata-Version: 2.4`,
  which passes the release toolchain's `twine check --strict` gate.

### Validation

- The release commit is `a78bf54d042ce1cf7eb16a056237fd32bb56d238`, targeted by
  annotated tag `v0.1.0`.
- The release gate passed 81 tests with 3 platform-conditioned skips, Ruff,
  the public-tree audit, seed-skill parity, starter-workspace validation,
  wheel/sdist build, and strict package metadata checks.
- Independent native acceptance passed on macOS and Windows. The Windows
  record separately documents two privileged symlink skips, Claude Code not
  being installed, DSH launcher behavior, and Windows ACL limits; those facts
  are not collapsed into a generic compatibility claim.
- GitHub Release `v0.1.0` and PyPI `skillferry==0.1.0` were published. A fresh
  PyPI install reported `skillferry --version` as `0.1.0`. Full publication
  readback is in [the release acceptance record](docs/acceptance/release-0.1.0.md).
