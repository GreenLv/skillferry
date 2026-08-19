---
name: release-checklist
description: Run a release checklist for a software repository: tests, public-tree audit, changelog, artifacts, and rollback readiness before any tag or publish.
targets: [codex, claude, dsh]
version: 0.1.0
---

# release-checklist

A compact, order-preserving release checklist for small-to-medium software
repositories. Demonstrates skillferry skill layout: `targets` frontmatter,
plus a `references/` file the agent can open for details.

## When to use

- Before tagging a version, publishing a package, or cutting a GitHub release.
- When asked "is this ready to release?" without a checklist at hand.

## Checklist

1. **Tests**: full unit + contract + negative tests pass locally on the
   release platform. Record the exact command and output tail as evidence.
2. **Public-tree audit**: no secrets, credentials, machine paths, or runtime
   state in the tree (`scripts/audit_public_tree.py .` or equivalent).
3. **Changelog**: every user-visible change since the last tag is listed
   under the new version heading.
4. **Version**: the version string is bumped in exactly one place of truth.
5. **Artifacts**: built from a clean checkout; wheel/sdist (or equivalent)
   build and install in a fresh environment.
6. **Rollback**: the previous release can be reinstalled; backups or revert
   steps are documented.
7. **Post-release verification**: after publish, read back the published
   artifact/visibility/branch state before announcing success.

## Rules

- Never infer whole-release success from one green signal; each gate must
  produce its own evidence.
- A failed gate is a blocker, not a note. Fix or downgrade the release scope.
- Record the checklist outcome (date, version, gates, evidence) in the repo.

## See also

- `references/release-gates.md` for per-gate details and acceptance evidence.
