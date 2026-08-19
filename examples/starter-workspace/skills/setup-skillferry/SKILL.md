---
name: setup-skillferry
description: Install, verify, and re-apply a portable skillferry workspace across Codex, Claude Code, and DeepSeek Harness on macOS, Windows, and Linux.
---

# setup-skillferry

Set up and keep a portable agent workspace healthy with skillferry:
one versioned, Git-friendly definition of skills, global rules, and MCP
connection templates that renders into Codex, Claude Code, and DeepSeek
Harness (DSH) — without ever copying secrets or runtime state.

## When to use

- Installing skillferry on a new machine or after a reinstall.
- Adding a new agent (target) to an existing workspace.
- Diagnosing `skillferry doctor` exit codes 1/2/3.
- Deciding whether an asset belongs in the workspace or stays machine-local.

## Workflow

1. **Install**: `pipx install skillferry` (or `python -m pip install skillferry`).
   Confirm with `skillferry --version`.
2. **Create or fetch a workspace**: `skillferry init my-workspace`, or clone the
   private Git repository that holds your workspace definition.
3. **Preview**: `skillferry plan` in the workspace root. Read the portability
   grade for every asset — `native`, `translated`, `degraded`, `manual`,
   `unsupported` — and resolve every conflict before applying.
4. **Apply**: `skillferry apply`. The tool backs up every changed file
   (recoverable under the local state directory) and writes only files it
   owns, tracked in a per-path hash ledger.
5. **Verify**: `skillferry doctor` must exit 0. Exit 2 means safe drift
   (`apply`), exit 3 means a human decision (read the conflict reasons).
6. **Check in**: commit workspace changes to Git; pull on other machines and
   re-run `apply`.

## Rules of thumb

- Anything a machine owns (auth, sessions, caches, sqlite state, absolute
  machine paths) never belongs in the workspace. `[protect]` exists to make
  that refusal explicit.
- Secrets are references, not values: MCP env entries are
  `secret:env/NAME` or `secret:file/PATH`. Each machine supplies the real
  values locally; `export --shareable` never expands them.
- The workspace is target-neutral. Use `overlays/platform/*.toml` for OS
  differences and `overlays/target/*.toml` for agent differences — never
  fork the workspace per agent.

## See also

- `skillferry import --from codex|claude` to draft a workspace from an
  existing agent setup.
- `skillferry migrate --from codex-profile-sync <bundle>` for the legacy
  bundle format.
- Repo docs: `docs/AGENT_MATRIX.md`, `docs/PORTABILITY_CONTRACT.md`,
  `docs/THREAT_MODEL.md`.
