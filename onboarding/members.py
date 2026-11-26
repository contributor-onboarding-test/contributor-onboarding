from gspread.exceptions import WorksheetNotFound
from gspread.utils import rowcol_to_a1

from . import settings
from .sheet import SheetError


def open_members(spreadsheet, create):
    """Returns the Members tab, or None when it does not exist and create is False."""
    try:
        return spreadsheet.worksheet(settings.MEMBERS_WORKSHEET)
    except WorksheetNotFound:
        if not create:
            return None
    worksheet = spreadsheet.add_worksheet(
        settings.MEMBERS_WORKSHEET, rows=100, cols=len(settings.MEMBER_COLUMNS)
    )
    column = list(settings.MEMBER_COLUMNS).index("exempt")
    spreadsheet.batch_update(
        {
            "requests": [
                {
                    "setDataValidation": {
                        "range": {
                            "sheetId": worksheet.id,
                            "startRowIndex": 1,
                            "startColumnIndex": column,
                            "endColumnIndex": column + 1,
                        },
                        "rule": {"condition": {"type": "BOOLEAN"}},
                    }
                }
            ]
        }
    )
    return worksheet


class Members:
    """Reads the Members tab and buffers its writes, sent at once by save()."""

    def __init__(self, worksheet):
        self.worksheet = worksheet
        self.rows = worksheet.get_all_values() if worksheet else []
        self.header = (
            self.rows[0] if self.rows else list(settings.MEMBER_COLUMNS.values())
        )
        self.columns = {}
        for key, title in settings.MEMBER_COLUMNS.items():
            if title not in self.header:
                raise SheetError(
                    f'the column "{title}" is missing from {settings.MEMBERS_WORKSHEET}'
                )
            self.columns[key] = self.header.index(title)
        self.new_rows = []
        self.values = []

    def _cell(self, row, key):
        values = self.rows[row - 1]
        index = self.columns[key]
        return values[index].strip() if index < len(values) else ""

    def ids(self):
        ids = {self._cell(row, "github_id") for row in range(2, len(self.rows) + 1)}
        index = self.columns["github_id"]
        return ids | {values[index] for values in self.new_rows}

    def add(self, member):
        values = [""] * len(self.header)
        for key, value in member.items():
            values[self.columns[key]] = value
        self.new_rows.append(values)

    def active(self):
        """Yields the members who were not removed and have not left."""
        for row in range(2, len(self.rows) + 1):
            if self._cell(row, "github_id") and not self._cell(row, "removed"):
                yield row, {key: self._cell(row, key) for key in self.columns}

    def set(self, row, key, value):
        self.values.append(
            {"range": rowcol_to_a1(row, self.columns[key] + 1), "values": [[value]]}
        )

    def save(self, spreadsheet=None):
        """spreadsheet is where the tab is created when it does not exist."""
        if self.worksheet is None:
            if not self.new_rows:
                return
            self.worksheet = open_members(spreadsheet, create=True)
        if self.new_rows:
            rows = self.new_rows if self.rows else [self.header] + self.new_rows
            # Kept as typed: Sheets would turn the dates into numbers.
            self.worksheet.append_rows(rows, value_input_option="RAW")
        if self.values:
            self.worksheet.batch_update(self.values)
