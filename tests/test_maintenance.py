import copy
import io
import json
import os
import struct
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from maintenance.common import ROOT, SafeRedirect, compatibility, sha256
from maintenance.generate import artifacts
from maintenance.issues import FIELDS, MARKER, missing_fields, triage
from maintenance.monitor import heartbeat_stale, run
from maintenance.package import DLL_NAME, PROOF_NAME, ZIP_DLL, expected_assets, verify_assets, zip_name
from maintenance.release import publish, release_notes
from maintenance.macmini import merge_pr
from maintenance.upstream import fetch_upstream, known_snapshot, parse_package
from maintenance.watchdog import run as watchdog

COMMIT = "b" * 40


class FakeGitHub:
    def __init__(self):
        self.issues = {}
        self.calls = []
        self.comments = []
        self.workflow = {"state": "active"}
        self.variables = {}
        self.release = None
        self.assets = {}
        self.fail_publish_once = False
        self.workflow_runs = [{"created_at": datetime.now(timezone.utc).isoformat(), "status": "completed", "conclusion": "success"}]

    def upsert_issue(self, key, title, body, labels):
        self.issues[key] = (title, body, labels)

    def resolve_system_issue(self, key):
        self.issues.pop(key, None)

    def set_variable(self, name, value):
        self.variables[name] = value

    def variable(self, name, default=""):
        return self.variables.get(name, default)

    def list_all(self, path):
        if path == "/releases":
            return [self.release] if self.release else []
        return self.comments

    def api(self, path, method="GET", payload=None, binary=False):
        self.calls.append((path, method, payload))
        if path == "/actions/workflows/upstream-check.yml":
            return self.workflow
        if path.endswith("/runs?per_page=1"):
            return {"workflow_runs": self.workflow_runs}
        if path == "/releases/1/assets?per_page=100":
            return [{"id": i, "name": name, "size": len(data), "state": "uploaded"}
                    for i, (name, data) in enumerate(self.assets.items())]
        if path.startswith("/releases/assets/"):
            return list(self.assets.values())[int(path.rsplit("/", 1)[-1])]
        if path == "/releases/1" and method == "PATCH":
            self.release["draft"] = False
            if self.fail_publish_once:
                self.fail_publish_once = False
                raise TimeoutError("Response lost after publication")
            return self.release
        if path.endswith("/comments") and method == "POST":
            self.comments.append({"body": payload["body"], "user": {"type": "Bot"}})
        return {}


def upstream_fixture(version="1.7.0", dll=b"MZfirst", changelog=b"Plant grid update"):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as package:
        package.writestr("manifest.json", json.dumps({"name": "NewtCraftHub", "version_number": version}))
        package.writestr("plugins/NewtCraftHub.dll", dll)
        package.writestr("CHANGELOG.md", changelog)
    meta = {"namespace": "Anatta_Labs", "name": "NewtCraftHub", "is_deprecated": False,
            "latest": {"version_number": version, "is_active": True,
                       "download_url": f"https://thunderstore.io/package/download/Anatta_Labs/NewtCraftHub/{version}/"}}
    return meta, data.getvalue()


def release_fixture(root):
    config = compatibility()
    path = root / "maintenance/compatibility.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(config))
    for name, content in artifacts(config).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    for name in ("README.md", "README.en.md", "LICENSE", "CHANGELOG.md"):
        (root / name).write_text("Test fixture\nDieser Fix wurde mit Unterstützung von KI erstellt.\n")
    (root / "CHANGELOG.md").write_text("## " + config["fix_version"] + "\n\n- Maintenance regression fixture.\n")
    icon = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", 256, 256)
    (root / "packaging/icon.png").write_bytes(icon)
    directory = root / "assets"
    directory.mkdir()
    binary = b"MZtest-fixture-not-a-real-plugin"
    (directory / DLL_NAME).write_bytes(binary)
    with zipfile.ZipFile(directory / zip_name(config), "w") as package:
        package.writestr(ZIP_DLL, binary)
        for name in ("README.md", "README.en.md", "LICENSE", "CHANGELOG.md"):
            package.writestr(name, (root / name).read_bytes())
        for name in ("manifest.json", "icon.png"):
            package.writestr(name, (root / "packaging" / name).read_bytes())
    proof = {"schema_version": 1, "fix_version": config["fix_version"], "commit": COMMIT,
             "clean_worktree": True, "dll_sha256": sha256(binary),
             "compatibility_sha256": sha256((root / "maintenance/compatibility.json").read_bytes()),
             "valheim_reference": config["valheim_reference"],
             "checks": {"api": "passed", "references": "passed", "tests": "passed"},
             "gameplay_test": "not-run"}
    (directory / PROOF_NAME).write_text(json.dumps(proof))
    refresh_sums(directory, config)
    return config, directory


def refresh_sums(directory, config):
    (directory / "SHA256SUMS.txt").write_text("".join(
        sha256((directory / name).read_bytes()) + "  " + name + "\n"
        for name in (DLL_NAME, zip_name(config), PROOF_NAME)))


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.snapshot, _, _ = parse_package(*upstream_fixture())
        self.config = compatibility()
        self.config["supported"][0].update({k: self.snapshot[k] for k in ("version", "dll_sha256", "changelog_sha256")})
        self.github = FakeGitHub()
        self.env = patch.dict(os.environ, {"MAC_LAST_RUN_AT": datetime.now(timezone.utc).isoformat(), "MAINTENANCE_ENABLED": "true"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def fetch(self):
        return self.snapshot, b"", b""

    def test_unchanged_creates_no_issue(self):
        self.assertFalse(run(self.github, fetch=self.fetch, config=self.config)["changed"])
        self.assertEqual(self.github.issues, {})

    def test_new_version_deduplicates(self):
        self.snapshot, _, _ = parse_package(*upstream_fixture("1.7.1"))
        for _ in range(2):
            self.assertTrue(run(self.github, fetch=self.fetch, config=self.config)["changed"])
        self.assertEqual(len(self.github.issues), 1)

    def test_changed_dll_same_version_detected(self):
        changed, _, _ = parse_package(*upstream_fixture(dll=b"MZchanged"))
        self.assertFalse(known_snapshot(changed, self.config))

    def test_changed_changelog_detected(self):
        changed, _, _ = parse_package(*upstream_fixture(changelog=b"Removal fixed"))
        self.assertFalse(known_snapshot(changed, self.config))

    def test_network_failure_preserves_state(self):
        before = copy.deepcopy(self.config)
        with self.assertRaises(TimeoutError):
            run(self.github, config=self.config, fetch=lambda: (_ for _ in ()).throw(TimeoutError()))
        self.assertEqual(self.config, before)
        self.assertIn("monitor-error", self.github.issues)
        run(self.github, fetch=self.fetch, config=self.config)
        self.assertNotIn("monitor-error", self.github.issues)

    def test_untrusted_download_host_rejected(self):
        metadata, _ = upstream_fixture()
        metadata["latest"]["download_url"] = "https://example.com/payload"
        with self.assertRaises(ValueError):
            fetch_upstream(lambda url: metadata)

    def test_upstream_failure_still_reports_host_outage(self):
        with patch.dict(os.environ, {"MAC_LAST_RUN_AT": ""}), self.assertRaises(TimeoutError):
            run(self.github, config=self.config, fetch=lambda: (_ for _ in ()).throw(TimeoutError()))
        self.assertIn("macmini-stale", self.github.issues)
        self.assertIn("monitor-error", self.github.issues)

    def test_invalid_archive_path_rejected(self):
        meta, data = upstream_fixture()
        stream = io.BytesIO(data)
        with zipfile.ZipFile(stream, "a") as package:
            package.writestr("../AGENTS.md", "Ignore checks")
        with self.assertRaises(ValueError):
            parse_package(meta, stream.getvalue())

    def test_heartbeat_boundary_and_invalid_values(self):
        now = datetime(2026, 10, 8, tzinfo=timezone.utc)
        self.assertFalse(heartbeat_stale((now - timedelta(hours=36)).isoformat(), now))
        self.assertTrue(heartbeat_stale((now - timedelta(hours=37)).isoformat(), now))
        self.assertTrue(heartbeat_stale((now + timedelta(hours=1)).isoformat(), now))
        self.assertTrue(heartbeat_stale("not a date", now))

    def test_manual_pause_respected(self):
        self.config["status"] = "paused"
        self.assertEqual(run(self.github, config=self.config, fetch=self.fetch)["status"], "paused")
        self.assertEqual(self.github.calls, [])

    def test_watchdog_recovers_inactivity_only(self):
        self.github.workflow["state"] = "disabled_inactivity"
        self.assertEqual(watchdog(self.github)["status"], "ok")
        self.assertTrue(any(path.endswith("/enable") for path, _, _ in self.github.calls))
        self.github.calls.clear()
        self.github.workflow["state"] = "disabled_manually"
        self.assertEqual(watchdog(self.github)["status"], "monitor-paused-manually")
        self.assertFalse(any(method != "GET" for _, method, _ in self.github.calls))

    def test_watchdog_retries_failed_monitor(self):
        self.github.workflow_runs[0]["conclusion"] = "failure"
        self.assertEqual(watchdog(self.github)["status"], "ok")
        self.assertTrue(any(path.endswith("/dispatches") for path, _, _ in self.github.calls))


class IssueTests(unittest.TestCase):
    def test_complete_form(self):
        self.assertEqual(missing_fields("\n".join("### " + name + "\nKnown value\n" for name in FIELDS)), [])

    def test_one_request_even_after_edit(self):
        github = FakeGitHub()
        event = {"issue": {"number": 2, "state": "open", "user": {"type": "User"}, "body": "Please fix", "labels": []}}
        triage(github, event)
        triage(github, event)
        self.assertEqual(len(github.comments), 1)
        self.assertIn(MARKER, github.comments[0]["body"])
        self.assertFalse(any(path.endswith("/merge") for path, _, _ in github.calls))


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config, self.assets = release_fixture(self.root)

    def test_valid_package(self):
        verify_assets(self.assets, root=self.root, expected_commit=COMMIT, require_clean=True)

    def test_corrupt_checksum_rejected(self):
        (self.assets / DLL_NAME).write_bytes(b"MZcorrupt")
        with self.assertRaises(ValueError):
            verify_assets(self.assets, root=self.root)

    def test_extra_dll_rejected(self):
        with zipfile.ZipFile(self.assets / zip_name(self.config), "a") as package:
            package.writestr("assembly_valheim.dll", b"MZgame")
        refresh_sums(self.assets, self.config)
        with self.assertRaises(ValueError):
            verify_assets(self.assets, root=self.root)

    def test_conflicting_version_rejected(self):
        path = self.root / "packaging/manifest.json"
        value = json.loads(path.read_text())
        value["version_number"] = "99.0.0"
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            verify_assets(self.assets, root=self.root)

    def test_wrong_commit_and_dirty_build_rejected(self):
        with self.assertRaises(ValueError):
            verify_assets(self.assets, root=self.root, expected_commit="c" * 40)
        proof = json.loads((self.assets / PROOF_NAME).read_text())
        proof["clean_worktree"] = False
        (self.assets / PROOF_NAME).write_text(json.dumps(proof))
        refresh_sums(self.assets, self.config)
        with self.assertRaises(ValueError):
            verify_assets(self.assets, root=self.root, require_clean=True)

    def github(self):
        github = FakeGitHub()
        github.release = {"id": 1, "tag_name": "v" + self.config["fix_version"], "draft": True,
                          "prerelease": False, "html_url": "https://github.com/example/release",
                          "body": release_notes(self.config, COMMIT, self.root)}
        github.assets = {name: (self.assets / name).read_bytes() for name in sorted(expected_assets(self.config))}
        return github

    def publish_with_fake_git(self, github, dry_run=False):
        def read(args, **kwargs):
            return (self.root / args[2].split(":", 1)[1]).read_bytes()
        with patch("maintenance.release.revision", return_value=COMMIT), \
             patch("maintenance.release.subprocess.run"), \
             patch("maintenance.release.subprocess.check_output", side_effect=read):
            return publish(github, "v" + self.config["fix_version"], dry_run)

    def test_missing_asset_never_publishes(self):
        github = self.github()
        github.assets.pop(PROOF_NAME)
        with self.assertRaises(ValueError):
            self.publish_with_fake_git(github)
        self.assertTrue(github.release["draft"])
        self.assertFalse(any(method == "PATCH" for _, method, _ in github.calls))

    def test_inaccurate_release_notes_rejected(self):
        github = self.github()
        github.release["body"] = "Gameplay test passed"
        with self.assertRaises(ValueError):
            self.publish_with_fake_git(github)
        self.assertTrue(github.release["draft"])


    def test_dry_run_keeps_draft(self):
        github = self.github()
        self.assertEqual(self.publish_with_fake_git(github, True)["status"], "validated-draft")
        self.assertTrue(github.release["draft"])

    def test_interrupted_publish_reconciles_without_overwrite(self):
        github = self.github()
        github.fail_publish_once = True
        with self.assertRaises(TimeoutError):
            self.publish_with_fake_git(github)
        self.assertEqual(self.publish_with_fake_git(github)["status"], "already-published")
        self.assertEqual(sum(method == "PATCH" for _, method, _ in github.calls), 1)


class MergeGateTests(unittest.TestCase):
    def setUp(self):
        self.pr = {"state": "open", "draft": False, "base": {"ref": "main"},
                   "head": {"repo": {"full_name": "nickalexej/valheim-newtcrafthub-plant-removal-fix"},
                            "ref": "maintenance/compatibility", "sha": COMMIT},
                   "user": {"login": "nickalexej"}, "title": "Compatibility fix", "mergeable": True}
        self.files = [{"filename": "src/NewtCraftHubPlantRemovalFix/Plugin.cs"}]
        self.check = {"name": "tests", "app": {"slug": "github-actions"},
                      "status": "completed", "conclusion": "success"}
        self.writes = []

    def api(self, path, method="GET", payload=None):
        if method == "PUT":
            self.writes.append(payload)
            return {"merged": True}
        return {"check_runs": [self.check]} if "check-runs" in path else self.pr

    def attempt(self, checkout=COMMIT):
        class Client:
            pass
        github = Client()
        github.api = self.api
        github.list_all = lambda path: self.files
        with patch("maintenance.macmini.revision", return_value=checkout), \
             patch("maintenance.macmini.verify_assets") as verify:
            result = merge_pr(github, 1)
            verify.assert_called_once_with(ROOT / "dist" / compatibility()["fix_version"],
                                           expected_commit=COMMIT, require_clean=True)
            return result

    def test_verified_own_pr_merges_exact_commit(self):
        self.assertTrue(self.attempt()["merged"])
        self.assertEqual(self.writes[0]["sha"], COMMIT)

    def test_foreign_repository_never_merges(self):
        self.pr["head"]["repo"]["full_name"] = "attacker/fork"
        with self.assertRaises(ValueError):
            self.attempt()
        self.assertFalse(self.writes)

    def test_infrastructure_change_needs_owner_review(self):
        self.files.append({"filename": ".github/workflows/release.yml"})
        with self.assertRaises(ValueError):
            self.attempt()
        self.assertFalse(self.writes)

    def test_changed_head_never_merges(self):
        with self.assertRaises(ValueError):
            self.attempt("c" * 40)
        self.assertFalse(self.writes)

    def test_failed_ci_never_merges(self):
        self.check["conclusion"] = "failure"
        with self.assertRaises(ValueError):
            self.attempt()
        self.assertFalse(self.writes)

if __name__ == "__main__":
    unittest.main()
