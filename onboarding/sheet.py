from gspread.utils import absolute_range_name, rowcol_to_a1

from . import settings


class SheetError(Exception):
    pass


class Sheet:
    """Reads applications and buffers result writes, sent at once by save()."""

    def __init__(self, worksheet):
        self.worksheet = worksheet
        self.rows = worksheet.get_all_values()
        self.header = self.rows[0] if self.rows else []
        self.links = self._links()
        self.columns = {}
        for key, title in settings.FORM_COLUMNS.items():
            self.columns[key] = self._find(title, required=True)
        self.new_headers = []
        for key, title in settings.RESULT_COLUMNS.items():
            index = self._find(title)
            if index is None:
                index = len(self.header) + len(self.new_headers)
                self.new_headers.append((index, title))
            self.columns[key] = index
        self.values = []
        self.dropdowns = []

    def _find(self, title, required=False):
        matches = [index for index, value in enumerate(self.header) if value == title]
        if len(matches) > 1:
            raise SheetError(f'the column "{title}" appears more than once')
        if not matches:
            if required:
                raise SheetError(f'the column "{title}" is missing')
            return None
        return matches[0]

    def _links(self):
        """Returns the URL behind each cell labelled by the Apps Script of the Sheet."""
        metadata = self.worksheet.spreadsheet.fetch_sheet_metadata(
            {
                "ranges": absolute_range_name(self.worksheet.title),
                "fields": "sheets.data.rowData.values.hyperlink",
            }
        )
        data = metadata["sheets"][0].get("data") or [{}]
        return {
            (row, column): cell["hyperlink"]
            for row, values in enumerate(data[0].get("rowData", []), start=1)
            for column, cell in enumerate(values.get("values", []))
            if cell.get("hyperlink")
        }

    def _cell(self, row, key):
        values = self.rows[row - 1]
        index = self.columns[key]
        if (row, index) in self.links:
            return self.links[(row, index)].strip()
        return values[index].strip() if index < len(values) else ""

    def pending(self):
        for row in range(2, len(self.rows) + 1):
            if self._cell(row, "username") and self._cell(row, "validation") in (
                "",
                settings.PENDING,
            ):
                yield row, {key: self._cell(row, key) for key in settings.FORM_COLUMNS}

    def set_result(self, row, errors, star_errors=None):
        """star_errors is None when the star check did not run."""
        pending, _accept, reject = settings.DECISIONS
        result = {
            "validation": (
                f"{settings.FAILED} {'; '.join(errors)}" if errors else settings.PASSED
            ),
            "decision": reject if errors else pending,
        }
        if star_errors is not None:
            result["stars"] = settings.FAILED if star_errors else settings.PASSED
        for key, value in result.items():
            self.values.append(
                {"range": rowcol_to_a1(row, self.columns[key] + 1), "values": [[value]]}
            )
        if not errors:
            self.dropdowns.append(row)

    def save(self):
        width = len(self.header) + len(self.new_headers)
        if width > self.worksheet.col_count:
            self.worksheet.add_cols(width - self.worksheet.col_count)
        values = [
            {"range": rowcol_to_a1(1, index + 1), "values": [[title]]}
            for index, title in self.new_headers
        ] + self.values
        if values:
            self.worksheet.batch_update(values)
        if self.dropdowns:
            self.worksheet.spreadsheet.batch_update(
                {"requests": [self._dropdown(row) for row in self.dropdowns]}
            )

    def _dropdown(self, row):
        column = self.columns["decision"]
        return {
            "setDataValidation": {
                "range": {
                    "sheetId": self.worksheet.id,
                    "startRowIndex": row - 1,
                    "endRowIndex": row,
                    "startColumnIndex": column,
                    "endColumnIndex": column + 1,
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": [
                            {"userEnteredValue": value} for value in settings.DECISIONS
                        ],
                    },
                    "strict": True,
                    "showCustomUi": True,
                },
            }
        }
