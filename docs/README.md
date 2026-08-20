# Documentation index

skillferry's documentation lives in three places: the bilingual root READMEs
([README.md](../README.md) / [README.zh-CN.md](../README.zh-CN.md)), this
`docs/` tree, and the root-level [CONTRIBUTING.md](../CONTRIBUTING.md) /
[SECURITY.md](../SECURITY.md) / [CHANGELOG.md](../CHANGELOG.md). This page
maps the `docs/` tree and suggests a reading order per role.

## Reading paths

| You are… | Read in this order |
| --- | --- |
| New user evaluating skillferry | [README](../README.md) → [PORTABILITY_CONTRACT](PORTABILITY_CONTRACT.md) → [COMPARISON](COMPARISON.md) |
| Security reviewer / cautious user | [THREAT_MODEL](THREAT_MODEL.md) → [SECURITY.md](../SECURITY.md) → the acceptance records |
| Contributor / adapter author | [CONTRIBUTING.md](../CONTRIBUTING.md) → [AGENT_MATRIX](AGENT_MATRIX.md) → [acceptance/](acceptance/) |
| Legacy codex-profile-sync user | [MIGRATION](MIGRATION.md) |

## Documents

| Document | Contents |
| --- | --- |
| [PORTABILITY_CONTRACT.md](PORTABILITY_CONTRACT.md) | What the five grades promise, overlay merge order, ownership/conflict rules, secret handling, exit codes |
| [THREAT_MODEL.md](THREAT_MODEL.md) | Assets and trust boundaries, the nine refused threats, acknowledged v1 limits, out of scope |
| [AGENT_MATRIX.md](AGENT_MATRIX.md) | Per-target loading paths (where each asset lands) and the evidence behind every grade |
| [COMPARISON.md](COMPARISON.md) | Measured landscape comparison; what we can and cannot claim about competitors |
| [MIGRATION.md](MIGRATION.md) | One-time conversion from a codex-profile-sync bundle |
| [acceptance/macos-native.md](acceptance/macos-native.md) | Evidence record: full rehearsal on a real macOS machine |
| [acceptance/windows-native.md](acceptance/windows-native.md) | Evidence record: full rehearsal on a real Windows machine |
| [acceptance/zero-change-codex-sync.md](acceptance/zero-change-codex-sync.md) | Proof that building skillferry never mutated the legacy codex-sync repo |

The acceptance records are intentionally English-only: they are timestamped
command transcripts and machine evidence, not prose to translate.

## Chinese translations

The core documents have Chinese translations in
[zh-CN/](zh-CN/README.md); the root entry point is
[README.zh-CN.md](../README.zh-CN.md).
