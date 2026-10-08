"""Generate build constants and packaging declarations from reviewed compatibility."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from maintenance.common import ROOT, compatibility


def artifacts(config):
    versions = ", ".join(json.dumps(row["version"]) for row in config["supported"])
    code = (
        "// Generated from maintenance/compatibility.json. Do not edit.\n"
        "namespace NewtCraftHubPlantRemovalFix {\n"
        "    internal static class Compatibility {\n"
        f"        internal const string FixVersion = {json.dumps(config['fix_version'])};\n"
        f"        internal const string MinimumNewtVersion = {json.dumps(config['minimum_newtcrafthub_version'])};\n"
        f"        internal const string ReferenceGameVersion = {json.dumps(config['valheim_reference']['version'])};\n"
        f"        internal static readonly string[] SupportedVersions = new[] {{ {versions} }};\n"
        "        internal static bool Supports(System.Version version) {\n"
        "            foreach (string supported in SupportedVersions)\n"
        "                if (version == new System.Version(supported)) return true;\n"
        "            return false;\n"
        "        }\n"
        "    }\n"
        "}\n")
    manifest = {
        "name": "NewtCraftHub_PlantRemovalFix", "version_number": config["fix_version"],
        "website_url": "https://github.com/" + config["repository"],
        "description": "Community addon fixing removal of planted mushrooms and pickables. "
                       "Requires NewtCraftHub; does not run standalone. Created with AI assistance.",
        "dependencies": ["Anatta_Labs-NewtCraftHub-" + config["minimum_newtcrafthub_version"]]
    }
    props = f'<Project><PropertyGroup><Version>{config["fix_version"]}</Version></PropertyGroup></Project>\n'
    return {"src/NewtCraftHubPlantRemovalFix/Compatibility.g.cs": code,
            "packaging/manifest.json": json.dumps(manifest, indent=2) + "\n",
            "maintenance/Version.props": props}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for name, content in artifacts(compatibility()).items():
        path = ROOT / name
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                raise ValueError("Generated file is out of date: " + name)
        else:
            path.write_text(content, encoding="utf-8")
    print("PASS: compatibility declarations are consistent.")


if __name__ == "__main__":
    main()
