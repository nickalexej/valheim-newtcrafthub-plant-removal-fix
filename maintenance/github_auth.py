"""Use the authorized local gh login, or the repository's GitHub Actions token."""
from __future__ import annotations

import os
import subprocess
import sys

from maintenance.common import ROOT, REPOSITORY, request, require

TOKEN_VARIABLES = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")


def gh_environment():
    # Local maintenance must use the gh login, not an inherited project token.
    env = {key: value for key, value in os.environ.items() if key not in TOKEN_VARIABLES and key != "GH_DEBUG"}
    env.update(GH_HOST="github.com", GH_REPO=REPOSITORY, GH_PROMPT_DISABLED="1")
    return env


def github_token():
    if os.environ.get("GITHUB_ACTIONS") == "true":
        require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY, "Unexpected GitHub Actions repository")
        token = os.environ.get("GITHUB_TOKEN")
        require(bool(token), "GitHub Actions token missing")
        return token
    try:
        result = subprocess.run(["gh", "auth", "token", "--hostname", "github.com"],
                                env=gh_environment(), capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError("Local gh login unavailable; check gh auth login on github.com") from None
    # Never include stdout/stderr in diagnostics: either may contain credentials.
    require(result.returncode == 0 and result.stdout.strip(),
            "Local gh login unavailable; run gh auth login --hostname github.com")
    token = result.stdout.strip()
    require(not any(char.isspace() for char in token), "Invalid gh authentication response")
    repo = request("https://api.github.com/repos/" + REPOSITORY, token=token)
    require(repo.get("full_name") == REPOSITORY and repo.get("permissions", {}).get("push") is True,
            "The active gh account needs write access to the maintenance repository")
    return token


def command_environment():
    env = gh_environment()
    env["GH_TOKEN"] = github_token()
    return env


def git_command(args):
    require(args and args[0] in {"add", "commit", "status", "diff", "log", "fetch", "push", "switch", "merge", "rev-parse", "tag"},
            "Unsupported maintenance git command")
    expected = "https://github.com/" + REPOSITORY + ".git"
    for options in (["remote", "get-url", "--all", "origin"], ["remote", "get-url", "--push", "--all", "origin"]):
        result = subprocess.run(["git", *options], cwd=ROOT, capture_output=True, text=True)
        require(result.returncode == 0 and result.stdout.splitlines() == [expected],
                "Maintenance origin must point only to the configured repository over HTTPS")
    if args[0] in {"fetch", "push"}:
        require(len(args) > 1 and args[1] == "origin", "Maintenance network operations must name origin")
        require(not any(value.startswith(("--repo", "--upload-pack", "--exec", "--receive-pack"))
                        for value in args[2:]), "Remote overrides are not allowed")
    return ["git", "-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential", *args]


def gh_command(args):
    require(args, "Missing gh command")
    require(not any(value.startswith(("--org", "--hostname")) or value in {"-o"} for value in args),
            "Organization and host overrides are not allowed")
    require(not any(value.startswith("https://github.com/") and
                    not value.startswith("https://github.com/" + REPOSITORY + "/") for value in args),
            "Foreign repository URL is not allowed")
    require(args[:2] != ["pr", "merge"], "Use maintenance.macmini merge-pr for checked merges")
    if args[0] == "api":
        require(len(args) > 1 and (args[1] == "repos/" + REPOSITORY or
                args[1].startswith("repos/" + REPOSITORY + "/")), "Repository-relative gh API endpoint required")
        require(not any(value in args[1] for value in ("..", "%", "\\")), "Invalid gh API endpoint")
        require(not any(value.startswith(("--hostname", "--header")) or value.startswith("-H") for value in args[2:]),
                "Host and header overrides are not allowed")
        return ["gh", *args]
    require(args[0] in {"pr", "issue", "release", "workflow", "run", "variable", "label"},
            "Unsupported maintenance gh command")
    # Repository selection is supplied here; callers omit -R/--repo.
    require(not any(value.startswith(("--repo", "-R")) for value in args), "Repository selection is fixed")
    return ["gh", *args, "--repo", REPOSITORY]


def main():
    require(len(sys.argv) > 2 and sys.argv[1] in {"git", "gh"},
            "Usage: python3 -m maintenance.github_auth {git|gh} ARGS")
    command = git_command(sys.argv[2:]) if sys.argv[1] == "git" else gh_command(sys.argv[2:])
    return subprocess.run(command, cwd=ROOT, env=command_environment()).returncode


if __name__ == "__main__":
    raise SystemExit(main())
