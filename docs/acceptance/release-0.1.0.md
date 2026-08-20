# Release 0.1.0 acceptance evidence

Status: **published on GitHub and PyPI** · Date: 2026-08-20 ·
Version: `0.1.0`

This record applies the repository's `release-checklist` seed skill and keeps
release identity, validation, publication, and evidence limitations separate.
The exact published source is the immutable tag target below. This file and
other documentation may receive follow-up commits on `main`; those commits do
not change the already-published artifact.

## Release identity

| Field | Recorded value |
| --- | --- |
| GitHub Release | [`skillferry 0.1.0`](https://github.com/GreenLv/skillferry/releases/tag/v0.1.0), published and not draft/prerelease |
| Tag | Annotated `v0.1.0` |
| Release commit | `a78bf54d042ce1cf7eb16a056237fd32bb56d238` |
| Package | [`skillferry==0.1.0`](https://pypi.org/project/skillferry/0.1.0/) |
| Native evidence | [macOS](macos-native.md) and [Windows](windows-native.md) |

## What was released

The release is the portable agent-workspace core: a versioned `workspace.toml`,
Codex/Claude Code/DeepSeek Harness adapters, explicit portability grades,
secret-reference-only MCP templates, ownership/conflict tracking, reversible
apply, import/export/migrate, and the security/public-tree gates described in
the [changelog](../../CHANGELOG.md).

## Validation gates

### Source and package gates

- `/opt/anaconda3/bin/python -m pytest` → `81 passed, 3 skipped` (exit 0).
  The skips were platform-conditioned junction/startup cases, not
  environment-detection fallbacks.
- Ruff, the public-tree audit, seed-skill parity, and
  `examples/starter-workspace` validation passed for all three rendered targets.
- `pyproject.toml`, `src/skillferry/__init__.py`, CLI output, and a fresh wheel
  install all reported `0.1.0`.
- A clean build produced
  `skillferry-0.1.0-py3-none-any.whl` and `skillferry-0.1.0.tar.gz`; strict
  `twine check` passed for both.
- The [release-commit CI run](https://github.com/GreenLv/skillferry/actions/runs/32382714062)
  passed on Ubuntu, macOS, and Windows with Python 3.11, 3.12, and 3.13.
  This is automated source/shape evidence, not native platform acceptance.

The build backend is pinned to `hatchling>=1.25,<1.32`: Hatchling 1.32+
emits `Metadata-Version: 2.5`, which the release toolchain's twine 6.2.0 /
packaging 26.x rejects. The accepted boundary is Hatchling 1.31.0 → metadata
2.4 and 1.32.0 → metadata 2.5.

### Native platform gates

- **macOS:** the isolated import → plan → apply → doctor → export lifecycle,
  real target-path read-only planning, rollback/conflict drills, DSH composed
  config, MCP child startup, and Web HTTP probe passed. No real agent home was
  an apply target; see [macOS native acceptance](macos-native.md).
- **Windows:** the native user-session lifecycle, CRLF preservation, Unicode
  and space-containing paths, NTFS junction refusal, rollback, DSH config and
  process loading passed. The final source run reported 82 passed and 2
  explicit privileged symlink skips; see [Windows native acceptance](windows-native.md).

Native records are independent of the GitHub Actions matrix. CI is automated
source/shape evidence and does not substitute for either native run.

## Publication readback

- Workflow run [`32382725301`](https://github.com/GreenLv/skillferry/actions/runs/32382725301)
  built and inspected the wheel/sdist, and its final `Publish to PyPI` job
  succeeded.
- The first PyPI attempt returned `invalid-publisher`. After the owner added
  the trusted publisher for `GreenLv/skillferry`, `release.yml`, environment
  `pypi`, the failed job was rerun and succeeded. This was an account/workflow
  configuration step, not a change to the release contents.
- PyPI readback returned HTTP 200 for version `0.1.0`, with wheel and sdist
  present and neither yanked. An independent fresh environment installed
  `skillferry==0.1.0` and reported `skillferry --version` → `0.1.0`.
- The remote annotated tag was read back and resolves to the release commit
  above; the GitHub Release is non-draft and non-prerelease.

## Evidence boundaries and limitations

- The Windows acceptance record does not claim a native Claude Code process
  run because Claude Code was not installed on that machine; its on-disk
  rendered shape was inspected.
- Windows ACL confidentiality remains dependent on the selected agent-home
  ACL. skillferry does not replace the operating system's ACL policy or act as
  a secret manager.
- Two privileged Windows symbolic-link tests were skipped explicitly; NTFS
  junction coverage passed without elevation.
- The release tag is the source-of-truth for the published package. Later
  documentation commits on `main` are evidence follow-ups, not retroactive
  changes to `v0.1.0`.

## Rollback

This was the first PyPI artifact, so there was no previous package to restore.
The publication rollback would be to remove the GitHub Release and `v0.1.0`
tag, then withdraw the `0.1.0` PyPI distributions according to PyPI's
maintainer process.
