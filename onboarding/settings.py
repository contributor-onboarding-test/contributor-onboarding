import os

GITHUB_ORG = "openwisp"
MEMBERSHIP_ORG = os.environ.get("MEMBERSHIP_ORG", GITHUB_ORG)
# Lets an organization owner test the whole flow with their own account.
SKIP_MEMBERSHIP_CHECK = os.environ.get("SKIP_MEMBERSHIP_CHECK", "").lower() in (
    "1",
    "true",
)
# the organization team accepted applicants are invited to
TEAM = os.environ.get("ONBOARDING_TEAM") or "community"
OWNERSHIP_TEXT = "Contributing to OpenWISP"
MIN_STARS = 20
REQUIRED_STARS = (
    "openwisp-controller",
    "openwisp-radius",
    "openwisp-firmware-upgrader",
    "openwisp-monitoring",
    "openwisp-network-topology",
    "netjsonconfig",
)
NETWORKING_REPOS = (
    "openwisp-controller",
    "openwisp-monitoring",
    "openwisp-radius",
    "openwisp-firmware-upgrader",
    "openwisp-network-topology",
    "netjsonconfig",
)
NETWORKING_PREFIXES = ("[fix]", "[change]", "[change!]", "[feature]")

WORKSHEET = os.environ.get("WORKSHEET", "Form Responses 1")
FORM_COLUMNS = {
    "name": "Full Name",
    "email": "Email",
    "username": "Github Username",
    "pr1": "Merged PR Link 1",
    "pr2": "Merged PR Link 2",
    "pr3": "Merged PR Link 3 (Networking module)",
    # shows the result of the star check
    "stars": "Have you started OpenWISP repositories",
    "meeting1": "Weekly meeting 1",
    "meeting2": "Weekly meeting 2",
}
# Form dates, read as dates rather than as text formatted for the Sheet's locale
DATE_COLUMNS = ("meeting1", "meeting2")
RESULT_COLUMNS = {
    "validation": "Validation",
    "decision": "Decision",
    # Pending until the Apps Script of the Sheet sends the email of the decision
    "email_status": "Email status",
}
# set by the Apps Script of the Sheet when a Form is submitted
PENDING = "Pending"
PASSED = "✅"
FAILED = "❌"
# the first one is the default of the dropdown
DECISIONS = ("Pending", "Accept", "Reject")
