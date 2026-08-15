# Relay Rules

[![Cross-platform tests](https://github.com/liyuhao957/relay-rules/actions/workflows/test.yml/badge.svg)](https://github.com/liyuhao957/relay-rules/actions/workflows/test.yml)

English | [简体中文](./README.zh-CN.md)

**Shared project rules for Claude Code and Codex. Three files by default, one source of truth, no workflow framework.**

Relay Rules keeps the instructions that matter in both tools without taking over your repository:

- **Small by default.** An empty project gets exactly three files.
- **Native to both agents.** Codex reads `AGENTS.md`; Claude Code imports it through `CLAUDE.md`.
- **Reversible.** Existing rules stay intact, updates are idempotent, and removal touches only Relay-managed content.
- **Cross-platform.** The same Python core runs behind thin macOS, Linux, and Windows launchers.

## What It Adds

The default `--profile core --agents both` install creates:

```text
AGENTS.md              Relay Rules managed block
CLAUDE.md              managed @AGENTS.md import
.relay/manifest.json   relative ownership metadata
```

Existing `AGENTS.md` and `CLAUDE.md` content is preserved. Relay Rules owns only the text between its markers, never either whole file or an agent configuration directory.

The optional `standard` profile adds three focused skills per selected agent. Nothing else is installed.

## Quick Start

Clone Relay Rules once:

```bash
git clone https://github.com/liyuhao957/relay-rules.git
```

macOS / Linux:

```bash
/path/to/relay-rules/scripts/install-rules.sh --target /path/to/project
```

Windows PowerShell:

```powershell
& "C:\path\to\relay-rules\scripts\install-rules.cmd" --target "C:\path\to\project"
```

Windows Command Prompt:

```bat
"C:\path\to\relay-rules\scripts\install-rules.cmd" --target "C:\path\to\project"
```

Run the same platform command to update. Both wrappers call the same Python CLI, are idempotent, and do not require `--force` or `--upgrade`.

Add `--dry-run` to preview without writing:

```bash
/path/to/relay-rules/scripts/install-rules.sh --target /path/to/project --dry-run
```

On Windows, replace `install-rules.sh` with `install-rules.cmd`.

The default is `--profile core --agents both`. Select one agent when needed:

```bash
scripts/install-rules.sh --target /path/to/project --agents codex
scripts/install-rules.sh --target /path/to/project --agents claude
```

The same flags work with `scripts\install-rules.cmd` on Windows.

## Choose a Profile

`core` is the default. It installs only the shared rules, manifest, and Claude import shown above.

`standard` additionally installs three focused, on-demand skills for implementation, review, and release safety:

```bash
scripts/install-rules.sh --target /path/to/project --profile standard
```

Windows uses `scripts\install-rules.cmd` with the same `--profile` value.

Claude receives them under `.claude/skills/`; Codex receives them under `.agents/skills/`. The source templates live in one canonical tree in this repository.

## Check and remove

`doctor` is read-only:

```bash
scripts/validate-installed-project.sh /path/to/project
```

```powershell
.\scripts\validate-installed-project.cmd "C:\path\to\project"
```

Remove only the managed blocks, manifest, and optional Relay skills:

```bash
scripts/uninstall-rules.sh --target /path/to/project
```

```powershell
.\scripts\uninstall-rules.cmd --target "C:\path\to\project"
```

Unrelated rules, settings, hooks, and skills remain untouched.

## Migrating from 0.3.x

The normal install command detects `.agent/rules-kit.json` and migrates automatically. Before changing anything it copies the legacy managed state to:

```text
.rules-kit/backups/relay-migrate-<timestamp>/
```

It restores the pre-install files recorded by the old installer, removes known Relay hooks and files, preserves unrelated Claude/Codex configuration, then installs the selected 0.4 profile. Adapted legacy documents remain in the migration backup for reference. Invalid hook JSON fails before any migration write.

## Tests

The canonical test runner is cross-platform and change-aware:

```bash
python tests/run.py                    # suites selected from the current diff
python tests/run.py --suite lifecycle  # one explicit suite
python tests/run.py --all              # complete regression
```

`tests/run.sh` and `tests\run.cmd` are equivalent convenience wrappers. Changes to the shared CLI automatically select all suites. Documentation, wrappers, templates, and individual tests select only their mapped checks. CI runs the complete suite on Windows, macOS, and Linux with Python 3.9 and 3.13.

## Why this shape

The integration follows both products' native loading model:

- Claude Code documents concise project memory in `CLAUDE.md`, supports `@AGENTS.md` imports, and discovers project skills under `.claude/skills/`: [memory](https://code.claude.com/docs/en/memory), [skills](https://code.claude.com/docs/en/skills), [plugins](https://code.claude.com/docs/en/plugins).
- Codex loads hierarchical `AGENTS.md` instructions and discovers repository skills under `.agents/skills/`: [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md), [skills](https://learn.chatgpt.com/docs/build-skills).

The redesign also takes cues from maintained projects: [Ruler](https://github.com/intellectronica/ruler) for cross-agent rule distribution, [OpenSpec](https://github.com/Fission-AI/OpenSpec) for opt-in profiles, [Spec Kit](https://github.com/github/spec-kit) for optional extensions, and [Superpowers](https://github.com/obra/superpowers) for relying on native skill discovery as clients mature.

Relay Rules deliberately does not install hooks, candidate inboxes, scanners, generated project maps, or mandatory handoff documents. Those mechanisms cost more context and maintenance than they return for ordinary repository work. Tool-specific automation can still be added by a project or packaged separately as a Claude/Codex plugin when it has a concrete use case.

## Requirements

- Python 3.9 or newer
- Windows: PowerShell or Command Prompt; Python available as `python` or `py`
- macOS / Linux: Bash for the convenience wrappers
- No Python packages or runtime dependencies

Normal Windows installation does not create symlinks and needs neither administrator rights nor Developer Mode. Restoring a legacy pre-install backup that itself contains symlinks remains subject to Windows symlink permissions.

## License

[MIT](./LICENSE)
