import unittest

from onboarding.github import TemporaryError
from onboarding.sheet import Sheet, SheetError
from onboarding.validate import run

from .test_checks import FakeGitHub

HEADER = [
    "Timestamp",
    "Full Name",
    "Email",
    "Github Username",
    "Merged PR Link 1",
    "Merged PR Link 2",
    "Merged PR Link 3 (Networking module)",
]


def row(name="Deepanshu Sahu", username="dee077"):
    return [
        "11/19/2026 9:44:24",
        name,
        "d@example.com",
        username,
        "https://github.com/openwisp/openwisp-users/pull/1",
        "https://github.com/openwisp/openwisp-utils/pull/2",
        "https://github.com/openwisp/openwisp-controller/pull/3",
    ]


class FakeSpreadsheet:
    def __init__(self):
        self.requests = []

    def batch_update(self, body):
        self.requests.extend(body["requests"])


class FakeWorksheet:
    id = 7

    def __init__(self, rows, col_count=7):
        self.rows = rows
        self.col_count = col_count
        self.updates = []
        self.spreadsheet = FakeSpreadsheet()

    def get_all_values(self):
        return self.rows

    def add_cols(self, count):
        self.col_count += count

    def batch_update(self, values):
        self.updates.extend(values)


def written(worksheet):
    return {update["range"]: update["values"][0][0] for update in worksheet.updates}


class TestValidate(unittest.TestCase):
    NOW = "2026-11-21 12:07 UTC"

    def test_results_are_written(self):
        worksheet = FakeWorksheet(
            [HEADER, row(), row(name="Someone Else"), ["", "", "", ""]]
        )
        counts = run(Sheet(worksheet), FakeGitHub(), now=self.NOW)
        self.assertEqual(counts, {"passed": 1, "failed": 1})
        self.assertEqual(worksheet.col_count, 11)
        self.assertEqual(
            written(worksheet),
            {
                "H1": "Validation",
                "I1": "Validation details",
                "J1": "Validated at",
                "K1": "Decision",
                "H2": "Passed",
                "I2": "",
                "J2": self.NOW,
                "K2": "Pending",
                "H3": "Failed",
                "I3": "the Name on your GitHub profile does not match your Full Name",
                "J3": self.NOW,
                "K3": "Rejected",
            },
        )
        (dropdown,) = worksheet.spreadsheet.requests
        rule = dropdown["setDataValidation"]
        self.assertEqual(
            rule["range"],
            {
                "sheetId": 7,
                "startRowIndex": 1,
                "endRowIndex": 2,
                "startColumnIndex": 10,
                "endColumnIndex": 11,
            },
        )
        self.assertEqual(
            [
                value["userEnteredValue"]
                for value in rule["rule"]["condition"]["values"]
            ],
            ["Pending", "Approved", "Rejected"],
        )

    def test_validated_rows_are_skipped(self):
        header = HEADER + [
            "Validation",
            "Validation details",
            "Validated at",
            "Decision",
        ]
        worksheet = FakeWorksheet(
            [header, row() + ["Failed", "x", "y", "Rejected"]], col_count=11
        )
        self.assertEqual(run(Sheet(worksheet), FakeGitHub(), now=self.NOW), {})
        self.assertEqual(worksheet.updates, [])

    def test_temporary_errors_are_retried(self):
        class BrokenGitHub(FakeGitHub):
            def user(self, username):
                raise TemporaryError("rate limited")

        worksheet = FakeWorksheet([HEADER, row()])
        counts = run(Sheet(worksheet), BrokenGitHub(), now=self.NOW)
        self.assertEqual(counts, {"retry": 1})
        self.assertEqual(
            list(written(worksheet).values()),
            ["Validation", "Validation details", "Validated at", "Decision"],
        )
        self.assertEqual(worksheet.spreadsheet.requests, [])

    def test_dry_run_writes_nothing(self):
        worksheet = FakeWorksheet([HEADER, row()])
        counts = run(Sheet(worksheet), FakeGitHub(), dry_run=True, now=self.NOW)
        self.assertEqual(counts, {"passed": 1})
        self.assertEqual(worksheet.updates, [])
        self.assertEqual(worksheet.col_count, 7)

    def test_columns(self):
        with self.subTest("a missing Form column"):
            with self.assertRaisesRegex(SheetError, '"Email" is missing'):
                Sheet(FakeWorksheet([[c for c in HEADER if c != "Email"]]))

        with self.subTest("a duplicated column"):
            with self.assertRaisesRegex(SheetError, "appears more than once"):
                Sheet(FakeWorksheet([HEADER + ["Email"]]))
