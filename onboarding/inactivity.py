import os
import sys
from collections import Counter
from datetime import date

from . import settings
from .activity import last_activity
from .github import GitHub, NotFound, RemovalError, TemporaryError
from .members import Members, open_members
from .validate import open_spreadsheet

OUTCOMES = (
    "active",
    "warned",
    "waiting for removal",
    "would remove",
    "removed",
    "needs review",
    "left",
)


def removal_blocker(github, login, membership):
    """Returns why the member must not be removed automatically, or None."""
    if membership["role"] == "admin":
        return "is an owner of the organization"
    teams = github.teams(settings.MEMBERSHIP_ORG, login)
    if set(teams) - {settings.TEAM}:
        return "is in other teams"
    return None


def review(github, org_id, member, today, remove):
    """Returns the outcome for the member and the cells to update."""
    changes = {}
    try:
        login = github.login(member["github_id"])
    except NotFound:
        return "needs review", {"note": "the GitHub account no longer exists"}
    if login != member["username"]:
        changes["username"] = login
    membership = github.membership(settings.MEMBERSHIP_ORG, login)
    if not membership or membership["state"] != "active":
        changes.update(removed=today.isoformat(), note="left the organization")
        return "left", changes
    last = date.fromisoformat(member["last_activity"] or member["joined"])
    latest = last_activity(github, org_id, settings.GITHUB_ORG, login, last)
    if latest and latest > last:
        last = latest
        changes["last_activity"] = latest.isoformat()
    warned = date.fromisoformat(member["warned"]) if member["warned"] else None
    if warned and last > warned:
        # active again after the warning
        changes.update(warned="", note="")
        warned = None
    inactive = (today - last).days
    if inactive < settings.WARN_AFTER:
        return "active", changes
    if warned is None:
        changes.update(warned=today.isoformat(), email_status=settings.PENDING)
        return "warned", changes
    if (
        inactive < settings.REMOVE_AFTER
        or (today - warned).days < settings.REMOVE_AFTER_WARNING
    ):
        return "waiting for removal", changes
    reason = removal_blocker(github, login, membership)
    if reason:
        changes["note"] = reason
        return "needs review", changes
    if not remove:
        changes["note"] = "would be removed"
        return "would remove", changes
    try:
        github.remove_member(settings.MEMBERSHIP_ORG, login)
    except RemovalError as error:
        changes["note"] = str(error)
        return "needs review", changes
    changes.update(removed=today.isoformat(), note="", email_status=settings.PENDING)
    return "removed", changes


def run(members, github, today, dry_run=False, remove=False):
    counts = Counter()
    org_id = github.organization_id(settings.GITHUB_ORG)
    for row, member in members.active():
        counts["members"] += 1
        if member["exempt"].casefold() in ("true", "yes"):
            counts["exempt"] += 1
            continue
        try:
            outcome, changes = review(
                github, org_id, member, today, remove and not dry_run
            )
        except TemporaryError:
            counts["retry"] += 1
            continue
        except ValueError:
            outcome, changes = "needs review", {"note": "a date is not YYYY-MM-DD"}
        counts[outcome] += 1
        for key, value in changes.items():
            members.set(row, key, value)
    if not dry_run:
        members.save()
    return counts


def main():
    dry_run = os.environ.get("DRY_RUN", "").lower() in ("1", "true")
    github = GitHub(
        token=os.environ.get("GITHUB_TOKEN"),
        membership_token=os.environ.get("MEMBERSHIP_TOKEN"),
    )
    # Logs show counts only: the Members tab contains personal data.
    print("Reading the Members tab")
    worksheet = open_members(open_spreadsheet(), create=False)
    if worksheet is None:
        print("No member joined through the Form yet")
        return 0
    members = Members(worksheet)
    if not settings.REMOVE_INACTIVE:
        print("Removals are a dry run: set REMOVE_INACTIVE to enable them")
    counts = run(
        members,
        github,
        date.today(),
        dry_run=dry_run,
        remove=settings.REMOVE_INACTIVE,
    )
    print(
        f"Members: {counts['members']}, exempt: {counts['exempt']}, "
        f"retry next run: {counts['retry']}"
    )
    for outcome in OUTCOMES:
        print(f"{outcome}: {counts[outcome]}")
    if dry_run:
        print("Dry run: nothing was written to the Sheet")
    else:
        print(f"Written to the Sheet: {len(members.values)} cells")
    return 0


if __name__ == "__main__":
    sys.exit(main())
