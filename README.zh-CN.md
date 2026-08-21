# skillferry

[![CI](https://github.com/GreenLv/skillferry/actions/workflows/ci.yml/badge.svg)](https://github.com/GreenLv/skillferry/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/GreenLv/skillferry)](https://github.com/GreenLv/skillferry/releases)
[![PyPI](https://img.shields.io/pypi/v/skillferry)](https://pypi.org/project/skillferry/)
[![License](https://img.shields.io/github/license/GreenLv/skillferry)](LICENSE)

[English](README.md)

**你的 Agent 工作流，跨工具、跨机器可移植。**

skillferry 把一份可版本化、可提交 Git 的 workspace 定义——Skills、全局指令、
不含秘密的 MCP 连接模板——渲染成 Codex、Claude Code、DeepSeek Harness 三家的
原生配置，覆盖 macOS / Windows / Linux。它从不复制凭据或运行时状态，并且
对每项资产诚实地报告可移植性等级。

> 同步能力，不复制秘密。· 写一次 Skill，到处可跑。· 你的 Agent 能力资产，
> 不该锁在某个客户端里。

> 发布状态：`0.1.0` 是当前在 GitHub 与 PyPI 上正式发布的版本。macOS 与
> Windows 原生验收分别记录；CI 矩阵是独立的自动化门禁。详见
> [0.1.0 发布验收记录](docs/acceptance/release-0.1.0.md)、
> [适配器能力矩阵](docs/zh-CN/AGENT_MATRIX.md) 和
> [更新日志](CHANGELOG.zh-CN.md)。

## 从这里开始

| 如果你想…… | 建议阅读 |
| --- | --- |
| 先理解它解决什么问题 | [为什么需要 skillferry](#为什么需要-skillferry) 和 [核心承诺](#核心承诺) |
| 快速了解工作流程 | [30 秒演示](#30-秒演示) |
| 安装并亲自试用 | [快速开始](#快速开始) |
| 查看可移植性和损失边界 | [兼容性矩阵](#兼容性矩阵) 与 [可移植性契约](docs/zh-CN/PORTABILITY_CONTRACT.md) |
| 查看安全与所有权边界 | [安全边界](#安全边界) 与 [安全威胁模型](docs/zh-CN/THREAT_MODEL.md) |
| 查看发布和平台证据 | [发布验收](docs/acceptance/release-0.1.0.md) 与 [文档索引](docs/zh-CN/README.md) |

## 为什么需要 skillferry

Agent 能力很容易积累，却很难安全迁移：Skills 分散在不同目录，全局指令使用
不同约定，MCP 配置形状彼此不兼容，而最方便的复制方式往往也会把凭据一起复制。

skillferry 把四条边界明确写进工作流：

1. 版本化 workspace 是事实源，Agent 配置只是渲染结果。
2. 每个适配器都必须说明自己实际能加载什么，用可移植性等级代替笼统的兼容声明。
3. Secret 引用可以跨 workspace 边界传播，但解析后的值只留在本机。
4. 所有权账本把本地编辑与生成变更变成可见冲突，而不是静默覆盖。

## 核心承诺

| 优先级 | 承诺 | 实际含义 |
| --- | --- | --- |
| 1 | **一份 workspace，多种目标** | `workspace.toml` 与显式声明的资产渲染成 Codex、Claude Code、DSH 各自的配置形状。 |
| 2 | **可移植性分级** | `native`、`translated`、`degraded`、`manual`、`unsupported` 说明加载行为与已知损失。 |
| 3 | **秘密不迁移** | workspace 只保存 `secret:env/...` 或 `secret:file/...` 引用，解析后的值只进入本机目标配置。 |
| 4 | **应用可回滚且尊重冲突** | 哈希、备份、脱敏副本、回滚和显式 `--resolve` 保护手工编辑的文件。 |
| 5 | **边界也是产品的一部分** | 会话、记忆、认证状态、任意插件和不支持的传输方式留在 v1 范围之外，不暗示它们可以无损迁移。 |

## 30 秒演示

```console
$ skillferry import --from codex --output ~/workspaces/demo   # ① 导入两个 skill + 一个 MCP
$ export GITHUB_PERSONAL_ACCESS_TOKEN=...                     # ② Token 只留在本机
$ skillferry plan --workspace ~/workspaces/demo               # ③ 三个 Agent 的等级一目了然
SKILL release-checklist
  codex   native
  claude  native
  dsh     native
MCP github
  codex   translated   secret resolved from local env
  claude  translated   secret resolved from local env
  dsh     translated   inserted as dsh-mcp-client entries in the profile cordis.patch.yml
$ skillferry apply --workspace ~/workspaces/demo              # ④ 一份 workspace 渲染三家
$ skillferry doctor --workspace ~/workspaces/demo             # ⑤ 零漂移
$ skillferry export ~/workspaces/public                       # 证明：公共副本永远无秘密
Exported 15 file(s) to ~/workspaces/public
No secret references were expanded; no secrets were copied.
```

五拍流程（导入 → Secret 引用 → 分级 → 应用 → 无秘密导出）由测试套件在 CI
中持续演练（`tests/test_plan_apply.py`、`tests/test_importers.py`、
`tests/test_export_audit.py`），并分别在 macOS 与 Windows 原生环境中演练；
详细记录见 [macOS](docs/acceptance/macos-native.md) 与
[Windows](docs/acceptance/windows-native.md)。

## 前后对比

| Before | After |
| --- | --- |
| 每个工具、每台机器重新写一遍 Skill、规则和 MCP 配置 | 一份 `workspace.toml` + 资产，`git pull` + `skillferry apply` |
| Token 被复制进配置、随后被提交进 Git | `secret:env/NAME` 引用；真实值由每台机器本地提供 |
| 只报"同步成功"，不知道丢失了什么 | `plan` 对每项资产输出 `native / translated / degraded / manual / unsupported` 与损失说明 |
| 同步工具悄悄覆盖手改内容 | 逐路径哈希账本：本地改动变成冲突（exit 3），绝不静默覆盖 |

真实需求证据：跨机器丢失 Skills/配置是官方 issue 中反复出现的需求
（[claude-code #36693](https://github.com/anthropics/claude-code/issues/36693)、
[#69231](https://github.com/anthropics/claude-code/issues/69231)、
[codex #26691](https://github.com/openai/codex/issues/26691)），MCP 客户端配置
分裂也是开放的标准化痛点（[SEP-2633](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2633)、
[MCP IG #2761](https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/2761)）。
这些链接说明需求背景，不替代本仓库自己的功能或兼容性证据。

## 快速开始

```console
$ pipx install skillferry==0.1.0
$ skillferry init my-workspace && cd my-workspace
# 放入 skills/**，编辑 instructions/global.md 与 mcp/servers.toml
$ skillferry plan          # 先读等级与冲突
$ skillferry apply         # 先备份、只写自己拥有的路径
$ skillferry doctor        # exit 0 = 完全同步
```

如果不需要固定版本，可以省略版本号。当前公开版本是 `0.1.0`，精确的发布身份
与验收边界见 [0.1.0 发布验收记录](docs/acceptance/release-0.1.0.md)。

`plan` 永不落盘；存在冲突时 `apply` 拒绝执行。`doctor` 退出码：`0` 同步、
`1` 出错、`2` 可安全应用的漂移、`3` 冲突；`plan` 与 `apply` 遇到冲突返回
`3` 且不写任何文件。冲突需要人工决策
（`--resolve <id>=adopt|overwrite|keep-local`）。

## 兼容性矩阵

等级由各适配器依据有证据支撑的能力表产出（[docs/zh-CN/AGENT_MATRIX.md](docs/zh-CN/AGENT_MATRIX.md)），
没有验证过的加载路径绝不标 `native`。

| 资产 | Codex | Claude Code | DeepSeek Harness |
| --- | --- | --- | --- |
| Skills（SKILL.md 目录） | `native` — `~/.agents/skills/` | `native` — `~/.claude/skills/`（[官方文档](https://code.claude.com/docs/en/skills)） | `native` — `~/.agents/skills/` |
| 全局规则 | `native` — `~/.codex/AGENTS.md` 标记块 | `translated` — `~/.claude/CLAUDE.md` 标记块 | `native` — `$DSH_HOME/AGENTS.md` 标记块 |
| MCP（stdio） | `translated` — `~/.codex/config.toml` 的 `[mcp_servers.<name>]`；Secret 从本机环境解析 | `translated` — 用户级 `~/.claude.json` `mcpServers`（[官方文档](https://code.claude.com/docs/en/mcp)） | `translated` — profile `cordis.patch.yml` 中的 `dsh-mcp-client` 条目 |
| MCP（http/sse） | `manual`（打印按目标的手工步骤） | `manual` | `manual` |
| 扩展/插件 | `manual` — 只声明期望状态，绝不自动安装 | `manual` | `manual` |

### 等级含义速览

`plan` 的等级是对*加载*的承诺：`native` 以目标自身格式加载、无损；
`translated` 可用，但经过备注点名的转换；`degraded` 可用，但有已知限制或
未验证行为；`manual` 只打印操作说明、不写文件；`unsupported` 不适用。
完整契约——合并顺序、冲突与退出码——见
[docs/zh-CN/PORTABILITY_CONTRACT.md](docs/zh-CN/PORTABILITY_CONTRACT.md)。

## 安全边界

安全是架构而不是文档，完整模型见
[docs/zh-CN/THREAT_MODEL.md](docs/zh-CN/THREAT_MODEL.md)。可机器验证的要点：

- workspace schema **在解析期拒绝字面秘密**：MCP `env` 值只允许
  `secret:env/NAME` 或 `secret:file/PATH` 引用（负向测试锁定）。
- 可共享导出（`skillferry export <目标目录>`）逐文件扫描，发现任何凭据
  形态内容即拒绝导出；引用永不展开。
- 备份为原始副本（0600、仅本地、用于精确回滚）+ **脱敏副本**（供人工查看）。
- JSON 报告与日志只含引用、永不含解析后的值。
- `[protect]` 声明 workspace 永不管理的路径；误声明在 schema 层被拒绝。
- `scripts/audit_public_tree.py` 在 CI 中对公共树执行负向审计。

## Workspace 布局

```toml
# workspace.toml —— 构造上即目标中立
schema_version = 1
[skills]                  directory = "skills"
                          default_targets = ["codex", "claude", "dsh"]
[instructions]            common = "instructions/global.md"   # marker | copy | include
[mcp]                     registry = "mcp/servers.toml"       # env 只允许 Secret 引用
[extensions]              manifest = "extensions/manifest.toml"
[overlays]                platform_dir / target_dir / host_dir  # base < target < platform < host < local
[protect]                 paths = []                          # 永不管理的声明
```

可直接运行的完整示例在
[examples/starter-workspace](examples/starter-workspace)（CI 持续校验），
附两个种子 skill：`setup-skillferry` 与 `release-checklist`。

合并序为 `base < target < platform < host < local override`：列表整体替换、
字典深合并、每个值的来源在 `plan` 中可见、冲突从不静默
（[docs/zh-CN/PORTABILITY_CONTRACT.md](docs/zh-CN/PORTABILITY_CONTRACT.md)）。

## 不是什么

skillferry 刻意做成无头 CLI。它不是全量 dotfiles 同步器（只管理显式声明的
结构化资产）、从不创建软链接或 Windows junction/reparse point（schema 层
拒绝）、没有 GUI、不切换 API
供应商、不同步会话/记忆、不承诺"任意插件无损转换"。与现有工具的诚实对比
（包括可写与不可写的声明边界）见
[docs/zh-CN/COMPARISON.md](docs/zh-CN/COMPARISON.md)。

## 适配器开发

新增一个目标成本有界：实现 `src/skillferry/adapters/base.py` 的接口（资产
落点、有证据的等级、MCP 渲染），并在 `src/skillferry/adapters/registry.py`
注册。每个等级需要达到的证据
门槛见 [docs/zh-CN/AGENT_MATRIX.md](docs/zh-CN/AGENT_MATRIX.md)。

## 从 codex-profile-sync 迁移

`skillferry migrate --from codex-profile-sync <bundle> --output <dir>` 把旧
bundle 的 skills 与 MCP 声明转换成 draft workspace（凭据值转为
`secret:env/...` 引用；旧 bundle 永不改动）。详见
[docs/zh-CN/MIGRATION.md](docs/zh-CN/MIGRATION.md)。

## 文档地图

[docs/](docs/) 目录的完整索引见 [docs/zh-CN/README.md](docs/zh-CN/README.md)。按角色
出发：

| 角色 | 从这里开始 |
| --- | --- |
| 所有人 | [docs/zh-CN/PORTABILITY_CONTRACT.md](docs/zh-CN/PORTABILITY_CONTRACT.md) —— 等级、合并顺序、冲突与退出码 |
| 安全评审 | [docs/zh-CN/THREAT_MODEL.md](docs/zh-CN/THREAT_MODEL.md) + [SECURITY.zh-CN.md](SECURITY.zh-CN.md) |
| 贡献者 | [CONTRIBUTING.zh-CN.md](CONTRIBUTING.zh-CN.md) + [docs/zh-CN/AGENT_MATRIX.md](docs/zh-CN/AGENT_MATRIX.md) |
| 对比替代方案 | [docs/zh-CN/COMPARISON.md](docs/zh-CN/COMPARISON.md) |
| 旧版迁移 | [docs/zh-CN/MIGRATION.md](docs/zh-CN/MIGRATION.md) |
| 发布与平台证据 | [docs/acceptance/release-0.1.0.md](docs/acceptance/release-0.1.0.md) · [docs/acceptance/macos-native.md](docs/acceptance/macos-native.md) · [docs/acceptance/windows-native.md](docs/acceptance/windows-native.md)（英文证据记录） |

英文文档入口为 [README.md](README.md)，英文更新历史见 [CHANGELOG.md](CHANGELOG.md)；
中文更新历史见 [CHANGELOG.zh-CN.md](CHANGELOG.zh-CN.md)。

## 路线图

- **A（0.1.0）**：可移植内核——skills/rules/MCP 渲染、等级、所有权账本、
  import/export/migrate、三平台 × Python 3.11–3.13 CI。
- **B**：Gemini CLI 适配器（v1.x 首位）、lockfile/溯源记录。
- **C**：团队层（`scope/team` overlay）、SSH/远程目标。
- **D**：随 SKILL.md/mcp.json 标准收敛，成为参考实现。

## 许可

Apache-2.0。见 [LICENSE](LICENSE)。
