# 更新日志

[English](CHANGELOG.md)

这里按时间倒序记录 skillferry 的正式公开版本。每个版本先列出影响最大的变化，
再说明实现内容，并给出精简的验证边界。`0.1.0` 是当前最新的正式发布版本。

## 未发布

### 文档

- 按“产品要解决的问题、核心承诺、发布状态、证据边界”重新组织双语 README。
- 新增中文更新日志，并同步文档索引、可移植性矩阵、对比说明、威胁模型和发布记录。
- 修正 `export` 命令的文档写法：可共享导出是 `skillferry export <目标目录>`，
  并不存在 `--shareable` 旗标（CLI 中从未实现过该旗标）。
- 当前文档整理与已经发布的 `v0.1.0` tag 分开；本节不包含运行时行为变化。

## 0.1.0 — 2026-08-20

可移植 Agent workspace 核心的首个公开版本（路线图阶段 A）。

### 重点

- 目标中立的 `workspace.toml` 一次描述 Skills、全局指令、MCP 模板、扩展、overlay
  和受保护路径，再由适配器渲染成 Codex、Claude Code、DeepSeek Harness 的配置。
- `plan` 输出有证据支撑的 `native`、`translated`、`degraded`、`manual` 或
  `unsupported` 等级，而不是把所有目标都写成无损兼容。
- Secret 引用留在 workspace 中，解析后的值只留在本机；可共享的 `export`
  会拒绝包含凭据形态内容的文件，也不会展开引用。
- 基于哈希的所有权账本、显式冲突解决、备份、脱敏副本和按目标回滚，避免静默覆盖。

### 变化

- 增加 schema v1：Skills、指令（`marker`/`copy`/`include`）、MCP registry、扩展
  manifest、正交 overlay（`base < target < platform < host < local`）和 `[protect]`
  声明。字面秘密、路径穿越、软链接、Windows junction/reparse point、不可审计二进制
  和受保护状态误声明都会被拒绝。
- 增加 CLI 工作流：`init`、`import --from codex|claude`、`plan`、`apply`、`doctor`、
  `status`、可共享的 `export` 和 `migrate --from codex-profile-sync`。
- 增加 Codex、Claude Code、DeepSeek Harness 适配器、`setup-skillferry` 与
  `release-checklist` 种子 skill，以及可运行的 `examples/starter-workspace`。
- 增加公共树审计器、workspace 校验器、双语 README 与核心文档翻译、可移植性契约、
  威胁模型、能力矩阵、对比说明、迁移指南和平台验收记录。
- 加固多行秘密扫描、导入 skill 检查、旧版迁移、部分写入回滚、备份脱敏，以及源变更
  与本地编辑的区分处理。
- 固定 `hatchling<1.32`，使发行包保持 `Metadata-Version: 2.4`，通过发布工具链的
  `twine check --strict` 门禁。

### 验证

- 发布提交为 `a78bf54d042ce1cf7eb16a056237fd32bb56d238`，带注释 tag `v0.1.0` 指向该提交。
- 发布门禁通过 81 项测试、3 项平台条件跳过、Ruff、公共树审计、种子 skill parity、
  starter workspace 校验、wheel/sdist 构建和严格包元数据检查。
- macOS 与 Windows 均完成独立原生验收。Windows 记录单独披露了 2 项需要权限的符号
  链接测试跳过、未安装 Claude Code、DSH 启动器行为和 Windows ACL 限制；这些事实不会
  被压缩成笼统的兼容性声明。
- GitHub Release `v0.1.0` 与 PyPI `skillferry==0.1.0` 均已发布；从 PyPI 新环境安装后，
  `skillferry --version` 返回 `0.1.0`。完整的发布回读见
  [发布验收记录](docs/acceptance/release-0.1.0.md)。
