# 从 codex-profile-sync 迁移（Migration）

`skillferry` 是私有 [codex-profile-sync](https://github.com/GreenLv/codex-profile-sync)
引擎（仅 Codex、面向 profile）的产品化后继。旧 bundle **永不被迁移修改**；
转换器只读它，并写出一份 draft workspace。

## 一次性转换

```console
$ skillferry migrate --from codex-profile-sync <bundle-dir> --output my-workspace
  copied   skills                         skill directory migrated as-is
  converted mcp:github.env.GITHUB_PERSONAL_ACCESS_TOKEN
                                          credential value became a secret:env reference
  manual   profiles                       Codex-only named profile configs are not portable
                                          assets; review them manually or drop them
```

## 转换什么

| 旧（sync.toml bundle） | workspace 结果 |
| --- | --- |
| `skills/`（当 `skills.enabled = true`） | 经过安全审计的 `skills/` 副本；软链接、敏感/运行时文件、检测到的凭据与不透明二进制会被拒绝；`default_targets` 覆盖三个目标 |
| `config/common.toml` `[mcp_servers.<name>]`（除 `node_repl`） | `mcp/servers.toml` 条目；字面 env 值转为 `secret:env/<KEY>` 引用 |
| — | `instructions/global.md` 占位、空扩展清单、overlay 骨架 |

## 不转换什么（有意为之）

- **命名 profile（`*.config.toml`）**：仅 Codex 的配置形态不是可移植资产；
  报告把它们列为 `manual` 后续项。
- **`node_repl`** 与任何 Codex 拥有的嵌入式服务器：在所有目标上都受保护，
  永不受管。
- **旧状态账本**：所有权在 skillferry 中重新开始；在带有旧版渲染文件的
  机器上首次 `apply` 会对已存在的内容浮出 `adopt`/冲突决策——这正是预期
  的接管协议（用 `--resolve` 配 `adopt` 或 `overwrite`）。

## 旧仓库政策

旧仓库不会被 skillferry 删除或修改。归档建议（README 公告、改名或归档）
是仓库所有者另行、显式授权的步骤。
