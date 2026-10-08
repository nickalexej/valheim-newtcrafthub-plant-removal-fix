"""Validate versioned release assets without starting Valheim."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from maintenance.common import ROOT, compatibility
from maintenance.package import verify_assets

parser = argparse.ArgumentParser()
parser.add_argument("--directory", type=Path)
parser.add_argument("--commit")
parser.add_argument("--require-clean", action="store_true")
args = parser.parse_args()
directory = args.directory or ROOT / "dist" / compatibility()["fix_version"]
verify_assets(directory, expected_commit=args.commit, require_clean=args.require_clean)
print("PASS: DLL, ZIP, dependency/version declarations, AI notice, build proof and SHA256 verified.")
