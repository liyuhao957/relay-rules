# Relay Rules

[![Cross-platform tests](https://github.com/liyuhao957/relay-rules/actions/workflows/test.yml/badge.svg)](https://github.com/liyuhao957/relay-rules/actions/workflows/test.yml)

English | [简体中文](./README.zh-CN.md)

**One command. Two files. One shared rule set for Claude Code and Codex.**

Relay Rules does one thing: it puts the same short engineering rules where both coding agents can read them. There are no profiles, agent selectors, hooks, background services, generated project maps, or package dependencies.

## Install

Clone Relay Rules once:

```bash
git clone https://github.com/liyuhao957/relay-rules.git
```

Then open your project directory and run one command.

macOS / Linux:

```bash
/path/to/relay-rules/scripts/install-rules.sh
```

Windows PowerShell:

```powershell
& "C:\path\to\relay-rules\scripts\install-rules.cmd"
```

Windows Command Prompt:

```bat
"C:\path\to\relay-rules\scripts\install-rules.cmd"
```

That is the complete installation. Run the same command again whenever Relay Rules changes; installation and updates are the same idempotent operation.

To install into another directory without changing directories, add `--target`:

```bash
/path/to/relay-rules/scripts/install-rules.sh --target /path/to/project
```

Add `--dry-run` to preview changes without writing anything.

## What It Adds

An empty project gets exactly two files:

```text
AGENTS.md              shared rules read directly by Codex
CLAUDE.md              managed @AGENTS.md import for Claude Code
```

Existing `AGENTS.md` and `CLAUDE.md` content is preserved. Relay Rules owns only the text between its markers, never either whole file. Project-specific instructions belong outside those markers and remain untouched.

The shared rules tell both agents to:

- verify important claims against current code, configuration, tests, and tool output;
- keep changes focused and preserve unrelated work;
- test the affected behavior and report what was actually verified;
- confirm the exact scope before consequential external actions.

Relay Rules does not share conversations or private memory between agents. It gives them the same written working agreement.

## Check and Remove

From the installed project directory, check the installation without changing files:

```bash
/path/to/relay-rules/scripts/validate-installed-project.sh
```

Windows PowerShell:

```powershell
& "C:\path\to\relay-rules\scripts\validate-installed-project.cmd"
```

Remove only Relay-managed content:

```bash
/path/to/relay-rules/scripts/uninstall-rules.sh
```

```powershell
& "C:\path\to\relay-rules\scripts\uninstall-rules.cmd"
```

Unrelated rules, settings, hooks, and skills remain untouched.

## Updating Older Installs

Running the normal install command also simplifies older Relay Rules installations:

- A `0.4.x` install is reduced to the same two-file footprint. Its old manifest and optional skills previously owned by Relay Rules are removed; custom skills are preserved.
- A `0.3.x` install is backed up before migration to `.rules-kit/backups/relay-migrate-<timestamp>/`. Known Relay hooks and files are removed, pre-install files are restored where available, and unrelated Claude/Codex configuration is preserved.

If legacy hook JSON is invalid, migration stops before writing anything rather than leaving a partial installation.

## Why This Shape

The integration uses each product's native instruction mechanism:

- Claude Code supports concise project memory in `CLAUDE.md` and `@AGENTS.md` imports: [official memory documentation](https://code.claude.com/docs/en/memory).
- Codex loads hierarchical `AGENTS.md` instructions: [official AGENTS.md documentation](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

The small cross-agent distribution model also follows the useful part of maintained projects such as [Ruler](https://github.com/intellectronica/ruler), while deliberately avoiding a second workflow framework on top of the agents themselves.

## Tests

```bash
python tests/run.py
python tests/run.py --all
```

CI runs the complete suite on Windows, macOS, and Linux with Python 3.9 and 3.13. Windows jobs also execute the PowerShell and Command Prompt entry points directly.

## Requirements

- Python 3.9 or newer
- Windows: PowerShell or Command Prompt; Python available as `python` or `py`
- macOS / Linux: Bash for the convenience wrappers
- No third-party Python packages

Normal Windows installation needs no administrator rights, Developer Mode, or symbolic links.

## License

[MIT](./LICENSE)
