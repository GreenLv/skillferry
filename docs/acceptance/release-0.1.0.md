# Release 0.1.0 acceptance evidence

Status: **GitHub release published; PyPI publish pending owner configuration** ·
Date: 2026-08-20 · Version: 0.1.0 · Tag: `v0.1.0` ·
Commit: `a78bf54d042ce1cf7eb16a056237fd32bb56d238` ·
Platform: macOS (aarch64) · Python 3.12.2

Release checklist (seed skill `release-checklist`) outcome, gate by gate.

## 1. Tests

`python3 -m pytest` → `81 passed, 3 skipped` (exit 0). The skips are
platform-conditioned junction/startup cases, not environment-detection
fallbacks.

## 2. Public-tree audit

`python3 scripts/audit_public_tree.py .` → passed on the release tree.
`python3 scripts/check_seed_skills_parity.py` → passed.
`python3 scripts/validate_workspace.py examples/starter-workspace` → all
three targets (codex/claude/dsh) OK.

## 3. Changelog

The docs-only `Unreleased` entries were folded into `0.1.0 — 2026-08-20`
before tagging; no user-visible change was left uncategorized.

## 4. Version

Single source of truth `pyproject.toml` = `src/skillferry/__init__.py` =
CLI output = `0.1.0` (fresh-venv wheel install verified both the console
script and the module).

## 5. Artifacts

Built from a clean tree: `python3 -m build` →
`skillferry-0.1.0-py3-none-any.whl` + `skillferry-0.1.0.tar.gz`.
`twine check --strict` (twine 6.2.0): both PASSED.
Fresh venv install of the wheel: `skillferry --version` → `0.1.0`.

Build-backend pin: hatchling 1.32+ emits `Metadata-Version: 2.5`, which the
repo's pinned twine 6.2.0 (packaging 26.x) rejects; `pyproject.toml` now
requires `hatchling>=1.25,<1.32` so distributions stay on `Metadata-Version:
2.4` (verified boundary: 1.31.0 → 2.4, 1.32.0 → 2.5).

## 6. Rollback

First release: no previous PyPI artifact to restore. Revert path = delete
the GitHub release, delete tag `v0.1.0`, and the project is unpublished.

## 7. Post-release verification

- GitHub release `skillferry 0.1.0` published (not draft, not prerelease)
  at tag `v0.1.0` → commit `a78bf54…`; remote tag verified via
  `git ls-remote --tags origin`.
- Workflow run 32382725301: `Build and inspect distributions` succeeded
  (artifact `python-package-distributions`, 163 271 bytes).
- `Publish to PyPI` **failed**: PyPI returned `invalid-publisher` — no
  trusted publisher matches `GreenLv/skillferry`, workflow `release.yml`,
  environment `pypi`. This is a PyPI-account configuration step, not a
  repository defect. Owner action: add the pending publisher on
  https://pypi.org (project `skillferry`, owner `GreenLv`, repository
  `skillferry`, workflow `release.yml`, environment `pypi`), then re-run
  the failed job (`gh run rerun 32382725301 --failed`).
