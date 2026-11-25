import os

GITHUB_ORG = "openwisp"
MEMBERSHIP_ORG = os.environ.get("MEMBERSHIP_ORG", GITHUB_ORG)
# TODO: set to False before using this outside the test organization. The
# membership check is skipped so that its owner can test the whole flow.
SKIP_MEMBERSHIP_CHECK = True
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
}
RESULT_COLUMNS = {
    "validation": "Validation",
    "decision": "Decision",
}
# set by the Apps Script of the Sheet when a Form is submitted
PENDING = "Pending"
PASSED = "✅"
FAILED = "❌"
# the first one is the default of the dropdown
DECISIONS = ("Pending", "Accept", "Reject")
