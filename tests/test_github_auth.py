import contextlib
import io
import os
import subprocess
import unittest
from unittest.mock import Mock, patch

from maintenance.common import REPOSITORY, GitHub
from maintenance.github_auth import command_environment, gh_command, gh_environment, git_command, github_token, main


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_local_login_ignores_inherited_tokens_and_other_host(self):
        with patch.dict(os.environ, {"GH_TOKEN": "unrelated", "GITHUB_TOKEN": "unrelated",
                                    "GH_HOST": "other.invalid", "GH_DEBUG": "api"}), \
             patch("maintenance.github_auth.subprocess.run", return_value=Mock(returncode=0, stdout="test-credential\n")) as run, \
             patch("maintenance.github_auth.request", return_value={"full_name": REPOSITORY, "permissions": {"push": True}}) as request:
            output = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                self.assertEqual(github_token(), "test-credential")
            self.assertEqual(output.getvalue(), "")
            env = run.call_args.kwargs["env"]
            self.assertNotIn("GH_TOKEN", env)
            self.assertNotIn("GITHUB_TOKEN", env)
            self.assertNotIn("GH_DEBUG", env)
            self.assertEqual(env["GH_HOST"], "github.com")
            self.assertEqual(env["GH_REPO"], REPOSITORY)
            self.assertTrue(run.call_args.kwargs["capture_output"])
            self.assertEqual(request.call_args.args, ("https://api.github.com/repos/" + REPOSITORY,))

    def test_missing_login_does_not_expose_subprocess_output(self):
        with patch("maintenance.github_auth.subprocess.run", return_value=Mock(returncode=1, stdout="secret-output", stderr="secret-error")), \
             patch("maintenance.github_auth.request") as request:
            with self.assertRaises(ValueError) as error:
                github_token()
            self.assertNotIn("secret", str(error.exception))
            request.assert_not_called()

    def test_missing_cli_or_timeout_fails_without_secret_diagnostics(self):
        for error in [FileNotFoundError("secret-error"), subprocess.TimeoutExpired("gh", 30, output="secret-output")]:
            with self.subTest(error=type(error).__name__), patch("maintenance.github_auth.subprocess.run", side_effect=error):
                with self.assertRaises(ValueError) as caught:
                    github_token()
                self.assertNotIn("secret", str(caught.exception))

    def test_readonly_or_wrong_repository_is_rejected(self):
        for repo in [{"full_name": REPOSITORY, "permissions": {"push": False}},
                     {"full_name": "other/repo", "permissions": {"push": True}}]:
            with patch("maintenance.github_auth.subprocess.run", return_value=Mock(returncode=0, stdout="test-credential")), \
                 patch("maintenance.github_auth.request", return_value=repo):
                with self.assertRaises(ValueError):
                    github_token()

    def test_actions_uses_only_matching_repository_workflow_token(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": REPOSITORY,
                                    "GITHUB_TOKEN": "workflow-credential", "GH_TOKEN": "unrelated"}), \
             patch("maintenance.github_auth.subprocess.run") as run:
            self.assertEqual(github_token(), "workflow-credential")
            run.assert_not_called()

    def test_actions_wrong_repository_or_missing_token_never_falls_back(self):
        for env in [{"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "other/repo", "GITHUB_TOKEN": "unrelated"},
                    {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": REPOSITORY}]:
            with patch.dict(os.environ, env), patch("maintenance.github_auth.subprocess.run") as run:
                with self.assertRaises(ValueError):
                    github_token()
                run.assert_not_called()

    def test_command_environment_replaces_foreign_credentials(self):
        with patch.dict(os.environ, {"GH_TOKEN": "old", "GITHUB_TOKEN": "old", "GH_DEBUG": "api"}), \
             patch("maintenance.github_auth.github_token", return_value="authorized"):
            env = command_environment()
            self.assertEqual(env["GH_TOKEN"], "authorized")
            self.assertNotIn("GITHUB_TOKEN", env)
            self.assertNotIn("GH_DEBUG", env)

    def test_api_client_targets_only_maintenance_repository(self):
        with patch("maintenance.github_auth.github_token", return_value="test-credential"), \
             patch("maintenance.common.request", return_value={}) as request:
            client = GitHub()
            client.api("/releases")
            self.assertEqual(request.call_args.args[0], "https://api.github.com/repos/" + REPOSITORY + "/releases")
            for endpoint in ["https://api.github.com/repos/other/repo", "/../other", "//https://other"]:
                with self.assertRaises(ValueError):
                    client.api(endpoint)

    def test_git_resets_existing_helpers_and_validates_both_remote_urls(self):
        with patch("maintenance.github_auth.subprocess.run", return_value=Mock(returncode=0,
                   stdout="https://github.com/" + REPOSITORY + ".git\n")) as run:
            command = git_command(["push", "origin", "maintenance/example"])
            self.assertEqual(command[1:5], ["-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential"])
            self.assertEqual(run.call_count, 2)

    def test_foreign_push_destination_is_rejected(self):
        expected = "https://github.com/" + REPOSITORY + ".git\n"
        with patch("maintenance.github_auth.subprocess.run", side_effect=[Mock(returncode=0, stdout=expected),
                   Mock(returncode=0, stdout="https://github.com/other/repo.git\n")]):
            with self.assertRaises(ValueError):
                git_command(["push", "origin", "main"])
        with patch("maintenance.github_auth.subprocess.run", return_value=Mock(returncode=0, stdout=expected)):
            for args in [["push", "other", "main"], ["push", "origin", "--repo=other"], ["fetch", "origin", "--upload-pack=other"]]:
                with self.assertRaises(ValueError):
                    git_command(args)

    def test_cli_repository_selection_is_fixed(self):
        self.assertEqual(gh_command(["release", "list"]), ["gh", "release", "list", "--repo", REPOSITORY])
        self.assertEqual(gh_command(["api", "repos/" + REPOSITORY + "/releases"])[1], "api")
        for args in [["auth", "token"], ["pr", "list", "--repo", "other/repo"],
                     ["variable", "list", "--org", "other"], ["api", "repos/other/repo"],
                     ["api", "repos/" + REPOSITORY + "/../other"],
                     ["pr", "view", "https://github.com/other/repo/pull/1"], ["pr", "merge", "1"],
                     ["api", "repos/" + REPOSITORY, "--hostname=other"]]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                gh_command(args)

    def test_wrapper_rejects_arbitrary_commands_before_loading_credentials(self):
        with patch("sys.argv", ["github_auth", "sh", "-c", "env"]), \
             patch("maintenance.github_auth.github_token") as token:
            with self.assertRaises(ValueError):
                main()
            token.assert_not_called()


if __name__ == "__main__":
    unittest.main()
