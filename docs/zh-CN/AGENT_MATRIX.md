# 适配器能力证据矩阵（Adapter Capability Evidence Matrix）

`skillferry plan` 输出的每个等级都必须有本文件记录的证据支撑。**适配器
绝不为未测试的行为声称 `native`。** 证据来源：(E1) 作者本人的 macOS 原生
验收（[acceptance/macos-native.md](../acceptance/macos-native.md)）、(E2)
作者已发布的 codex-profile-sync 引擎与 codex-sync 脚本、(E3) 官方产品文档
（下文链接）、(E4) CI 测试套件（形状断言，非产品行为），以及 (E5) 独立的
Windows 原生验收记录（[acceptance/windows-native.md](../acceptance/windows-native.md)）。

## 加载路径（各资产落在哪里）

| 目标 | Skills | 全局规则 | MCP（stdio） |
| --- | --- | --- | --- |
| Codex | `~/.agents/skills/<name>/`（E1/E5：与 DSH 共享，自动发现） | `~/.codex/AGENTS.md`，标记块分隔（E2：与作者的 `manage-global-agents.py` 同机制） | `~/.codex/config.toml` `[mcp_servers.<name>]` command/args/env（E2/E3：Codex 配置格式） |
| Claude Code | `~/.claude/skills/<name>/`（E3：[个人 skills 文档](https://code.claude.com/docs/en/skills)） | `~/.claude/CLAUDE.md`，标记块原样渲染（E3：CLAUDE.md 是纯 markdown；Claude 没有受管块概念） | 用户级 `~/.claude.json` `mcpServers`（E3：[MCP 文档](https://code.claude.com/docs/en/mcp)——用户级服务器存储在 `~/.claude.json`）；项目级 `.mcp.json` 不在 v1 管理范围 |
| DSH | `~/.agents/skills/<name>/`（E1/E5：原生自动加载，已验证） | `$DSH_HOME/AGENTS.md`，标记块（E2：`manage-global-agents.py` 的 dsh 目标） | `$DSH_HOME/profiles/<profile>/cordis.patch.yml`，`dsh-mcp-client` 插入条目（E2：`apply-dsh-mcp.py`；E1/E5：真实 profile 已验证） |

## 等级推导

### Skills

三个目标都是 `native`。SKILL.md frontmatter（`name`、`description`）是共享
标准；skillferry 专属字段（`targets`、`version`）会被 Agent 忽略，因此无损。

证据：E1（Codex/DSH）、E3（Claude 个人 skills 目录与 frontmatter 格式）、
E4（`test_apply_creates_all_three_target_shapes`）。

### 全局规则（策略 × 目标）

| 策略 | Codex | Claude Code | DSH |
| --- | --- | --- | --- |
| `marker`（默认） | `native`（E2） | `translated` — CLAUDE.md 没有受管块概念；块原样追加（E3） | `native`（E2） |
| `include` | `translated` — 渲染为 AGENTS.md 中的 `@path` 导入 | `translated` — CLAUDE.md 中的 `@path` 导入 | `degraded` — DSH AGENTS.md 的导入行为**未验证** |
| `copy` | `degraded` — 整体替换 AGENTS.md；未受管内容冲突 | `degraded` | `degraded` |

### MCP

| 目标 | stdio 等级与备注 | http/sse |
| --- | --- | --- |
| Codex | 有秘密时 `translated`（"secret resolved from local env"），否则 `native`；`~/.codex/config.toml` 中小节级所有权 | `manual` |
| Claude Code | `translated` — 用户级 `.claude.json`；文件以规范化 JSON 格式重写（其余键全部保留）；项目级 `.mcp.json` 不在 v1 管理范围 | `manual` |
| DSH | `translated` — profile patch 块中的 `dsh-mcp-client` 插件条目 | `manual` |

证据：Codex 与 DSH 格式为 E2/E1；Claude 的 `.claude.json` `mcpServers`
形状为 E3；E4 断言渲染出的确切形状。

### 扩展 / 插件

v1 中所有目标都是 `manual`。skillferry 声明期望状态（来源 + 固定版本）但
从不安装或升级扩展。按目标打印操作说明
（`src/skillferry/adapters/*.py` extension_instructions）。

## 明确不可声称的

- **"Claude Code 原生扫描 `~/.agents/skills/`"** —— 未验证、不声称；Claude
  skills 渲染到 `~/.claude/skills/`。
- **"DSH 支持 AGENTS.md 的 `@path` 导入"** —— 未验证；`include` 策略下评为
  `degraded`。
- **"任意 http/sse MCP 服务器可自动配置"** —— v1 只渲染 `stdio`；其余一律
  `manual` 并打印按目标说明。
- **Windows 上的原生证据** —— 独立 Windows 验收记录已通过 v1 生命周期与
  DSH 进程检查，明确的跳过项和限制见该记录。`windows-latest` 上的 CI 变绿
  仍只是自动化形状证据，不能替代原生记录。

## 如何修改一个等级

1. 在 [acceptance/macos-native.md](../acceptance/macos-native.md)（或
   Windows 记录）中记录新证据：日期、命令、观察到的输出。
2. 更新本表与适配器的等级函数。
3. 新增或更新断言渲染形状的回归测试。
