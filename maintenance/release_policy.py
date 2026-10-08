"""Read-only release decisions from published provenance and actual build inputs."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import PurePosixPath

from maintenance.common import ROOT, VERSION, GitHub, require
from maintenance.generate import artifacts

GENERATED = {
    "src/NewtCraftHubPlantRemovalFix/Compatibility.g.cs",
    "maintenance/Version.props", "packaging/manifest.json",
}
CONFIG = "maintenance/compatibility.json"


def version_key(version):
    require(isinstance(version, str) and VERSION.fullmatch(version), "Invalid plugin version")
    return tuple(map(int, version.split(".")))


def git(*args, root=ROOT):
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)
    require(result.returncode == 0, "Release comparison needs complete local history and matching release tags")
    return result.stdout


def build_input(name):
    path = PurePosixPath(name)
    return (name.startswith("src/") or name == "global.json" or
            (len(path.parts) == 1 and (path.suffix.lower() in {".props", ".targets", ".csproj", ".rsp"}
             or name.lower() in {"nuget.config", "packages.lock.json"})))


def snapshot(ref=None, root=ROOT):
    """Read Git objects as data only. ref=None includes uncommitted/new inputs."""
    if ref is None:
        names = git("ls-files", "--cached", "--others", "--exclude-standard", "-z", root=root).decode().split("\0")
        read = lambda name: (root / name).read_bytes()
        exists = lambda name: (root / name).exists()
    else:
        names = git("ls-tree", "-r", "--name-only", "-z", ref, root=root).decode().split("\0")
        read = lambda name: git("show", ref + ":" + name, root=root)
        exists = lambda name: True
    selected = {name for name in names if name and (build_input(name) or name in GENERATED or name == CONFIG)}
    return {name: read(name) for name in sorted(selected) if exists(name)}


def inputs(files, *, validate_generated=False):
    require(CONFIG in files, "Release comparison has no compatibility declarations")
    config = json.loads(files[CONFIG])
    version = config["fix_version"]
    version_key(version)
    if validate_generated:
        for name, text in artifacts(config).items():
            require(files.get(name) == text.encode(), "Generated declarations are stale: " + name)
    result = {name: data for name, data in files.items() if build_input(name) and name not in GENERATED}
    # Remove ONLY the plugin's own version; all other generated declarations still count.
    for name in GENERATED:
        require(name in files, "Release comparison is missing generated declarations: " + name)
        text = files[name].decode()
        if name.endswith(".json"):
            manifest = json.loads(text)
            require(manifest.pop("version_number") == version, "Manifest version disagrees")
            result[name] = json.dumps(manifest, sort_keys=True).encode()
        else:
            old = f'FixVersion = "{version}"' if name.endswith(".cs") else f"<Version>{version}</Version>"
            require(text.count(old) == 1, "Generated plugin version disagrees: " + name)
            result[name] = text.replace(old, "PLUGIN_VERSION").encode()
    reference = config["valheim_reference"]
    result["valheim_reference"] = json.dumps(
        {"version": reference["version"], "sha256": reference["sha256"]}, sort_keys=True).encode()
    return config, result


def compare(before, after, baseline):
    old_config, old = inputs(before)
    config, current = inputs(after, validate_generated=True)
    reasons = sorted(name for name in old.keys() | current.keys() if old.get(name) != current.get(name))
    required = bool(reasons)
    previous = old_config["fix_version"]
    version = config["fix_version"]
    valid_version = version_key(version) > version_key(previous) if required else version == previous
    return {"baseline": baseline, "baseline_version": previous, "version": version,
            "release_required": required, "reasons": reasons, "version_valid": valid_version,
            "status": ("release-required" if required else "no-release") if valid_version else
                      ("version-bump-required" if required else "version-only-change-rejected"),
            "owner_review_required": any(name == "valheim_reference" or
                name not in GENERATED and not name.endswith(".cs") for name in reasons)}


def published_baseline(github, target, root=ROOT):
    stable = [row for row in github.list_all("/releases") if not row["draft"] and not row["prerelease"]]
    require(stable, "No published stable release available; inspect release history before proceeding")
    for row in stable:
        tag = row["tag_name"]
        require(tag.startswith("v") and VERSION.fullmatch(tag[1:]), "Ambiguous stable release tag")
    tags = [row["tag_name"] for row in stable]
    require(len(tags) == len(set(tags)), "Duplicate stable release tags")
    latest = max(stable, key=lambda row: version_key(row["tag_name"][1:]))
    tag = latest["tag_name"]
    obj = github.api("/git/ref/tags/" + tag)["object"]
    for _ in range(8):
        if obj["type"] != "tag":
            break
        obj = github.api("/git/tags/" + obj["sha"])["object"]
    require(obj["type"] == "commit", "Release tag does not resolve to a commit")
    commit = git("rev-parse", "refs/tags/" + tag + "^{commit}", root=root).decode().strip()
    require(commit == obj["sha"], "Local release tag disagrees with published tag")
    git("merge-base", "--is-ancestor", commit, target, root=root)
    return {"tag": tag, "commit": commit}


def decision(github, ref=None, root=ROOT):
    target = git("rev-parse", "--verify", (ref or "HEAD") + "^{commit}", root=root).decode().strip()
    baseline = published_baseline(github, target, root)
    before = snapshot(baseline["commit"], root)
    require(json.loads(before[CONFIG])["fix_version"] == baseline["tag"][1:], "Release tag/version mismatch")
    return compare(before, snapshot(target if ref else None, root), baseline)


def enforce(result):
    require(result["version_valid"], "Release policy: " + result.get("status", "invalid version"))
    return result["release_required"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ref", help="Compare a commit instead of the working tree")
    parser.add_argument("--enforce", action="store_true", help="Reject missing or unnecessary version bumps")
    args = parser.parse_args()
    result = decision(GitHub(), args.ref)
    print(json.dumps(result, indent=2))
    if args.enforce:
        enforce(result)


if __name__ == "__main__":
    main()
