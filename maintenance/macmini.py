"""Only policy-approved own-repository PRs may merge; build evidence binds the SHA."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

from maintenance.common import ROOT, GitHub, REPOSITORY, SYSTEM_AUTHORS, compatibility, require
from maintenance.github_auth import github_token
from maintenance.package import expected_assets, verify_assets
from maintenance.release import release_exists, release_notes, revision, validate_release

ALLOWED = {
    "src/NewtCraftHubPlantRemovalFix/Plugin.cs",
    "src/NewtCraftHubPlantRemovalFix/Compatibility.g.cs",
    "maintenance/compatibility.json", "maintenance/Version.props", "packaging/manifest.json",
    "README.md", "README.en.md", "CHANGELOG.md"
}


def merge_pr(github, number):
    pr = github.api(f"/pulls/{number}")
    require(pr["state"] == "open" and not pr["draft"] and pr["base"]["ref"] == "main", "PR not ready")
    require(pr["head"]["repo"]["full_name"] == REPOSITORY and pr["head"]["ref"].startswith("maintenance/"),
            "Only own maintenance branches can auto-merge")
    require(pr["user"]["login"] in SYSTEM_AUTHORS, "PR author is not the maintainer")
    files = github.list_all(f"/pulls/{number}/files")
    require(files and all(row["filename"] in ALLOWED and not row.get("previous_filename") for row in files),
            "Infrastructure/test/auth changes need owner review")
    head = pr["head"]["sha"]
    require(revision("HEAD") == head, "Checkout must match PR head")
    verify_assets(ROOT / "dist" / compatibility()["fix_version"], expected_commit=head, require_clean=True)
    checks = github.api(f"/commits/{head}/check-runs?per_page=100")["check_runs"]
    ci = [row for row in checks if row["name"] == "tests" and row["app"]["slug"] == "github-actions"]
    require(ci and ci[0]["status"] == "completed" and ci[0]["conclusion"] == "success", "GitHub CI must pass for this SHA")
    require(pr["mergeable"] is True, "PR mergeability not confirmed")
    return github.api(f"/pulls/{number}/merge", "PUT",
                      {"sha": head, "merge_method": "merge",
                       "commit_title": "🐛 " + pr["title"], "commit_message": ""})


def prepare_release(github, dry_run=False):
    config = compatibility()
    tag = "v" + config["fix_version"]
    commit = revision("HEAD")
    require(github.api("/git/ref/heads/main")["object"]["sha"] == commit, "Only current merged main can prepare a release")
    assets_dir = ROOT / "dist" / config["fix_version"]
    verify_assets(assets_dir, expected_commit=commit, require_clean=True)
    existing = release_exists(github, tag)
    if existing and not existing["draft"]:
        return {"status": "already-published", "url": existing["html_url"]}
    if dry_run:
        return {"status": "ready", "tag": tag, "commit": commit}
    env = dict(os.environ, GH_TOKEN=github_token())
    ref = subprocess.run(["git", "rev-parse", "--verify", tag + "^{commit}"], cwd=ROOT, capture_output=True, text=True)
    if ref.returncode == 0:
        require(ref.stdout.strip() == commit, "Existing tag points elsewhere")
    else:
        subprocess.run(["git", "tag", "-a", tag, "-m", "🔖 " + tag, commit], cwd=ROOT, check=True)
    subprocess.run(["git", "-c", "credential.helper=!gh auth git-credential", "push", "origin", "refs/tags/" + tag],
                   cwd=ROOT, env=env, check=True)
    if existing is None:
        notes = assets_dir / "release-notes.tmp"
        notes.write_text(release_notes(config, commit))
        try:
            subprocess.run(["gh", "release", "create", tag, "--repo", REPOSITORY, "--draft", "--verify-tag",
                            "--title", tag + " · NewtCraftHub Plant Removal Fix", "--notes-file", str(notes)],
                           cwd=ROOT, env=env, check=True)
        finally:
            notes.unlink()
        existing = release_exists(github, tag)
    uploaded = github.api(f"/releases/{existing['id']}/assets?per_page=100")
    expected = expected_assets(config)
    require(len(uploaded) == len({row["name"] for row in uploaded})
            and {row["name"] for row in uploaded} <= expected, "Unexpected draft assets")
    for asset in uploaded:
        require(github.api(f"/releases/assets/{asset['id']}", binary=True) ==
                (assets_dir / asset["name"]).read_bytes(), "Draft asset conflict; inspect before retrying")
    missing = sorted(expected - {row["name"] for row in uploaded})
    if missing:
        subprocess.run(["gh", "release", "upload", tag, "--repo", REPOSITORY] +
                       [str(assets_dir / name) for name in missing], cwd=ROOT, env=env, check=True)
    with tempfile.TemporaryDirectory() as temporary:
        validate_release(github, release_exists(github, tag), tag, commit, Path(temporary))
    github.api("/actions/workflows/release.yml/dispatches", "POST", {"ref": "main", "inputs": {"tag": tag}})
    return {"status": "publication-dispatched", "tag": tag}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    merge = commands.add_parser("merge-pr")
    merge.add_argument("number", type=int)
    prepare = commands.add_parser("prepare-release")
    prepare.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    github = GitHub()
    result = merge_pr(github, args.number) if args.command == "merge-pr" else prepare_release(github, args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
