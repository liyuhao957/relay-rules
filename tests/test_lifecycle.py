from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from lib import ROOT, file_paths, run_cli, run_wrapper, tree_snapshot, write


class LifecycleTests(unittest.TestCase):
    def test_core_install_is_three_files_on_an_empty_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "project with spaces"
            target.mkdir()
            run_cli("install", "--target", str(target))
            self.assertEqual(
                {"AGENTS.md", "CLAUDE.md", ".relay/manifest.json"},
                file_paths(target),
            )
            run_cli("doctor", "--target", str(target))
            run_cli("remove", "--target", str(target))
            self.assertEqual(set(), file_paths(target))

    def test_existing_content_is_preserved_and_updates_are_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            write(target / "AGENTS.md", "# Team rules\nKeep this.\n")
            write(target / "CLAUDE.md", "# Claude notes\nKeep this too.\n")
            write(target / ".claude/settings.json", '{"permissions": {"allow": []}}\n')
            write(target / ".agents/skills/custom/SKILL.md", "custom\n")

            run_cli("install", "--target", str(target))
            self.assertIn("Keep this.", (target / "AGENTS.md").read_text())
            self.assertIn("Keep this too.", (target / "CLAUDE.md").read_text())
            self.assertEqual(
                '{"permissions": {"allow": []}}\n',
                (target / ".claude/settings.json").read_text(),
            )

            installed = tree_snapshot(target)
            run_cli("install", "--target", str(target))
            self.assertEqual(installed, tree_snapshot(target))

            before_doctor = tree_snapshot(target)
            run_cli("doctor", "--target", str(target))
            self.assertEqual(before_doctor, tree_snapshot(target))

            run_cli("remove", "--target", str(target))
            self.assertEqual("# Team rules\nKeep this.\n", (target / "AGENTS.md").read_text())
            self.assertEqual(
                "# Claude notes\nKeep this too.\n", (target / "CLAUDE.md").read_text()
            )
            self.assertTrue((target / ".agents/skills/custom/SKILL.md").is_file())
            self.assertTrue((target / ".claude/settings.json").is_file())

    def test_crlf_content_is_restored_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            agents = target / "AGENTS.md"
            claude = target / "CLAUDE.md"
            agents.write_bytes(b"# Windows rules\r\nKeep CRLF.\r\n")
            claude.write_bytes(b"# Windows Claude\r\nKeep CRLF too.\r\n")
            original_agents = agents.read_bytes()
            original_claude = claude.read_bytes()

            run_cli("install", "--target", str(target))
            self.assertNotIn(b"\n", agents.read_bytes().replace(b"\r\n", b""))
            self.assertNotIn(b"\n", claude.read_bytes().replace(b"\r\n", b""))
            run_cli("remove", "--target", str(target))

            self.assertEqual(original_agents, agents.read_bytes())
            self.assertEqual(original_claude, claude.read_bytes())

    def test_standard_profile_can_be_added_and_removed_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            write(target / ".agents/skills/custom/SKILL.md", "custom\n")
            run_cli("install", "--target", str(target), "--profile", "standard")
            manifest = json.loads((target / ".relay/manifest.json").read_text())
            self.assertEqual(6, len(manifest["ownedFiles"]))
            for rel in manifest["ownedFiles"]:
                self.assertTrue((target / rel).is_file(), rel)

            run_cli("install", "--target", str(target), "--profile", "core")
            self.assertTrue((target / ".agents/skills/custom/SKILL.md").is_file())
            for rel in manifest["ownedFiles"]:
                self.assertFalse((target / rel).exists(), rel)

            run_cli(
                "install",
                "--target",
                str(target),
                "--profile",
                "standard",
                "--agents",
                "codex",
            )
            self.assertFalse((target / "CLAUDE.md").exists())
            codex_manifest = json.loads((target / ".relay/manifest.json").read_text())
            self.assertEqual(3, len(codex_manifest["ownedFiles"]))
            self.assertTrue(all(path.startswith(".agents/") for path in codex_manifest["ownedFiles"]))

            run_cli("remove", "--target", str(target))
            self.assertEqual({".agents/skills/custom/SKILL.md"}, file_paths(target))

    def test_dry_run_and_malformed_markers_do_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            missing = parent / "missing"
            run_cli("install", "--target", str(missing), "--dry-run")
            self.assertFalse(missing.exists())

            target = parent / "project"
            target.mkdir()
            write(target / "AGENTS.md", "before\n<!-- relay-rules:start -->\nbroken\n")
            before = tree_snapshot(target)
            result = run_cli("install", "--target", str(target), check=False)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("Malformed", result.stderr)
            self.assertEqual(before, tree_snapshot(target))

    def test_doctor_detects_managed_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            run_cli("install", "--target", str(target))
            agents = target / "AGENTS.md"
            agents.write_text(agents.read_text().replace("Work from evidence", "Work from guesses"))
            result = run_cli("doctor", "--target", str(target), check=False)
            self.assertEqual(1, result.returncode)
            self.assertIn("managed block differs", result.stderr)

    def test_unmanaged_profile_collision_fails_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            write(
                target / ".agents/skills/relay-implement/SKILL.md",
                "user-owned skill\n",
            )
            before = tree_snapshot(target)
            result = run_cli(
                "install",
                "--target",
                str(target),
                "--profile",
                "standard",
                check=False,
            )
            self.assertEqual(1, result.returncode)
            self.assertIn("Unmanaged file conflicts", result.stderr)
            self.assertEqual(before, tree_snapshot(target))

    def test_install_refuses_managed_paths_through_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "project"
            outside = root / "outside"
            target.mkdir()
            outside.mkdir()
            try:
                (target / ".relay").symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")

            result = run_cli("install", "--target", str(target), check=False)
            self.assertEqual(1, result.returncode)
            self.assertIn("through a symlink", result.stderr)
            self.assertEqual(set(), file_paths(outside))
            self.assertFalse((target / "AGENTS.md").exists())

    @unittest.skipUnless(os.name == "nt", "Windows wrapper lifecycle")
    def test_windows_cmd_wrappers_cover_the_full_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            kit = temp_root / "relay kit with spaces & tools"
            (kit / "scripts").parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(ROOT / "scripts", kit / "scripts")
            shutil.copytree(ROOT / "templates", kit / "templates")
            shutil.copy2(ROOT / "VERSION", kit / "VERSION")

            target = temp_root / "project with spaces & \u9879\u76ee"
            target.mkdir()
            write(target / "AGENTS.md", "# Existing Windows rules\n")

            install = kit / "scripts/install-rules.cmd"
            doctor = kit / "scripts/validate-installed-project.cmd"
            uninstall = kit / "scripts/uninstall-rules.cmd"

            before_dry_run = tree_snapshot(target)
            run_wrapper(install, "--target", str(target), "--dry-run")
            self.assertEqual(before_dry_run, tree_snapshot(target))

            run_wrapper(install, "--target", str(target), "--profile", "standard")
            installed = tree_snapshot(target)
            run_wrapper(install, "--target", str(target), "--profile", "standard")
            self.assertEqual(installed, tree_snapshot(target))

            before_doctor = tree_snapshot(target)
            run_wrapper(doctor, str(target))
            self.assertEqual(before_doctor, tree_snapshot(target))

            run_wrapper(uninstall, "--target", str(target))
            self.assertEqual("# Existing Windows rules\n", (target / "AGENTS.md").read_text())
            self.assertEqual({"AGENTS.md"}, file_paths(target))


if __name__ == "__main__":
    unittest.main()
