import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

import gspread

from . import settings
from .checks import validate
from .github import GitHub, TemporaryError
from .sheet import Sheet


def run(sheet, github, dry_run=False, now=None):
    now = now or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    counts = Counter()
    for row, application in sheet.pending():
        try:
            errors = validate(github, application)
        except TemporaryError:
            counts["retry"] += 1
            continue
        sheet.set_result(row, not errors, errors, now)
        counts["failed" if errors else "passed"] += 1
    if not dry_run:
        sheet.save()
    return counts


def open_worksheet():
    client = gspread.service_account_from_dict(
        json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT"])
    )
    return client.open_by_key(os.environ["SHEET_ID"]).worksheet(settings.WORKSHEET)


def main():
    dry_run = os.environ.get("DRY_RUN", "").lower() in ("1", "true")
    github = GitHub(
        token=os.environ.get("GITHUB_TOKEN"),
        membership_token=os.environ.get("MEMBERSHIP_TOKEN"),
    )
    counts = run(Sheet(open_worksheet()), github, dry_run=dry_run)
    mode = " (dry run, nothing written)" if dry_run else ""
    print(
        f"passed: {counts['passed']}, failed: {counts['failed']}, "
        f"retry next run: {counts['retry']}{mode}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
