# Migration from codex-profile-sync

> 中文版：[迁移指南](zh-CN/MIGRATION.md)

`skillferry` is the productized successor to the private
[codex-profile-sync](https://github.com/GreenLv/codex-profile-sync) engine
(Codex-only, profile-oriented). The legacy bundle is **never modified** by
the migration; the converter reads it and writes a draft workspace.

## One-time conversion

```console
$ skillferry migrate --from codex-profile-sync <bundle-dir> --output my-workspace
  copied   skills                         skill directory migrated as-is
  converted mcp:github.env.GITHUB_PERSONAL_ACCESS_TOKEN
                                          credential value became a secret:env reference
  manual   profiles                       Codex-only named profile configs are not portable
                                          assets; review them manually or drop them
```

## What converts

| Legacy (sync.toml bundle) | Workspace result |
| --- | --- |
| `skills/` (when `skills.enabled = true`) | Safety-audited `skills/` copy; symlinks, sensitive/runtime files, detected credentials, and opaque binaries are refused; `default_targets` covers all three targets |
| `config/common.toml` `[mcp_servers.<name>]` (except `node_repl`) | `mcp/servers.toml` entries; literal env values become `secret:env/<KEY>` references |
| — | `instructions/global.md` stub, empty extension manifest, overlay skeletons |

## What does not convert (deliberate)

- **Named profiles** (`*.config.toml`): Codex-only config shapes are not
  portable assets; the report lists them as `manual` follow-ups.
- **`node_repl`** and any Codex-owned embedded servers: protected on every
  target, never managed.
- **The legacy state ledger**: ownership restarts fresh in skillferry; the
  first `apply` on a machine with legacy-rendered files will surface
  `adopt`/conflict decisions for anything already present, which is the
  intended takeover protocol (use `--resolve` with `adopt` or `overwrite`).

## Old repository policy

The legacy repository is not deleted or modified by skillferry. Archival
guidance (README notice, rename, or archive) is a separate, explicitly
authorized step for the repository owner.
