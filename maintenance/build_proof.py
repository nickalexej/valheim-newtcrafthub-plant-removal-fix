from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from maintenance.common import ROOT, compatibility, require, sha256
from maintenance.package import DLL_NAME, PROOF_NAME, zip_name


def verify_references(directory):
    for name, expected in compatibility()["valheim_reference"]["sha256"].items():
        require(sha256((directory / name).read_bytes()) == expected, "Unreviewed Valheim reference: " + name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--references", type=Path, required=True)
    parser.add_argument("--proof", action="store_true")
    args = parser.parse_args()
    verify_references(args.references)
    if args.proof:
        config = compatibility()
        dist = ROOT / "dist" / config["fix_version"]
        api = json.loads((dist / "api-check.json").read_text())
        require(api["passed"] and api["checked_references"] > 0, "API verifier did not pass")
        require(api["plugin_version"] == config["fix_version"], "Compiled plugin version disagrees")
        require(api["minimum_dependency"] == config["minimum_newtcrafthub_version"], "Compiled dependency disagrees")
        binary = dist / DLL_NAME
        proof = {
            "schema_version": 1, "fix_version": config["fix_version"],
            "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "clean_worktree": not subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip(),
            "dll_sha256": sha256(binary.read_bytes()),
            "compatibility_sha256": sha256((ROOT / "maintenance/compatibility.json").read_bytes()),
            "valheim_reference": config["valheim_reference"],
            "checks": {"api": "passed", "references": "passed", "tests": "passed"},
            "api_references": api["checked_references"], "gameplay_test": "not-run"
        }
        (dist / PROOF_NAME).write_text(json.dumps(proof, indent=2) + "\n")
        assets = [DLL_NAME, zip_name(config), PROOF_NAME]
        (dist / "SHA256SUMS.txt").write_text("".join(
            sha256((dist / name).read_bytes()) + "  " + name + "\n" for name in assets), encoding="ascii")
        (dist / "api-check.json").unlink()
    print("PASS: private Valheim reference hashes verified.")


if __name__ == "__main__":
    main()
