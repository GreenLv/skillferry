# Portability contract

> 中文版：[可移植性契约](zh-CN/PORTABILITY_CONTRACT.md)

`skillferry plan` is a promise, not a progress bar: for every asset and
every target it prints a grade plus the losses, so "applied" never hides
"translated with something dropped". This document is that contract.

## Grades

| Grade | Meaning |
| --- | --- |
| `native` | Rendered into the target's own format/location and loaded without translation. Requires verified loading evidence ([AGENT_MATRIX](AGENT_MATRIX.md)). |
| `translated` | Works, but the target format differs from the neutral one; the notes name exactly what was transformed (e.g. "secret resolved from local env", "block appended verbatim"). |
| `degraded` | Works with known limitations or unverified behavior; the notes state them. |
| `manual` | skillferry prints per-target instructions instead of writing; the user performs the step. |
| `unsupported` | Not applicable to this target (e.g. a target with no rules file). |

Example (`plan` output):

```
SKILL release-checklist
  codex   native
  claude  native
  dsh     native
MCP github
  codex   translated   secret resolved from local env
  claude  translated   secret resolved from local env
  dsh     translated   inserted as dsh-mcp-client entries in the profile cordis.patch.yml
```

## The workspace is target-neutral

- No path in the workspace is an agent path; each adapter declares its own
  landing directories ([AGENT_MATRIX](AGENT_MATRIX.md)).
- No value in the workspace is a secret; MCP env values are
  `secret:env/NAME` / `secret:file/PATH` references, enforced at schema
  level.
- No machine-local fact (paths, hostnames, credentials, session state)
  belongs in the committed tree; `workspace.local.toml` is the one local
  escape hatch and is gitignored + excluded from exports.

## Overlay merge order

`base < overlays/target/<t> < overlays/platform/<p> < overlays/host/<h> < workspace.local.toml`

Semantics: dicts deep-merge; **lists replace wholesale** (a platform list
does not append to a base list). `plan` shows the merged values; every
value's origin is tracked in the workspace provenance map and surfaced when
a merge changes a value. Conflicting writes (same target path from two
declared sources) are conflicts, never silent last-writer-wins.

## Ownership and conflict rules

For every managed file/section/block, the local state ledger records what
skillferry last wrote (plain, non-secret records: file hashes, values, and
secret **references** — never resolved values).

| Situation | Behavior |
| --- | --- |
| Target missing | `create` |
| Target identical to source | `adopt` (first time) / no change |
| Source changed, target still matches the ledger | `update` |
| Target differs from ledger and from source (local edit) | `conflict` → exit 3 |
| Target exists, unregistered, differs from source | `conflict` → exit 3 |
| Source removed, target still matches the ledger | `delete` |
| Same name as a generated entry, hand-written (e.g. DSH `mcp-<name>`) | `conflict` → exit 3 |

Every conflict carries a stable `--resolve` id with decisions
`adopt` (register local content as the baseline), `overwrite` (force the
source), or `keep-local` (alias of adopt, for intent clarity).

## Secret handling contract

- References resolve **only** at apply time, on the local machine, from the
  process environment or a local file.
- A missing secret source is a conflict before anything is written.
- Reports, JSON output, logs, and `export --shareable` contain references,
  never resolved values.
- Backups: raw copies (exact rollback) plus redacted copies (human
  inspection), both local-only with restrictive permissions.
- The source-change vs local-edit distinction uses previously recorded
  references re-resolved locally, so adding a secret key upstream is an
  `update`, while editing a value by hand is a `conflict`
  (`test_source_change_is_update_not_conflict`, `test_local_edit_is_conflict`).

## Exit codes

`0` in sync · `1` error · `2` safe drift (`apply` will fix) · `3` conflict
needs a human. `doctor` uses all four; `plan` returns `3` on conflicts
(writes none); `apply` returns `3` on conflicts (writes none).
