from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from lib import run_cli, write


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
    def test_install_migrates_legacy_state_with_a_recoverable_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            seed_legacy(target)
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
            self.assertFalse((target / ".agent").exists())
            self.assertFalse((target / ".relay/manifest.json").exists())
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


if __name__ == "__main__":
    unittest.main()
