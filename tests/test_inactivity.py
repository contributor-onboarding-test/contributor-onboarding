import unittest
from datetime import date
from unittest import mock

from onboarding import settings
from onboarding.github import RemovalError, TemporaryError
from onboarding.inactivity import run
from onboarding.members import Members

from .test_checks import FakeGitHub
from .test_validate import FakeWorksheet, written

TODAY = date(2026, 11, 26)
COLUMNS = list(settings.MEMBER_COLUMNS)


def member(**values):
    values = {
        "github_id": "1",
        "username": "dee077",
        "name": "Deepanshu Sahu",
        "email": "d@example.com",
        "joined": "2026-08-01",
        **values,
    }
    return [values.get(key, "") for key in COLUMNS]


def cell(key, row=2):
    return f"{chr(ord('A') + COLUMNS.index(key))}{row}"


class TestInactivity(unittest.TestCase):
    def review(self, *rows, activity=None, remove=False, dry_run=False, **github):
        worksheet = FakeWorksheet([list(settings.MEMBER_COLUMNS.values()), *rows])
        github.setdefault("members", {"dee077"})
        self.github = FakeGitHub(**github)
        with mock.patch(
            "onboarding.inactivity.last_activity", return_value=activity
        ) as last_activity:
            counts = run(
                Members(worksheet), self.github, TODAY, dry_run=dry_run, remove=remove
            )
        self.last_activity = last_activity
        return counts, written(worksheet)

    def test_active_member(self):
        counts, cells = self.review(member(joined="2026-11-01"))
        self.assertEqual(counts, {"members": 1, "active": 1})
        self.assertEqual(cells, {})

        with self.subTest("activity after the last one is recorded"):
            counts, cells = self.review(member(), activity=date(2026, 11, 20))
            self.assertEqual(counts["active"], 1)
            self.assertEqual(cells, {cell("last_activity"): "2026-11-20"})
            self.assertEqual(
                self.last_activity.call_args.args,
                (self.github, "ORG_ID", "openwisp", "dee077", date(2026, 8, 1)),
            )

    def test_warning(self):
        counts, cells = self.review(member(joined="2026-10-01"))
        self.assertEqual(counts["warned"], 1)
        self.assertEqual(
            cells, {cell("warned"): "2026-11-26", cell("email_status"): "Pending"}
        )

        with self.subTest("activity after the warning clears it"):
            counts, cells = self.review(
                member(warned="2026-11-01", email_status="✅"),
                activity=date(2026, 11, 20),
            )
            self.assertEqual(counts["active"], 1)
            self.assertEqual(
                cells,
                {
                    cell("last_activity"): "2026-11-20",
                    cell("warned"): "",
                    cell("note"): "",
                },
            )

        with self.subTest("removal waits 30 days after the warning"):
            counts, cells = self.review(member(warned="2026-11-10"))
            self.assertEqual(counts["waiting for removal"], 1)
            self.assertEqual(cells, {})

    def test_removal(self):
        inactive = member(warned="2026-10-01", email_status="✅")

        with self.subTest("a dry run of removals by default"):
            counts, cells = self.review(inactive)
            self.assertEqual(counts["would remove"], 1)
            self.assertEqual(cells, {cell("note"): "would be removed"})
            self.assertEqual(self.github.removed, [])

        with self.subTest("removed when enabled"):
            counts, cells = self.review(inactive, remove=True)
            self.assertEqual(counts["removed"], 1)
            self.assertEqual(self.github.removed, [(settings.MEMBERSHIP_ORG, "dee077")])
            self.assertEqual(
                cells,
                {
                    cell("removed"): "2026-11-26",
                    cell("note"): "",
                    cell("email_status"): "Pending",
                },
            )

        with self.subTest("a dry run of the workflow removes no one"):
            counts, cells = self.review(inactive, remove=True, dry_run=True)
            self.assertEqual(counts["would remove"], 1)
            self.assertEqual(self.github.removed, [])
            self.assertEqual(cells, {})

        for github, note in (
            ({"owners": {"dee077"}}, "is an owner of the organization"),
            ({"user_teams": {"dee077": ["community", "core"]}}, "is in other teams"),
            (
                {
                    "removal_error": RemovalError(
                        "GitHub refused the removal (HTTP 403)"
                    )
                },
                "GitHub refused the removal (HTTP 403)",
            ),
        ):
            with self.subTest("a member is left for review", note=note):
                counts, cells = self.review(inactive, remove=True, **github)
                self.assertEqual(counts["needs review"], 1)
                self.assertEqual(cells, {cell("note"): note})
                self.assertEqual(self.github.removed, [])

    def test_accounts(self):
        with self.subTest("a member who left"):
            counts, cells = self.review(member(), members=set())
            self.assertEqual(counts["left"], 1)
            self.assertEqual(
                cells,
                {cell("removed"): "2026-11-26", cell("note"): "left the organization"},
            )

        with self.subTest("a renamed account is followed by its ID"):
            counts, cells = self.review(
                member(joined="2026-11-01"), ids={"renamed": 1}, members={"renamed"}
            )
            self.assertEqual(counts["active"], 1)
            self.assertEqual(cells, {cell("username"): "renamed"})

        with self.subTest("a deleted account"):
            counts, cells = self.review(member(), ids={})
            self.assertEqual(counts["needs review"], 1)
            self.assertEqual(
                cells, {cell("note"): "the GitHub account no longer exists"}
            )

    def test_skipped_members(self):
        rows = (
            member(exempt="TRUE"),
            member(github_id="2", removed="2026-10-01"),
            member(github_id=""),
        )
        counts, cells = self.review(*rows)
        self.assertEqual(counts, {"members": 1, "exempt": 1})
        self.assertEqual(cells, {})

        with self.subTest("a temporary error is retried next week"):
            with mock.patch.object(
                FakeGitHub, "membership", side_effect=TemporaryError("rate limited")
            ):
                counts, cells = self.review(member())
            self.assertEqual(counts, {"members": 1, "retry": 1})

        with self.subTest("a date typed in another format"):
            counts, cells = self.review(member(joined="1/8/2026"))
            self.assertEqual(counts["needs review"], 1)
            self.assertEqual(cells, {cell("note"): "a date is not YYYY-MM-DD"})
