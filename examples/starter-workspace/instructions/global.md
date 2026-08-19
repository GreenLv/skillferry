# Portable global instructions

This file is rendered by `skillferry apply` into each agent's global
instructions file (marker-delimited blocks by default):

- Codex: `~/.codex/AGENTS.md`
- Claude Code: `~/.claude/CLAUDE.md`
- DeepSeek Harness: `$DSH_HOME/AGENTS.md`

Keep this file target-neutral: no agent-specific configuration, no machine
paths, no secrets. Agent- or OS-specific rules belong in
`overlays/target/*.toml` or `overlays/platform/*.toml`.

- Prefer correctness, authorization boundaries, and verification evidence
  over speed.
- Record completed artifacts and the next verification entry point when a
  task spans multiple sessions.
- Treat exit codes, permission boundaries, and product defects as separate
  failure classes.
