# Relay Rules（接力规则）

[![跨平台测试](https://github.com/liyuhao957/relay-rules/actions/workflows/test.yml/badge.svg)](https://github.com/liyuhao957/relay-rules/actions/workflows/test.yml)

[English](./README.md) | 简体中文

**一条命令安装。Claude Code 和 Codex 共用一套真正属于这个项目的规则。**

Relay Rules 不再只是往所有仓库塞同一份通用提示词。它给两个 coding agent 一个很小的共同入口，再根据当前任务，只读取这个项目真正相关的上下文。新项目可以从空白开始成长，已经成熟并且有自己规则、文档和习惯的老项目也能安全接入。

没有安装等级、agent 选择、Hook、后台服务、生成式代码地图或第三方依赖。

## 安装

只需克隆一次 Relay Rules：

```bash
git clone https://github.com/liyuhao957/relay-rules.git
```

进入需要安装规则的项目目录，然后运行一条命令。

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

这就是完整安装过程。如果目标项目不是当前目录，可以使用 `--target`；增加 `--dry-run` 可以预览全部受管改动而不写文件：

```bash
/path/to/relay-rules/scripts/install-rules.sh --target /path/to/project --dry-run
```

不用选择 profile，也不用选择 Claude 或 Codex。每次安装固定同时支持两个 Agent，并且固定包含项目适配、按需路由和规则维护。

## 装完以后会发生什么

安装后先得到一套 `Status: pending` 的安全骨架。Claude Code 或 Codex 下次开始正式工作时，会从共享规则中看到这个状态，并被要求先检查真实仓库、完成项目适配。想立即明确触发，也只需对 Agent 说：

> 为这个项目适配 Relay Rules。

真正理解项目的是 Agent，不是安装脚本。一个零依赖的文件复制器无法只看文件名，就可靠判断产品意图、架构边界和团队约定；Relay Rules 不会伪装自己做到了这一点。

### 新项目

Agent 只记录当前确实存在的事实，尚未确定的产品方向放进 `Unverified`。以后代码产生了真实命令、模块和约定，再通过维护流程只补受影响的规则。

### 已经成熟的老项目

Agent 会先盘点已有的 `AGENTS.md`、`AGENTS.override.md`、`CLAUDE.md`、子目录规则、`.claude/rules/`、项目文档、manifest、代表性入口、测试、CI 和高风险流程，然后：

- 保留已有规则和项目文件，不覆盖、不另起一套争夺控制权；
- 已经有写得好的项目文档时，只建立指针，不复制一遍制造双份事实；
- 只记录能被当前代码、配置、测试或工具输出证明的事实；
- 区分“实际验证过的命令”和“只是找到了但没有运行的命令”；
- 为 monorepo 或不同子系统建立按任务、按路径触发的路由；
- 线上、生产、计费、发布等无法从本地证明的内容明确标成未验证，不猜。

适配阶段只修改 Relay 的项目上下文，不会顺手重写业务代码。

## 会安装什么

```text
AGENTS.md                       Codex 读取的小型共享入口
AGENTS.override.md              仅当项目原本已有 override 时加入同一入口
CLAUDE.md                       Claude Code 的 @AGENTS.md 导入，或已有的 AGENTS.md 链接
.relay/
  manifest.json                安全更新和卸载需要的所有权记录
  index.md                     项目自己维护的任务/路径路由表
  project.md                   项目自己维护的已验证上下文
  workflows/
    adapt.md                   Relay 维护的项目适配流程
    maintain.md                Relay 维护的规则维护流程
```

适配完成后，Agent 只会在确有需要时增加聚焦的 `.relay/rules/*.md`。

Relay 只拥有 `AGENTS.md`、普通 `CLAUDE.md` 和根目录已有 `AGENTS.override.md` 中带标记的受管块，以及 manifest 和两个 workflow。Relay 不会主动创建 `AGENTS.override.md`；成熟项目原本用了它时，安装器才把同一入口加进去，避免 Codex 的 override 优先级挡住 Relay。已有的 `CLAUDE.md -> AGENTS.md` 符号链接会直接复用，不修改链接本身。`.relay/index.md` 与 `.relay/project.md` 只在第一次安装时创建，适配后的内容升级永远不会覆盖。上述精确路径以外的已有文件不会被碰。

## “按需索取”怎么工作

平时的链路很短：

1. 两个 Agent 都先拿到同一份精简入口。
2. 它们读取 `.relay/index.md`；这只是路由表，不是一本需要全部塞进上下文的大手册。
3. 当前任务或文件路径匹配哪一项，才读取对应的已有项目文档或 `.relay/rules/*.md`。
4. 只有当命令、边界、约定、流程或风险发生了长期变化，才更新受影响的那条路由或规则。

这是一套 Agent 遵循的项目规则，不是暗中运行的强制执行器。最终判断仍由 Claude Code 或 Codex 完成；`doctor` 负责检查安装结构、适配状态，以及路由里引用的 Markdown 文件是否真实存在。

## 检查、更新和卸载

只读检查安装状态：

```bash
/path/to/relay-rules/scripts/validate-installed-project.sh
```

同时要求项目已经完成适配：

```bash
/path/to/relay-rules/scripts/validate-installed-project.sh --require-adapted
```

Windows 使用对应的 `.cmd`，参数完全相同。

更新时，先在 Relay Rules 的 clone 中运行 `git pull`，然后在目标项目里重新运行普通安装命令。更新会刷新受管入口和 workflow，但会保留已经适配的 `.relay/index.md`、`.relay/project.md`、`.relay/rules/`、已有 Agent 设置和项目自有规则。

卸载 Relay 管理的内容：

```bash
/path/to/relay-rules/scripts/uninstall-rules.sh
```

没有改过的初始骨架会被删除。已经适配或人工修改过的项目上下文会保留在 `.relay/`，因为里面可能有这个项目自己的知识；卸载命令会明确列出保留了什么。

## 更新以前的安装

正常安装命令会自动处理旧版 Relay Rules：

- `0.5.x`：保留已有 `AGENTS.md`、`CLAUDE.md` 内容，并补上新的项目级 `.relay/` 体系。
- `0.4.x`：只移除旧 manifest 中登记的 Relay 可选技能，保留自定义技能，再升级为固定的项目级安装。
- `0.3.x`：先备份到 `.rules-kit/backups/relay-migrate-<timestamp>/`，移除已知旧 Hook 和旧文件，能找到安装前文件时就恢复；新 manifest 会记录备份位置，适配时再核实并继承仍然有效的老项目知识。

已有的 `CLAUDE.md -> AGENTS.md` 符号链接会被支持并保留。其他受管路径上的符号链接、受管标记、manifest、Hook 配置或新的 `.relay/` 路径无法安全处理时，安装会在产生冲突改动前停止。

## 为什么采用这个结构

- Claude Code 官方支持项目级 `CLAUDE.md`、`@AGENTS.md` 导入和按路径加载的规则，也明确建议把常驻说明保持精简：[Claude Code memory 官方文档](https://code.claude.com/docs/en/memory)。
- Codex 官方会按目录层级组成项目指令链，同一目录中 `AGENTS.override.md` 优先于 `AGENTS.md`：[Codex AGENTS.md 官方文档](https://learn.chatgpt.com/docs/agent-configuration/agents-md)。
- 仍在维护的 [Ruler](https://github.com/intellectronica/ruler) 证明了“项目只有一份规则事实源，再按上下文分发”的价值。

Relay Rules 用两个产品都原生支持的方式做共同入口，把项目路由和事实继续保持为一份。适配和维护流程各自在 `.relay/workflows/` 只保存一次，不再为 Claude 和 Codex 分别复制同样的技能；正常使用也不依赖 Hook。

## Windows 支持

Windows、macOS 和 Linux 使用同一个 Python 核心、同一批模板、同一套所有权与迁移逻辑。Windows 的 `.cmd` 同时支持 `python` 和系统常见的 `py -3` 启动器，也覆盖带空格、中文字符的路径以及已有 CRLF 文件。

普通安装不需要管理员权限、开发者模式或符号链接。

## 测试

```bash
python tests/run.py
python tests/run.py --all
```

CI 会在 Windows、macOS、Linux 上分别使用 Python 3.9 和 3.13 执行完整测试，并在每个平台用原生入口跑完安装、检查、卸载；Windows 同时覆盖 PowerShell 和命令提示符。

## 环境要求

- Python 3.9 或更高版本
- 克隆和更新本仓库需要 Git（目标项目本身不是 Git 仓库也可以安装）
- Windows：PowerShell 或命令提示符；Python 可通过 `python` 或 `py` 启动
- macOS / Linux：便捷入口需要 Bash
- 不需要第三方 Python 包

## 许可证

[MIT](./LICENSE)
