from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

from maintenance.common import ROOT, GitHub, REPOSITORY, VERSION, compatibility, require
from maintenance.package import expected_assets, verify_assets
from maintenance.release_policy import decision, enforce


def revision(ref):
    return subprocess.check_output(["git", "rev-parse", ref], cwd=ROOT, text=True).strip()


def release_exists(github, tag):
    # Draft releases are not always available through /releases/tags.
    rows = [row for row in github.list_all("/releases") if row["tag_name"] == tag]
    require(len(rows) <= 1, "Duplicate releases")
    return rows[0] if rows else None


def release_notes(config, commit, root=ROOT):
    versions = ", ".join(row["version"] for row in config["supported"])
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    section = re.search(r"^## " + re.escape(config["fix_version"]) + r"(?:[^\n]*)\n(.*?)(?=^## |\Z)",
                        changelog, re.MULTILINE | re.DOTALL)
    require(section is not None and section[1].strip(), "Release needs changes in CHANGELOG")
    changes = section[1].strip()
    return (f"Kompatibel mit NewtCraftHub: **{versions}**.\n\n"
            f"Valheim-Referenz: **{config['valheim_reference']['version']}**. Quellstand: {commit}.\n\n"
            f"Änderungen:\n{changes}\n\n"
            "Prüfungen: Release-Build, private Referenzprüfsummen, statische API- und Harmony-Prüfung, "
            "Wartungs-Regressionstests und Paket-/SHA256-Prüfung.\n\n"
            "**Für diese Veröffentlichung wurde kein Funktionstest in Valheim ausgeführt.**\n\n"
            "Installation: DLL nach BepInEx/plugins/NewtCraftHubPlantRemovalFix kopieren oder ZIP entsprechend entpacken. "
            "NewtCraftHub muss separat installiert sein. Details und Änderungen stehen in README und CHANGELOG.\n")


def validate_release(github, release, tag, commit, directory, root=ROOT):
    require(release["tag_name"] == tag and release["prerelease"] is False, "Wrong tag/release type")
    assets = github.api(f"/releases/{release['id']}/assets?per_page=100")
    expected = expected_assets(compatibility(root))
    require(len(assets) == len(expected) and {asset["name"] for asset in assets} == expected, "Missing/unexpected/duplicate assets")
    for asset in assets:
        require(asset["state"] == "uploaded" and 0 < asset["size"] <= 32 * 1024 * 1024, "Invalid release asset")
        data = github.api(f"/releases/assets/{asset['id']}", binary=True)
        require(len(data) == asset["size"], "Incomplete download")
        (directory / asset["name"]).write_bytes(data)
    verify_assets(directory, root=root, expected_commit=commit, require_clean=True)
    require(release.get("body") == release_notes(compatibility(root), commit, root),
            "Release notes must match source, changes, checks and gameplay limitation")


def publish(github, tag, dry_run=False):
    require(tag.startswith("v") and VERSION.fullmatch(tag[1:]), "Invalid release tag")
    commit = revision(tag + "^{commit}")
    subprocess.run(["git", "merge-base", "--is-ancestor", commit, "origin/main"], cwd=ROOT, check=True)
    release = release_exists(github, tag)
    require(release is not None, "Draft release missing")
    if not release["draft"]:
        return {"status": "already-published", "url": release["html_url"]}
    policy = decision(github, commit)
    require(enforce(policy), "Release has no plugin changes")
    with tempfile.TemporaryDirectory(prefix="newt-release-") as temporary:
        # Execute only trusted main publisher code; tagged source is read as data.
        source = Path(temporary) / "source"
        for name in ("maintenance/compatibility.json", "maintenance/Version.props",
                     "src/NewtCraftHubPlantRemovalFix/Compatibility.g.cs",
                     "packaging/manifest.json", "packaging/icon.png",
                     "README.md", "README.en.md", "LICENSE", "CHANGELOG.md"):
            target = source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(subprocess.check_output(["git", "show", commit + ":" + name], cwd=ROOT))
        config = compatibility(source)
        require(tag == "v" + config["fix_version"], "Tag/version mismatch")
        assets = Path(temporary) / "assets"
        assets.mkdir()
        validate_release(github, release, tag, commit, assets, root=source)
    if dry_run:
        return {"status": "validated-draft", "url": release["html_url"]}
    # The only public-publication mutation, after all checks. Retry reconciles draft state.
    updated = github.api(f"/releases/{release['id']}", "PATCH", {"draft": False, "make_latest": "true"})
    require(updated["draft"] is False, "GitHub did not publish the release")
    return {"status": "published", "url": updated["html_url"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(publish(GitHub(), args.tag, args.dry_run), indent=2))


if __name__ == "__main__":
    main()
