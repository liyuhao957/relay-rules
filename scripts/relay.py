#!/usr/bin/env python3
"""Install and maintain shared, project-aware rules for coding agents."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MIN_PYTHON = (3, 9)
VERSION_FILE = ROOT / "VERSION"
CORE_TEMPLATE = ROOT / "templates/core/AGENTS.md"
PROJECT_TEMPLATE = ROOT / "templates/project/.relay"
MANIFEST_PATH = Path(".relay/manifest.json")
MANIFEST_SCHEMA = 2
BLOCK_START = "<!-- relay-rules:start -->"
BLOCK_END = "<!-- relay-rules:end -->"
CLAUDE_BODY = "@AGENTS.md"
BASE_BLOCK_FILES = ("AGENTS.md", "CLAUDE.md")
OPTIONAL_OVERRIDE_FILE = "AGENTS.override.md"
ALLOWED_BLOCK_FILES = {*BASE_BLOCK_FILES, OPTIONAL_OVERRIDE_FILE}
PROJECT_CONTEXT_MARKER = "<!-- relay-rules:project-context -->"
ADAPTATION_PLACEHOLDER = "<!-- relay-rules:adaptation-placeholder -->"
MANAGED_TEMPLATES = {
    ".relay/workflows/adapt.md": PROJECT_TEMPLATE / "workflows/adapt.md",
    ".relay/workflows/maintain.md": PROJECT_TEMPLATE / "workflows/maintain.md",
}
SEEDED_TEMPLATES = {
    ".relay/index.md": PROJECT_TEMPLATE / "index.md",
    ".relay/project.md": PROJECT_TEMPLATE / "project.md",
}
PREVIOUS_OPTIONAL_SKILL_NAMES = (
    "relay-implement",
    "relay-review",
    "relay-release-safety",
)

LEGACY_SKILL_NAMES = (
    "adapt-rules",
    "continue",
    "doc-drift",
    "drift-check",
    "implement",
    "quality-gate",
    "release-safety",
    "review",
    "review-changes",
    "rule-health",
)
LEGACY_CLAUDE_FILES = (
    ".claude/README.md",
    ".claude/settings.example.json",
    ".claude/agents/docs-drift-checker.md",
    ".claude/agents/qa.md",
    ".claude/agents/reviewer.md",
    ".claude/hooks/pre_bash_release_guard.py",
    ".claude/hooks/stop_quality_reminder.py",
    ".claude/rules/build-test.md",
    ".claude/rules/data-sync.md",
    ".claude/rules/docs.md",
    ".claude/rules/localization.md",
    ".claude/rules/performance.md",
    ".claude/rules/release.md",
    ".claude/rules/rules-kit.md",
    ".claude/rules/ui-copy.md",
)
LEGACY_CODEX_FILES = (
    ".codex/README.md",
    ".codex/hooks.example.json",
    ".codex/hooks/post_edit_domain_router.py",
    ".codex/hooks/pre_bash_release_guard.py",
    ".codex/hooks/stop_quality_reminder.py",
)
LEGACY_SCRIPT_FILES = (
    "scripts/bootstrap-project-context.py",
    "scripts/check-doc-drift.py",
    "scripts/suggest-rule-updates.py",
)
LEGACY_HOOK_FRAGMENTS = (
    ".claude/hooks/pre_bash_release_guard.py",
    ".claude/hooks/stop_quality_reminder.py",
    ".codex/hooks/post_edit_domain_router.py",
    ".codex/hooks/pre_bash_release_guard.py",
    ".codex/hooks/stop_quality_reminder.py",
)
LEGACY_BACKUP_ROOTS = (
    "AGENTS.md",
    "CLAUDE.md",
    ".agent",
    ".agents",
    ".claude",
    ".codex",
    *LEGACY_SCRIPT_FILES,
)


class RelayError(Exception):
    pass


def version() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def target_path(raw: str, *, create: bool, dry_run: bool = False) -> Path:
    target = Path(raw).expanduser().resolve(strict=False)
    if not target.exists():
        if not create:
            raise RelayError(f"Target directory does not exist: {target}")
        if not dry_run:
            target.mkdir(parents=True)
    if target.exists() and not target.is_dir():
        raise RelayError(f"Target is not a directory: {target}")
    return target


def read_text(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8", newline="") as file:
            return file.read()
    except UnicodeDecodeError as exc:
        raise RelayError(f"Expected UTF-8 text file: {path}") from exc


def normalized_text(path: Path) -> str:
    return read_text(path).replace("\r\n", "\n").replace("\r", "\n")


def ensure_safe_path(
    path: Path, target: Path, *, allow_leaf_symlink: bool = False
) -> None:
    try:
        relative = path.relative_to(target)
    except ValueError as exc:
        raise RelayError(f"Path escapes the target project: {path}") from exc
    current = target
    for index, part in enumerate(relative.parts):
        current /= part
        is_leaf = index == len(relative.parts) - 1
        if current.is_symlink() and not (allow_leaf_symlink and is_leaf):
            raise RelayError(f"Refusing a path through a symlink: {current}")
        if not is_leaf and current.exists() and not current.is_dir():
            raise RelayError(f"Refusing a path through a non-directory: {current}")


def is_shared_claude_symlink(path: Path, target: Path) -> bool:
    return (
        path == target / "CLAUDE.md"
        and path.is_symlink()
        and path.resolve(strict=False) == (target / "AGENTS.md").resolve(strict=False)
    )


def write_text(path: Path, content: str, *, dry_run: bool, target: Path) -> bool:
    ensure_safe_path(path, target)
    if path.exists() and read_text(path) == content:
        return False
    rel = path.relative_to(target)
    if dry_run:
        print(f"[dry-run] write {rel}")
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.relay-tmp-{os.getpid()}")
    created = False
    try:
        with temp.open("x", encoding="utf-8", newline="") as file:
            created = True
            file.write(content)
        if path.exists():
            shutil.copymode(path, temp)
        os.replace(temp, path)
    except FileExistsError as exc:
        raise RelayError(f"Refusing an existing Relay temporary path: {temp}") from exc
    except BaseException:
        if created:
            temp.unlink(missing_ok=True)
        raise
    return True


def remove_path(path: Path, *, dry_run: bool, target: Path) -> bool:
    ensure_safe_path(path, target, allow_leaf_symlink=True)
    if not path.exists() and not path.is_symlink():
        return False
    rel = path.relative_to(target)
    if dry_run:
        print(f"[dry-run] remove {rel}")
        return True
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()
    return True


def prune_empty_parents(path: Path, target: Path) -> None:
    current = path
    while current != target and current.is_dir():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def preferred_newline(text: str) -> str:
    if "\r\n" in text:
        return "\r\n"
    if "\r" in text:
        return "\r"
    return "\n"


def block(body: str, newline: str) -> str:
    normalized = body.rstrip().replace("\r\n", "\n").replace("\r", "\n")
    return newline.join((BLOCK_START, *normalized.split("\n"), BLOCK_END))


def block_span(text: str, path: Path) -> tuple[int, int] | None:
    starts = [match.start() for match in re.finditer(re.escape(BLOCK_START), text)]
    ends = [match.end() for match in re.finditer(re.escape(BLOCK_END), text)]
    if not starts and not ends:
        return None
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise RelayError(f"Malformed Relay Rules markers in {path}; fix them before retrying")
    return starts[0], ends[0]


def set_managed_block(
    path: Path,
    body: str,
    *,
    dry_run: bool,
    target: Path,
) -> bool:
    ensure_safe_path(path, target)
    text = read_text(path) if path.exists() else ""
    newline = preferred_newline(text)
    managed = block(body, newline)
    span = block_span(text, path)
    original = without_managed_block(text, path) if span else text
    bom = "\ufeff" if original.startswith("\ufeff") else ""
    original = original[len(bom) :]
    separator = newline * 2 if original else newline
    updated = bom + managed + separator + original
    return write_text(path, updated, dry_run=dry_run, target=target)


def without_managed_block(text: str, path: Path) -> str:
    newline = preferred_newline(text)
    span = block_span(text, path)
    if not span:
        return text
    before = text[: span[0]]
    after = text[span[1] :]
    if before in ("", "\ufeff"):
        if after.startswith(newline * 2):
            after = after[len(newline) * 2 :]
        elif after.startswith(newline):
            after = after[len(newline) :]
    else:
        if after == newline:
            after = ""
        if before.endswith(newline * 2):
            before = before[: -len(newline)]
    return before + after


def remove_managed_block(path: Path, *, dry_run: bool, target: Path) -> bool:
    ensure_safe_path(path, target)
    if not path.exists():
        return False
    text = read_text(path)
    span = block_span(text, path)
    if not span:
        return False
    updated = without_managed_block(text, path)
    if not updated.strip():
        return remove_path(path, dry_run=dry_run, target=target)
    return write_text(path, updated, dry_run=dry_run, target=target)


def load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(read_text(path))
    except (json.JSONDecodeError, OSError) as exc:
        raise RelayError(f"Invalid {label}: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RelayError(f"Invalid {label}: expected a JSON object in {path}")
    return value


def legacy_owned_files() -> set[str]:
    return {
        f"{root}/{name}/SKILL.md"
        for root in (".claude/skills", ".agents/skills")
        for name in PREVIOUS_OPTIONAL_SKILL_NAMES
    }


def validate_path_list(value: Any, *, field: str, allowed: set[str]) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RelayError(f"Invalid Relay manifest: {field} must be a string array")
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise RelayError(
            f"Invalid Relay manifest: refusing unknown {field} path(s): "
            f"{', '.join(unknown)}"
        )
    return sorted(set(value))


def validate_block_files(value: Any) -> list[str]:
    return validate_path_list(
        value,
        field="blockFiles",
        allowed=ALLOWED_BLOCK_FILES,
    )


def validate_manifest(
    data: dict[str, Any],
) -> tuple[int, list[str], list[str], list[str]]:
    schema = data.get("schema")
    if type(schema) is not int:
        raise RelayError(f"Invalid Relay manifest: unsupported schema {schema!r}")
    blocks = validate_block_files(data.get("blockFiles", []))
    if schema == 1:
        owned = validate_path_list(
            data.get("ownedFiles", []),
            field="ownedFiles",
            allowed=legacy_owned_files(),
        )
        return schema, blocks, owned, []
    if schema == MANIFEST_SCHEMA:
        managed = validate_path_list(
            data.get("managedFiles", []),
            field="managedFiles",
            allowed=set(MANAGED_TEMPLATES),
        )
        seeded = validate_path_list(
            data.get("seededFiles", []),
            field="seededFiles",
            allowed=set(SEEDED_TEMPLATES),
        )
        legacy_backup = data.get("legacyBackup")
        if legacy_backup is not None:
            legacy_path = Path(legacy_backup) if isinstance(legacy_backup, str) else None
            if (
                legacy_path is None
                or legacy_path.is_absolute()
                or ".." in legacy_path.parts
                or len(legacy_path.parts) != 3
                or legacy_path.parts[:2] != (".rules-kit", "backups")
                or not legacy_path.name.startswith("relay-migrate-")
            ):
                raise RelayError("Invalid Relay manifest: legacyBackup is not a Relay backup")
        return schema, blocks, managed, seeded
    raise RelayError(f"Invalid Relay manifest: unsupported schema {schema!r}")


def desired_block_files(target: Path) -> list[str]:
    names = set(BASE_BLOCK_FILES)
    override = target / OPTIONAL_OVERRIDE_FILE
    if override.exists() or override.is_symlink():
        names.add(OPTIONAL_OVERRIDE_FILE)
    return sorted(names)


def desired_manifest(
    block_files: list[str], *, legacy_backup: str | None = None
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "version": version(),
        "blockFiles": block_files,
        "managedFiles": sorted(MANAGED_TEMPLATES),
        "seededFiles": sorted(SEEDED_TEMPLATES),
    }
    if legacy_backup:
        data["legacyBackup"] = legacy_backup
    return data


def template_text(path: Path) -> str:
    return normalized_text(path)


def managed_block_body(name: str) -> str:
    return CLAUDE_BODY if name == "CLAUDE.md" else normalized_text(CORE_TEMPLATE).rstrip()


def adaptation_status(path: Path) -> str | None:
    if not path.is_file():
        return None
    matches = re.findall(
        r"^Status:\s*(pending|adapted)\s*$", read_text(path), re.MULTILINE
    )
    return matches[0] if len(matches) == 1 else None


def preflight_relay_context(
    target: Path, *, managed: list[str], seeded: list[str]
) -> None:
    for rel, source in MANAGED_TEMPLATES.items():
        destination = target / rel
        ensure_safe_path(destination, target)
        if destination.exists() and not destination.is_file():
            raise RelayError(f"Expected a managed file, found another path: {destination}")
        if (
            destination.exists()
            and rel not in managed
            and read_text(destination) != template_text(source)
        ):
            raise RelayError(f"Unmanaged file conflicts with Relay Rules: {destination}")

    for rel in SEEDED_TEMPLATES:
        destination = target / rel
        ensure_safe_path(destination, target)
        if destination.exists() and not destination.is_file():
            raise RelayError(f"Expected a project context file, found another path: {destination}")
        if destination.exists() and rel not in seeded:
            if PROJECT_CONTEXT_MARKER not in read_text(destination):
                raise RelayError(
                    f"Unmanaged project context conflicts with Relay Rules: {destination}"
                )


def route_targets(index_text: str) -> list[str]:
    targets: list[str] = []
    in_routes = False
    for line in index_text.splitlines():
        if line.strip() == "## Routes":
            in_routes = True
            continue
        if in_routes and line.startswith("## "):
            break
        if not in_routes or not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        for match in re.findall(r"`([^`]+\.md(?:#[^`]*)?)`", cells[1]):
            if match not in targets:
                targets.append(match)
    return targets


def json_text(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=True) + "\n"


def unique_backup_dir(target: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = target / ".rules-kit/backups" / f"relay-migrate-{stamp}"
    candidate = base
    suffix = 2
    while candidate.exists():
        candidate = base.with_name(f"{base.name}-{suffix}")
        suffix += 1
    return candidate


def copy_for_backup(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        destination.symlink_to(os.readlink(source))
    elif source.is_dir():
        shutil.copytree(source, destination, symlinks=True)
    else:
        shutil.copy2(source, destination)


def restored_path(target: Path, raw: Any) -> Path | None:
    if not isinstance(raw, str) or not raw:
        return None
    candidate = (target / raw).resolve(strict=False)
    try:
        candidate.relative_to(target)
    except ValueError:
        raise RelayError("Legacy preInstallBackup points outside the target project")
    return candidate if candidate.is_dir() else None


def restored_file(root: Path, rel: str) -> Path | None:
    current = root
    parts = Path(rel).parts
    for index, part in enumerate(parts):
        current /= part
        if current.is_symlink():
            raise RelayError(
                f"Legacy preInstallBackup has a symlink in a managed path: {current}"
            )
        if not current.exists():
            return None
        if index < len(parts) - 1 and not current.is_dir():
            raise RelayError(
                f"Legacy preInstallBackup has a non-directory in a managed path: {current}"
            )
    if not current.is_file():
        raise RelayError(f"Legacy preInstallBackup expected a file: {current}")
    return current


def preflight_restored_relay_context(
    target: Path,
    restore_from: Path,
    *,
    managed: list[str],
    seeded: list[str],
) -> None:
    for rel, source_template in MANAGED_TEMPLATES.items():
        destination = target / rel
        if destination.exists() or destination.is_symlink():
            continue
        source = restored_file(restore_from, rel)
        if (
            source is not None
            and rel not in managed
            and read_text(source) != template_text(source_template)
        ):
            raise RelayError(
                f"Legacy preInstallBackup conflicts with Relay Rules: {source}"
            )

    for rel in SEEDED_TEMPLATES:
        destination = target / rel
        if destination.exists() or destination.is_symlink():
            continue
        source = restored_file(restore_from, rel)
        if source is not None and rel not in seeded:
            if PROJECT_CONTEXT_MARKER not in read_text(source):
                raise RelayError(
                    f"Legacy preInstallBackup conflicts with Relay Rules: {source}"
                )


def copy_missing_tree(source: Path, target: Path) -> None:
    for item in sorted(source.rglob("*")):
        rel = item.relative_to(source)
        destination = target / rel
        if destination.exists() or destination.is_symlink():
            continue
        ensure_safe_path(destination, target)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if item.is_symlink():
            destination.symlink_to(os.readlink(item))
        elif item.is_dir():
            destination.mkdir(exist_ok=True)
        else:
            shutil.copy2(item, destination)


def merge_dicts(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def merge_restored_json(source: Path, destination: Path, target: Path) -> None:
    if not source.is_file() or not destination.is_file():
        return
    base = load_json(source, label="pre-install JSON")
    current = load_json(destination, label="current JSON")
    merged = merge_dicts(base, current)
    write_text(destination, json_text(merged), dry_run=False, target=target)


def cleaned_hook_config(path: Path) -> str | None | bool:
    """Return new text, None when the file should be removed, or False unchanged."""
    if not path.exists():
        return False
    raw = read_text(path)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        if any(fragment in raw for fragment in LEGACY_HOOK_FRAGMENTS):
            raise RelayError(f"Cannot safely remove legacy hooks from invalid JSON: {path}: {exc}") from exc
        return False
    has_legacy_reference = any(fragment in raw for fragment in LEGACY_HOOK_FRAGMENTS)
    if not isinstance(data, dict) or not isinstance(data.get("hooks"), dict):
        if has_legacy_reference:
            raise RelayError(f"Cannot safely identify legacy hooks in {path}")
        return False

    changed = False
    hooks = data["hooks"]
    for event in list(hooks):
        groups = hooks[event]
        if not isinstance(groups, list):
            continue
        kept_groups = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                kept_groups.append(group)
                continue
            kept_hooks = []
            for hook in group["hooks"]:
                command = hook.get("command", "") if isinstance(hook, dict) else ""
                if isinstance(command, str) and any(
                    fragment in command for fragment in LEGACY_HOOK_FRAGMENTS
                ):
                    changed = True
                else:
                    kept_hooks.append(hook)
            if kept_hooks:
                updated_group = dict(group)
                updated_group["hooks"] = kept_hooks
                kept_groups.append(updated_group)
        if kept_groups:
            hooks[event] = kept_groups
        else:
            hooks.pop(event)
    if not changed:
        if has_legacy_reference:
            raise RelayError(f"Cannot safely identify legacy hooks in {path}")
        return False
    if not hooks:
        data.pop("hooks")
    if not data:
        return None
    cleaned = json.dumps(data, indent=2, ensure_ascii=True) + "\n"
    if any(fragment in cleaned for fragment in LEGACY_HOOK_FRAGMENTS):
        raise RelayError(f"Cannot safely remove every legacy hook from {path}")
    return cleaned


def legacy_cleanup_paths() -> list[str]:
    paths = [*LEGACY_CLAUDE_FILES, *LEGACY_CODEX_FILES, *LEGACY_SCRIPT_FILES]
    paths.extend(f".claude/skills/{name}" for name in LEGACY_SKILL_NAMES)
    paths.extend(f".agents/skills/{name}" for name in LEGACY_SKILL_NAMES)
    paths.extend(f".claude/skills/{name}" for name in PREVIOUS_OPTIONAL_SKILL_NAMES)
    paths.extend(f".agents/skills/{name}" for name in PREVIOUS_OPTIONAL_SKILL_NAMES)
    return paths


def migrate_legacy(target: Path, *, dry_run: bool) -> Path:
    metadata_path = target / ".agent/rules-kit.json"
    ensure_safe_path(metadata_path, target)
    metadata = load_json(metadata_path, label="legacy Relay Rules metadata")
    restore_from = restored_path(target, metadata.get("preInstallBackup"))
    for rel in legacy_cleanup_paths():
        ensure_safe_path(target / rel, target, allow_leaf_symlink=True)
    for rel in (".claude/settings.json", ".codex/hooks.json"):
        ensure_safe_path(target / rel, target)
    cleaned_configs = {
        target / ".claude/settings.json": cleaned_hook_config(target / ".claude/settings.json"),
        target / ".codex/hooks.json": cleaned_hook_config(target / ".codex/hooks.json"),
    }
    backup = unique_backup_dir(target)
    ensure_safe_path(backup, target)
    if restore_from:
        for rel in (".claude/settings.json", ".codex/hooks.json"):
            source = restored_file(restore_from, rel)
            if source is not None:
                load_json(source, label="pre-install JSON")
        for rel in ("AGENTS.md", OPTIONAL_OVERRIDE_FILE):
            source = restored_file(restore_from, rel)
            if source is not None:
                block_span(read_text(source), source)
        restored_claude = restore_from / "CLAUDE.md"
        if restored_claude.exists() or restored_claude.is_symlink():
            if not is_shared_claude_symlink(restored_claude, restore_from):
                source = restored_file(restore_from, "CLAUDE.md")
                if source is not None:
                    block_span(read_text(source), source)
        for item in restore_from.rglob("*"):
            destination = target / item.relative_to(restore_from)
            if not destination.exists() and not destination.is_symlink():
                ensure_safe_path(destination, target)
    if dry_run:
        print(f"[dry-run] back up legacy install to {backup.relative_to(target)}")
        print("[dry-run] remove legacy Relay Rules files and hook entries")
        if restore_from:
            print(f"[dry-run] restore pre-install files from {restore_from.relative_to(target)}")
        return backup

    for rel in LEGACY_BACKUP_ROOTS:
        source = target / rel
        if source.exists() or source.is_symlink():
            copy_for_backup(source, backup / rel)

    remove_path(target / ".agent", dry_run=False, target=target)
    remove_path(target / "AGENTS.md", dry_run=False, target=target)
    remove_path(target / "CLAUDE.md", dry_run=False, target=target)
    for rel in legacy_cleanup_paths():
        remove_path(target / rel, dry_run=False, target=target)

    for path, cleaned in cleaned_configs.items():
        if cleaned is False:
            continue
        if cleaned is None:
            remove_path(path, dry_run=False, target=target)
        else:
            write_text(path, cleaned, dry_run=False, target=target)

    for rel in (
        ".agents/skills",
        ".claude/skills",
        ".claude/hooks",
        ".claude/rules",
        ".claude/agents",
        ".codex/hooks",
        "scripts",
    ):
        prune_empty_parents(target / rel, target)
    if restore_from:
        copy_missing_tree(restore_from, target)
        for rel in (".claude/settings.json", ".codex/hooks.json"):
            merge_restored_json(restore_from / rel, target / rel, target)
    print(f"Migrated legacy Relay Rules install; backup: {backup}")
    return backup


def install(args: argparse.Namespace) -> int:
    target = target_path(args.target, create=True, dry_run=args.dry_run)
    manifest_path = target / MANIFEST_PATH
    ensure_safe_path(manifest_path, target)
    migrated_backup: str | None = None
    legacy = target / ".agent/rules-kit.json"
    if legacy.exists():
        preliminary_managed: list[str] = []
        preliminary_seeded: list[str] = []
        if manifest_path.exists():
            preliminary = load_json(manifest_path, label="Relay manifest")
            (
                preliminary_schema,
                _preliminary_blocks,
                preliminary_managed,
                preliminary_seeded,
            ) = validate_manifest(preliminary)
            if preliminary_schema != MANIFEST_SCHEMA:
                preliminary_managed = []
                preliminary_seeded = []
        metadata = load_json(legacy, label="legacy Relay Rules metadata")
        restore_from = restored_path(target, metadata.get("preInstallBackup"))
        if restore_from and not manifest_path.exists():
            restored_manifest = restored_file(restore_from, MANIFEST_PATH.as_posix())
            if restored_manifest is not None:
                restored_data = load_json(
                    restored_manifest, label="pre-install Relay manifest"
                )
                (
                    restored_schema,
                    _restored_blocks,
                    restored_managed,
                    restored_seeded,
                ) = validate_manifest(restored_data)
                if restored_schema == MANIFEST_SCHEMA:
                    preliminary_managed = restored_managed
                    preliminary_seeded = restored_seeded
        if restore_from:
            preflight_restored_relay_context(
                target,
                restore_from,
                managed=preliminary_managed,
                seeded=preliminary_seeded,
            )
        preflight_relay_context(
            target,
            managed=preliminary_managed,
            seeded=preliminary_seeded,
        )
        override = target / OPTIONAL_OVERRIDE_FILE
        if override.exists() or override.is_symlink():
            ensure_safe_path(override, target)
            block_span(read_text(override), override)
        backup = migrate_legacy(target, dry_run=args.dry_run)
        migrated_backup = backup.relative_to(target).as_posix()

    old_schema: int | None = None
    old_blocks: list[str] = []
    old_managed: list[str] = []
    old_seeded: list[str] = []
    old_manifest: dict[str, Any] | None = None
    if manifest_path.exists():
        old_manifest = load_json(manifest_path, label="Relay manifest")
        old_schema, old_blocks, old_managed, old_seeded = validate_manifest(old_manifest)

    block_files = desired_block_files(target)
    for name in sorted(set(block_files) | set(old_blocks)):
        path = target / name
        if is_shared_claude_symlink(path, target):
            continue
        ensure_safe_path(path, target)
        if path.exists():
            block_span(read_text(path), path)

    legacy_owned = old_managed if old_schema == 1 else []
    current_managed = old_managed if old_schema == MANIFEST_SCHEMA else []
    current_seeded = old_seeded if old_schema == MANIFEST_SCHEMA else []
    for rel in legacy_owned:
        ensure_safe_path(target / rel, target, allow_leaf_symlink=True)
    for rel in current_managed:
        ensure_safe_path(target / rel, target, allow_leaf_symlink=True)

    preflight_relay_context(
        target,
        managed=current_managed,
        seeded=current_seeded,
    )

    for rel in legacy_owned:
        path = target / rel
        if remove_path(path, dry_run=args.dry_run, target=target) and not args.dry_run:
            prune_empty_parents(path.parent, target)

    for name in block_files:
        if is_shared_claude_symlink(target / name, target):
            continue
        set_managed_block(
            target / name,
            managed_block_body(name),
            dry_run=args.dry_run,
            target=target,
        )

    for rel, source in MANAGED_TEMPLATES.items():
        write_text(
            target / rel,
            template_text(source),
            dry_run=args.dry_run,
            target=target,
        )
    for rel, source in SEEDED_TEMPLATES.items():
        destination = target / rel
        if not destination.exists():
            write_text(
                destination,
                template_text(source),
                dry_run=args.dry_run,
                target=target,
            )

    legacy_backup = migrated_backup
    if old_manifest and isinstance(old_manifest.get("legacyBackup"), str):
        legacy_backup = old_manifest["legacyBackup"]
    write_text(
        manifest_path,
        json_text(desired_manifest(block_files, legacy_backup=legacy_backup)),
        dry_run=args.dry_run,
        target=target,
    )
    prefix = "Would install" if args.dry_run else "Installed"
    print(f"{prefix} Relay Rules {version()} in {target}")
    if not args.dry_run:
        state = adaptation_status(target / ".relay/index.md") or "invalid"
        print(f"Project adaptation: {state}")
        if state == "pending":
            print(
                "Next agent session will see the pending adaptation. "
                "You can also ask Claude Code or Codex to adapt Relay Rules now."
            )
    return 0


def remove(args: argparse.Namespace) -> int:
    target = target_path(args.target, create=False)
    ensure_safe_path(target / MANIFEST_PATH, target)
    legacy = target / ".agent/rules-kit.json"
    if legacy.exists():
        migrate_legacy(target, dry_run=args.dry_run)
        prefix = "Would remove" if args.dry_run else "Removed"
        print(f"{prefix} legacy Relay Rules install from {target}")
        return 0

    manifest_path = target / MANIFEST_PATH
    schema: int | None = None
    managed: list[str] = []
    seeded: list[str] = []
    if manifest_path.exists():
        manifest = load_json(manifest_path, label="Relay manifest")
        schema, _blocks, managed, seeded = validate_manifest(manifest)

    has_managed_block = False
    for name in sorted(ALLOWED_BLOCK_FILES):
        path = target / name
        if is_shared_claude_symlink(path, target):
            continue
        ensure_safe_path(path, target)
        if path.exists():
            has_managed_block = block_span(read_text(path), path) is not None or has_managed_block
    if not manifest_path.exists() and not has_managed_block:
        raise RelayError(f"No Relay Rules install found in {target}")
    for rel in managed:
        ensure_safe_path(target / rel, target, allow_leaf_symlink=True)
    for rel in seeded:
        ensure_safe_path(target / rel, target)

    preserved: list[str] = []
    if schema == MANIFEST_SCHEMA:
        for rel in managed:
            path = target / rel
            if path.exists() and (
                not path.is_file()
                or read_text(path) != template_text(MANAGED_TEMPLATES[rel])
            ):
                preserved.append(rel)
        for rel in seeded:
            path = target / rel
            if path.exists() and (
                not path.is_file()
                or read_text(path) != template_text(SEEDED_TEMPLATES[rel])
            ):
                preserved.append(rel)

    for name in sorted(ALLOWED_BLOCK_FILES):
        if is_shared_claude_symlink(target / name, target):
            continue
        remove_managed_block(target / name, dry_run=args.dry_run, target=target)

    if schema == 1:
        for rel in managed:
            path = target / rel
            if remove_path(path, dry_run=args.dry_run, target=target) and not args.dry_run:
                prune_empty_parents(path.parent, target)
    elif schema == MANIFEST_SCHEMA:
        for rel in managed:
            path = target / rel
            if rel in preserved:
                continue
            if remove_path(path, dry_run=args.dry_run, target=target) and not args.dry_run:
                prune_empty_parents(path.parent, target)
        for rel in seeded:
            path = target / rel
            if rel in preserved:
                continue
            if remove_path(path, dry_run=args.dry_run, target=target) and not args.dry_run:
                prune_empty_parents(path.parent, target)

    removed_manifest = remove_path(manifest_path, dry_run=args.dry_run, target=target)
    if removed_manifest and not args.dry_run:
        prune_empty_parents(manifest_path.parent, target)
    prefix = "Would remove" if args.dry_run else "Removed"
    print(f"{prefix} Relay Rules from {target}; unrelated project files were preserved.")
    if preserved:
        print(f"Preserved modified project context: {', '.join(sorted(preserved))}")
    return 0


def exact_block(path: Path, body: str) -> str | None:
    if not path.exists():
        return f"missing {path.name}"
    text = read_text(path)
    newline = preferred_newline(text)
    span = block_span(text, path)
    if not span:
        return f"missing managed block in {path.name}"
    expected_start = 1 if text.startswith("\ufeff") else 0
    if span[0] != expected_start:
        return f"managed block is not first in {path.name}; run install to repair it"
    if text[span[0] : span[1]] != block(body, newline):
        return f"managed block differs in {path.name}"
    return None


def doctor(args: argparse.Namespace) -> int:
    target = target_path(args.target, create=False)
    issues: list[str] = []
    notes: list[str] = []
    ensure_safe_path(target / MANIFEST_PATH, target)
    if (target / ".agent/rules-kit.json").exists():
        issues.append("legacy install detected; run install again to migrate it")
    manifest_path = target / MANIFEST_PATH
    manifest: dict[str, Any] | None = None
    blocks: list[str] = []
    if manifest_path.exists():
        try:
            manifest = load_json(manifest_path, label="Relay manifest")
            schema, blocks, managed, seeded = validate_manifest(manifest)
            if schema != MANIFEST_SCHEMA:
                issues.append("obsolete Relay manifest remains; run install to update it")
                blocks = []
                managed = []
                seeded = []
            else:
                expected = desired_manifest(
                    desired_block_files(target),
                    legacy_backup=(
                        manifest.get("legacyBackup")
                        if isinstance(manifest.get("legacyBackup"), str)
                        else None
                    )
                )
                for field in ("version", "blockFiles", "managedFiles", "seededFiles"):
                    if manifest.get(field) != expected[field]:
                        issues.append(f"manifest field {field} differs; run install to repair it")
        except RelayError as exc:
            issues.append(str(exc))
            blocks = []
            managed = []
            seeded = []
    else:
        issues.append(f"missing {MANIFEST_PATH}; run install to add project context")
        managed = []
        seeded = []

    checked_blocks = set(BASE_BLOCK_FILES) | set(blocks)
    override = target / OPTIONAL_OVERRIDE_FILE
    if override.exists() or override.is_symlink():
        checked_blocks.add(OPTIONAL_OVERRIDE_FILE)
    for name in sorted(checked_blocks):
        path = target / name
        if is_shared_claude_symlink(path, target):
            continue
        ensure_safe_path(path, target)
        issue = exact_block(path, managed_block_body(name))
        if issue:
            issues.append(issue)

    for rel in managed:
        path = target / rel
        source = MANAGED_TEMPLATES[rel]
        if not path.is_file():
            issues.append(f"missing managed file: {rel}")
        elif read_text(path) != template_text(source):
            issues.append(f"managed file differs: {rel}; run install to repair it")

    for rel in seeded:
        path = target / rel
        if not path.is_file():
            issues.append(f"missing project context: {rel}")
        elif PROJECT_CONTEXT_MARKER not in read_text(path):
            issues.append(f"missing Relay project-context marker: {rel}")

    state = adaptation_status(target / ".relay/index.md")
    if state is None:
        issues.append("missing or invalid adaptation status in .relay/index.md")
    else:
        index_text = read_text(target / ".relay/index.md")
        reviewed = re.findall(r"^Last adapted:\s*(\S+)\s*$", index_text, re.MULTILINE)
        if len(reviewed) != 1:
            issues.append("missing or duplicate Last adapted value in .relay/index.md")
        elif state == "adapted" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", reviewed[0]):
            issues.append("Last adapted must use YYYY-MM-DD after adaptation")

    if state == "pending":
        notes.append("project adaptation is pending")
        if args.require_adapted:
            issues.append("project adaptation is pending; ask an agent to adapt Relay Rules")
    elif state == "adapted":
        for rel in (".relay/index.md", ".relay/project.md"):
            path = target / rel
            if path.is_file() and ADAPTATION_PLACEHOLDER in read_text(path):
                issues.append(f"adaptation placeholder remains in {rel}")
        index_path = target / ".relay/index.md"
        if index_path.is_file():
            for raw in route_targets(read_text(index_path)):
                route = raw.split("#", 1)[0].replace("\\", "/")
                route_path = Path(route)
                if (
                    not route
                    or route_path.is_absolute()
                    or ".." in route_path.parts
                    or any(character in route for character in "*<>")
                ):
                    issues.append(f"invalid or unresolved route target: {raw}")
                elif not (target / route_path).is_file():
                    issues.append(f"missing route target: {raw}")

    if issues:
        print("Relay Rules doctor found problems:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        return 1
    suffix = f" (adaptation: {state})" if state else ""
    print(f"Relay Rules {version()} is healthy in {target}{suffix}")
    for note in notes:
        print(f"  - {note}")
    return 0


def validate_template(_args: argparse.Namespace) -> int:
    issues: list[str] = []
    current_version = version()
    if not re.fullmatch(r"\d+\.\d+\.\d+", current_version):
        issues.append("VERSION must use semantic version form x.y.z")
    if not CORE_TEMPLATE.is_file():
        issues.append("missing templates/core/AGENTS.md")
    else:
        core = normalized_text(CORE_TEMPLATE)
        if BLOCK_START in core or BLOCK_END in core:
            issues.append("core template must not contain managed-block markers")
        if len(core.splitlines()) > 50:
            issues.append("core AGENTS template exceeds 50 lines")
        for required in (".relay/index.md", ".relay/workflows/maintain.md"):
            if required not in core:
                issues.append(f"core AGENTS template does not route to {required}")
    if (ROOT / "templates/skills").exists():
        issues.append("obsolete templates/skills tree still exists")
    expected_project_files = {
        path.relative_to(ROOT / "templates/project").as_posix()
        for path in (*MANAGED_TEMPLATES.values(), *SEEDED_TEMPLATES.values())
    }
    actual_project_files = {
        path.relative_to(ROOT / "templates/project").as_posix()
        for path in (ROOT / "templates/project").rglob("*")
        if path.is_file()
    }
    if actual_project_files != expected_project_files:
        issues.append("project template file set differs from the fixed Relay footprint")
    for rel, source in SEEDED_TEMPLATES.items():
        if not source.is_file():
            issues.append(f"missing seeded template: {source.relative_to(ROOT)}")
            continue
        text = template_text(source)
        if PROJECT_CONTEXT_MARKER not in text or ADAPTATION_PLACEHOLDER not in text:
            issues.append(f"invalid pending project template: {rel}")
    for rel, source in MANAGED_TEMPLATES.items():
        if not source.is_file() or not template_text(source).strip():
            issues.append(f"missing managed workflow template: {rel}")
    if issues:
        print("Template validation failed:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        return 1
    print(f"Relay Rules template {current_version} is valid")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="relay.py", description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install", help="install or update a project")
    install_parser.add_argument(
        "--target", default=".", help="project root (default: current directory)"
    )
    install_parser.add_argument("--dry-run", action="store_true")
    install_parser.set_defaults(handler=install)

    remove_parser = subparsers.add_parser(
        "remove", aliases=["uninstall"], help="remove managed files"
    )
    remove_parser.add_argument(
        "--target", default=".", help="project root (default: current directory)"
    )
    remove_parser.add_argument("--dry-run", action="store_true")
    remove_parser.set_defaults(handler=remove)

    doctor_parser = subparsers.add_parser(
        "doctor", help="check an installed project without writing"
    )
    doctor_parser.add_argument(
        "--target", default=".", help="project root (default: current directory)"
    )
    doctor_parser.add_argument(
        "--require-adapted",
        action="store_true",
        help="fail while project-specific adaptation is pending",
    )
    doctor_parser.set_defaults(handler=doctor)

    validate_parser = subparsers.add_parser(
        "validate-template", help="check this source tree"
    )
    validate_parser.set_defaults(handler=validate_template)
    return result


def main() -> int:
    if sys.version_info < MIN_PYTHON:
        required = ".".join(map(str, MIN_PYTHON))
        print(f"error: Relay Rules requires Python {required} or newer", file=sys.stderr)
        return 1
    try:
        args = parser().parse_args()
        return args.handler(args)
    except RelayError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
