import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from maintenance.common import compatibility
from maintenance.generate import artifacts
from maintenance.macmini import prepare_release
from maintenance.release import publish
from maintenance.release_policy import CONFIG, compare, decision, enforce, snapshot


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run_git("init", "-q")
        self.config = compatibility()
        self.write_config()
        self.write("src/NewtCraftHubPlantRemovalFix/Plugin.cs", "original plugin")
        self.write("src/NewtCraftHubPlantRemovalFix/NewtCraftHubPlantRemovalFix.csproj", "build inputs")
        self.write("global.json", '{"sdk": {"version": "10.0.401"}}')
        self.commit()
        self.tag = "v" + self.config["fix_version"]
        self.run_git("tag", self.tag)
        self.baseline = self.run_git("rev-parse", "HEAD")
        self.github = Mock()
        self.github.list_all.return_value = [{"tag_name": self.tag, "draft": False, "prerelease": False}]
        self.github.api.return_value = {"object": {"type": "commit", "sha": self.baseline}}

    def run_git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.PIPE, text=True).strip()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def write_config(self):
        self.write(CONFIG, json.dumps(self.config))
        for name, text in artifacts(self.config).items():
            self.write(name, text)

    def commit(self):
        self.run_git("add", ".")
        self.run_git("-c", "user.name=Test", "-c", "user.email=tests@example.invalid", "commit", "-qm", "Fixture")

    def check(self, ref=None):
        return decision(self.github, ref, self.root)

    def bump(self):
        parts = list(map(int, self.config["fix_version"].split(".")))
        parts[-1] += 1
        self.config["fix_version"] = ".".join(map(str, parts))
        self.write_config()

    def test_unchanged_and_reverted_content_needs_no_release(self):
        self.assertFalse(enforce(self.check()))
        self.write("src/NewtCraftHubPlantRemovalFix/Plugin.cs", "changed")
        self.commit()
        self.write("src/NewtCraftHubPlantRemovalFix/Plugin.cs", "original plugin")
        self.commit()
        self.assertFalse(enforce(self.check("HEAD")))

    def test_docs_workflows_tests_tools_and_evidence_do_not_count(self):
        for name in ["README.md", "CHANGELOG.md", ".github/workflows/ci.yml", "tests/example.py",
                     "maintenance/release.py", "scripts/package.ps1", "tools/ApiVerification/Program.cs"]:
            self.write(name, "maintenance change")
        self.config["supported"][0]["evidence"] = "Reviewed code evidence"
        self.config["supported"][0]["changelog_sha256"] = "a" * 64
        self.config["valheim_reference"]["source"] = "Reviewed source"
        self.config["status"] = "paused"
        self.write_config()
        result = self.check()
        self.assertFalse(enforce(result))
        self.assertEqual(result["reasons"], [])
        self.assertEqual(result["baseline"], {"tag": self.tag, "commit": self.baseline})

    def test_version_only_bump_is_rejected(self):
        self.bump()
        result = self.check()
        self.assertEqual(result["status"], "version-only-change-rejected")
        with self.assertRaises(ValueError):
            enforce(result)

    def test_code_change_requires_higher_version(self):
        self.write("src/NewtCraftHubPlantRemovalFix/Plugin.cs", "new behavior")
        result = self.check()
        self.assertEqual(result["status"], "version-bump-required")
        with self.assertRaises(ValueError):
            enforce(result)
        self.bump()
        self.assertTrue(enforce(self.check()))

    def test_compatibility_and_minimum_dependency_require_release(self):
        self.config["supported"][0]["version"] = "1.8.0"
        self.config["minimum_newtcrafthub_version"] = "1.8.0"
        self.write_config()
        self.assertTrue(self.check()["release_required"])
        self.bump()
        self.assertTrue(enforce(self.check()))

    def test_added_supported_version_requires_release(self):
        row = copy.deepcopy(self.config["supported"][0])
        row["version"] = "1.8.0"
        self.config["supported"].append(row)
        self.bump()
        self.assertTrue(enforce(self.check()))

    def test_reference_change_needs_release_and_owner_review(self):
        self.config["valheim_reference"]["sha256"]["assembly_valheim.dll"] = "a" * 64
        self.bump()
        result = self.check()
        self.assertTrue(enforce(result))
        self.assertTrue(result["owner_review_required"])

    def test_build_inputs_and_added_deleted_source_are_detected(self):
        for name in ["global.json", "Directory.Build.props", "NuGet.Config",
                     "src/NewtCraftHubPlantRemovalFix/packages.lock.json",
                     "src/NewtCraftHubPlantRemovalFix/NewtCraftHubPlantRemovalFix.csproj"]:
            with self.subTest(name=name):
                before = snapshot(root=self.root)
                self.write(name, "changed build configuration")
                result = compare(before, snapshot(root=self.root), {})
                self.assertIn(name, result["reasons"])
                self.assertTrue(result["owner_review_required"])
        self.write("src/NewtCraftHubPlantRemovalFix/New.cs", "new input")
        self.assertIn("src/NewtCraftHubPlantRemovalFix/New.cs", self.check()["reasons"])
        (self.root / "src/NewtCraftHubPlantRemovalFix/Plugin.cs").unlink()
        self.assertIn("src/NewtCraftHubPlantRemovalFix/Plugin.cs", self.check()["reasons"])

    def test_stale_generated_files_fail_closed(self):
        self.config["fix_version"] = "9.0.0"
        self.write(CONFIG, json.dumps(self.config))
        with self.assertRaisesRegex(ValueError, "stale"):
            self.check()

    def test_missing_or_draft_only_baseline_fails_closed(self):
        for releases in [[], [{"tag_name": self.tag, "draft": True, "prerelease": False}],
                         [{"tag_name": self.tag, "draft": False, "prerelease": True}]]:
            self.github.list_all.return_value = releases
            with self.assertRaisesRegex(ValueError, "No published stable"):
                self.check()

    def test_duplicate_or_malformed_baseline_fails_closed(self):
        stable = self.github.list_all.return_value[0]
        for releases in [[stable, stable], [dict(stable, tag_name="unversioned")]]:
            self.github.list_all.return_value = releases
            with self.assertRaises(ValueError):
                self.check()

    def test_remote_tag_mismatch_fails_closed(self):
        self.github.api.return_value = {"object": {"type": "commit", "sha": "a" * 40}}
        with self.assertRaisesRegex(ValueError, "disagrees"):
            self.check()

    def test_missing_local_tag_fails_closed(self):
        self.run_git("tag", "-d", self.tag)
        with self.assertRaisesRegex(ValueError, "matching release tags"):
            self.check()

    def test_annotated_tag_resolves_without_executing_source(self):
        self.github.api.side_effect = [{"object": {"type": "tag", "sha": "a" * 40}},
                                       {"object": {"type": "commit", "sha": self.baseline}}]
        self.assertFalse(enforce(self.check()))

    def test_baseline_must_be_ancestor(self):
        parent = self.baseline
        self.write("README.md", "later release")
        self.commit()
        self.run_git("tag", "-f", self.tag)
        self.github.api.return_value = {"object": {"type": "commit", "sha": self.run_git("rev-parse", "HEAD")}}
        with self.assertRaises(ValueError):
            self.check(parent)

    def test_latest_stable_version_is_selected_independent_of_api_order(self):
        stable = self.github.list_all.return_value[0]
        self.github.list_all.return_value = [
            dict(stable, tag_name="v9.0.0", draft=True),
            dict(stable, tag_name="v8.0.0", prerelease=True),
            dict(stable, tag_name="v0.1.0"), stable]
        self.assertEqual(self.check()["baseline"]["tag"], self.tag)

    def test_tag_must_match_baseline_version(self):
        self.run_git("tag", "v0.9.0")
        self.github.list_all.return_value[0]["tag_name"] = "v0.9.0"
        with self.assertRaisesRegex(ValueError, "tag/version mismatch"):
            self.check()

    def test_committed_decision_excludes_uncommitted_changes(self):
        self.write("src/NewtCraftHubPlantRemovalFix/Plugin.cs", "local work")
        self.assertTrue(self.check()["release_required"])
        self.assertFalse(self.check("HEAD")["release_required"])

    def test_plugin_version_downgrade_is_rejected(self):
        self.write("src/NewtCraftHubPlantRemovalFix/Plugin.cs", "changed")
        self.config["fix_version"] = "0.0.1"
        self.write_config()
        with self.assertRaisesRegex(ValueError, "version-bump-required"):
            enforce(self.check())


class EntryPointTests(unittest.TestCase):
    def test_preparation_of_published_version_needs_no_assets(self):
        github = Mock()
        github.api.return_value = {"object": {"sha": "a" * 40}}
        published = {"draft": False, "html_url": "https://example.invalid/release"}
        with patch("maintenance.macmini.revision", return_value="a" * 40), \
             patch("maintenance.macmini.subprocess.check_output", return_value=""), \
             patch("maintenance.macmini.release_exists", return_value=published), \
             patch("maintenance.macmini.decision", return_value={"version_valid": True, "release_required": False}), \
             patch("maintenance.macmini.verify_assets") as verify:
            for _ in range(2):
                self.assertEqual(prepare_release(github)["status"], "already-published")
            verify.assert_not_called()
        self.assertTrue(all(call.args[0] == "/git/ref/heads/main" for call in github.api.call_args_list))

    def test_prepare_rejects_version_only_change_before_assets_or_writes(self):
        github = Mock()
        github.api.return_value = {"object": {"sha": "a" * 40}}
        with patch("maintenance.macmini.revision", return_value="a" * 40), \
             patch("maintenance.macmini.subprocess.check_output", return_value=""), \
             patch("maintenance.macmini.release_exists", return_value=None), \
             patch("maintenance.macmini.decision", return_value={"version_valid": False,
                   "status": "version-only-change-rejected", "release_required": False}), \
             patch("maintenance.macmini.verify_assets") as verify:
            with self.assertRaisesRegex(ValueError, "version-only"):
                prepare_release(github)
            verify.assert_not_called()
        self.assertTrue(all(call.args[0] == "/git/ref/heads/main" for call in github.api.call_args_list))

    def test_preparation_requires_package_for_actual_plugin_release(self):
        github = Mock()
        github.api.return_value = {"object": {"sha": "a" * 40}}
        with patch("maintenance.macmini.revision", return_value="a" * 40), \
             patch("maintenance.macmini.subprocess.check_output", return_value=""), \
             patch("maintenance.macmini.release_exists", return_value=None), \
             patch("maintenance.macmini.decision", return_value={"version_valid": True, "release_required": True}), \
             patch("maintenance.macmini.verify_assets", side_effect=ValueError("Missing package")) as verify:
            with self.assertRaisesRegex(ValueError, "Missing package"):
                prepare_release(github, dry_run=True)
            self.assertEqual(verify.call_args.kwargs, {"expected_commit": "a" * 40, "require_clean": True})

    def test_publisher_rejects_empty_or_unversioned_release_before_assets(self):
        for result in [{"release_required": False, "version_valid": True},
                       {"release_required": False, "version_valid": False, "status": "version-only-change-rejected"},
                       {"release_required": True, "version_valid": False, "status": "version-bump-required"}]:
            github = Mock()
            with patch("maintenance.release.revision", return_value="a" * 40), \
                 patch("maintenance.release.subprocess.run"), \
                 patch("maintenance.release.release_exists", return_value={"draft": True}), \
                 patch("maintenance.release.decision", return_value=result), \
                 patch("maintenance.release.validate_release") as validate:
                with self.assertRaises(ValueError):
                    publish(github, "v0.1.2")
                validate.assert_not_called()
                github.api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
