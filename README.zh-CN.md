# Relay Rules（接力规则）

[![跨平台测试](https://github.com/liyuhao957/relay-rules/actions/workflows/test.yml/badge.svg)](https://github.com/liyuhao957/relay-rules/actions/workflows/test.yml)

[English](./README.md) | 简体中文

**让 Claude Code 和 Codex 共用项目规则：默认只增加 3 个文件，只有一份事实源，不再安装一整套工作流框架。**

Relay Rules 只保留真正需要两个工具共同遵守的约定，不接管你的仓库：

- **默认极小。** 空项目只增加 3 个文件。
- **遵循原生机制。** Codex 读取 `AGENTS.md`，Claude Code 通过 `CLAUDE.md` 导入它。
- **可以完整撤销。** 原有规则不会丢失，重复更新结果一致，卸载只处理 Relay 管理的内容。
- **跨平台一致。** macOS、Linux、Windows 的薄入口共用同一个 Python 核心。

## 会增加什么

默认的 `--profile core --agents both` 安装结果是：

```text
AGENTS.md              Relay Rules 受管块
CLAUDE.md              受管的 @AGENTS.md 导入
.relay/manifest.json   只含相对路径的所有权清单
```

项目已有的 `AGENTS.md`、`CLAUDE.md` 内容会保留。Relay Rules 只拥有标记之间的文字，不拥有整个文件，也不接管任何 agent 配置目录。

可选的 `standard` profile 会为每个选中的 agent 增加 3 个聚焦技能，除此之外不安装其他内容。

## 快速开始

只需克隆一次 Relay Rules：

```bash
git clone https://github.com/liyuhao957/relay-rules.git
```

macOS / Linux：

```bash
/path/to/relay-rules/scripts/install-rules.sh --target /path/to/project
```

Windows PowerShell：

```powershell
& "C:\path\to\relay-rules\scripts\install-rules.cmd" --target "C:\path\to\project"
```

Windows 命令提示符：

```bat
"C:\path\to\relay-rules\scripts\install-rules.cmd" --target "C:\path\to\project"
```

更新仍然运行对应平台的同一条命令。两种入口都调用同一个 Python CLI，行为幂等，不需要判断该用 `--force` 还是 `--upgrade`。

增加 `--dry-run` 可以只看计划、不写文件：

```bash
/path/to/relay-rules/scripts/install-rules.sh --target /path/to/project --dry-run
```

Windows 把 `install-rules.sh` 换成 `install-rules.cmd` 即可。

默认参数是 `--profile core --agents both`。也可以只面向一个工具：

```bash
scripts/install-rules.sh --target /path/to/project --agents codex
scripts/install-rules.sh --target /path/to/project --agents claude
```

Windows 使用 `scripts\install-rules.cmd`，其余参数完全相同。

## 选择 profile

`core` 是默认方案，只安装共享规则、清单和上面的 Claude 导入。

`standard` 额外安装 3 个按需加载的技能，分别用于实现、审查和发布安全：

```bash
scripts/install-rules.sh --target /path/to/project --profile standard
```

Windows 使用 `scripts\install-rules.cmd`，`--profile` 的取值相同。

Claude 的技能位于 `.claude/skills/`，Codex 的技能位于 `.agents/skills/`；本仓库只维护一份规范源，安装时按工具分发。

## 检查与卸载

`doctor` 完全只读：

```bash
scripts/validate-installed-project.sh /path/to/project
```

```powershell
.\scripts\validate-installed-project.cmd "C:\path\to\project"
```

卸载只移除受管块、清单和可选的 Relay 技能：

```bash
scripts/uninstall-rules.sh --target /path/to/project
```

```powershell
.\scripts\uninstall-rules.cmd --target "C:\path\to\project"
```

项目自己的规则、设置、Hook 和技能都不会被动到。

## 从 0.3.x 迁移

正常安装命令会识别 `.agent/rules-kit.json` 并自动迁移。动任何文件前，它先把旧版受管状态完整备份到：

```text
.rules-kit/backups/relay-migrate-<timestamp>/
```

随后恢复旧安装器记录的安装前文件，移除已知的 Relay Hook 和旧文件，保留无关的 Claude/Codex 配置，再安装所选的 0.4 profile。以前适配过的项目文档留在迁移备份里供查阅。如果 Hook 配置 JSON 已损坏，迁移会在写入前失败，不制造半迁移状态。

## 测试

规范测试入口跨平台，并且默认按改动选套件：

```bash
python tests/run.py                    # 从当前 diff 选择相关套件
python tests/run.py --suite lifecycle  # 明确运行一个套件
python tests/run.py --all              # 完整回归
```

`tests/run.sh` 和 `tests\run.cmd` 是等价的便捷入口。只有共享 CLI 这类核心改动会自动全量；文档、薄入口、模板和单个测试只跑映射到的检查。CI 会在 Windows、macOS、Linux 上分别使用 Python 3.9 和 3.13 执行完整回归。

## 为什么改成这样

集成方式同时遵循两个产品的原生加载机制：

- Claude Code 官方文档说明了精简 `CLAUDE.md`、`@AGENTS.md` 导入，以及 `.claude/skills/` 项目技能：[memory](https://code.claude.com/docs/en/memory)、[skills](https://code.claude.com/docs/en/skills)、[plugins](https://code.claude.com/docs/en/plugins)。
- Codex 原生读取分层 `AGENTS.md`，并从 `.agents/skills/` 发现仓库技能：[AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)、[skills](https://learn.chatgpt.com/docs/build-skills)。

这次也参考了仍在维护的类似项目：[Ruler](https://github.com/intellectronica/ruler) 的跨 agent 规则分发、[OpenSpec](https://github.com/Fission-AI/OpenSpec) 的可选 profile、[Spec Kit](https://github.com/github/spec-kit) 的扩展机制，以及 [Superpowers](https://github.com/obra/superpowers) 随客户端成熟而转向原生技能发现的做法。

Relay Rules 不再默认安装 Hook、候选收件箱、漂移扫描器、生成式项目地图或强制交接文档。这些机制对普通仓库工作的上下文和维护成本高于收益。确有用途的工具专属自动化，应该由具体项目自行添加，或独立打包成 Claude/Codex 插件，而不是塞进所有项目的默认路径。

## 环境要求

- Python 3.9 或更高版本
- Windows：PowerShell 或命令提示符；Python 可通过 `python` 或 `py` 启动
- macOS / Linux：便捷入口需要 Bash
- 无第三方 Python 包或运行时依赖

Windows 普通安装不创建符号链接，不需要管理员权限或开发者模式。只有迁移时恢复的旧安装前备份本身包含符号链接，才会受到 Windows 符号链接权限限制。

## 许可证

[MIT](./LICENSE)
