"""Repository-scoped GitHub App authentication. Secrets never appear in output."""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from maintenance.common import REPOSITORY, request, require

CONFIG = Path.home() / ".config/newtcrafthub-maintenance/github-app.json"
PERMISSIONS = {"contents": "write", "pull_requests": "write", "issues": "write",
               "actions": "write", "workflows": "write", "statuses": "write", "variables": "write"}


def encoded(value):
    return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).rstrip(b"=")


def github_token():
    existing = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if existing:
        return existing
    require(CONFIG.is_file(), "Configure the repository-scoped GitHub App on this machine")
    require(CONFIG.stat().st_mode & 0o077 == 0, "GitHub App config must have mode 600")
    settings = json.loads(CONFIG.read_text())
    require(settings["repository"] == REPOSITORY, "Wrong GitHub App repository")
    key = Path(settings["private_key"])
    require(key.is_file() and key.stat().st_mode & 0o077 == 0, "Private key must exist with mode 600")
    now = int(time.time())
    content = encoded({"alg": "RS256", "typ": "JWT"}) + b"." + encoded(
        {"iat": now - 60, "exp": now + 540, "iss": str(settings["app_id"])})
    signature = subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(key)],
                               input=content, capture_output=True, check=True).stdout
    jwt = (content + b"." + base64.urlsafe_b64encode(signature).rstrip(b"=")).decode()
    # Explicit repository_ids further narrows every installation token.
    result = request(f"https://api.github.com/app/installations/{int(settings['installation_id'])}/access_tokens",
                     method="POST", payload={"repository_ids": [int(settings["repository_id"])],
                                             "permissions": PERMISSIONS}, token=jwt)
    repositories = request("https://api.github.com/installation/repositories", token=result["token"])["repositories"]
    require([repo["full_name"] for repo in repositories] == [REPOSITORY], "App token must grant exactly this repository")
    return result["token"]


def main():
    require(len(sys.argv) > 1, "Usage: python3 -m maintenance.github_auth COMMAND [ARGS]")
    env = dict(os.environ, GH_TOKEN=github_token())
    # gh and Git use the same ephemeral credential without saving the token.
    if sys.argv[1] == "git":
        command = ["git", "-c", "credential.helper=!gh auth git-credential"] + sys.argv[2:]
    else:
        command = sys.argv[1:]
    return subprocess.run(command, env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main())
