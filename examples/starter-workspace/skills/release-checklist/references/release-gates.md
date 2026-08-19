# Release gates

Details for each gate in the parent checklist, including what counts as
acceptance evidence and the common failure modes.

## 1. Tests

Acceptance evidence: the exact command run, the exit code, and the last
lines of output. Never accept "it passed earlier on another machine" as
evidence for this release — each platform keeps its own record.

Common failures: flaky tests papered over with retries, tests skipped via
markers, environment-dependent tests silently skipped.

## 2. Public-tree audit

The audit must fail the release when it finds: credential-shaped strings,
user-specific absolute paths, private keys, email addresses, forbidden
runtime filenames (auth.json, history.jsonl), sqlite state, or symlinks.

Common failures: generated build artifacts committed by accident, example
files containing real tokens, `.DS_Store` or editor state in the tree.

## 3. Changelog

Every user-visible change since the last tag: features, behavior changes,
removals, fixes. Keep security-relevant changes explicit.

## 4. Version

One source of truth (single-file bump); the built artifact and the
installed CLI must report the same string.

## 5. Artifacts

Build from a clean checkout (no local edits, no untracked inputs), then
install into a fresh environment and run the version/self-test commands.

## 6. Rollback

Either a reinstallable previous artifact or a documented revert path, plus
recoverable backups for any migrated local state.

## 7. Post-release verification

After publishing, read back the remote state (visibility, default branch,
artifact contents, CI result) before describing the release as complete.
