# macOS native acceptance evidence

Status: **executed and passing** · Historical rehearsal: 2026-08-19 · Native
DSH supplement: 2026-08-20 · Machine: macOS (aarch64) · Python 3.12 ·
skillferry 0.1.0 · Every path below is sanitized: `<HOME>` = the user home,
`<TMP>` = an isolated rehearsal directory. Sections 1–6 preserve the earlier
read-only rehearsal; §8 records the current `ba501391a13723d318eab117da7b760b09c0edea`
baseline and supersedes its old MCP process-startup coverage. No real Codex,
Claude Code, or DSH configuration was an apply target.

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

## 8. Native DSH process supplement (2026-08-20)

Baseline: `ba501391a13723d318eab117da7b760b09c0edea` (`fix: validate DSH
native startup`). The starter workspace was copied into `<TMP>/workspace`.
The run set `HOME=<TMP>/fake-home`, `DSH_HOME=<TMP>/fake-dsh`, and
`SKILLFERRY_STATE_DIR=<TMP>/state`; the npm cache and XDG config/cache/data
directories were also isolated below `<TMP>`. No real agent directory was an
apply target.

### Isolated SkillFerry lifecycle

| Operation | Result |
| --- | --- |
| `skillferry plan --platform auto` | exit 0; resolved `macos`, targets `codex`, `claude`, `dsh`; MCP `everything` rendered for all three targets |
| `skillferry doctor` before apply | exit 2; expected safe drift in the empty fake homes |
| `skillferry apply --yes` | exit 0; recoverable backup and ledger created below the isolated state directory |
| `skillferry doctor` after apply | exit 0; `Changes: none` and no conflicts |
| `dsh --version` | `0.1.0-rc.8` |

The generated target files contained the exact reference server in all three
shapes: Codex `[mcp_servers.everything]` with
`@modelcontextprotocol/server-everything`, Claude
`mcpServers.everything` with the same `npx` args, and DSH `mcp-everything` using
`@deepseek-ai/dsh-mcp-client`, `serverName: everything`, and the same args.

### DSH composed config and Web/MCP startup

`dsh --profile web --dump-config` exited 0 and included:

```text
- id: mcp-everything
  name: '@deepseek-ai/dsh-mcp-client'
  config:
    serverName: everything
    args:
      - '-y'
      - '@modelcontextprotocol/server-everything'
```

The Web process was started with the isolated environment and
`dsh --profile web --no-open --host 127.0.0.1 --port 41873`. The process-level
evidence was:

```text
Starting default (STDIO) server...
dsh web: http://127.0.0.1:41873
HTTP root probe: 200
```

The running process tree contained the DSH Web process, its
`npm exec @modelcontextprotocol/server-everything` child, and the resulting
`mcp-server-everything` Node process. This verifies that the rendered MCP
entry was loaded and started, rather than only appearing in a file. The first
attempt inside the command sandbox correctly failed closed with
`listen EPERM`; the same isolated command was rerun in system context because
the sandbox forbids local socket listeners. This was an execution-environment
restriction, not a SkillFerry or DSH configuration error.

The DSH session was stopped with Ctrl-C. Post-stop checks confirmed the
41873 listener was absent, the HTTP probe could not connect, and no process
whose command or working tree belonged to this temporary DSH/MCP run
remained. No LLM request was made; this supplement verifies composed config,
MCP child startup, Web HTTP serving, and cleanup only.

## 9. Repository gates (2026-08-20)

Run from the same macOS checkout at the baseline above:

```text
/opt/anaconda3/bin/python -m pytest
81 passed, 3 skipped

/opt/anaconda3/bin/python -m ruff check .
All checks passed!

/opt/anaconda3/bin/python scripts/audit_public_tree.py .
Public-tree audit passed

/opt/anaconda3/bin/python scripts/check_seed_skills_parity.py
Seed skill parity check passed.

/opt/anaconda3/bin/python scripts/validate_workspace.py examples/starter-workspace
[OK] workspace(codex/macos): 2 skill(s), 1 MCP server(s), 0 extension(s)
[OK] workspace(claude/macos): 2 skill(s), 1 MCP server(s), 0 extension(s)
[OK] workspace(dsh/macos): 2 skill(s), 1 MCP server(s), 0 extension(s)

/opt/anaconda3/bin/python -m build --no-isolation
Successfully built skillferry-0.1.0.tar.gz and
skillferry-0.1.0-py3-none-any.whl
```

The three skips are the explicit Windows-only NTFS junction tests in
`tests/conftest.py`; no macOS test failed. The build backend was unavailable
in the base interpreter, so Hatchling was installed only into a temporary
build-dependency directory and the build artifacts were emitted outside the
repository. No tag, Release, or PyPI publication was performed.
