import unittest
from unittest import mock

from onboarding import settings
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
    "Have you started OpenWISP repositories",
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
        "Pending",
    ]


class FakeSpreadsheet:
    def __init__(self, links):
        self.links = links
        self.requests = []
        self.params = None

    def batch_update(self, body):
        self.requests.extend(body["requests"])

    def fetch_sheet_metadata(self, params):
        self.params = params
        rows = []
        for (row, column), url in self.links.items():
            while len(rows) < row:
                rows.append({"values": []})
            values = rows[row - 1]["values"]
            while len(values) <= column:
                values.append({})
            values[column] = {"hyperlink": url}
        return {"sheets": [{"data": [{"rowData": rows}]}]}


class FakeWorksheet:
    id = 7
    title = "Form Responses 1"

    def __init__(self, rows, col_count=8, links=None):
        self.rows = rows
        self.col_count = col_count
        self.updates = []
        self.spreadsheet = FakeSpreadsheet(links or {})

    def get_all_values(self):
        return self.rows

    def add_cols(self, count):
        self.col_count += count

    def batch_update(self, values):
        self.updates.extend(values)


def written(worksheet):
    return {update["range"]: update["values"][0][0] for update in worksheet.updates}


class TestValidate(unittest.TestCase):
    def test_results_are_written(self):
        worksheet = FakeWorksheet(
            [HEADER, row(), row(name="Someone Else"), ["", "", "", ""]]
        )
        counts = run(Sheet(worksheet), FakeGitHub())
        self.assertEqual(
            counts, {"pending": 2, "passed": 1, "failed": 1, "failed account": 1}
        )
        self.assertEqual(worksheet.col_count, 10)
        self.assertEqual(
            written(worksheet),
            {
                "I1": "Validation",
                "J1": "Decision",
                "I2": "✅",
                "J2": "Pending",
                "H2": "✅",
                "I3": "❌ the Name on your GitHub profile does not match"
                " your Full Name",
                "J3": "Reject",
                "H3": "✅",
            },
        )
        requests = worksheet.spreadsheet.requests
        aligned = {
            (
                request["repeatCell"]["range"]["startRowIndex"],
                request["repeatCell"]["range"]["startColumnIndex"],
            )
            for request in requests
            if "repeatCell" in request
        }
        self.assertEqual(
            aligned,
            {(1, 7), (1, 8), (1, 9), (2, 7), (2, 8), (2, 9)},
            "Every written result must be middle aligned",
        )
        (dropdown,) = [
            request for request in requests if "setDataValidation" in request
        ]
        rule = dropdown["setDataValidation"]
        self.assertEqual(
            rule["range"],
            {
                "sheetId": 7,
                "startRowIndex": 1,
                "endRowIndex": 2,
                "startColumnIndex": 9,
                "endColumnIndex": 10,
            },
        )
        self.assertEqual(
            [
                value["userEnteredValue"]
                for value in rule["rule"]["condition"]["values"]
            ],
            ["Pending", "Accept", "Reject"],
        )

    def test_pending_rows_are_validated(self):
        header = HEADER + ["Validation", "Decision"]
        worksheet = FakeWorksheet(
            [
                header,
                row() + ["pending", ""],
                row() + ["✅", "Accept"],
                row(name="Someone Else") + ["❌ x", "Reject"],
            ],
            col_count=10,
        )
        counts = run(Sheet(worksheet), FakeGitHub())
        self.assertEqual(counts, {"pending": 1, "passed": 1})
        self.assertEqual(written(worksheet), {"I2": "✅", "J2": "Pending", "H2": "✅"})

    def test_star_column(self):
        with self.subTest("failed star check"):
            worksheet = FakeWorksheet([HEADER, row()])
            run(Sheet(worksheet), FakeGitHub(stars={}))
            self.assertEqual(written(worksheet)["H2"], "❌")

        with self.subTest(
            "the star check does not run for a member"
        ), mock.patch.object(settings, "SKIP_MEMBERSHIP_CHECK", False):
            worksheet = FakeWorksheet([HEADER, row()])
            run(Sheet(worksheet), FakeGitHub(members={"dee077"}))
            self.assertNotIn("H2", written(worksheet))

    def test_links_behind_labels_are_validated(self):
        labelled = row()
        links = {}
        for index, label in (
            (4, "Merged PR 1"),
            (5, "Merged PR 2"),
            (6, "Merged PR 3"),
        ):
            links[(2, index)] = labelled[index]
            labelled[index] = label
        worksheet = FakeWorksheet([HEADER, labelled], links=links)
        counts = run(Sheet(worksheet), FakeGitHub())
        self.assertEqual(counts, {"pending": 1, "passed": 1})
        self.assertEqual(
            worksheet.spreadsheet.params,
            {
                "ranges": "'Form Responses 1'",
                "fields": "sheets.data.rowData.values.hyperlink",
            },
        )

    def test_temporary_errors_are_retried(self):
        class BrokenGitHub(FakeGitHub):
            def user(self, username):
                raise TemporaryError("rate limited")

        worksheet = FakeWorksheet([HEADER, row()])
        counts = run(Sheet(worksheet), BrokenGitHub())
        self.assertEqual(counts, {"pending": 1, "retry": 1})
        self.assertEqual(list(written(worksheet).values()), ["Validation", "Decision"])
        self.assertEqual(worksheet.spreadsheet.requests, [])

    def test_dry_run_writes_nothing(self):
        worksheet = FakeWorksheet([HEADER, row()])
        counts = run(Sheet(worksheet), FakeGitHub(), dry_run=True)
        self.assertEqual(counts, {"pending": 1, "passed": 1})
        self.assertEqual(worksheet.updates, [])
        self.assertEqual(worksheet.col_count, 8)

    def test_columns(self):
        with self.subTest("a missing Form column"):
            with self.assertRaisesRegex(SheetError, '"Email" is missing'):
                Sheet(FakeWorksheet([[c for c in HEADER if c != "Email"]]))

        with self.subTest("a duplicated column"):
            with self.assertRaisesRegex(SheetError, "appears more than once"):
                Sheet(FakeWorksheet([HEADER + ["Email"]]))
