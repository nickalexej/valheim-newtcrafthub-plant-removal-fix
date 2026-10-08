from __future__ import annotations

import json
import os
import re
from pathlib import Path

from maintenance.common import GitHub, require

FIELDS = {
    "Valheim-Version": "Valheim-Version",
    "NewtCraftHub-Version": "NewtCraftHub-Version",
    "Fix-Version": "Fix-Version",
    "Werkzeug": "Werkzeug (Hammer/Kultivator)",
    "Spielmodus": "Spielmodus (Solo/Server)",
    "Weitere Mods": "weitere relevante Mods",
    "Log-Auszug": "relevanter BepInEx-Log-Auszug"
}
MARKER = "<!-- newt-issue-triage:v1 -->"


def missing_fields(body):
    missing = []
    for heading, description in FIELDS.items():
        match = re.search(r"(?mi)^### " + re.escape(heading) + r"\s*\n([\s\S]*?)(?=^### |\Z)", body)
        value = match.group(1).strip() if match else ""
        if not value or value in {"_No response_", "Keine Angabe", "Bitte auswählen"}:
            missing.append(description)
    return missing


def triage(github, event):
    issue = event.get("issue") or {}
    if "pull_request" in issue or issue.get("state") != "open" or issue.get("user", {}).get("type") == "Bot":
        return {"status": "ignored"}
    labels = {row["name"] for row in issue.get("labels", [])}
    if "maintenance" in labels:
        return {"status": "maintenance"}
    number = int(issue["number"])
    missing = missing_fields(issue.get("body") or "")
    github.api(f"/issues/{number}/labels", "POST", ["needs-info" if missing else "triage"])
    if not missing:
        if "needs-info" in labels:
            github.api(f"/issues/{number}/labels/needs-info", "DELETE")
        return {"status": "ready"}
    comments = github.list_all(f"/issues/{number}/comments")
    if not any(MARKER in row.get("body", "") and row["user"].get("type") == "Bot" for row in comments):
        github.api(f"/issues/{number}/comments", "POST", {
            "body": MARKER + "\nDanke für den Bericht. Für die Prüfung fehlen noch:\n\n"
                    + "\n".join("- " + field for field in missing)
                    + "\n\nBitte ergänze die Angaben im Fehlerformular. Die Valheim-Spielversion und die "
                    "NewtCraftHub-Modversion sind unterschiedliche Angaben. Teile nur den relevanten Log-Auszug. "
                    "Diese automatische Antwort sammelt Angaben; sie bestätigt noch keine Fehlerursache."})
    return {"status": "needs-info", "missing": missing}


if __name__ == "__main__":
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    require(event.get("action") in {"opened", "edited", "reopened"}, "Unexpected issue event")
    print(json.dumps(triage(GitHub(), event), ensure_ascii=False))
