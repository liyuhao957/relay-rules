# Relay Rules（接力规则）

[![跨平台测试](https://github.com/liyuhao957/relay-rules/actions/workflows/test.yml/badge.svg)](https://github.com/liyuhao957/relay-rules/actions/workflows/test.yml)

[English](./README.md) | 简体中文

**一条命令，2 个文件，一套规则，同时给 Claude Code 和 Codex 使用。**

Relay Rules 现在只做一件事：把同一份精简开发规则放到两个 coding agent 都能读取的位置。没有安装等级、agent 选择、Hook、后台服务、生成式项目地图或第三方依赖。

## 安装

只需克隆一次 Relay Rules：

```bash
git clone https://github.com/liyuhao957/relay-rules.git
```

然后进入需要安装规则的项目目录，只运行一条命令。

macOS / Linux：

```bash
/path/to/relay-rules/scripts/install-rules.sh
```

Windows PowerShell：

```powershell
& "C:\path\to\relay-rules\scripts\install-rules.cmd"
```

Windows 命令提示符：

```bat
"C:\path\to\relay-rules\scripts\install-rules.cmd"
```

这就是完整安装过程。以后 Relay Rules 有更新，仍然运行同一条命令；首次安装和更新是同一个幂等操作。

如果不想进入目标项目目录，可以增加 `--target`：

```bash
/path/to/relay-rules/scripts/install-rules.sh --target /path/to/project
```

增加 `--dry-run` 可以只预览改动，不写任何文件。

## 会增加什么

空项目固定增加 2 个文件：

```text
AGENTS.md              Codex 直接读取的共享规则
CLAUDE.md              Claude Code 使用的 @AGENTS.md 导入
```

项目已有的 `AGENTS.md` 和 `CLAUDE.md` 内容会保留。Relay Rules 只维护标记之间的文字，不拥有整个文件。项目自己的规则写在标记之外，更新和卸载都不会碰它们。

这份共享规则主要要求两个 agent：

- 重要判断以当前代码、配置、测试和工具输出为准；
- 控制改动范围，保留用户无关的本地修改；
- 验证受影响的行为，并如实说明实际检查结果；
- 推送、发布、删除等重要外部动作前确认准确范围。

Relay Rules 不会让 Claude Code 和 Codex 共享聊天记录或私有记忆，它只让两者遵守同一份书面工作约定。

## 检查与卸载

在已安装的项目目录中，只读检查安装状态：

```bash
/path/to/relay-rules/scripts/validate-installed-project.sh
```

Windows PowerShell：

```powershell
& "C:\path\to\relay-rules\scripts\validate-installed-project.cmd"
```

只移除 Relay 管理的内容：

```bash
/path/to/relay-rules/scripts/uninstall-rules.sh
```

```powershell
& "C:\path\to\relay-rules\scripts\uninstall-rules.cmd"
```

项目自己的规则、设置、Hook 和技能都不会被删除。

## 更新旧版安装

正常运行安装命令时，也会自动简化以前的 Relay Rules 安装：

- `0.4.x` 会收敛成同样的 2 个文件。旧 manifest 和以前由 Relay Rules 安装的可选技能会被移除，用户自己的技能会保留。
- `0.3.x` 会先备份到 `.rules-kit/backups/relay-migrate-<timestamp>/`，再移除已知的 Relay Hook 和旧文件；能够找到安装前文件时会恢复它们，同时保留无关的 Claude/Codex 配置。

如果旧 Hook 配置的 JSON 已损坏，迁移会在写入前停止，不留下半迁移状态。

## 为什么这样设计

集成方式只使用两个产品的原生规则机制：

- Claude Code 通过精简 `CLAUDE.md` 和 `@AGENTS.md` 导入项目规则：[官方 memory 文档](https://code.claude.com/docs/en/memory)。
- Codex 原生读取分层 `AGENTS.md`：[官方 AGENTS.md 文档](https://learn.chatgpt.com/docs/agent-configuration/agents-md)。

跨 agent 分发规则的思路也参考了仍在维护的 [Ruler](https://github.com/intellectronica/ruler)，但 Relay Rules 只保留其中最有用的小型规则同步，不再叠加另一套工作流框架。

## 测试

```bash
python tests/run.py
python tests/run.py --all
```

CI 会在 Windows、macOS、Linux 上分别使用 Python 3.9 和 3.13 执行完整测试。Windows 任务还会直接运行 PowerShell 和命令提示符入口。

## 环境要求

- Python 3.9 或更高版本
- Windows：PowerShell 或命令提示符；Python 可通过 `python` 或 `py` 启动
- macOS / Linux：便捷入口需要 Bash
- 不需要第三方 Python 包

Windows 普通安装不需要管理员权限、开发者模式或符号链接。

## 许可证

[MIT](./LICENSE)
