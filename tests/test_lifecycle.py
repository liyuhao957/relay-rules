from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from lib import ROOT, file_paths, run_cli, run_wrapper, tree_snapshot, write


INSTALLED_FILES = {
    "AGENTS.md",
    "CLAUDE.md",
    ".relay/index.md",
    ".relay/manifest.json",
    ".relay/project.md",
    ".relay/workflows/adapt.md",
    ".relay/workflows/maintain.md",
}
PROJECT_CONTEXT_MARKER = "<!-- relay-rules:project-context -->"


class LifecycleTests(unittest.TestCase):
    def test_install_adds_one_fixed_project_rule_system_to_current_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "project with spaces"
            target.mkdir()
            result = run_cli("install", cwd=target)
            self.assertEqual(INSTALLED_FILES, file_paths(target))
            self.assertIn("Project adaptation: pending", result.stdout)
            doctor = run_cli("doctor", cwd=target)
            self.assertIn("adaptation: pending", doctor.stdout)

            strict = run_cli("doctor", "--require-adapted", cwd=target, check=False)
            self.assertEqual(1, strict.returncode)
            self.assertIn("adaptation is pending", strict.stderr)

            run_cli("remove", cwd=target)
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

    def test_platform_wrapper_installs_the_current_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            suffix = ".cmd" if os.name == "nt" else ".sh"
            run_wrapper(ROOT / f"scripts/install-rules{suffix}", cwd=target)
            self.assertEqual(INSTALLED_FILES, file_paths(target))
            run_wrapper(ROOT / f"scripts/validate-installed-project{suffix}", cwd=target)
            run_wrapper(ROOT / f"scripts/uninstall-rules{suffix}", cwd=target)
            self.assertEqual(set(), file_paths(target))

    def test_crlf_content_is_restored_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            agents = target / "AGENTS.md"
            override = target / "AGENTS.override.md"
            claude = target / "CLAUDE.md"
            agents.write_bytes(b"# Windows rules\r\nKeep CRLF.\r\n")
            override.write_bytes(b"# Windows override\r\nKeep this too.\r\n")
            claude.write_bytes(b"# Windows Claude\r\nKeep CRLF too.\r\n")
            original_agents = agents.read_bytes()
            original_override = override.read_bytes()
            original_claude = claude.read_bytes()

            run_cli("install", "--target", str(target))
            self.assertNotIn(b"\n", agents.read_bytes().replace(b"\r\n", b""))
            self.assertNotIn(b"\n", override.read_bytes().replace(b"\r\n", b""))
            self.assertNotIn(b"\n", claude.read_bytes().replace(b"\r\n", b""))
            run_cli("remove", "--target", str(target))

            self.assertEqual(original_agents, agents.read_bytes())
            self.assertEqual(original_override, override.read_bytes())
            self.assertEqual(original_claude, claude.read_bytes())

    def test_existing_codex_override_is_managed_and_restored(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            write(target / "AGENTS.md", "# Shared team rules\n")
            write(target / "AGENTS.override.md", "# Existing Codex override\nKeep this.\n")

            run_cli("install", "--target", str(target))
            override = (target / "AGENTS.override.md").read_text()
            self.assertIn("# Existing Codex override\nKeep this.\n", override)
            self.assertIn("<!-- relay-rules:start -->", override)
            manifest = json.loads((target / ".relay/manifest.json").read_text())
            self.assertEqual(
                ["AGENTS.md", "AGENTS.override.md", "CLAUDE.md"],
                manifest["blockFiles"],
            )
            run_cli("doctor", "--target", str(target))

            installed = tree_snapshot(target)
            run_cli("install", "--target", str(target))
            self.assertEqual(installed, tree_snapshot(target))

            run_cli("remove", "--target", str(target))
            self.assertEqual("# Shared team rules\n", (target / "AGENTS.md").read_text())
            self.assertEqual(
                "# Existing Codex override\nKeep this.\n",
                (target / "AGENTS.override.md").read_text(),
            )

    def test_leading_blocks_restore_files_without_final_newlines_or_with_bom(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            originals = {
                "AGENTS.md": b"# Existing rules without newline",
                "AGENTS.override.md": b"# Existing override without newline",
                "CLAUDE.md": b"\xef\xbb\xbf# Existing Claude notes",
            }
            for name, content in originals.items():
                (target / name).write_bytes(content)

            run_cli("install", "--target", str(target))
            for name in originals:
                text = (target / name).read_text(encoding="utf-8-sig")
                self.assertTrue(text.startswith("<!-- relay-rules:start -->"), name)

            run_cli("remove", "--target", str(target))
            for name, content in originals.items():
                self.assertEqual(content, (target / name).read_bytes(), name)

    def test_claude_symlink_to_agents_is_reused_and_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            write(target / "AGENTS.md", "# Existing shared rules\n")
            try:
                (target / "CLAUDE.md").symlink_to("AGENTS.md")
            except OSError as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")

            run_cli("install", "--target", str(target))
            self.assertTrue((target / "CLAUDE.md").is_symlink())
            self.assertEqual("AGENTS.md", os.readlink(target / "CLAUDE.md"))
            self.assertIn("<!-- relay-rules:start -->", (target / "CLAUDE.md").read_text())
            run_cli("doctor", "--target", str(target))

            run_cli("remove", "--target", str(target))
            self.assertTrue((target / "CLAUDE.md").is_symlink())
            self.assertEqual("AGENTS.md", os.readlink(target / "CLAUDE.md"))
            self.assertEqual(
                "# Existing shared rules\n", (target / "AGENTS.md").read_text()
            )

    def test_unrelated_claude_symlink_is_rejected_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "project"
            target.mkdir()
            write(root / "outside.md", "keep\n")
            try:
                (target / "CLAUDE.md").symlink_to(root / "outside.md")
            except OSError as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")
            before = tree_snapshot(target)

            result = run_cli("install", "--target", str(target), check=False)
            self.assertEqual(1, result.returncode)
            self.assertIn("through a symlink", result.stderr)
            self.assertEqual(before, tree_snapshot(target))
            self.assertFalse((target / "AGENTS.md").exists())
            self.assertEqual("keep\n", (root / "outside.md").read_text())

    def test_doctor_detects_an_override_created_after_install(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            run_cli("install", "--target", str(target))
            write(target / "AGENTS.override.md", "# New Codex override\n")

            doctor = run_cli("doctor", "--target", str(target), check=False)
            self.assertEqual(1, doctor.returncode)
            self.assertIn("manifest field blockFiles differs", doctor.stderr)
            self.assertIn("missing managed block in AGENTS.override.md", doctor.stderr)

            run_cli("install", "--target", str(target))
            run_cli("doctor", "--target", str(target))
            run_cli("remove", "--target", str(target))
            self.assertEqual(
                "# New Codex override\n", (target / "AGENTS.override.md").read_text()
            )

    def test_previous_optional_skills_are_removed_on_update(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            run_cli("install", "--target", str(target))
            write(target / ".agents/skills/custom/SKILL.md", "custom\n")
            owned = sorted(
                f".{agent}/skills/{name}/SKILL.md"
                for agent in ("claude", "agents")
                for name in (
                    "relay-implement",
                    "relay-review",
                    "relay-release-safety",
                )
            )
            for rel in owned:
                write(target / rel, "old Relay skill\n")
            write(
                target / ".relay/manifest.json",
                json.dumps(
                    {
                        "schema": 1,
                        "version": "0.4.0",
                        "profile": "standard",
                        "agents": ["claude", "codex"],
                        "blockFiles": ["AGENTS.md", "CLAUDE.md"],
                        "ownedFiles": owned,
                    }
                )
                + "\n",
            )

            run_cli("install", "--target", str(target))
            self.assertTrue((target / ".agents/skills/custom/SKILL.md").is_file())
            manifest = json.loads((target / ".relay/manifest.json").read_text())
            self.assertEqual(2, manifest["schema"])
            for rel in owned:
                self.assertFalse((target / rel).exists(), rel)
            run_cli("doctor", "--target", str(target))

            run_cli("remove", "--target", str(target))
            self.assertEqual({".agents/skills/custom/SKILL.md"}, file_paths(target))

    def test_two_file_0_5_install_upgrades_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            write(
                target / "AGENTS.md",
                "# Team rules\n\n"
                "<!-- relay-rules:start -->\n"
                "# Old generic Relay rules\n"
                "<!-- relay-rules:end -->\n",
            )
            write(
                target / "CLAUDE.md",
                "# Claude notes\n\n"
                "<!-- relay-rules:start -->\n"
                "@AGENTS.md\n"
                "<!-- relay-rules:end -->\n",
            )

            run_cli("install", "--target", str(target))
            agents = (target / "AGENTS.md").read_text()
            self.assertIn("# Team rules", agents)
            self.assertNotIn("Old generic Relay rules", agents)
            self.assertEqual(1, agents.count("<!-- relay-rules:start -->"))
            self.assertIn("Status: pending", (target / ".relay/index.md").read_text())
            manifest = json.loads((target / ".relay/manifest.json").read_text())
            self.assertEqual(2, manifest["schema"])
            run_cli("doctor", "--target", str(target))

    def test_established_project_is_adapted_without_overwriting_existing_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            write(target / "AGENTS.md", "# Team rules\nUse the repository Makefile.\n")
            write(target / "CLAUDE.md", "# Claude notes\nKeep release work manual.\n")
            write(target / "README.md", "# Mature service\n")
            write(target / "src/service.py", "def health():\n    return 'ok'\n")
            write(target / "tests/test_service.py", "def test_health():\n    assert True\n")
            write(target / ".claude/rules/backend.md", "Existing backend rules\n")
            source_before = (target / "src/service.py").read_bytes()

            run_cli("install", "--target", str(target))
            self.assertEqual(source_before, (target / "src/service.py").read_bytes())
            self.assertIn("Use the repository Makefile.", (target / "AGENTS.md").read_text())
            self.assertIn("Keep release work manual.", (target / "CLAUDE.md").read_text())
            self.assertEqual(
                "Existing backend rules\n",
                (target / ".claude/rules/backend.md").read_text(),
            )

            adapted_index = (
                f"{PROJECT_CONTEXT_MARKER}\n"
                "# Project Rule Index\n\n"
                "Status: adapted\n"
                "Last adapted: 2026-08-15\n\n"
                "## Routes\n\n"
                "| Trigger | Read |\n"
                "|---|---|\n"
                "| Service code under `src/` | `.relay/rules/backend.md` |\n"
                "| Commands and architecture | `.relay/project.md` |\n"
            )
            adapted_project = (
                f"{PROJECT_CONTEXT_MARKER}\n"
                "# Verified Project Context\n\n"
                "## Purpose And Shape\n\n"
                "- Mature Python service; entry points live under `src/`.\n\n"
                "## Verified Commands\n\n"
                "- Test command is still unverified.\n"
            )
            write(target / ".relay/index.md", adapted_index)
            write(target / ".relay/project.md", adapted_project)
            write(
                target / ".relay/rules/backend.md",
                "# Backend\n\n- Preserve the public health contract.\n",
            )

            before_update = {
                rel: (target / rel).read_bytes()
                for rel in (
                    ".relay/index.md",
                    ".relay/project.md",
                    ".relay/rules/backend.md",
                    ".claude/rules/backend.md",
                    "src/service.py",
                )
            }
            write(target / ".relay/workflows/adapt.md", "outdated managed workflow\n")
            run_cli("install", "--target", str(target))
            for rel, content in before_update.items():
                self.assertEqual(content, (target / rel).read_bytes(), rel)
            self.assertEqual(
                (ROOT / "templates/project/.relay/workflows/adapt.md").read_text(),
                (target / ".relay/workflows/adapt.md").read_text(),
            )
            run_cli("doctor", "--target", str(target), "--require-adapted")

            (target / ".relay/rules/backend.md").unlink()
            missing_route = run_cli(
                "doctor", "--target", str(target), "--require-adapted", check=False
            )
            self.assertEqual(1, missing_route.returncode)
            self.assertIn("missing route target", missing_route.stderr)
            write(
                target / ".relay/rules/backend.md",
                "# Backend\n\n- Preserve the public health contract.\n",
            )

            run_cli("remove", "--target", str(target))
            self.assertEqual("# Team rules\nUse the repository Makefile.\n", (target / "AGENTS.md").read_text())
            self.assertEqual("# Claude notes\nKeep release work manual.\n", (target / "CLAUDE.md").read_text())
            self.assertEqual(adapted_index, (target / ".relay/index.md").read_text())
            self.assertEqual(adapted_project, (target / ".relay/project.md").read_text())
            self.assertTrue((target / ".relay/rules/backend.md").is_file())
            self.assertFalse((target / ".relay/manifest.json").exists())
            self.assertFalse((target / ".relay/workflows/adapt.md").exists())

            run_cli("install", "--target", str(target))
            run_cli("doctor", "--target", str(target), "--require-adapted")
            self.assertEqual(adapted_index, (target / ".relay/index.md").read_text())
            self.assertEqual(adapted_project, (target / ".relay/project.md").read_text())
            run_cli("remove", "--target", str(target))
            self.assertFalse((target / ".relay/manifest.json").exists())

    def test_unmanaged_relay_context_conflict_fails_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            write(target / ".relay/index.md", "# Another tool owns this file\n")
            before = tree_snapshot(target)
            result = run_cli("install", "--target", str(target), check=False)
            self.assertEqual(1, result.returncode)
            self.assertIn("Unmanaged project context conflicts", result.stderr)
            self.assertEqual(before, tree_snapshot(target))
            self.assertFalse((target / "AGENTS.md").exists())

    def test_manifest_cannot_claim_paths_outside_the_fixed_footprint(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "project"
            target.mkdir()
            write(root / "outside.md", "keep\n")
            write(
                target / ".relay/manifest.json",
                json.dumps(
                    {
                        "schema": 2,
                        "version": "0.6.0",
                        "blockFiles": ["AGENTS.md", "CLAUDE.md"],
                        "managedFiles": ["../outside.md"],
                        "seededFiles": [],
                    }
                )
                + "\n",
            )
            before = tree_snapshot(target)

            result = run_cli("install", "--target", str(target), check=False)
            self.assertEqual(1, result.returncode)
            self.assertIn("refusing unknown managedFiles", result.stderr)
            self.assertEqual(before, tree_snapshot(target))
            self.assertEqual("keep\n", (root / "outside.md").read_text())

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

    def test_doctor_requires_the_managed_block_to_stay_first(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            write(target / "AGENTS.md", "# Existing project rules\n")
            run_cli("install", "--target", str(target))
            agents = target / "AGENTS.md"
            agents.write_text("# Accidentally moved ahead\n\n" + agents.read_text())

            result = run_cli("doctor", "--target", str(target), check=False)
            self.assertEqual(1, result.returncode)
            self.assertIn("managed block is not first", result.stderr)

            run_cli("install", "--target", str(target))
            run_cli("doctor", "--target", str(target))
            self.assertEqual(1, agents.read_text().count("# Accidentally moved ahead"))

    def test_removed_install_modes_are_rejected_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            removed_options = (
                ("--profile", "standard"),
                ("--agents", "codex"),
                ("--upgrade",),
                ("--force",),
                ("--bootstrap",),
                ("--no-backup",),
            )
            for options in removed_options:
                with self.subTest(option=options[0]):
                    before = tree_snapshot(target)
                    result = run_cli(
                        "install",
                        "--target",
                        str(target),
                        *options,
                        check=False,
                    )
                    self.assertEqual(2, result.returncode)
                    self.assertIn("unrecognized arguments", result.stderr)
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

    def test_install_refuses_a_non_directory_in_a_managed_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            write(target / ".relay/workflows", "not a directory\n")
            before = tree_snapshot(target)

            result = run_cli("install", "--target", str(target), check=False)
            self.assertEqual(1, result.returncode)
            self.assertIn("through a non-directory", result.stderr)
            self.assertEqual(before, tree_snapshot(target))
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
            write(target / "AGENTS.override.md", "# Existing Windows override\n")

            install = kit / "scripts/install-rules.cmd"
            doctor = kit / "scripts/validate-installed-project.cmd"
            uninstall = kit / "scripts/uninstall-rules.cmd"

            before_dry_run = tree_snapshot(target)
            run_wrapper(install, "--dry-run", cwd=target)
            self.assertEqual(before_dry_run, tree_snapshot(target))

            run_wrapper(install, cwd=target)
            installed = tree_snapshot(target)
            run_wrapper(install, cwd=target)
            self.assertEqual(installed, tree_snapshot(target))

            before_doctor = tree_snapshot(target)
            run_wrapper(doctor, cwd=target)
            self.assertEqual(before_doctor, tree_snapshot(target))

            run_wrapper(uninstall, cwd=target)
            self.assertEqual("# Existing Windows rules\n", (target / "AGENTS.md").read_text())
            self.assertEqual(
                "# Existing Windows override\n",
                (target / "AGENTS.override.md").read_text(),
            )
            self.assertEqual({"AGENTS.md", "AGENTS.override.md"}, file_paths(target))

            explicit_target = temp_root / "another mature project & \u89c4\u5219"
            explicit_target.mkdir()
            write(explicit_target / "README.md", "# Existing project\n")
            run_wrapper(install, "--target", str(explicit_target), cwd=temp_root)
            run_wrapper(doctor, "--target", str(explicit_target), cwd=temp_root)
            run_wrapper(uninstall, "--target", str(explicit_target), cwd=temp_root)
            self.assertEqual({"README.md"}, file_paths(explicit_target))


if __name__ == "__main__":
    unittest.main()
