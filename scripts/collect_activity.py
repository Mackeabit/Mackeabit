"""Collect real public repository activity without the profile contribution API."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "GitHub REST public repository activity"


class EmptyRepository(Exception):
    """GitHub explicitly reports an uninitialized repository."""


class GitHub:
    def __init__(self, use_gh=False):
        self.use_gh = use_gh
        self.token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

    def get(self, path, params=None):
        endpoint = path + ("?" + urlencode(params) if params else "")
        for attempt in range(3):
            if self.use_gh:
                result = subprocess.run(
                    ["gh", "api", endpoint, "-H", "Accept: application/vnd.github+json"],
                    capture_output=True, text=True, encoding="utf-8", check=False,
                )
                if result.returncode == 0:
                    return json.loads(result.stdout)
                if path.endswith("/commits") and "Git Repository is empty" in result.stderr and "409" in result.stderr:
                    raise EmptyRepository(path)
                # Fail closed on authentication, permission, and API errors.
                raise RuntimeError(f"GitHub request failed: {path}; {result.stderr.strip()}")
            headers = {"Accept": "application/vnd.github+json", "User-Agent": "Mackeabit-profile-activity"}
            if self.token:
                headers["Authorization"] = "Bearer " + self.token
            try:
                with urlopen(Request("https://api.github.com/" + endpoint, headers=headers), timeout=30) as response:
                    return json.load(response)
            except HTTPError as error:
                if error.code == 409 and path.endswith("/commits"):
                    detail = error.read().decode("utf-8", errors="replace")
                    if "Git Repository is empty" in detail:
                        raise EmptyRepository(path) from error
                if error.code < 500 or attempt == 2:
                    raise RuntimeError(f"GitHub returned HTTP {error.code}: {path}") from error
            except (URLError, TimeoutError):
                if attempt == 2:
                    raise
            time.sleep(2 ** attempt)
        raise RuntimeError(f"GitHub request did not complete: {path}")

    def pages(self, path, **params):
        # Do not silently publish a partial calendar when pagination fails.
        for page in range(1, 1001):
            batch = self.get(path, dict(params, per_page=100, page=page))
            if not isinstance(batch, list):
                raise ValueError(f"Expected a GitHub list: {path}")
            yield from batch
            if len(batch) < 100:
                return
        raise RuntimeError(f"Pagination limit reached: {path}")


def utc_day(timestamp):
    moment = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        raise ValueError("Activity timestamp is missing a timezone")
    return moment.astimezone(timezone.utc).date()


def collect(client, account, today):
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", account):
        raise ValueError("Invalid GitHub account")
    identity = client.get(f"users/{account}")
    if identity["login"].lower() != account.lower():
        raise ValueError("Unexpected GitHub identity")
    account = identity["login"]
    # 53 Sunday-first columns, ending at today's cell. No invented future days.
    start = today - timedelta(days=(today.weekday() + 1) % 7 + 52 * 7)
    since = start.isoformat() + "T00:00:00Z"
    repositories = sorted(
        (repo for repo in client.pages(f"users/{account}/repos", type="owner")
         if not repo["private"] and not repo["fork"]
         and repo["owner"]["login"].lower() == account.lower()),
        key=lambda repo: repo["full_name"].lower(),
    )
    if not repositories:
        raise ValueError("No public owned non-fork repositories were returned")
    events = {}

    def add(key, kind, timestamp):
        day = utc_day(timestamp)
        if start <= day <= today:
            # Commit SHAs are unique across repositories; issue and PR IDs are global.
            event = {"kind": kind, "date": day.isoformat()}
            if key in events and events[key] != event:
                raise ValueError("Conflicting duplicate activity")
            events[key] = event

    for repo in repositories:
        name = repo["full_name"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", name):
            raise ValueError("Unexpected repository name")
        if repo.get("default_branch"):
            try:
                for commit in client.pages(
                    f"repos/{name}/commits", author=account,
                    sha=repo["default_branch"], since=since,
                ):
                    # Exclude automation and records not attributed to this GitHub account.
                    if (commit.get("author") or {}).get("login", "").lower() == account.lower():
                        add("commit:" + commit["sha"], "commits", commit["commit"]["author"]["date"])
            except EmptyRepository:
                pass
        for issue in client.pages(
            f"repos/{name}/issues", state="all", creator=account,
            since=since, sort="created", direction="desc",
        ):
            if (issue.get("user") or {}).get("login", "").lower() == account.lower():
                kind = "pull_requests" if "pull_request" in issue else "issues"
                add(f"issue:{issue['id']}", kind, issue["created_at"])

    totals = Counter(event["kind"] for event in events.values())
    counts = Counter(event["date"] for event in events.values())
    maximum = max(counts.values(), default=0)
    days = []
    for offset in range((today - start).days + 1):
        day = start + timedelta(days=offset)
        count = counts[day.isoformat()]
        days.append({
            "date": day.isoformat(), "count": count,
            "level": math.ceil(4 * count / maximum) if count else 0,
            "x": offset // 7, "y": offset % 7,
        })
    canonical = json.dumps(sorted(events.items()), separators=(",", ":"), sort_keys=True)
    return {
        "schema_version": 1, "account": account, "source": SOURCE,
        "scope": "Public owned non-fork repositories; default-branch authored commits and created issues/pull requests; UTC dates",
        "start": start.isoformat(), "end": today.isoformat(),
        "total_contributions": len(events), "active_days": len(counts),
        "calendar_days": len(days), "repositories_scanned": len(repositories),
        "counts_by_type": {kind: totals[kind] for kind in ("commits", "issues", "pull_requests")},
        "activity_digest": hashlib.sha256(canonical.encode()).hexdigest(),
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "days": days,
    }


def save_calendar(calendar, output, previous):
    if previous.exists():
        prior = json.loads(previous.read_text(encoding="utf-8"))
        if prior.get("total_contributions", 0) and not calendar["total_contributions"]:
            raise ValueError("Refusing to replace real activity with an empty result")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(calendar, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", default=os.environ.get("PROFILE_OWNER", "Mackeabit"))
    parser.add_argument("--as-of", type=date.fromisoformat, default=datetime.now(timezone.utc).date())
    parser.add_argument("--output", type=Path, default=ROOT / ".tmp" / "repository-activity.json")
    parser.add_argument("--use-gh", action="store_true", help="Use the locally authenticated GitHub CLI; no token is copied.")
    args = parser.parse_args()
    calendar = collect(GitHub(args.use_gh), args.account, args.as_of)
    save_calendar(calendar, args.output, ROOT / "generated" / "activity.json")
    print(json.dumps({key: value for key, value in calendar.items() if key != "days"}, indent=2))


if __name__ == "__main__":
    main()
