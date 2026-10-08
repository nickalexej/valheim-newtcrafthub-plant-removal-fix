from __future__ import annotations

import argparse
import io
import json
import zipfile
from pathlib import Path, PurePosixPath

from maintenance.common import API_URL, VERSION, compatibility, require, request, sha256


def parse_package(metadata, archive):
    require(metadata.get("namespace") == "Anatta_Labs" and metadata.get("name") == "NewtCraftHub", "Unexpected package")
    version = metadata["latest"]["version_number"]
    require(VERSION.fullmatch(version), "Invalid Thunderstore version")
    require(metadata["latest"].get("is_active") is True and not metadata.get("is_deprecated"), "Upstream package inactive/deprecated")
    with zipfile.ZipFile(io.BytesIO(archive)) as package:
        files = package.infolist()
        require(len(files) <= 1000 and sum(entry.file_size for entry in files) <= 128 * 1024 * 1024, "Oversized package")
        for entry in files:
            path = PurePosixPath(entry.filename)
            require(not path.is_absolute() and ".." not in path.parts and "\\" not in entry.filename, "Unsafe archive path")
        def read_one(name):
            entries = [entry for entry in files if PurePosixPath(entry.filename).name.lower() == name.lower()]
            require(len(entries) == 1 and entries[0].file_size <= 16 * 1024 * 1024, "Missing/ambiguous/oversized " + name)
            return package.read(entries[0])
        manifest = json.loads(read_one("manifest.json"))
        require(manifest["name"] == "NewtCraftHub" and manifest["version_number"] == version, "Metadata and package disagree")
        dll = read_one("NewtCraftHub.dll")
        require(dll.startswith(b"MZ"), "Upstream DLL is not a PE assembly")
        changelog = read_one("CHANGELOG.md")
        changelog.decode("utf-8-sig")  # Reject invalid text; never execute it.
    snapshot = {"version": version, "dll_sha256": sha256(dll), "changelog_sha256": sha256(changelog)}
    snapshot["fingerprint"] = sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode())
    return snapshot, dll, changelog


def fetch_upstream(fetch=request):
    metadata = fetch(API_URL)
    version = metadata["latest"]["version_number"]
    require(VERSION.fullmatch(version), "Invalid upstream version")
    expected = f"https://thunderstore.io/package/download/Anatta_Labs/NewtCraftHub/{version}/"
    require(metadata["latest"]["download_url"] == expected, "Unexpected download URL")
    return parse_package(metadata, fetch(expected, binary=True))


def known_snapshot(snapshot, config):
    return any(all(snapshot[key] == row[key] for key in ("version", "dll_sha256", "changelog_sha256"))
               for row in config["supported"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--save-inputs", type=Path)
    args = parser.parse_args()
    snapshot, dll, changelog = fetch_upstream()
    snapshot["known"] = known_snapshot(snapshot, compatibility())
    if args.save_inputs:
        args.save_inputs.mkdir(parents=True, exist_ok=True)
        (args.save_inputs / "NewtCraftHub.dll").write_bytes(dll)
        (args.save_inputs / "CHANGELOG.md").write_bytes(changelog)
    text = json.dumps(snapshot, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
