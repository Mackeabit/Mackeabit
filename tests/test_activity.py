"""Protect identity, pagination, deduplication and failure handling before publishing."""

from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from collect_activity import GitHub, collect, save_calendar


def repository(name, **extra):
    return dict(full_name=f"Mackeabit/{name}", owner={"login": "Mackeabit"},
                private=False, fork=False, size=10, default_branch="main", **extra)


def commit(sha, timestamp="2026-10-31T03:00:00Z", actor="Mackeabit"):
    return {"sha": sha, "author": {"login": actor}, "commit": {"author": {"date": timestamp}}}


class FixtureClient:
    def __init__(self):
        self.calls = []
        self.data = {
            "users/Mackeabit/repos": [repository("One"), repository("Two")],
            "repos/Mackeabit/One/commits": [commit("same"), commit("bot", actor="github-actions[bot]")],
            "repos/Mackeabit/Two/commits": [commit("same"), commit("today", "2026-11-01T00:30:00+09:00")],
            "repos/Mackeabit/One/issues": [
                {"id": 1, "user": {"login": "Mackeabit"}, "created_at": "2026-11-01T01:00:00Z"},
                {"id": 2, "user": {"login": "Mackeabit"}, "created_at": "2026-11-01T01:00:00Z", "pull_request": {}},
                {"id": 3, "user": {"login": "someone-else"}, "created_at": "2026-11-01T01:00:00Z"},
                {"id": 4, "user": {"login": "Mackeabit"}, "created_at": "2024-01-01T01:00:00Z"},
            ],
            "repos/Mackeabit/Two/issues": [],
        }

    def get(self, endpoint):
        return {"login": "Mackeabit"}

    def pages(self, endpoint, **params):
        self.calls.append((endpoint, params))
        return iter(deepcopy(self.data[endpoint]))


class ActivityTests(unittest.TestCase):
    def test_real_actor_deduplication_dates_and_issue_pr_split(self):
        client = FixtureClient()
        result = collect(client, "Mackeabit", date(2026, 11, 1))
        self.assertEqual(result["counts_by_type"], {"commits": 2, "issues": 1, "pull_requests": 1})
        self.assertEqual(result["total_contributions"], 4)
        self.assertEqual(result["active_days"], 2)
        counts = {d["date"]: d["count"] for d in result["days"]}
        self.assertEqual(counts["2026-10-31"], 2)  # UTC, including +09:00 activity.
        self.assertEqual(counts["2026-11-01"], 2)
        self.assertEqual(len(result["days"]), 365)
        self.assertEqual(result["days"][0]["y"], 0)
        self.assertTrue(all(params["sha"] == "main" for endpoint, params in client.calls if endpoint.endswith("/commits")))

    def test_excludes_private_fork_and_other_owner(self):
        client = FixtureClient()
        private = repository("Secret")
        private["private"] = True
        fork = repository("Fork")
        fork["fork"] = True
        other = repository("Other")
        other["owner"]["login"] = "Other"
        client.data["users/Mackeabit/repos"].extend([private, fork, other])
        result = collect(client, "Mackeabit", date(2026, 11, 1))
        self.assertEqual(result["repositories_scanned"], 2)
        self.assertNotIn("Secret", json.dumps(result))

    def test_pagination_fetches_more_than_one_page(self):
        class Paged(GitHub):
            def get(self, path, params=None):
                return list(range(100)) if params["page"] == 1 else [100]
        self.assertEqual(list(Paged().pages("example")), list(range(101)))

    def test_zero_size_metadata_does_not_discard_real_commits(self):
        client = FixtureClient()
        for repo in client.data["users/Mackeabit/repos"]:
            repo["size"] = 0
        result = collect(client, "Mackeabit", date(2026, 11, 1))
        self.assertEqual(result["counts_by_type"]["commits"], 2)

    def test_second_page_failure_is_not_treated_as_complete(self):
        class Broken(GitHub):
            def get(self, path, params=None):
                if params["page"] == 2:
                    raise RuntimeError("API failed")
                return list(range(100))
        with self.assertRaises(RuntimeError):
            list(Broken().pages("example"))

    def test_empty_results_preserve_previous_files(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = Path(directory) / "activity.json"
            output = Path(directory) / "calendar.json"
            previous.write_text('{"total_contributions": 12}', encoding="utf-8")
            output.write_text("last valid data", encoding="utf-8")
            with self.assertRaises(ValueError):
                save_calendar({"total_contributions": 0}, output, previous)
            self.assertEqual(output.read_text(encoding="utf-8"), "last valid data")


if __name__ == "__main__":
    unittest.main()
