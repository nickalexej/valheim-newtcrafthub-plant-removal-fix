from __future__ import annotations

import io
import json
import struct
import zipfile
from pathlib import Path, PurePosixPath

from maintenance.common import ROOT, SHA256, compatibility, require, sha256
from maintenance.generate import artifacts

DLL_NAME = "NewtCraftHubPlantRemovalFix.dll"
PROOF_NAME = "BUILD-VERIFICATION.json"
ZIP_DLL = "BepInEx/plugins/NewtCraftHubPlantRemovalFix/" + DLL_NAME


def zip_name(config):
    latest = max((row["version"] for row in config["supported"]), key=lambda v: tuple(map(int, v.split("."))))
    return f"NewtCraftHubPlantRemovalFix-{config['fix_version']}-for-NewtCraftHub-{latest}.zip"


def expected_assets(config):
    return {DLL_NAME, zip_name(config), "SHA256SUMS.txt", PROOF_NAME}


def verify_assets(directory, *, root=ROOT, expected_commit=None, require_clean=False):
    config = compatibility(root)
    expected = expected_assets(config)
    require({path.name for path in directory.iterdir() if path.is_file()} == expected, "Unexpected/missing release assets")
    for name, text in artifacts(config).items():
        require((root / name).read_text(encoding="utf-8") == text, "Outdated generated file: " + name)
    binary = (directory / DLL_NAME).read_bytes()
    require(binary.startswith(b"MZ"), "Invalid plugin DLL")
    require(b"/Users/" not in binary and b"C:\\Users\\" not in binary, "Local debug path in DLL")
    readme = (root / "README.md").read_text(encoding="utf-8")
    require(readme.strip().endswith("Dieser Fix wurde mit Unterstützung von KI erstellt."), "AI notice missing")
    with zipfile.ZipFile(directory / zip_name(config)) as package:
        entries = package.infolist()
        require(len(entries) == len({entry.filename for entry in entries}), "Duplicate ZIP entry")
        for entry in entries:
            path = PurePosixPath(entry.filename)
            require(not path.is_absolute() and ".." not in path.parts and "\\" not in entry.filename, "Unsafe ZIP path")
        files = {entry.filename for entry in entries if not entry.is_dir()}
        require(files == {ZIP_DLL, "manifest.json", "icon.png", "README.md", "README.en.md", "LICENSE", "CHANGELOG.md"},
                "ZIP must contain only plugin and declared documentation")
        require(package.testzip() is None, "Corrupt ZIP")
        require(package.read(ZIP_DLL) == binary, "DLL differs between assets")
        for name in ("README.md", "README.en.md", "LICENSE", "CHANGELOG.md"):
            require(package.read(name) == (root / name).read_bytes(), "Documentation differs: " + name)
        require(package.read("manifest.json") == (root / "packaging/manifest.json").read_bytes(), "Manifest differs")
        icon = package.read("icon.png")
        require(icon == (root / "packaging/icon.png").read_bytes(), "Icon differs")
        require(icon.startswith(b"\x89PNG\r\n\x1a\n") and struct.unpack(">II", icon[16:24]) == (256, 256), "Invalid icon")
    sums = {}
    for line in (directory / "SHA256SUMS.txt").read_text(encoding="ascii").splitlines():
        digest, name = line.split("  ", 1)
        require(SHA256.fullmatch(digest) and Path(name).name == name and name not in sums, "Invalid checksum entry")
        sums[name] = digest
    require(set(sums) == {DLL_NAME, zip_name(config), PROOF_NAME}, "Checksum coverage incomplete")
    for name, digest in sums.items():
        require(sha256((directory / name).read_bytes()) == digest, "Checksum mismatch: " + name)
    proof = json.loads((directory / PROOF_NAME).read_text(encoding="utf-8"))
    require(proof["schema_version"] == 1 and proof["fix_version"] == config["fix_version"], "Invalid build proof")
    require(proof["dll_sha256"] == sha256(binary), "Build proof DLL mismatch")
    require(proof["compatibility_sha256"] == sha256((root / "maintenance/compatibility.json").read_bytes()), "Build proof compatibility mismatch")
    require(proof["valheim_reference"] == config["valheim_reference"], "Build proof reference mismatch")
    require(proof["checks"]["api"] == "passed" and proof["checks"]["references"] == "passed", "Build/API checks missing")
    require(proof["checks"]["tests"] == "passed", "Maintenance regression tests missing")
    require(proof["gameplay_test"] == "not-run", "Automated build cannot claim gameplay verification")
    require(SHA256.fullmatch(proof["dll_sha256"]) and len(proof["commit"]) == 40
            and all(c in "0123456789abcdef" for c in proof["commit"]), "Invalid build provenance")
    if expected_commit:
        require(proof["commit"] == expected_commit, "Build proof belongs to another commit")
    if require_clean:
        require(proof["clean_worktree"] is True, "Release built from uncommitted changes")
    return proof
