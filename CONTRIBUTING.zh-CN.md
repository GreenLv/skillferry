# 贡献指南

skillferry 是一个围绕三项承诺构建的无头 CLI：**目标中立、可移植性契约、
秘密永不流动**。削弱其中任何一项的贡献都是回退，不是功能。

## 基本规则

- 引擎内无网络请求。每条命令都只在本机执行。
- 报告、日志、JSON 输出、导出或状态账本中不允许出现解析后的秘密。只允许
  引用。
- 没有证据就没有等级：在修改任何 `native`/`translated`/… 标签前，先更新
  [docs/AGENT_MATRIX.md](docs/AGENT_MATRIX.md) 与验收记录。
- 冲突从不静默。新的接管路径必须走所有权账本与 `--resolve`。
- Windows 与 macOS 验收是彼此独立的记录；CI 变绿只是自动化证据，不是原生
  验收。

## 开发循环

```console
$ python -m pip install -e ".[dev]"
$ python -m pytest          # 一切必须保持绿色
$ python -m ruff check .    # E, F, I, UP, B
$ python scripts/audit_public_tree.py .
$ python scripts/check_seed_skills_parity.py
$ python scripts/validate_workspace.py examples/starter-workspace
```

任何影响行为的改动都需要测试；安全相关行为需要负向测试（禁止的文件、
软链接、路径穿越、秘密泄露）。

## 新增适配器

在 [src/skillferry/adapters/base.py](src/skillferry/adapters/base.py) 实现
`Adapter` 接口（资产落点、等级推导、MCP 渲染），在
`src/skillferry/adapters/registry.py` 注册，为渲染出的文件添加形状测试，并在
矩阵中记录能力证据。没有证据的
新适配器按构造就无法进入 `native`。

## 发布清单

`release-checklist` 种子 skill 是本仓库的权威门禁清单；打任何 tag 或发布
之前先运行它。
