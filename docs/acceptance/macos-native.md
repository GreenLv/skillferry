# macOS native acceptance evidence

Status: **executed and passing** · Date: 2026-08-19 · Machine: macOS
(aarch64) · Python 3.12 (local runs; CI matrix covers 3.11–3.13) ·
skillferry 0.1.0 · Every path below is sanitized: `<HOME>` = the user home,
`<TMP>` = the isolated rehearsal directory. No real agent configuration was
modified by the rehearsal; the real-machine `plan` run is read-only by
construction (`plan` performs zero writes).

## 0. Real-machine facts (probes, read-only)

| Probe | Result |
| --- | --- |
| `codex --version` | codex-cli 0.146.0 |
| `claude --version` | 2.1.81 (Claude Code) |
| `dsh --version` | 0.1.0-rc.7 |
| Real home layout | `~/.agents/skills/` (30 skills, shared root), `~/.codex/AGENTS.md` + `config.toml`, `~/.claude/` (Claude Code install, no personal skills dir yet), `$DSH_HOME/profiles/web/cordis.patch.yml` + `$DSH_HOME/AGENTS.md` |

Real-machine read-only plan against the actual homes resolved every native
path correctly (full transcript below in §4); **nothing was written**.

## 1. Beat 1 — import classifies and converts a token

```
$ skillferry import --from codex --codex-home <FAKE>/.codex --skills-home <FAKE>/.agents/skills --output <TMP>/ws
  PORTABLE   skills/demo-skill                                        skill directory
  PORTABLE   skills/release-checklist                                 skill directory
  SENSITIVE  config.toml [mcp_servers.github].env.GITHUB_PERSONAL_ACCESS_TOKEN credential value converted to a secret:env reference
  LOCAL-ONLY config.toml [mcp_servers.node_repl]                      Codex-owned embedded server
  PORTABLE   mcp/servers.toml                                         registry written with 2 server(s)
  PORTABLE   instructions/global.md                                   AGENTS.md content
  SENSITIVE  auth.json                                                left untouched
  LOCAL-ONLY sessions                                                 left untouched
```

The workspace registry contains `GITHUB_PERSONAL_ACCESS_TOKEN =
"secret:env/GITHUB_PERSONAL_ACCESS_TOKEN"`; the literal token never entered
the draft workspace (verified by grep, and locked by CI test
`test_import_codex_token_becomes_reference`).

## 2. Beat 2+3 — plan prints three-target grades (secret resolved only locally)

```
$ skillferry plan --workspace <TMP>/ws --home <TMP>/home --dsh-home <TMP>/home/.dsh
MCP github
  claude translated   secret resolved from local env; user-level ~/.claude.json mcpServers; ...
  codex  translated   secret resolved from local env; managed as [mcp_servers.<name>] in ~/.codex/config.toml
  dsh    translated   secret resolved from local env; inserted as dsh-mcp-client entries in the profile cordis.patch.yml
MCP time
  codex  native   managed as [mcp_servers.<name>] in ~/.codex/config.toml
  ...
RULES global
  codex  native   marker-delimited blocks in AGENTS.md
  dsh    native   marker-delimited blocks in $DSH_HOME/AGENTS.md
  claude translated   CLAUDE.md has no managed-block concept; block appended verbatim
SKILL demo-skill / release-checklist
  codex/claude/dsh  native (all)
```

## 3. Beat 4 — apply renders all three targets; doctor zero-drift

`apply --yes` exited 0 with a recoverable backup directory. Rendered shapes
(actual files from the rehearsal, token values replaced by
`<resolved-locally>`):

`~/.codex/config.toml`:
```toml
[mcp_servers.github]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
[mcp_servers.github.env]
GITHUB_PERSONAL_ACCESS_TOKEN = "<resolved-locally>"
[mcp_servers.time]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-time"]
```

`~/.claude.json` (mcpServers.github with `type: stdio`, `env` resolved; all
other keys preserved):
```json
{ "mcpServers": { "github": { "type": "stdio", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"], "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "<resolved-locally>" } }, "time": { "type": "stdio", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-time"] } } }
```

`~/.dsh/profiles/web/cordis.patch.yml` (managed block appended; surrounding
content byte-preserved; per-entry `dsh-mcp-client` insert):
```yaml
# >>> BEGIN SKILLFERRY DSH MCP >>>
- insert:
    - id: mcp-github
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: github
        transport: stdio
        command: "npx"
        args: ["-y", "@modelcontextprotocol/server-github"]
        env:
          GITHUB_PERSONAL_ACCESS_TOKEN: "<resolved-locally>"
        failOnStartupError: false
- insert:
    - id: mcp-time
      ...
# <<< END SKILLFERRY DSH MCP <<<
```

Skill files landed in `~/.agents/skills/<name>/` (Codex + DSH) and
`~/.claude/skills/<name>/` (Claude Code). `doctor` on the same homes:
`Changes: none` — **exit 0**.

## 4. Beat 5 — export is secret-free

```
$ skillferry export --workspace <TMP>/ws <TMP>/public
Exported 15 file(s) to <TMP>/public
No secret references were expanded; no secrets were copied.
```
`grep` for credential patterns over the exported tree: zero hits (also
machine-verified by CI tests `test_export_*`).

## 5. Real-machine read-only plan (native paths, zero writes)

```
Workspace: <HOME>/Documents/Github/skillferry/examples/starter-workspace
Platform: macos   Targets: codex, claude, dsh
...
Changes:  (all three targets resolved to real homes: <HOME>/.codex, <HOME>/.claude, <HOME>/.dsh, <HOME>/.agents)
```
`plan` performs zero writes (asserted by construction and covered by the
test suite); no real agent configuration was modified during acceptance.

## 6. Conflict and rollback drills (same rehearsal home)

- Hand-edited managed skill → `doctor` exit 3 with
  `resolve: --resolve skill:codex:release-checklist:SKILL.md=adopt|overwrite|keep-local`.
- `apply --resolve ...=overwrite` restored the source content; `doctor`
  returned to exit 0.
- Missing `GITHUB_PERSONAL_ACCESS_TOKEN` env → plan conflict
  ("environment variable ... is not set on this machine"), exit 3.
- Source-side change (new env key / changed args) → `update`, **not**
  conflict; local-side value edit → conflict (exit 3).
- Mid-apply failure (target dir replaced by a file) → all already-written
  targets rolled back byte-for-byte (`test_rollback_restores_targets_on_failure`).
- Backup dirs contain raw copies (0600) plus `<file>.redacted` copies in
  which credential values are masked (`<redacted>`).

## 7. Automated suite

`pytest` (68 tests) and `ruff` are green locally and wired into the CI
matrix (3 OS × Python 3.11–3.13) with the public-tree audit, seed-skill
parity check, workspace validation, wheel build, and installed-CLI version
check.
