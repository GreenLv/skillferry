# Comparison with existing tools

Measured 2026-08 via the GitHub API (stars) and repository activity
(last push). "Active" = pushed within roughly the last 3 months at
measurement time; the table is a point-in-time measurement, not a trend
claim. Competitor capabilities are stated only where their READMEs or the
cited community threads make them explicit; claims we cannot verify are
listed as not-verified.

## Adjacent categories (proof of demand, not direct competitors)

| Category | Example | Measurement |
| --- | --- | --- |
| Skill content | anthropics/skills | ~170k★, active |
| Multi-agent config/API switcher | farion1231/cc-switch | ~128k★, active |
| GUI skill manager | xingkongliang/skills-manager | ~3.8k★, active |

## Direct headless niche: cross-agent config sync

| Repo | Stars (2026-08) | Status | Notable limitation (from their own materials / community reports) |
| --- | --- | --- | --- |
| gotalab/skillport | 408 | slowed | — |
| amtiYo/agents | 85 | active | — |
| athola/skrills | 69 | active | — |
| nicepkg/vsync | 55 | **no push for ~7 months** | setup manual; npm ecosystem full of dead duplicates |
| 2ue/ccman | 52 | — | — |
| xiaolai/cc-suite | 41 | — | — |
| slash9494/ai-config-sync-manager | 28 | — | two-tool scope |
| miniLV/Plexus | 27 | stalled | local one-shot, no cross-machine |
| Leoyang183/sync-agents-settings | 8 | stalled | — |
| berlinguyinca/ai-sync | 37 | — | Claude-only |
| Vek-Sync | 3 | — | MCP-only |
| cortesi/agentsmd | 9 | — | rules-only |

**Pattern**: the headless "sync agent config" niche is a graveyard of
near-identical, mostly single-agent or rules-only tools under ~500 stars.
That is the discovery/trust problem any new entrant must solve — and it is
why skillferry leads with the portability contract and the security boundary
rather than "supports N agents".

## What we can write vs. what we cannot write

**We can write (evidence anchors):**

- Codex and DSH both natively discover `~/.agents/skills/` — verified by the
  author's macOS acceptance ([acceptance/macos-native.md](acceptance/macos-native.md)).
- The workspace format is target-neutral; each agent is only a render
  target ([PORTABILITY_CONTRACT](PORTABILITY_CONTRACT.md)).
- Secret references are schema-enforced; `export --shareable` never expands
  them; this is machine-verified in CI, not documented intent.
- Every grade is derived from the capability table
  ([AGENT_MATRIX](AGENT_MATRIX.md)), including honest `manual`/`degraded`
  labels.

**We cannot write (not verified — do not claim):**

- "Claude Code natively scans `~/.agents/skills/`."
- Any performance or reliability comparison of competitor tools we have not
  run (no benchmark exists in this repo).
- "Model skills always trigger" claims: community reports of skills not
  triggering are user perception, not our measurement.
- Star trends (the numbers above are a single 2026-08 snapshot).

## Explicitly not doing (v1)

GUI (the GUI segment has volume but a different shape); provider/API
switching; session/memory/history sync; dotfiles wholesale sync;
lossless arbitrary plugin conversion; "support N agents" as a headline;
SSH targets; team layer (v1.x).
