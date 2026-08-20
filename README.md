# skillferry

**Your agent workflow, portable across tools and machines.**

skillferry turns one versioned, Git-friendly workspace — skills, global
instructions, and non-secret MCP connection templates — into the native
configurations of Codex, Claude Code, and DeepSeek Harness, on macOS,
Windows, and Linux. It never copies credentials or runtime state, and it
tells you honestly, per asset, how portable that asset is.

> Sync capabilities, not credentials. · Write skills once. Run them across
> agents. · Your agent capabilities should not be locked inside one client.

## 30-second demo

```console
$ skillferry import --from codex --output ~/workspaces/demo   # 1. two skills + one MCP server
$ export GITHUB_PERSONAL_ACCESS_TOKEN=...                     # 2. token lives on this machine only
$ skillferry plan --workspace ~/workspaces/demo               # 3. grades for all three agents
SKILL release-checklist
  codex   native
  claude  native
  dsh     native
MCP github
  codex   translated   secret resolved from local env
  claude  translated   secret resolved from local env
  dsh     translated   inserted as dsh-mcp-client entries in the profile cordis.patch.yml
$ skillferry apply --workspace ~/workspaces/demo              # 4. one workspace, three agents
$ skillferry doctor --workspace ~/workspaces/demo             # 5. zero drift
$ skillferry export --shareable ~/workspaces/public           # proof: no secrets, ever
Exported 15 file(s). No secret references were expanded.
```

The five-beat flow — import, secret references, per-target grades, apply,
secret-free export — is rehearsed in CI by the test suite (see
`tests/test_plan_apply.py`, `tests/test_importers.py`,
`tests/test_export_audit.py`) and was accepted natively on macOS in
[docs/acceptance/macos-native.md](docs/acceptance/macos-native.md).

## Before / after

| Before | After |
| --- | --- |
| Re-author the same skills, rules, and MCP configs per tool, per machine | One `workspace.toml` + assets, `git pull`, `skillferry apply` |
| Tokens copied into configs that end up in Git | `secret:env/NAME` references; each machine supplies real values locally |
| "Sync succeeded" with no idea what was lost in translation | `plan` prints `native / translated / degraded / manual / unsupported` per asset with loss notes |
| Sync tools silently overwrite hand edits | Per-path hash ledger: local modifications become conflicts (exit 3), never silent overwrites |

Why this matters to real users: cross-machine skill/config loss is one of the
most-requested fixes in the official trackers ([claude-code #36693](https://github.com/anthropics/claude-code/issues/36693), [#69231](https://github.com/anthropics/claude-code/issues/69231), [codex #26691](https://github.com/openai/codex/issues/26691)), and the MCP client-configuration split is an open standardization pain point ([SEP-2633](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2633), [MCP IG #2761](https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/2761)).

## Quick start

```console
$ pipx install skillferry
$ skillferry init my-workspace && cd my-workspace
# add skills/**, edit instructions/global.md and mcp/servers.toml
$ skillferry plan          # read every grade and conflict first
$ skillferry apply         # backs up, writes only owned paths
$ skillferry doctor        # exit 0 = in sync
```

`plan` and `apply` are dry-run-safe by design: `plan` never writes, and
`apply` refuses to run when any conflict exists. Exit codes: `0` in sync,
`1` error, `2` safe drift, `3` conflict needs a human decision
(`--resolve <id>=adopt|overwrite|keep-local`).

## Compatibility matrix

Grades are produced by each adapter from an evidence-backed capability table
([docs/AGENT_MATRIX.md](docs/AGENT_MATRIX.md)); nothing is labeled `native`
without a verified loading path.

| Asset | Codex | Claude Code | DeepSeek Harness |
| --- | --- | --- | --- |
| Skills (SKILL.md dirs) | `native` — `~/.agents/skills/` | `native` — `~/.claude/skills/` ([docs](https://code.claude.com/docs/en/skills)) | `native` — `~/.agents/skills/` |
| Global rules | `native` — marker blocks in `~/.codex/AGENTS.md` | `translated` — marker blocks in `~/.claude/CLAUDE.md` | `native` — marker blocks in `$DSH_HOME/AGENTS.md` |
| MCP (stdio) | `translated` — `[mcp_servers.<name>]` in `~/.codex/config.toml`; secrets resolved from local env | `translated` — user-level `~/.claude.json` `mcpServers` ([docs](https://code.claude.com/docs/en/mcp)) | `translated` — `dsh-mcp-client` entries in the profile `cordis.patch.yml` |
| MCP (http/sse) | `manual` (per-target instructions printed) | `manual` | `manual` |
| Extensions/plugins | `manual` — declared expected state, never auto-installed | `manual` | `manual` |

## Security boundary

The security model is architecture, not documentation. See
[docs/THREAT_MODEL.md](docs/THREAT_MODEL.md); machine-verifiable highlights:

- The workspace schema **rejects literal secrets**: MCP `env` values must be
  `secret:env/NAME` or `secret:file/PATH` references (`src/skillferry/workspace.py`,
  negative tests in `tests/test_workspace.py`).
- `export --shareable` scans every copied file and refuses to export on any
  credential-shaped content; it never expands a reference
  (`src/skillferry/secrets.py`, `tests/test_export_audit.py`).
- Backups are raw (0600, local-only, for exact rollback) **plus** redacted
  copies for human inspection (`src/skillferry/io_ops.py`,
  `test_backups_redact_secrets`).
- JSON reports and logs contain references, never resolved values
  (`test_env_secret_lands_only_in_local_config`).
- `[protect]` declares what a workspace may never manage (auth, sessions,
  sqlite, caches, embedded servers); mis-declarations fail at schema level.
- `scripts/audit_public_tree.py` fails CI when the public tree contains
  credential patterns, machine paths, or runtime filenames.

## Workspace layout

```toml
# workspace.toml — target-neutral by construction
schema_version = 1
[skills]                  directory = "skills"
                          default_targets = ["codex", "claude", "dsh"]
[instructions]            common = "instructions/global.md"   # marker | copy | include
[mcp]                     registry = "mcp/servers.toml"       # env: secret refs only
[extensions]              manifest = "extensions/manifest.toml"
[overlays]                platform_dir / target_dir / host_dir  # base < target < platform < host < local
[protect]                 paths = []                          # never-manage declarations
```

A complete runnable example ships in
[examples/starter-workspace](examples/starter-workspace) (validated in CI),
together with two seed skills: `setup-skillferry` and `release-checklist`.

Merge order is `base < target < platform < host < local override`; lists
replace wholesale and dicts deep-merge, every value's origin is visible to
`plan`, and conflicts are never silent
([docs/PORTABILITY_CONTRACT.md](docs/PORTABILITY_CONTRACT.md)).

## Not a dotfiles / symlink / GUI tool

skillferry is deliberately a headless CLI. It is **not** a full-dotfiles
synchronizer (it manages only declared, structured assets), it never creates
symlinks or Windows junction/reparse points (the schema rejects them), it ships
no GUI, it does not switch API
providers, sync sessions/history, or "losslessly convert any plugin". The
honest comparison with the existing landscape, including what we can and
cannot claim about competitors, is in
[docs/COMPARISON.md](docs/COMPARISON.md).

## Adapter development

Adding a target is bounded: implement `adapters/base.py`'s interface (where
each asset lands, the capability-backed grades, and the MCP rendering) and
register it in `adapters/registry.py`. See
[docs/AGENT_MATRIX.md](docs/AGENT_MATRIX.md) for the evidence bar each grade
must meet.

## Migrating from codex-profile-sync

`skillferry migrate --from codex-profile-sync <bundle> --output <dir>` converts
the legacy bundle's skills and MCP declarations into a draft workspace
(credential values become `secret:env/...` references; the bundle is never
modified). Details in [docs/MIGRATION.md](docs/MIGRATION.md).

## Roadmap

- **A (this release)**: the portable core — skills/rules/MCP rendering,
  grades, ownership ledger, import/export/migrate, CI on 3 OS × Python 3.11–3.13.
- **B**: Gemini CLI adapter (first v1.x target), `lockfile`/provenance records.
- **C**: team layer (`scope/team` overlays), SSH/remote targets.
- **D**: reference implementations as the SKILL.md/mcp.json standards converge.

## License

Apache-2.0. See [LICENSE](LICENSE).
