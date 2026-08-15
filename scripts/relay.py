#!/usr/bin/env python3
"""Install and maintain the small Relay Rules project footprint."""

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
OBSOLETE_SKILLS_TEMPLATE = ROOT / "templates/skills"
MANIFEST_PATH = Path(".relay/manifest.json")
BLOCK_START = "<!-- relay-rules:start -->"
BLOCK_END = "<!-- relay-rules:end -->"
CLAUDE_BODY = "@AGENTS.md"
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
    with temp.open("w", encoding="utf-8", newline="") as file:
        file.write(content)
    os.replace(temp, path)
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
    path: Path, body: str, *, dry_run: bool, target: Path
) -> bool:
    ensure_safe_path(path, target)
    text = read_text(path) if path.exists() else ""
    newline = preferred_newline(text)
    managed = block(body, newline)
    span = block_span(text, path)
    if span:
        updated = text[: span[0]] + managed + text[span[1] :]
    elif not text:
        updated = managed + newline
    else:
        separator = newline if text.endswith(("\n", "\r")) else newline * 2
        updated = text + separator + managed + newline
    return write_text(path, updated, dry_run=dry_run, target=target)


def remove_managed_block(path: Path, *, dry_run: bool, target: Path) -> bool:
    ensure_safe_path(path, target)
    if not path.exists():
        return False
    text = read_text(path)
    newline = preferred_newline(text)
    span = block_span(text, path)
    if not span:
        return False
    before = text[: span[0]]
    after = text[span[1] :]
    if after == newline:
        after = ""
    if before.endswith(newline * 2):
        before = before[: -len(newline)]
    updated = before + after
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


def all_known_owned_files() -> set[str]:
    return {
        f"{root}/{name}/SKILL.md"
        for root in (".claude/skills", ".agents/skills")
        for name in PREVIOUS_OPTIONAL_SKILL_NAMES
    }


def validate_owned_files(value: Any) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RelayError("Invalid Relay manifest: ownedFiles must be a string array")
    unknown = sorted(set(value) - all_known_owned_files())
    if unknown:
        raise RelayError(f"Invalid Relay manifest: refusing unknown owned path(s): {', '.join(unknown)}")
    return sorted(set(value))


def validate_block_files(value: Any) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RelayError("Invalid Relay manifest: blockFiles must be a string array")
    allowed = {"AGENTS.md", "CLAUDE.md"}
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise RelayError(f"Invalid Relay manifest: unknown block file(s): {', '.join(unknown)}")
    return list(value)


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
            source = restore_from / rel
            if source.is_file():
                load_json(source, label="pre-install JSON")
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
    ensure_safe_path(target / MANIFEST_PATH, target)
    legacy = target / ".agent/rules-kit.json"
    if legacy.exists():
        migrate_legacy(target, dry_run=args.dry_run)
        if args.dry_run:
            print(f"[dry-run] install Relay Rules in {target}")
            return 0

    manifest_path = target / MANIFEST_PATH
    old_owned: list[str] = []
    if manifest_path.exists():
        manifest = load_json(manifest_path, label="Relay manifest")
        old_owned = validate_owned_files(manifest.get("ownedFiles", []))
        validate_block_files(manifest.get("blockFiles", []))

    block_paths = [target / "AGENTS.md", target / "CLAUDE.md"]
    for path in block_paths:
        ensure_safe_path(path, target)
        if path.exists():
            block_span(read_text(path), path)
    for rel in old_owned:
        ensure_safe_path(target / rel, target, allow_leaf_symlink=True)

    for rel in old_owned:
        path = target / rel
        if remove_path(path, dry_run=args.dry_run, target=target) and not args.dry_run:
            prune_empty_parents(path.parent, target)

    core_body = normalized_text(CORE_TEMPLATE).rstrip()
    set_managed_block(target / "AGENTS.md", core_body, dry_run=args.dry_run, target=target)
    set_managed_block(target / "CLAUDE.md", CLAUDE_BODY, dry_run=args.dry_run, target=target)
    if remove_path(manifest_path, dry_run=args.dry_run, target=target) and not args.dry_run:
        prune_empty_parents(manifest_path.parent, target)
    prefix = "Would install" if args.dry_run else "Installed"
    print(f"{prefix} Relay Rules {version()} in {target}")
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
    owned: list[str] = []
    if manifest_path.exists():
        manifest = load_json(manifest_path, label="Relay manifest")
        owned = validate_owned_files(manifest.get("ownedFiles", []))
        validate_block_files(manifest.get("blockFiles", []))

    has_managed_block = False
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = target / name
        ensure_safe_path(path, target)
        if path.exists():
            has_managed_block = block_span(read_text(path), path) is not None or has_managed_block
    if not manifest_path.exists() and not has_managed_block:
        raise RelayError(f"No Relay Rules install found in {target}")
    for rel in owned:
        ensure_safe_path(target / rel, target, allow_leaf_symlink=True)

    for name in ("AGENTS.md", "CLAUDE.md"):
        remove_managed_block(target / name, dry_run=args.dry_run, target=target)
    for rel in owned:
        path = target / rel
        if remove_path(path, dry_run=args.dry_run, target=target) and not args.dry_run:
            prune_empty_parents(path.parent, target)
    removed_manifest = remove_path(manifest_path, dry_run=args.dry_run, target=target)
    if removed_manifest and not args.dry_run:
        prune_empty_parents(manifest_path.parent, target)
    prefix = "Would remove" if args.dry_run else "Removed"
    print(f"{prefix} Relay Rules from {target}; unrelated project files were preserved.")
    return 0


def exact_block(path: Path, body: str) -> str | None:
    if not path.exists():
        return f"missing {path.name}"
    text = read_text(path)
    newline = preferred_newline(text)
    span = block_span(text, path)
    if not span:
        return f"missing managed block in {path.name}"
    if text[span[0] : span[1]] != block(body, newline):
        return f"managed block differs in {path.name}"
    return None


def doctor(args: argparse.Namespace) -> int:
    target = target_path(args.target, create=False)
    issues: list[str] = []
    ensure_safe_path(target / MANIFEST_PATH, target)
    if (target / ".agent/rules-kit.json").exists():
        issues.append("legacy install detected; run install again to migrate it")
    manifest_path = target / MANIFEST_PATH
    if manifest_path.exists():
        try:
            manifest = load_json(manifest_path, label="Relay manifest")
            validate_block_files(manifest.get("blockFiles", []))
            validate_owned_files(manifest.get("ownedFiles", []))
        except RelayError as exc:
            issues.append(str(exc))
        issues.append("obsolete .relay/manifest.json remains; run install to remove it")

    issue = exact_block(target / "AGENTS.md", normalized_text(CORE_TEMPLATE).rstrip())
    if issue:
        issues.append(issue)
    issue = exact_block(target / "CLAUDE.md", CLAUDE_BODY)
    if issue:
        issues.append(issue)

    if issues:
        print("Relay Rules doctor found problems:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        return 1
    print(f"Relay Rules {version()} is healthy in {target}")
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
        if len(core.splitlines()) > 40:
            issues.append("core AGENTS template exceeds 40 lines")
    if OBSOLETE_SKILLS_TEMPLATE.exists():
        issues.append("obsolete templates/skills tree still exists")
    if (ROOT / "templates/project").exists():
        issues.append("obsolete templates/project tree still exists")
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
