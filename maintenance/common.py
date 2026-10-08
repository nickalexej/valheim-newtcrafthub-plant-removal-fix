from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "nickalexej/valheim-newtcrafthub-plant-removal-fix"
API_URL = "https://thunderstore.io/api/experimental/package/Anatta_Labs/NewtCraftHub/"
CHANGELOG_URL = "https://thunderstore.io/c/valheim/p/Anatta_Labs/NewtCraftHub/changelog"
VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
SHA256 = re.compile(r"[0-9a-f]{64}")
SYSTEM_AUTHORS = {"github-actions[bot]", "nickalexej", "nickalexej-newtcraft-maintenance[bot]"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def utcnow():
    return datetime.now(timezone.utc)


def iso_now():
    return utcnow().isoformat(timespec="seconds")


def compatibility(root=ROOT):
    value = json.loads((root / "maintenance/compatibility.json").read_text(encoding="utf-8"))
    require(value["schema_version"] == 1 and value["repository"] == REPOSITORY, "Unexpected compatibility schema/repository")
    require(VERSION.fullmatch(value["fix_version"]), "Invalid fix version")
    require(value["status"] in {"active", "paused", "upstream-fixed"}, "Invalid maintenance status")
    require(VERSION.fullmatch(value["minimum_newtcrafthub_version"]), "Invalid dependency version")
    require(value["supported"], "At least one supported upstream version is required")
    versions = []
    for row in value["supported"]:
        require(VERSION.fullmatch(row["version"]), "Invalid upstream version")
        require(SHA256.fullmatch(row["dll_sha256"]) and SHA256.fullmatch(row["changelog_sha256"]), "Invalid upstream digest")
        require(row["assessment"] == "required" and row["evidence"].strip(), "Compatibility needs code-based evidence")
        versions.append(row["version"])
    require(len(versions) == len(set(versions)), "Duplicate supported version")
    require(value["minimum_newtcrafthub_version"] == min(versions, key=lambda v: tuple(map(int, v.split(".")))), "Dependency must equal oldest supported version")
    reference = value["valheim_reference"]
    require(VERSION.fullmatch(reference["version"]), "Invalid Valheim reference version")
    for name, digest in reference["sha256"].items():
        require(Path(name).name == name and SHA256.fullmatch(digest), "Invalid reference digest")
    if value["status"] == "upstream-fixed":
        require(VERSION.fullmatch(value["upstream_fixed_from"] or ""), "Retirement needs confirmed upstream version")
        require(value.get("upstream_fixed_evidence", "").strip(), "Retirement needs code and test evidence")
    return value


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        require(newurl.startswith("https://"), "Refusing insecure redirect")
        redirected = super().redirect_request(request, fp, code, msg, headers, newurl)
        if redirected:
            # Never forward repository credentials to a CDN or another host.
            redirected.remove_header("Authorization")
        return redirected


def request(url, *, method="GET", payload=None, token=None, binary=False, attempts=3, limit=32 * 1024 * 1024):
    require(url.startswith("https://"), "HTTPS required")
    headers = {"User-Agent": "NewtCraftHub-PlantRemovalFix-Maintenance", "Accept": "application/json"}
    if token:
        require(url.startswith("https://api.github.com/"), "Credentials only go to GitHub API")
        headers.update({"Authorization": "Bearer " + token, "X-GitHub-Api-Version": "2022-11-28"})
    if binary:
        headers["Accept"] = "application/octet-stream"
    body = None if payload is None else json.dumps(payload).encode()
    if body is not None:
        headers["Content-Type"] = "application/json"
    opener = urllib.request.build_opener(SafeRedirect())
    for attempt in range(attempts):
        try:
            with opener.open(urllib.request.Request(url, data=body, headers=headers, method=method), timeout=20) as response:
                data = response.read(limit + 1)
                require(len(data) <= limit, "Response exceeds size limit")
                if binary:
                    return data
                return json.loads(data) if data else None
        except urllib.error.HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt + 1 == attempts:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt + 1 == attempts:
                raise
        # Writes are never retried here: a timeout may have already applied them.
        if method != "GET":
            raise RuntimeError("Write outcome unknown; reconcile remote state before retrying")
        time.sleep(1 + attempt)
    raise RuntimeError("Request failed")


class GitHub:
    def __init__(self, token=None):
        if token is None:
            from maintenance.github_auth import github_token
            token = github_token()
        require(bool(token), "GitHub authentication required")
        self.token = token
        self.base = "https://api.github.com/repos/" + REPOSITORY

    def api(self, path, method="GET", payload=None, binary=False):
        require(path.startswith("/") and ".." not in path and "://" not in path, "Repository-relative endpoint required")
        return request(self.base + path, method=method, payload=payload, token=self.token, binary=binary)

    def list_all(self, path):
        result = []
        for page in range(1, 101):
            separator = "&" if "?" in path else "?"
            rows = self.api(path + separator + f"per_page=100&page={page}")
            require(isinstance(rows, list), "Expected paginated list")
            result.extend(rows)
            if len(rows) < 100:
                return result
        raise RuntimeError("Pagination limit exceeded")

    def upsert_issue(self, key, title, body, labels):
        marker = "<!-- newt-maintenance:" + key + " -->"
        matches = [row for row in self.list_all("/issues?state=all")
                   if "pull_request" not in row and marker in (row.get("body") or "")
                   and row["user"]["login"] in SYSTEM_AUTHORS]
        require(len(matches) <= 1, "Duplicate maintenance marker; resolve manually")
        content = marker + "\n" + body
        if matches:
            row = matches[0]
            if row.get("body") != content or row["state"] != "open":
                self.api(f"/issues/{row['number']}", "PATCH", {"body": content, "state": "open"})
            return row["number"]
        return self.api("/issues", "POST", {"title": title, "body": content, "labels": labels})["number"]

    def resolve_system_issue(self, key):
        marker = "<!-- newt-maintenance:" + key + " -->"
        for row in self.list_all("/issues?state=open"):
            if "pull_request" not in row and marker in (row.get("body") or "") and row["user"]["login"] in SYSTEM_AUTHORS:
                self.api(f"/issues/{row['number']}", "PATCH", {"state": "closed", "state_reason": "completed"})

    def set_variable(self, name, value):
        require(re.fullmatch(r"[A-Z][A-Z0-9_]*", name), "Invalid variable")
        try:
            self.api("/actions/variables/" + name)
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            self.api("/actions/variables", "POST", {"name": name, "value": value})
        else:
            self.api("/actions/variables/" + name, "PATCH", {"name": name, "value": value})

    def variable(self, name, default=""):
        try:
            return self.api("/actions/variables/" + name)["value"]
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return default
            raise
