# Adapter capability evidence matrix

Every grade printed by `skillferry plan` must be backed by evidence recorded
here. **An adapter never claims `native` for an untested behavior.** The
sources are: (E1) the author's own macOS acceptance runs
([acceptance/macos-native.md](acceptance/macos-native.md)), (E2) the
author's published codex-profile-sync engine and codex-sync scripts, (E3)
official product documentation (links below), (E4) the CI test suite
(shape assertions, not product behavior).

## Loading paths (where each asset lands)

| Target | Skills | Global rules | MCP (stdio) |
| --- | --- | --- | --- |
| Codex | `~/.agents/skills/<name>/` (E1: shared with DSH, auto-discovered) | `~/.codex/AGENTS.md`, marker-delimited blocks (E2: same mechanism as the author's `manage-global-agents.py`) | `~/.codex/config.toml` `[mcp_servers.<name>]` command/args/env (E2/E3: Codex config format) |
| Claude Code | `~/.claude/skills/<name>/` (E3: [personal skills docs](https://code.claude.com/docs/en/skills)) | `~/.claude/CLAUDE.md`, marker blocks rendered verbatim (E3: CLAUDE.md is plain markdown; Claude has no managed-block concept) | user-level `~/.claude.json` `mcpServers` (E3: [MCP docs](https://code.claude.com/docs/en/mcp) — user-scoped servers are stored in `~/.claude.json`); project-level `.mcp.json` is **not** managed by v1 |
| DSH | `~/.agents/skills/<name>/` (E1: native auto-load, verified) | `$DSH_HOME/AGENTS.md`, marker blocks (E2: `manage-global-agents.py` dsh target) | `$DSH_HOME/profiles/<profile>/cordis.patch.yml`, `dsh-mcp-client` insert entries (E2: `apply-dsh-mcp.py`; E1: verified live profile) |

## Grade derivations

### Skills

All three targets: `native`. SKILL.md frontmatter (`name`, `description`)
is the shared standard; skillferry-only fields (`targets`, `version`) are
ignored by the agents and therefore lossless.

Evidence: E1 (Codex/DSH), E3 (Claude personal skills directory and
frontmatter format), E4 (`test_apply_creates_all_three_target_shapes`).

### Global rules (strategy × target)

| Strategy | Codex | Claude Code | DSH |
| --- | --- | --- | --- |
| `marker` (default) | `native` (E2) | `translated` — CLAUDE.md has no managed-block concept; the block is appended verbatim (E3) | `native` (E2) |
| `include` | `translated` — rendered as `@path` imports in AGENTS.md | `translated` — `@path` imports in CLAUDE.md | `degraded` — import behavior in DSH AGENTS.md is **unverified** |
| `copy` | `degraded` — replaces the whole AGENTS.md; unmanaged content conflicts | `degraded` | `degraded` |

### MCP

| Target | stdio grade and notes | http/sse |
| --- | --- | --- |
| Codex | `translated` when secrets present ("secret resolved from local env"), else `native`; section-level ownership in `~/.codex/config.toml` | `manual` |
| Claude Code | `translated` — user-level `.claude.json`; the file is rewritten with normalized JSON formatting (all other keys preserved); project `.mcp.json` not managed by v1 | `manual` |
| DSH | `translated` — `dsh-mcp-client` plugin entries in the profile patch block | `manual` |

Evidence: E2/E1 for Codex and DSH formats; E3 for Claude's `.claude.json`
`mcpServers` shape; E4 asserts the exact rendered shapes.

### Extensions / plugins

All targets: `manual` in v1. skillferry declares the expected state
(source + pinned version) but never installs or upgrades extensions.
Instructions are printed per target
(`src/skillferry/adapters/*.py` extension_instructions).

## Explicitly not claimable

- **"Claude Code natively scans `~/.agents/skills/`"** — not verified and
  not claimed; Claude skills are rendered to `~/.claude/skills/`.
- **"DSH supports `@path` imports in AGENTS.md"** — unverified; graded
  `degraded` under the `include` strategy.
- **"Any http/sse MCP server is auto-configurable"** — v1 renders only
  `stdio`; everything else is `manual` with per-target instructions.
- **Native evidence on Windows** — pending a Windows-native acceptance run;
  see [acceptance/windows-native.md](acceptance/windows-native.md). CI green
  on `windows-latest` is automated shape evidence, not native acceptance.

## How to change a grade

1. Record the new evidence in
   [acceptance/macos-native.md](acceptance/macos-native.md) (or the Windows
   record) with date, command, and observed output.
2. Update this table and the adapter's grade functions.
3. Add or update the regression test that asserts the rendered shape.
