"""Verify release packaging and dependency declarations without starting Valheim."""
from pathlib import Path
import hashlib
import json
import re
import struct
import xml.etree.ElementTree as ET
import zipfile

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "packaging/manifest.json").read_text(encoding="utf-8"))
version = manifest["version_number"]
assert manifest["dependencies"] == ["Anatta_Labs-NewtCraftHub-1.7.0"]
assert re.fullmatch(r"[A-Za-z0-9_]+", manifest["name"])
assert len(manifest["description"]) <= 250
project = ET.parse(root / "src/NewtCraftHubPlantRemovalFix/NewtCraftHubPlantRemovalFix.csproj")
assert project.findtext(".//Version") == version
source = (root / "src/NewtCraftHubPlantRemovalFix/Plugin.cs").read_text(encoding="utf-8")
assert '[BepInDependency(NewtGuid, "1.7.0")]' in source
assert 'public const string NewtGuid = "newton.newtcraftboxes";' in source
assert "newt.Metadata.Version != new System.Version(1, 7, 0)" in source
assert f'[BepInPlugin(PluginGuid, "NewtCraftHub Plant Removal Fix", "{version}")]' in source

readme = (root / "README.md").read_text(encoding="utf-8")
assert readme.strip().endswith("Dieser Fix wurde mit Unterstützung von KI erstellt.")
assert (root / "README.en.md").is_file()
assert (root / "LICENSE").is_file()

dist = root / "dist"
name = f"NewtCraftHubPlantRemovalFix-{version}-for-NewtCraftHub-1.7.0.zip"
binary = (dist / "NewtCraftHubPlantRemovalFix.dll").read_bytes()
assert binary.startswith(b"MZ")
assert b"/Users/" not in binary and b"C:\\Users\\" not in binary
with zipfile.ZipFile(dist / name) as package:
    assert package.testzip() is None
    files = {entry for entry in package.namelist() if not entry.endswith("/")}
    expected_dll = "BepInEx/plugins/NewtCraftHubPlantRemovalFix/NewtCraftHubPlantRemovalFix.dll"
    assert {entry for entry in files if entry.lower().endswith(".dll")} == {expected_dll}
    assert {"manifest.json", "icon.png", "README.md", "README.en.md", "LICENSE", "CHANGELOG.md"} <= files
    assert package.read(expected_dll) == binary
    assert json.loads(package.read("manifest.json")) == manifest
    assert package.read("README.md").decode("utf-8") == readme
    icon = package.read("icon.png")
    assert icon.startswith(b"\x89PNG\r\n\x1a\n")
    assert struct.unpack(">II", icon[16:24]) == (256, 256)

checksums = (dist / "SHA256SUMS.txt").read_text(encoding="ascii").splitlines()
assert len(checksums) == 2
for line in checksums:
    expected_hash, filename = line.split("  ", 1)
    assert Path(filename).name == filename
    assert hashlib.sha256((dist / filename).read_bytes()).hexdigest() == expected_hash

print("PASS: DLL, ZIP integrity, 256x256 PNG, version declarations, exact NewtCraftHub 1.7.0 dependency, AI notice and SHA256 checksums verified.")
