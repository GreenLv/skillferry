# 与现有工具对比（Comparison with Existing Tools）

2026-08 通过 GitHub API（star 数与最近 push）实测。"活跃" = 测量时大约
最近 3 个月内有过 push；表格是一次时点测量，不是趋势声明。竞品能力只在
它们自己的 README 或被引用的社区帖子里明确写到的部分才会被陈述；无法
验证的声明列为未验证。

## 相邻品类（需求证明，而非直接竞品）

| 品类 | 示例 | 测量 |
| --- | --- | --- |
| Skill 内容 | anthropics/skills | ~170k★，活跃 |
| 多 Agent 配置/API 切换器 | farion1231/cc-switch | ~128k★，活跃 |
| GUI skill 管理器 | xingkongliang/skills-manager | ~3.8k★，活跃 |

## 直接的无头细分：跨 Agent 配置同步

| 仓库 | Stars（2026-08） | 状态 | 显著限制（来自其自身材料/社区报告） |
| --- | --- | --- | --- |
| gotalab/skillport | 408 | 放缓 | — |
| amtiYo/agents | 85 | 活跃 | — |
| athola/skrills | 69 | 活跃 | — |
| nicepkg/vsync | 55 | **约 7 个月无 push** | 手工配置；npm 生态充满死掉的重复包 |
| 2ue/ccman | 52 | — | — |
| xiaolai/cc-suite | 41 | — | — |
| slash9494/ai-config-sync-manager | 28 | — | 仅两个工具 |
| miniLV/Plexus | 27 | 停滞 | 本地一次性，无跨机器 |
| Leoyang183/sync-agents-settings | 8 | 停滞 | — |
| berlinguyinca/ai-sync | 37 | — | 仅 Claude |
| Vek-Sync | 3 | — | 仅 MCP |
| cortesi/agentsmd | 9 | — | 仅规则 |

**规律**：无头"同步 Agent 配置"这个细分是大量近似雷同、大多单 Agent 或
仅规则的 ~500★ 以下工具的坟场。这是任何新入场者都必须解决的
发现/信任问题——也是 skillferry 选择用可移植性契约与安全边界打头阵、
而不是拿"支持 N 个 Agent"当头条的原因。

## 我们能写什么 vs. 不能写什么

**能写（证据锚点）：**

- Codex 与 DSH 都原生发现 `~/.agents/skills/` —— 作者 macOS 验收已验证
  （[acceptance/macos-native.md](../acceptance/macos-native.md)）。
- workspace 格式目标中立；每个 Agent 只是渲染目标
  （[PORTABILITY_CONTRACT](PORTABILITY_CONTRACT.md)）。
- 秘密引用由 schema 强制；`export --shareable` 永不展开它们；这是 CI 中
  机器验证过的，不是文档化意图。
- 每个等级都从能力表推导（[AGENT_MATRIX](AGENT_MATRIX.md)），包括诚实的
  `manual`/`degraded` 标签。

**不能写（未验证——不要声称）：**

- "Claude Code 原生扫描 `~/.agents/skills/`。"
- 任何我们没跑过的竞品性能或可靠性对比（本仓库没有基准）。
- "Model skills 一定触发"类说法：社区里 skills 不触发的报告是用户感知，
  不是我们的测量。
- Star 趋势（上面的数字是 2026-08 的单次快照）。

## v1 明确不做

GUI（GUI 细分有量级但形态不同）；供应商/API 切换；会话/记忆/历史同步；
全量 dotfiles 同步；任意插件无损转换；把"支持 N 个 Agent"当头条；SSH
目标；团队层（v1.x）。
