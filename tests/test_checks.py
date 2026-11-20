import unittest

from onboarding import settings
from onboarding.checks import normalize_name, validate
from onboarding.github import NotFound, TemporaryError

STARS = [f"openwisp/{repo}" for repo in settings.REQUIRED_STARS] + [
    f"openwisp/extra-{index}" for index in range(14)
]


class FakeGitHub:
    def __init__(self, **overrides):
        self.users = {
            "dee077": {"name": "Deepanshu Sahu", "bio": "Contributing to OpenWISP"}
        }
        self.readmes = {}
        self.stars = {"dee077": STARS}
        self.pulls = {
            ("openwisp-users", "1"): {
                "merged": True,
                "user": {"login": "dee077"},
                "title": "[docs] Fixed typo",
            },
            ("openwisp-utils", "2"): {
                "merged": True,
                "user": {"login": "dee077"},
                "title": "[qa] Fixed lint",
            },
            ("openwisp-controller", "3"): {
                "merged": True,
                "user": {"login": "dee077"},
                "title": "[fix] Fixed command status",
            },
        }
        self.members = set()
        self.__dict__.update(overrides)

    def user(self, username):
        if username not in self.users:
            raise NotFound(username)
        return self.users[username]

    def profile_readme(self, username):
        return self.readmes.get(username, "")

    def starred_repos(self, username):
        return iter(self.stars.get(username, []))

    def pull_request(self, owner, repo, number):
        if (repo, number) not in self.pulls:
            raise NotFound(repo)
        return self.pulls[(repo, number)]

    def is_member(self, org, username):
        return username in self.members


def application(**overrides):
    data = {
        "name": "Deepanshu Sahu",
        "email": "d@example.com",
        "username": "dee077",
        "pr1": "https://github.com/openwisp/openwisp-users/pull/1",
        "pr2": "https://github.com/openwisp/openwisp-utils/pull/2/files",
        "pr3": "https://github.com/openwisp/openwisp-controller/pull/3",
    }
    data.update(overrides)
    return data


class TestChecks(unittest.TestCase):
    def test_valid_application(self):
        self.assertEqual(validate(FakeGitHub(), application()), [])

    def test_name(self):
        with self.subTest("case, spaces and accents are ignored"):
            self.assertEqual(normalize_name("  josé  DA silva "), "jose da silva")

        with self.subTest("a partial name fails"):
            github = FakeGitHub(users={"dee077": {"name": "Deepanshu", "bio": ""}})
            github.readmes["dee077"] = "Contributing to OpenWISP"
            self.assertEqual(
                validate(github, application()),
                ["the Name on your GitHub profile does not match your Full Name"],
            )

        with self.subTest("an empty GitHub name fails"):
            github = FakeGitHub(
                users={"dee077": {"name": None, "bio": "Contributing to OpenWISP"}}
            )
            self.assertIn(
                "the Name on your GitHub profile does not match your Full Name",
                validate(github, application()),
            )

    def test_ownership_text(self):
        github = FakeGitHub(users={"dee077": {"name": "Deepanshu Sahu", "bio": ""}})

        with self.subTest("missing from bio and README"):
            self.assertEqual(
                validate(github, application()),
                [
                    '"Contributing to OpenWISP" is missing from your GitHub bio '
                    "and profile README"
                ],
            )

        with self.subTest("the README is enough"):
            github.readmes["dee077"] = "Hi! contributing to openwisp"
            self.assertEqual(validate(github, application()), [])

    def test_unknown_user(self):
        github = FakeGitHub(users={})
        self.assertIn(
            'GitHub user "dee077" does not exist', validate(github, application())
        )

    def test_already_member(self):
        github = FakeGitHub(members={"dee077"})
        self.assertEqual(
            validate(github, application()),
            [f"you are already a member of {settings.MEMBERSHIP_ORG}"],
        )

    def test_stars(self):
        with self.subTest("a private profile shows no stars"):
            errors = validate(FakeGitHub(stars={}), application())
            self.assertEqual(
                errors,
                [
                    "no starred OpenWISP repositories are visible: "
                    "your GitHub profile must be public"
                ],
            )

        with self.subTest("too few and missing required repositories"):
            github = FakeGitHub(stars={"dee077": ["openwisp/netjsonconfig"]})
            errors = validate(github, application())
            self.assertIn(
                "you starred 1 OpenWISP repositories, at least 20 are required",
                errors,
            )
            self.assertTrue(errors[1].startswith("these repositories are not starred"))
            self.assertNotIn("netjsonconfig", errors[1])

        with self.subTest("stars outside OpenWISP do not count"):
            github = FakeGitHub(stars={"dee077": STARS[:19] + ["other/repo"]})
            self.assertIn(
                "you starred 19 OpenWISP repositories, at least 20 are required",
                validate(github, application()),
            )

    def test_pull_requests(self):
        cases = (
            (
                {"pr1": "https://github.com/other/openwisp-users/pull/1"},
                "PR 1 is not a link to an OpenWISP pull request",
            ),
            ({"pr2": "not a link"}, "PR 2 is not a link to an OpenWISP pull request"),
            ({"pr2": application()["pr1"]}, "PR 2 is a duplicate of another PR"),
            (
                {"pr1": "https://github.com/openwisp/openwisp-users/pull/9"},
                "PR 1 does not exist",
            ),
        )
        for overrides, error in cases:
            with self.subTest(error):
                self.assertIn(error, validate(FakeGitHub(), application(**overrides)))

        with self.subTest("not merged and not opened by the applicant"):
            github = FakeGitHub()
            github.pulls[("openwisp-users", "1")] = {
                "merged": False,
                "user": {"login": "someone"},
                "title": "[fix] x",
            }
            errors = validate(github, application())
            self.assertEqual(
                errors, ["PR 1 is not merged", "PR 1 was not opened by you"]
            )

        with self.subTest("the networking PR needs a module and a prefix"):
            github = FakeGitHub()
            github.pulls[("openwisp-utils", "3")] = {
                "merged": True,
                "user": {"login": "DEE077"},
                "title": "[docs] Updated docs",
            }
            errors = validate(
                github,
                application(pr3="https://github.com/openwisp/openwisp-utils/pull/3"),
            )
            self.assertEqual(
                errors,
                [
                    "PR 3 is not in a networking module",
                    "PR 3 title does not start with [fix], [change] or [feature]",
                ],
            )

    def test_temporary_error_is_raised(self):
        class BrokenGitHub(FakeGitHub):
            def user(self, username):
                raise TemporaryError("rate limited")

        with self.assertRaises(TemporaryError):
            validate(BrokenGitHub(), application())
