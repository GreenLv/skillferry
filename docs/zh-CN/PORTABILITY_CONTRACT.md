# 可移植性契约（Portability Contract）

`skillferry plan` 是一份承诺，不是一个进度条：对每项资产、每个目标，它都
输出等级与损失说明，所以"已应用（applied）"永远不会掩盖"已转译、但丢了
点什么"。本文档就是这份契约。

## 等级

| 等级 | 含义 |
| --- | --- |
| `native` | 以目标自身的格式与位置渲染，加载时无需转换。必须要有已验证的加载证据（[AGENT_MATRIX](AGENT_MATRIX.md)）。 |
| `translated` | 可用，但目标格式与中性格式不同；备注精确说明转换了什么（例如 "secret resolved from local env"、"block appended verbatim"）。 |
| `degraded` | 可用，但有已知限制或未验证的行为；备注会说明。 |
| `manual` | skillferry 打印按目标的手工步骤，由用户执行。 |
| `unsupported` | 对该目标不适用（例如没有规则文件的目标）。 |

`plan` 输出示例：

```
SKILL release-checklist
  codex   native
  claude  native
  dsh     native
MCP github
  codex   translated   secret resolved from local env
  claude  translated   secret resolved from local env
  dsh     translated   inserted as dsh-mcp-client entries in the profile cordis.patch.yml
```

## workspace 在构造上目标中立

- workspace 里没有任何路径是某个 Agent 的路径；每个适配器自行声明落盘
  目录（[AGENT_MATRIX](AGENT_MATRIX.md)）。
- workspace 里没有任何值是秘密；MCP env 值必须是 `secret:env/NAME` /
  `secret:file/PATH` 引用，由 schema 层强制。
- 任何机器本地事实（路径、主机名、凭据、会话状态）都不属于提交进 Git 的
  目录树；`workspace.local.toml` 是唯一的本地逃生口，已被 gitignore 并从
  导出中排除。

## Overlay 合并顺序

`base < overlays/target/<t> < overlays/platform/<p> < overlays/host/<h> < workspace.local.toml`

语义：字典深合并；**列表整体替换**（平台列表不会追加到 base 列表）。
`plan` 展示合并后的值；每个值的来源都记录在 workspace 溯源图
（provenance map）中，并在合并改变某个值时浮出。两个声明来源写入同一个
目标路径是冲突，绝不是静默的"后写者胜"。

## 所有权与冲突规则

对每个受管文件/小节/块，本地状态账本记录 skillferry 上次写入的内容
（明文、非秘密记录：文件哈希、值、秘密**引用**——绝不记录解析后的值）。

| 情形 | 行为 |
| --- | --- |
| 目标缺失 | `create` |
| 目标与源一致 | `adopt`（首次）/ 无变化 |
| 源变更、目标仍与账本一致 | `update` |
| 目标与账本和源都不同（本地改动） | `conflict` → exit 3 |
| 目标存在、未登记、与源不同 | `conflict` → exit 3 |
| 源被删除、目标仍与账本一致 | `delete` |
| 与生成的条目同名的手写条目（如 DSH `mcp-<name>`） | `conflict` → exit 3 |

每个冲突都带稳定的 `--resolve` id，决策为 `adopt`（把本地内容登记为基准）、
`overwrite`（强制用源覆盖）、`keep-local`（adopt 的别名，语义更明确）。

## 秘密处理契约

- 引用**只在 apply 时**、在本地机器上、从进程环境或本地文件解析。
- 秘密源缺失在写入任何东西之前就是一个冲突。
- 报告、JSON 输出、日志与 `export --shareable` 只含引用，绝不含解析后的值。
- 备份：原始副本（用于精确回滚）+ 脱敏副本（供人工查看），都仅存本地并带
  受限权限。
- "源变更"与"本地改动"的区分基于先前记录的引用在本机重新解析：上游新增
  一个秘密键是 `update`，而手工改动一个值则是 `conflict`
  （`test_source_change_is_update_not_conflict`、`test_local_edit_is_conflict`）。

## 退出码

`0` 同步 · `1` 出错 · `2` 可安全应用的漂移（`apply` 会修复）· `3` 冲突需
人工决策。`doctor` 使用全部四种；`plan` 在冲突时返回 `3`（不写任何东西）；
`apply` 在冲突时返回 `3`（不写任何东西）。
