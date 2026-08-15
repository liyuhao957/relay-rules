from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from lib import run_cli, tree_snapshot, write


LEGACY_CLAUDE_HOOK = {
    "type": "command",
    "command": "python3 .claude/hooks/stop_quality_reminder.py",
    "timeout": 10,
}
CUSTOM_HOOK = {"type": "command", "command": "python3 tools/my_hook.py"}


def seed_legacy(target: Path, *, with_preinstall: bool = True) -> None:
    preinstall = ".rules-kit/backups/original" if with_preinstall else None
    metadata = {
        "rulesKitVersion": "0.3.2",
        "managedPaths": ["AGENTS.md", "CLAUDE.md", ".agent", ".claude", ".codex"],
        "preInstallBackup": preinstall,
    }
    write(target / ".agent/rules-kit.json", json.dumps(metadata))
    write(target / ".agent/project-map.md", "adapted legacy facts\n")
    write(target / "AGENTS.md", "old Relay Rules AGENTS\n")
    write(target / "CLAUDE.md", "old Relay Rules CLAUDE\n")
    write(target / ".claude/hooks/stop_quality_reminder.py", "old hook\n")
    write(target / ".codex/hooks/post_edit_domain_router.py", "old hook\n")
    write(target / ".claude/skills/implement/SKILL.md", "old skill\n")
    write(target / ".agents/skills/implement/SKILL.md", "old skill\n")
    write(target / ".claude/skills/custom/SKILL.md", "custom skill\n")
    write(target / "scripts/check-doc-drift.py", "old scanner\n")
    settings = {
        "hooks": {"Stop": [{"hooks": [LEGACY_CLAUDE_HOOK, CUSTOM_HOOK]}]},
        "permissions": {"allow": ["Read"]},
    }
    write(target / ".claude/settings.json", json.dumps(settings))
    codex_hooks = {
        "hooks": {
            "PostToolUse": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python3 .codex/hooks/post_edit_domain_router.py",
                        }
                    ]
                }
            ]
        }
    }
    write(target / ".codex/hooks.json", json.dumps(codex_hooks))
    if with_preinstall:
        write(target / preinstall / "AGENTS.md", "# Original team rules\n")
        write(target / preinstall / "CLAUDE.md", "# Original Claude notes\n")
        original_settings = {
            "env": {"ORIGINAL_SETTING": "kept"},
            "permissions": {"deny": ["Write"]},
        }
        write(
            target / preinstall / ".claude/settings.json",
            json.dumps(original_settings),
        )


class MigrationTests(unittest.TestCase):
    def test_legacy_dry_run_previews_migration_and_new_context_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            seed_legacy(target)
            before = tree_snapshot(target)

            result = run_cli("install", "--target", str(target), "--dry-run")
            self.assertIn("back up legacy install", result.stdout)
            self.assertIn("write .relay/index.md", result.stdout)
            self.assertIn("write .relay/manifest.json", result.stdout)
            self.assertEqual(before, tree_snapshot(target))
            self.assertFalse(list((target / ".rules-kit/backups").glob("relay-migrate-*")))

    def test_install_migrates_legacy_state_with_a_recoverable_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            seed_legacy(target)
            write(target / "AGENTS.override.md", "# Existing Codex override\n")
            run_cli("install", "--target", str(target))

            backups = list((target / ".rules-kit/backups").glob("relay-migrate-*"))
            self.assertEqual(1, len(backups))
            backup = backups[0]
            self.assertEqual(
                "adapted legacy facts\n",
                (backup / ".agent/project-map.md").read_text(),
            )
            self.assertEqual("old Relay Rules AGENTS\n", (backup / "AGENTS.md").read_text())

            agents = (target / "AGENTS.md").read_text()
            self.assertIn("# Original team rules", agents)
            self.assertNotIn("old Relay Rules AGENTS", agents)
            self.assertIn("<!-- relay-rules:start -->", agents)
            override = (target / "AGENTS.override.md").read_text()
            self.assertIn("# Existing Codex override", override)
            self.assertIn("<!-- relay-rules:start -->", override)
            self.assertFalse((target / ".agent").exists())
            manifest = json.loads((target / ".relay/manifest.json").read_text())
            self.assertEqual(2, manifest["schema"])
            self.assertEqual(backup.relative_to(target).as_posix(), manifest["legacyBackup"])
            self.assertIn("Status: pending", (target / ".relay/index.md").read_text())
            self.assertFalse((target / "scripts/check-doc-drift.py").exists())
            self.assertFalse((target / ".claude/skills/implement").exists())
            self.assertTrue((target / ".claude/skills/custom/SKILL.md").is_file())

            settings = json.loads((target / ".claude/settings.json").read_text())
            custom = settings["hooks"]["Stop"][0]["hooks"][0]["command"]
            self.assertEqual("python3 tools/my_hook.py", custom)
            self.assertEqual(["Read"], settings["permissions"]["allow"])
            self.assertEqual(["Write"], settings["permissions"]["deny"])
            self.assertEqual("kept", settings["env"]["ORIGINAL_SETTING"])
            self.assertFalse((target / ".codex/hooks.json").exists())
            run_cli("doctor", "--target", str(target))

    def test_remove_understands_a_legacy_install(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            seed_legacy(target, with_preinstall=False)
            run_cli("remove", "--target", str(target))
            self.assertFalse((target / ".agent").exists())
            self.assertFalse((target / "AGENTS.md").exists())
            self.assertFalse((target / "CLAUDE.md").exists())
            self.assertFalse((target / ".relay/manifest.json").exists())
            backups = list((target / ".rules-kit/backups").glob("relay-migrate-*"))
            self.assertEqual(1, len(backups))

    def test_invalid_hook_json_fails_before_migration_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            seed_legacy(target)
            write(
                target / ".claude/settings.json",
                '{"command": "python3 .claude/hooks/stop_quality_reminder.py"',
            )
            before = (target / "AGENTS.md").read_text()
            result = run_cli("install", "--target", str(target), check=False)
            self.assertEqual(1, result.returncode)
            self.assertIn("Cannot safely remove legacy hooks", result.stderr)
            self.assertEqual(before, (target / "AGENTS.md").read_text())
            self.assertFalse(list((target / ".rules-kit/backups").glob("relay-migrate-*")))

    def test_new_context_conflict_fails_before_legacy_migration(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            seed_legacy(target)
            write(target / ".relay/workflows/adapt.md", "owned by another tool\n")
            before = tree_snapshot(target)

            result = run_cli("install", "--target", str(target), check=False)
            self.assertEqual(1, result.returncode)
            self.assertIn("Unmanaged file conflicts", result.stderr)
            self.assertEqual(before, tree_snapshot(target))
            self.assertTrue((target / ".agent/rules-kit.json").is_file())
            self.assertFalse(list((target / ".rules-kit/backups").glob("relay-migrate-*")))

    def test_restored_context_conflict_fails_before_legacy_migration(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            seed_legacy(target)
            preinstall = target / ".rules-kit/backups/original"
            write(preinstall / ".relay/index.md", "# Another tool owns this file\n")
            before = tree_snapshot(target)

            result = run_cli("install", "--target", str(target), check=False)
            self.assertEqual(1, result.returncode)
            self.assertIn("preInstallBackup conflicts", result.stderr)
            self.assertEqual(before, tree_snapshot(target))
            self.assertTrue((target / ".agent/rules-kit.json").is_file())
            self.assertFalse(list((target / ".rules-kit/backups").glob("relay-migrate-*")))

    def test_legacy_restore_preserves_a_claude_agents_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            seed_legacy(target)
            restored_claude = target / ".rules-kit/backups/original/CLAUDE.md"
            restored_claude.unlink()
            try:
                restored_claude.symlink_to("AGENTS.md")
            except OSError as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")

            run_cli("install", "--target", str(target))
            self.assertTrue((target / "CLAUDE.md").is_symlink())
            self.assertEqual("AGENTS.md", os.readlink(target / "CLAUDE.md"))
            run_cli("doctor", "--target", str(target))


if __name__ == "__main__":
    unittest.main()
