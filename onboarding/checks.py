import re
import unicodedata

from . import settings
from .github import NotFound

PR_URL = re.compile(
    r"^https?://github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)/pull/(?P<number>\d+)"
    r"(?:[/?#].*)?$"
)


def normalize_name(name):
    name = unicodedata.normalize("NFKD", name or "")
    name = "".join(char for char in name if not unicodedata.combining(char))
    return " ".join(name.casefold().split())


def check_account(github, application):
    username = application["username"]
    try:
        user = github.user(username)
    except NotFound:
        return [f'GitHub user "{username}" does not exist']
    errors = []
    if normalize_name(user.get("name")) != normalize_name(application["name"]):
        errors.append("the Name on your GitHub profile does not match your Full Name")
    text = settings.OWNERSHIP_TEXT.casefold()
    bio = (user.get("bio") or "").casefold()
    if text not in bio and text not in github.profile_readme(username).casefold():
        errors.append(
            f'"{settings.OWNERSHIP_TEXT}" is missing from your GitHub bio '
            "and profile README"
        )
    return errors


def check_membership(github, application):
    if github.is_member(settings.MEMBERSHIP_ORG, application["username"]):
        return [f"you are already a member of {settings.MEMBERSHIP_ORG}"]
    return []


def check_stars(github, application):
    prefix = f"{settings.GITHUB_ORG}/"
    starred = {
        name.removeprefix(prefix)
        for name in github.starred_repos(application["username"])
        if name.startswith(prefix)
    }
    if not starred:
        return [
            "no starred OpenWISP repositories are visible: "
            "your GitHub profile must be public"
        ]
    errors = []
    if len(starred) < settings.MIN_STARS:
        errors.append(
            f"you starred {len(starred)} OpenWISP repositories, "
            f"at least {settings.MIN_STARS} are required"
        )
    missing = [repo for repo in settings.REQUIRED_STARS if repo not in starred]
    if missing:
        errors.append(f"these repositories are not starred: {', '.join(missing)}")
    return errors


def check_pull_requests(github, application):
    errors = []
    seen = set()
    username = application["username"].casefold()
    for field in ("pr1", "pr2", "pr3"):
        url = application[field].strip()
        label = f"PR {field[-1]}"
        match = PR_URL.match(url)
        if not match or match["owner"] != settings.GITHUB_ORG:
            errors.append(f"{label} is not a link to an OpenWISP pull request")
            continue
        key = (match["repo"], match["number"])
        if key in seen:
            errors.append(f"{label} is a duplicate of another PR")
            continue
        seen.add(key)
        try:
            pull = github.pull_request(*match.group("owner", "repo", "number"))
        except NotFound:
            errors.append(f"{label} does not exist")
            continue
        if not pull.get("merged"):
            errors.append(f"{label} is not merged")
        if pull["user"]["login"].casefold() != username:
            errors.append(f"{label} was not opened by you")
        if field == "pr3":
            if match["repo"] not in settings.NETWORKING_REPOS:
                errors.append(f"{label} is not in a networking module")
            if not pull["title"].lower().startswith(settings.NETWORKING_PREFIXES):
                errors.append(
                    f"{label} title does not start with [fix], [change] or [feature]"
                )
    return errors


def run_checks(github, application):
    """Returns the reasons the application fails for each check which ran.

    The other checks do not run for an existing member. Raises
    TemporaryError when GitHub cannot be reached.
    """
    if settings.SKIP_MEMBERSHIP_CHECK:
        membership = []
    else:
        membership = check_membership(github, application)
    if membership:
        return {"membership": membership}
    return {
        "membership": membership,
        "account": check_account(github, application),
        "stars": check_stars(github, application),
        "pull_requests": check_pull_requests(github, application),
    }


def validate(github, application):
    """Returns the reasons the application fails; an empty list means it passed."""
    return [
        error for errors in run_checks(github, application).values() for error in errors
    ]
