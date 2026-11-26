import json
import os
import sys
from collections import Counter
from datetime import date

import gspread

from . import settings
from .checks import run_checks
from .github import GitHub, InviteError, TemporaryError
from .members import Members, open_members
from .sheet import Sheet


def check_invites(sheet, members, github, today, counts):
    """Records who joined, so the weekly review checks their activity."""
    for row, applicant in sheet.invited():
        try:
            membership = github.membership(
                settings.MEMBERSHIP_ORG, applicant["username"]
            )
            if membership and membership["state"] == "active":
                github_id = str(github.user(applicant["username"])["id"])
        except TemporaryError:
            counts["retry"] += 1
            continue
        if membership is None:
            sheet.set_invite_status(row, settings.EXPIRED)
            counts["invites expired"] += 1
        elif membership["state"] == "active":
            sheet.set_invite_status(row, settings.JOINED)
            counts["joined"] += 1
            if github_id not in members.ids():
                members.add(
                    {
                        "github_id": github_id,
                        **applicant,
                        "joined": today.isoformat(),
                    }
                )


def run(sheet, github, dry_run=False, today=None):
    spreadsheet = sheet.worksheet.spreadsheet
    members = Members(open_members(spreadsheet, create=False))
    today = today or date.today()
    counts = Counter()
    check_invites(sheet, members, github, today, counts)
    for row, application in sheet.pending():
        counts["pending"] += 1
        try:
            results = run_checks(github, application)
        except TemporaryError:
            counts["retry"] += 1
            continue
        errors = [error for check in results.values() for error in check]
        sheet.set_result(row, errors, results.get("stars"))
        counts["failed" if errors else "passed"] += 1
        if errors:
            counts["emails queued"] += 1
        # Only the number of rows failing each check is logged, never which.
        for name, check_errors in results.items():
            if check_errors:
                counts[f"failed {name}"] += 1
    for row, accepted, passed, username in sheet.decided():
        if not accepted:
            sheet.set_email_status(row, settings.PENDING)
            counts["emails queued"] += 1
        elif not passed:
            # Only an application which passed every check is invited.
            counts["accepted without passing"] += 1
        elif dry_run:
            counts["to invite"] += 1
        else:
            try:
                github.invite(settings.MEMBERSHIP_ORG, settings.TEAM, username)
            except TemporaryError:
                counts["retry"] += 1
                continue
            except InviteError as error:
                sheet.set_email_status(row, f"{settings.FAILED} {error}")
                counts["invites failed"] += 1
                continue
            sheet.set_email_status(row, settings.PENDING)
            sheet.set_invite_status(row, settings.INVITED)
            counts["invited"] += 1
            counts["emails queued"] += 1
    if not dry_run:
        sheet.save()
        members.save(spreadsheet)
    return counts


def open_spreadsheet():
    client = gspread.service_account_from_dict(
        json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT"])
    )
    return client.open_by_key(os.environ["SHEET_ID"])


def main():
    dry_run = os.environ.get("DRY_RUN", "").lower() in ("1", "true")
    github = GitHub(
        token=os.environ.get("GITHUB_TOKEN"),
        membership_token=os.environ.get("MEMBERSHIP_TOKEN"),
    )
    # Logs show counts only: the applications contain personal data.
    print("Reading the Sheet")
    sheet = Sheet(open_spreadsheet().worksheet(settings.WORKSHEET))
    print(f"Applications: {max(len(sheet.rows) - 1, 0)}")
    if settings.SKIP_MEMBERSHIP_CHECK:
        print("The membership check is skipped")
    counts = run(sheet, github, dry_run=dry_run)
    print(f"Checked: {counts['pending']}")
    print(
        f"passed: {counts['passed']}, failed: {counts['failed']}, "
        f"retry next run: {counts['retry']}"
    )
    for name in ("membership", "account", "stars", "pull_requests", "meetings"):
        print(f"failed {name.replace('_', ' ')} check: {counts[f'failed {name}']}")
    if dry_run:
        print(f"to invite: {counts['to invite']}")
    else:
        print(
            f"invited: {counts['invited']}, invites failed: {counts['invites failed']}"
        )
    print(f"accepted without passing the checks: {counts['accepted without passing']}")
    print(f"emails queued: {counts['emails queued']}")
    print(f"joined: {counts['joined']}, invites expired: {counts['invites expired']}")
    if dry_run:
        print("Dry run: nothing was written to the Sheet")
    else:
        print(
            f"Written to the Sheet: {len(sheet.values)} cells, "
            f"{len(sheet.dropdowns)} Decision dropdowns"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
