import unittest
from datetime import date, datetime
from unittest import mock

from gspread.exceptions import WorksheetNotFound

from onboarding import settings
from onboarding.github import InviteError, TemporaryError
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
    "Weekly meeting 1",
    "Weekly meeting 2",
]
RESULTS = ["Validation", "Decision", "Email status", "Invite status"]


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
        "11/4/2026",
        "11/18/2026",
    ]


def unformatted(value):
    """Returns the value as the Sheets API does without formatting."""
    try:
        day = datetime.strptime(value, "%m/%d/%Y").date()
    except ValueError:
        return value
    return (day - date(1899, 12, 30)).days


class FakeSpreadsheet:
    def __init__(self, links):
        self.links = links
        self.requests = []
        self.params = None
        self.worksheets = {}

    def worksheet(self, title):
        if title not in self.worksheets:
            raise WorksheetNotFound(title)
        return self.worksheets[title]

    def add_worksheet(self, title, rows, cols):
        self.worksheets[title] = FakeWorksheet([], col_count=cols)
        return self.worksheets[title]

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

    def __init__(self, rows, col_count=10, links=None):
        self.rows = rows
        self.col_count = col_count
        self.updates = []
        self.spreadsheet = FakeSpreadsheet(links or {})

    def get_all_values(self, value_render_option=None):
        if value_render_option is None:
            return self.rows
        return [[unformatted(value) for value in row] for row in self.rows]

    def add_cols(self, count):
        self.col_count += count

    def batch_update(self, values):
        self.updates.extend(values)

    def append_rows(self, rows, value_input_option):
        self.rows = self.rows + rows


def written(worksheet):
    return {update["range"]: update["values"][0][0] for update in worksheet.updates}


class TestValidate(unittest.TestCase):
    def test_results_are_written(self):
        worksheet = FakeWorksheet(
            [HEADER, row(), row(name="Someone Else"), ["", "", "", ""]]
        )
        counts = run(Sheet(worksheet), FakeGitHub())
        self.assertEqual(
            counts,
            {
                "pending": 2,
                "passed": 1,
                "failed": 1,
                "failed account": 1,
                "emails queued": 1,
            },
        )
        self.assertEqual(worksheet.col_count, 14)
        self.assertEqual(
            written(worksheet),
            {
                "K1": "Validation",
                "L1": "Decision",
                "M1": "Email status",
                "N1": "Invite status",
                "K2": "✅",
                "L2": "Pending",
                "H2": "✅",
                "K3": "❌ the Name on your GitHub profile does not match"
                " your Full Name",
                "L3": "Reject",
                "M3": "Pending",
                "H3": "✅",
            },
        )
        passed, rejected = worksheet.spreadsheet.requests
        self.assertEqual(rejected["setDataValidation"]["range"]["startRowIndex"], 2)
        rule = passed["setDataValidation"]
        self.assertEqual(
            rule["range"],
            {
                "sheetId": 7,
                "startRowIndex": 1,
                "endRowIndex": 2,
                "startColumnIndex": 11,
                "endColumnIndex": 12,
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
        header = HEADER + RESULTS
        worksheet = FakeWorksheet(
            [
                header,
                row() + ["pending", "", ""],
                row() + ["✅", "Accept", "✅"],
                row(name="Someone Else") + ["❌ x", "Reject", "✅"],
            ],
            col_count=14,
        )
        counts = run(Sheet(worksheet), FakeGitHub())
        self.assertEqual(counts, {"pending": 1, "passed": 1})
        self.assertEqual(written(worksheet), {"K2": "✅", "L2": "Pending", "H2": "✅"})

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
        self.assertEqual(
            list(written(worksheet).values()),
            RESULTS,
        )
        self.assertEqual(worksheet.spreadsheet.requests, [])

    def decided(self, *rows):
        header = HEADER + RESULTS
        return FakeWorksheet([header] + [row() + values for values in rows], 14)

    def test_decisions(self):
        worksheet = self.decided(
            ["✅", "Accept", ""],
            ["✅", "reject", ""],
            ["❌ x", "Accept", ""],
            ["✅", "Pending", ""],
            ["✅", "Accept", "✅"],
        )
        github = FakeGitHub()
        counts = run(Sheet(worksheet), github)
        self.assertEqual(
            counts,
            {"invited": 1, "emails queued": 2, "accepted without passing": 1},
        )
        self.assertEqual(
            github.invited, [(settings.MEMBERSHIP_ORG, "community", "dee077")]
        )
        self.assertEqual(
            written(worksheet), {"M2": "Pending", "N2": "Invited", "M3": "Pending"}
        )

    def test_invite_errors(self):
        with self.subTest("a refused invite is reported in the row"):
            worksheet = self.decided(["✅", "Accept", ""])
            error = InviteError("GitHub refused the invite (HTTP 422)")
            counts = run(Sheet(worksheet), FakeGitHub(invite_error=error))
            self.assertEqual(counts, {"invites failed": 1})
            self.assertEqual(
                written(worksheet), {"M2": "❌ GitHub refused the invite (HTTP 422)"}
            )

        with self.subTest("a temporary error is retried on the next run"):
            worksheet = self.decided(["✅", "Accept", ""])
            github = FakeGitHub(invite_error=TemporaryError("rate limited"))
            self.assertEqual(run(Sheet(worksheet), github), {"retry": 1})
            self.assertEqual(written(worksheet), {})

    def test_invites_are_followed(self):
        worksheet = FakeWorksheet(
            [
                HEADER + RESULTS,
                row() + ["✅", "Accept", "✅", "Invited"],
                row(username="gone") + ["✅", "Accept", "✅", "Invited"],
                row(username="waiting") + ["✅", "Accept", "✅", "Invited"],
            ],
            col_count=14,
        )
        github = FakeGitHub(members={"dee077"}, pending_invites={"waiting"})
        counts = run(Sheet(worksheet), github, today=date(2026, 11, 26))
        self.assertEqual(counts, {"joined": 1, "invites expired": 1})
        self.assertEqual(written(worksheet), {"N2": "Joined", "N3": "Expired"})
        members = worksheet.spreadsheet.worksheets["Members"]
        self.assertEqual(
            members.rows,
            [
                list(settings.MEMBER_COLUMNS.values()),
                ["1", "dee077", "Deepanshu Sahu", "d@example.com", "2026-11-26"]
                + [""] * 6,
            ],
        )
        (checkbox,) = worksheet.spreadsheet.requests
        self.assertEqual(checkbox["setDataValidation"]["range"]["startColumnIndex"], 8)

        with self.subTest("a member is added once"):
            worksheet.rows[1][-1] = "Invited"
            run(Sheet(worksheet), github, today=date(2026, 11, 27))
            self.assertEqual(len(members.rows), 2)

        with self.subTest("a dry run does not create the Members tab"):
            worksheet.rows[1][-1] = "Invited"
            del worksheet.spreadsheet.worksheets["Members"]
            counts = run(Sheet(worksheet), github, dry_run=True)
            self.assertEqual(counts["joined"], 1)
            self.assertEqual(worksheet.spreadsheet.worksheets, {})

    def test_dry_run_does_not_invite(self):
        worksheet = self.decided(["✅", "Accept", ""])
        github = FakeGitHub()
        self.assertEqual(run(Sheet(worksheet), github, dry_run=True), {"to invite": 1})
        self.assertEqual(github.invited, [])
        self.assertEqual(worksheet.updates, [])

    def test_dry_run_writes_nothing(self):
        worksheet = FakeWorksheet([HEADER, row()])
        counts = run(Sheet(worksheet), FakeGitHub(), dry_run=True)
        self.assertEqual(counts, {"pending": 1, "passed": 1})
        self.assertEqual(worksheet.updates, [])
        self.assertEqual(worksheet.col_count, 10)

    def test_meeting_dates_are_read_as_dates(self):
        worksheet = FakeWorksheet([HEADER, row()[:8] + ["11/5/2026", "not a date"]])
        counts = run(Sheet(worksheet), FakeGitHub())
        self.assertEqual(counts["failed meetings"], 1)
        self.assertEqual(
            written(worksheet)["K2"],
            "❌ weekly meeting 1 on 05 November 2026 is a Thursday, but the "
            "meetings are on Wednesdays; weekly meeting 2 is not a date",
        )

    def test_columns(self):
        with self.subTest("a missing Form column"):
            with self.assertRaisesRegex(SheetError, '"Email" is missing'):
                Sheet(FakeWorksheet([[c for c in HEADER if c != "Email"]]))

        with self.subTest("a duplicated column"):
            with self.assertRaisesRegex(SheetError, "appears more than once"):
                Sheet(FakeWorksheet([HEADER + ["Email"]]))
