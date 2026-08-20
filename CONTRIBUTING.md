# Contributing

> 中文版：[贡献指南](CONTRIBUTING.zh-CN.md)

skillferry is a headless CLI built around three promises: **target
neutrality, a portability contract, and secrets that never move**. A
contribution that weakens any of them is a regression, not a feature.

## Ground rules

- No network requests in the engine. Every command is local-only.
- No resolved secrets in reports, logs, JSON output, exports, or the state
  ledger. References only.
- No grade without evidence: update
  [docs/AGENT_MATRIX.md](docs/AGENT_MATRIX.md) and the acceptance record
  before changing any `native`/`translated`/… label.
- Conflicts are never silent. New takeover paths must go through the
  ownership ledger and `--resolve`.
- Windows and macOS acceptance stay independent records; CI greenness is
  automated evidence, not native acceptance.

## Development loop

```console
$ python -m pip install -e ".[dev]"
$ python -m pytest          # everything must stay green
$ python -m ruff check .    # E, F, I, UP, B
$ python scripts/audit_public_tree.py .
$ python scripts/check_seed_skills_parity.py
$ python scripts/validate_workspace.py examples/starter-workspace
```

Every change that affects behavior needs tests; security-relevant behavior
needs negative tests (prohibited files, symlinks, path traversal, secret
leakage).

## Adding an adapter

Implement the `Adapter` interface in
[src/skillferry/adapters/base.py](src/skillferry/adapters/base.py) (asset
locations, grade derivations, MCP rendering), register it in
`adapters/registry.py`, add shape tests for the rendered files, and record
the capability evidence in the matrix. A new adapter without evidence stays
out of `native` by construction.

## Release checklist

The `release-checklist` seed skill is the canonical gate list for this repo;
run it before any tag or publish.
