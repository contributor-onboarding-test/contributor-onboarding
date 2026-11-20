from gspread.utils import rowcol_to_a1

from . import settings


class SheetError(Exception):
    pass


class Sheet:
    """Reads applications and buffers result writes, sent at once by save()."""

    def __init__(self, worksheet):
        self.worksheet = worksheet
        self.rows = worksheet.get_all_values()
        self.header = self.rows[0] if self.rows else []
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

    def _cell(self, row, key):
        values = self.rows[row - 1]
        index = self.columns[key]
        return values[index].strip() if index < len(values) else ""

    def pending(self):
        for row in range(2, len(self.rows) + 1):
            if self._cell(row, "username") and not self._cell(row, "validation"):
                yield row, {key: self._cell(row, key) for key in settings.FORM_COLUMNS}

    def set_result(self, row, passed, errors, validated_at):
        result = {
            "validation": "Passed" if passed else "Failed",
            "details": "; ".join(errors),
            "validated_at": validated_at,
            "decision": "Pending" if passed else "Rejected",
        }
        for key, value in result.items():
            self.values.append(
                {"range": rowcol_to_a1(row, self.columns[key] + 1), "values": [[value]]}
            )
        if passed:
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
