"""Read the current upstream state on request without writing to GitHub."""

from __future__ import annotations

import argparse
import json
import os

from maintenance.common import compatibility
from maintenance.upstream import fetch_upstream, known_snapshot


def run(github=None, *, dry_run=False, fetch=fetch_upstream, config=None):
    # Older callers may still pass a GitHub client and dry_run.
    config = config or compatibility()
    if config["status"] != "active" or os.environ.get("MAINTENANCE_ENABLED", "true").lower() != "true":
        return {"status": "paused", "changed": False}
    snapshot, _, _ = fetch()
    return {"status": "ok", "changed": not known_snapshot(snapshot, config), "upstream": snapshot}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Accepted for compatibility. All checks are read-only.")
    parser.parse_args()
    print(json.dumps(run(), indent=2))


if __name__ == "__main__":
    main()
