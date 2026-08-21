# 安全威胁模型（Threat Model）

skillferry 搬运的是**能力定义**——从不搬运秘密，从不搬运机器状态。本文档
列出资产、信任边界、设计上拒绝的威胁，以及明确不在范围内的事项。

## 资产与信任边界

| 层 | 内容 | 存储位置 | 敏感度 |
| --- | --- | --- | --- |
| 公共引擎（本仓库） | 代码、文档、种子 skills、starter 示例 | Git / PyPI | 公开 |
| workspace | `workspace.toml`、skills、instructions、MCP 模板、扩展清单、overlays | 用户自己的 Git 仓库 | 用户自选——schema 让*安全默认值*可强制执行 |
| 本地机器状态 | 解析后的秘密、所有权账本、备份 | `SKILLFERRY_STATE_DIR`（平台状态目录，0700/0600）与各 Agent 自己的配置目录 | 私有，绝不导出 |

解析后的秘密值**唯一**会出现的场所，是 Agent 自身读取的本地运行时配置
文件（例如 `~/.codex/config.toml`），并使用受限权限与脱敏备份。

## 设计上拒绝的威胁

1. **秘密进入 workspace。** `workspace.toml` / `mcp/servers.toml` 的 env 值
   必须匹配 `secret:env/NAME` 或 `secret:file/PATH`；任何其他内容都会在任何
   plan 构建之前于 schema 校验阶段失败
   （`src/skillferry/workspace.py`，`tests/test_workspace.py` 中的负向测试）。
   导入与迁移的 skill 树在复制前先被检查；检测到的凭据内容、运行时状态
   文件名、不透明二进制与软链接都会被拒绝，而不会被标为可移植。
2. **秘密通过导出泄露。** 可共享导出（`skillferry export <目标目录>`）逐文件
   扫描凭据形态内容并禁止软链接；对无法检查的不透明二进制拒绝导出，发现任何问题即整体拒绝，
   且永不展开引用（`src/skillferry/secrets.py`，`tests/test_export_audit.py`）。
3. **秘密通过报告/日志泄露。** `plan --json` / `doctor --json` 只输出引用；
   渲染后的值永远到不了 `public_dict()`
   （`test_env_secret_lands_only_in_local_config`）。
4. **秘密通过备份泄露。** 备份以 0600 存放在本地状态目录下，每个文本备份
   都有一份凭据脱敏副本供人工查看，原始副本保留精确回滚能力
   （`src/skillferry/io_ops.py`，`test_backups_redact_secrets`）。
5. **静默覆盖。** 每个受管路径都在本地所有权账本中做哈希跟踪。未登记的
   本地内容、被本地修改的受管内容、以及与生成条目撞名的手写条目都是冲突
   （exit 3）——只能用显式的 `--resolve ...=adopt|overwrite|keep-local`
   解决。
6. **机器状态接管。** `[protect]` 加上各适配器的受保护名称（auth、历史、
   会话、sqlite、缓存、嵌入式服务器如 Codex 的 `node_repl`）永不受管；
   schema 拒绝误声明（`tests/test_workspace.py`、`test_protected_mcp_server_never_managed`）。
7. **基于路径的攻击。** 软链接与 Windows junction/reparse point 在
   workspace、目标父目录和每次写入处都被拒绝；schema 拒绝绝对路径与 `..`；
   导入与旧版迁移在复制前拒绝类链接路径；apply 操作被限制在声明过的受管
   根目录内（`src/skillferry/io_ops.py`，`tests/test_plan_apply.py`）。
8. **本地覆盖被意外公开。** `workspace.local.toml` 被 gitignore、从导出中
   排除，其文件名也被 `scripts/audit_public_tree.py` 禁止。
9. **多目标部分失败。** apply 按目标组回滚；一个目标失败会恢复所有已写
   内容（`test_rollback_restores_targets_on_failure`）。

## v1 已承认、未完全缓解的威胁

- **workspace 内容的供应链。** skillferry 应用 workspace 声明的内容。恶意
  workspace 可以把 MCP 指向任意本地命令。缓解：可移植性等级与 `plan`
  预览是必读的；未来版本将加入签名/lockfile 溯源（路线图 B）。
- **拥有用户账户的本地攻击者。** skillferry 假定操作系统账户边界。它不会
  在静态存储上对解析后的秘密做超出文件权限的再加密；它不是秘密管理器。
- **Claude Code 的 `~/.claude.json` 是单一用户级 JSON 文件。** skillferry
  保留它不管理的每个键，但会用规范化格式重写该文件（等级备注中如实说明；
  `tests` 断言其他键存活）。备份 + 脱敏副本覆盖恢复。
- **Windows ACL 语义。** POSIX 模式位不能映射到 Windows；在 Windows 上，
  秘密以默认 ACL 落入配置文件。Windows 原生验收已通过，但该限制在单独记录中
  明确说明（[docs/acceptance/windows-native.md](../acceptance/windows-native.md)），
  不能从 macOS 或 CI 结果推断。

## 范围外

会话/记忆同步、凭据存储与轮换、秘密的网络分发、SSH 目标（v1.x）、Agent
运行时状态（信任、市场、历史）明确不是功能；`[protect]` 强制执行边界。
