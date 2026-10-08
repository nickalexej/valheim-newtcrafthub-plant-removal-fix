from __future__ import annotations

import json
from datetime import datetime

from maintenance.common import GitHub, compatibility, iso_now, utcnow


def run(github):
    if compatibility()["status"] != "active" or github.variable("MAINTENANCE_ENABLED", "true").lower() != "true":
        return {"status": "paused"}
    workflow = github.api("/actions/workflows/upstream-check.yml")
    state = workflow["state"]
    if state == "disabled_manually":
        return {"status": "monitor-paused-manually"}
    if state == "disabled_inactivity":
        github.api("/actions/workflows/upstream-check.yml/enable", "PUT")
        github.api("/actions/workflows/upstream-check.yml/dispatches", "POST", {"ref": "main"})
    elif state == "active":
        runs = github.api("/actions/workflows/upstream-check.yml/runs?per_page=1")["workflow_runs"]
        stale = not runs or (utcnow() - datetime.fromisoformat(runs[0]["created_at"].replace("Z", "+00:00"))).total_seconds() > 26 * 3600
        failed = bool(runs and runs[0].get("status") == "completed" and runs[0].get("conclusion") == "failure")
        if stale or failed:
            github.api("/actions/workflows/upstream-check.yml/dispatches", "POST", {"ref": "main"})
    else:
        return {"status": "unexpected-workflow-state", "state": state}
    github.set_variable("MAC_LAST_RUN_AT", iso_now())
    github.resolve_system_issue("macmini-stale")
    return {"status": "ok", "workflow_state": state}


if __name__ == "__main__":
    print(json.dumps(run(GitHub()), indent=2))
