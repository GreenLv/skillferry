# 文档索引（中文）

skillferry 的仓库文档分为三处：根目录的双语 README
（[README.md](../../README.md) / [README.zh-CN.md](../../README.zh-CN.md)）、
本 `docs/` 目录，以及根目录的
[CONTRIBUTING.md](../../CONTRIBUTING.md) /
[SECURITY.md](../../SECURITY.md) / [CHANGELOG.md](../../CHANGELOG.md) /
[CHANGELOG.zh-CN.md](../../CHANGELOG.zh-CN.md)。
本页是 `docs/` 树的中文入口，并按角色给出阅读顺序。

## 按角色阅读

| 你的身份 | 阅读顺序 |
| --- | --- |
| 评估是否采用 skillferry 的新用户 | [README.zh-CN.md](../../README.zh-CN.md) → [可移植性契约](PORTABILITY_CONTRACT.md) → [与现有工具对比](COMPARISON.md) |
| 安全评审 / 谨慎用户 | [安全威胁模型](THREAT_MODEL.md) → [SECURITY.zh-CN.md](../../SECURITY.zh-CN.md) → 英文验收记录 |
| 贡献者 / 适配器作者 | [CONTRIBUTING.zh-CN.md](../../CONTRIBUTING.zh-CN.md) → [适配器能力矩阵](AGENT_MATRIX.md) |
| codex-profile-sync 老用户 | [迁移指南](MIGRATION.md) |

## 文档清单

| 文档 | 内容 |
| --- | --- |
| [PORTABILITY_CONTRACT.md](PORTABILITY_CONTRACT.md) 可移植性契约 | 五个等级的含义、overlay 合并顺序、所有权与冲突规则、秘密处理、退出码 |
| [THREAT_MODEL.md](THREAT_MODEL.md) 安全威胁模型 | 资产与信任边界、设计上拒绝的九类威胁、v1 已承认的限制、范围外事项 |
| [AGENT_MATRIX.md](AGENT_MATRIX.md) 适配器能力矩阵 | 各目标的资产落点（加载路径），以及每个等级背后的证据 |
| [COMPARISON.md](COMPARISON.md) 与现有工具对比 | 实测的生态对比；对竞品哪些能写、哪些不能写 |
| [MIGRATION.md](MIGRATION.md) 迁移指南 | 从 codex-profile-sync bundle 的一次性转换 |
| [发布验收记录](../acceptance/release-0.1.0.md) | 0.1.0 的发布身份、门禁结果、发布后回读与证据边界 |
| [英文验收记录](../acceptance/macos-native.md) | macOS 真机完整演练的证据记录 |
| [英文验收记录](../acceptance/windows-native.md) | Windows 真机完整演练的证据记录 |

验收记录刻意保持英文：它们是带时间戳的命令实录与机器证据，不是需要翻译
的叙述性文字。

## 英文原版

每个核心中文文档对应的英文原版位于 `docs/` 同级目录、文件名相同，两份保持
同步。验收记录是英文原始证据；更新历史另见根目录的
[CHANGELOG.zh-CN.md](../../CHANGELOG.zh-CN.md)。若发现翻译差异，以英文原版
和验收记录中的事实为准，并欢迎提交 issue。
