import os

GITHUB_ORG = "openwisp"
MEMBERSHIP_ORG = os.environ.get("MEMBERSHIP_ORG", GITHUB_ORG)
OWNERSHIP_TEXT = "Contributing to OpenWISP"
MIN_STARS = 20
REQUIRED_STARS = (
    "openwisp-controller",
    "openwisp-radius",
    "openwisp-firmware-upgrader",
    "openwisp-monitoring",
    "netjsonconfig",
    "docker-openwisp",
)
NETWORKING_REPOS = (
    "openwisp-controller",
    "openwisp-monitoring",
    "openwisp-radius",
    "openwisp-firmware-upgrader",
    "openwisp-network-topology",
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
}
RESULT_COLUMNS = {
    "validation": "Validation",
    "details": "Validation details",
    "validated_at": "Validated at",
    "decision": "Decision",
}
DECISIONS = ("Pending", "Approved", "Rejected")
