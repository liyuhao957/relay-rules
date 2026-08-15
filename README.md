# Relay Rules

[![Cross-platform tests](https://github.com/liyuhao957/relay-rules/actions/workflows/test.yml/badge.svg)](https://github.com/liyuhao957/relay-rules/actions/workflows/test.yml)

English | [简体中文](./README.zh-CN.md)

**One install command. One project-aware rule system shared by Claude Code and Codex.**

Relay Rules gives both coding agents a small common entry point, then routes them to only the project context relevant to the current task. It works in a new repository and in an established codebase with existing rules, documentation, and conventions.

There are no install profiles, agent selectors, hooks, background services, generated code maps, or third-party packages.

## Install

Clone Relay Rules once:

```bash
git clone https://github.com/liyuhao957/relay-rules.git
```

Open the project where you want the rules, then run one command.

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

That is the complete installation. `--target` is available when the project is not the current directory, and `--dry-run` previews every managed change without writing:

```bash
/path/to/relay-rules/scripts/install-rules.sh --target /path/to/project --dry-run
```

There is no profile or agent choice. Every installation supports both Claude Code and Codex and includes project adaptation, on-demand routing, and rule maintenance.

## What Happens Next

Installation creates a safe skeleton with `Status: pending`. When Claude Code or Codex next starts substantive work, the shared rule tells it to inspect the actual repository and adapt the skeleton first. To request that step explicitly, say:

> Adapt Relay Rules to this project.

The agent, not the installer, performs semantic adaptation. A zero-dependency file copier cannot honestly infer product intent, architecture, or team conventions from filenames alone.

### New project

The agent records only what exists today and lists unknown product decisions as unverified. As the project gains real commands, modules, and conventions, the maintenance workflow updates only the affected rules.

### Established project

The agent first inventories existing `AGENTS.md`, `AGENTS.override.md`, `CLAUDE.md`, nested instructions, `.claude/rules/`, project documentation, manifests, representative entry points, tests, CI, and high-risk workflows. It then:

- preserves existing rules and project files;
- points to good existing documentation instead of copying it;
- records only facts supported by current code, configuration, tests, or tool output;
- separates commands it actually verified from commands it only located;
- builds task- and path-based routes for monorepos and distinct subsystems;
- leaves remote, production, billing, release, and other unprovable facts explicitly unverified.

Adaptation changes Relay context only. It does not rewrite product code.

## What Gets Installed

```text
AGENTS.md                       small shared entry point for Codex
AGENTS.override.md              same entry added only when this override already exists
CLAUDE.md                       managed @AGENTS.md import, or an existing link to AGENTS.md
.relay/
  manifest.json                safe ownership and update metadata
  index.md                     project-owned task/path routing map
  project.md                   project-owned verified project context
  workflows/
    adapt.md                   Relay-managed adaptation procedure
    maintain.md                Relay-managed rule maintenance procedure
```

After adaptation, the agent may add focused `.relay/rules/*.md` files when a real project area needs them.

Relay owns only the marked blocks in `AGENTS.md`, a regular `CLAUDE.md`, and an already-existing root `AGENTS.override.md`, plus the manifest and two workflow files. It never creates `AGENTS.override.md`; when a mature project already uses one, adding the same block there prevents Codex's override precedence from hiding Relay. An existing `CLAUDE.md -> AGENTS.md` symlink is reused without editing the link. Relay seeds `.relay/index.md` and `.relay/project.md` once but never overwrites their adapted content. Existing files outside those exact paths remain untouched.

## On-Demand Context

The normal flow is deliberately small:

1. Both agents receive the short shared entry point.
2. They read `.relay/index.md`, which is a routing table rather than a full handbook.
3. They open only the existing project docs or `.relay/rules/*.md` files whose task or path trigger matches the work.
4. When a durable command, boundary, convention, workflow, or risk changes, they update only the affected route or rule.

This is instruction-driven behavior, not a hidden enforcement layer. Claude Code and Codex still make the final judgment, while `doctor` verifies the installed structure, adaptation state, and routed Markdown targets.

## Check, Update, And Remove

Check the installation without changing files:

```bash
/path/to/relay-rules/scripts/validate-installed-project.sh
```

Require completed project adaptation as well:

```bash
/path/to/relay-rules/scripts/validate-installed-project.sh --require-adapted
```

Windows uses the corresponding `.cmd` entry point with the same options.

To update, run `git pull` inside the Relay Rules clone and run the normal install command again. Updates replace the managed entry block and workflows, while preserving adapted `.relay/index.md`, `.relay/project.md`, `.relay/rules/`, existing agent settings, and custom project rules.

Remove Relay-managed content:

```bash
/path/to/relay-rules/scripts/uninstall-rules.sh
```

Unchanged starter context is removed. Adapted or otherwise modified project context is preserved in `.relay/` because it belongs to the project and may contain useful knowledge; the command lists what it kept.

## Updating Older Installs

The normal install command handles previous Relay Rules versions:

- `0.5.x`: keeps existing `AGENTS.md` and `CLAUDE.md` content and adds the project-aware `.relay/` system.
- `0.4.x`: removes only the old optional skills named in its manifest, preserves custom skills, and upgrades the manifest to the fixed project-aware installation.
- `0.3.x`: backs up the old rules system to `.rules-kit/backups/relay-migrate-<timestamp>/`, removes known legacy hooks and files, restores pre-install files where available, and records the backup in the new manifest so adaptation can review still-valid project knowledge.

An existing `CLAUDE.md -> AGENTS.md` symlink is supported and preserved. If another managed-path symlink, marker, manifest, hook configuration, or new `.relay/` path cannot be handled safely, installation stops before making the conflicting change.

## Why This Shape

- Claude Code officially supports project instructions in `CLAUDE.md`, `@AGENTS.md` imports, and path-scoped rules. Its documentation also recommends keeping always-loaded instructions concise: [Claude Code memory documentation](https://code.claude.com/docs/en/memory).
- Codex officially builds project instruction chains from hierarchical agent files and prefers `AGENTS.override.md` over `AGENTS.md` in the same directory: [Codex AGENTS.md documentation](https://learn.chatgpt.com/docs/agent-configuration/agents-md).
- Maintained tools such as [Ruler](https://github.com/intellectronica/ruler) demonstrate the value of one project-owned rule source and context-specific instruction routing.

Relay Rules uses the native common denominator for the entry point and keeps the project-owned routing source shared. Adaptation and maintenance each live once under `.relay/workflows/`, so the same capability does not need separate Claude and Codex skill copies. Ordinary use does not require hooks.

## Windows Support

Windows uses the same Python core, templates, ownership rules, migration logic, and tests as macOS and Linux. The `.cmd` wrappers support both `python` and the Windows `py -3` launcher, paths with spaces and non-ASCII characters, and CRLF project files.

Normal installation needs no administrator rights, Developer Mode, or symbolic links.

## Tests

```bash
python tests/run.py
python tests/run.py --all
```

CI runs the complete suite on Windows, macOS, and Linux with Python 3.9 and 3.13. Every platform also exercises its native install, check, and remove wrappers end to end; Windows covers both PowerShell and Command Prompt.

## Requirements

- Python 3.9 or newer
- Git to clone and update this repository (the installer itself also works in non-Git project directories)
- Windows: PowerShell or Command Prompt; Python available as `python` or `py`
- macOS / Linux: Bash for the convenience wrappers
- No third-party Python packages

## License

[MIT](./LICENSE)
