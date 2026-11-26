import unittest
from datetime import date
from unittest import mock

from onboarding import activity
from onboarding.activity import last_activity

SINCE = date(2026, 9, 1)


def contributions(issue=None, pull=None, review=None, discussions=(), pulls=()):
    return {
        "user": {
            "contributionsCollection": {
                name: {"nodes": [{"occurredAt": value}] if value else []}
                for name, value in (
                    ("issueContributions", issue),
                    ("pullRequestContributions", pull),
                    ("pullRequestReviewContributions", review),
                )
            },
            "repositoryDiscussions": {
                "nodes": [
                    {"createdAt": created, "repository": {"owner": {"login": owner}}}
                    for created, owner in discussions
                ]
            },
            "pullRequests": {"nodes": list(pulls)},
        }
    }


def pull(owner, *commits):
    return {
        "repository": {"owner": {"login": owner}},
        "commits": {
            "nodes": [
                {
                    "commit": {
                        "committedDate": committed,
                        "authors": {"nodes": [{"user": {"login": author}}]},
                    }
                }
                for committed, author in commits
            ]
        },
    }


def comments(*nodes, next_page=False):
    return {
        "user": {
            "issueComments": {
                "pageInfo": {"hasNextPage": next_page, "endCursor": "next"},
                "nodes": [
                    {
                        "createdAt": created,
                        "updatedAt": updated,
                        "repository": {"owner": {"login": owner}},
                    }
                    for created, updated, owner in nodes
                ],
            }
        }
    }


def discussion_comments(*nodes, previous_page=False):
    return {
        "user": {
            "repositoryDiscussionComments": {
                "pageInfo": {"hasPreviousPage": previous_page, "startCursor": "prev"},
                "nodes": [
                    {
                        "createdAt": created,
                        "discussion": {"repository": {"owner": {"login": owner}}},
                    }
                    for created, owner in nodes
                ],
            }
        }
    }


class FakeGraphQL:
    def __init__(self, first, comment_pages=(), discussion_pages=()):
        self.pages = {
            activity.CONTRIBUTIONS: [first],
            activity.COMMENTS: list(comment_pages) or [comments()],
            activity.DISCUSSION_COMMENTS: list(discussion_pages)
            or [discussion_comments()],
        }
        self.calls = []

    def graphql(self, query, token=None, **variables):
        self.calls.append((query, variables))
        return self.pages[query].pop(0)


@mock.patch.object(
    activity, "date", wraps=date, **{"today.return_value": date(2026, 11, 26)}
)
class TestActivity(unittest.TestCase):
    def last(self, github):
        return last_activity(github, "ORG_ID", "openwisp", "dee077", SINCE)

    def test_no_activity(self, _date):
        self.assertIsNone(self.last(FakeGraphQL(contributions())))

    def test_newest_of_every_kind(self, _date):
        github = FakeGraphQL(
            contributions(
                issue="2026-09-10T10:00:00Z",
                pull="2026-09-12T10:00:00Z",
                review="2026-09-11T10:00:00Z",
            )
        )
        self.assertEqual(self.last(github), date(2026, 9, 12))
        query, variables = github.calls[0]
        self.assertEqual(variables["org"], "ORG_ID")
        self.assertEqual(variables["since"], "2026-09-01T00:00:00+00:00")

    def test_only_the_organization_and_the_member_count(self, _date):
        github = FakeGraphQL(
            contributions(
                discussions=[
                    ("2026-10-05T00:00:00Z", "other"),
                    ("2026-09-20T00:00:00Z", "openwisp"),
                ],
                pulls=[
                    pull("other", ("2026-10-09T00:00:00Z", "dee077")),
                    pull(
                        "openwisp",
                        ("2026-10-07T00:00:00Z", "someone"),
                        ("2026-09-25T00:00:00Z", "DEE077"),
                    ),
                ],
            )
        )
        self.assertEqual(self.last(github), date(2026, 9, 25))

    def test_comments(self, _date):
        github = FakeGraphQL(
            contributions(),
            comment_pages=[
                comments(
                    ("2026-11-01T00:00:00Z", "2026-11-02T00:00:00Z", "other"),
                    ("2026-09-03T00:00:00Z", "2026-10-15T00:00:00Z", "openwisp"),
                    next_page=True,
                ),
                comments(
                    ("2026-10-10T00:00:00Z", "2026-10-10T00:00:00Z", "openwisp"),
                    ("2026-08-01T00:00:00Z", "2026-08-30T00:00:00Z", "openwisp"),
                    next_page=True,
                ),
            ],
        )
        self.assertEqual(self.last(github), date(2026, 10, 10))
        # The page reaching edits older than SINCE is the last one read.
        self.assertEqual(
            [variables for _, variables in github.calls[1:3]],
            [
                {"login": "dee077", "after": None},
                {"login": "dee077", "after": "next"},
            ],
        )
        self.assertEqual(len(github.calls), 4)

    def test_discussion_comments(self, _date):
        github = FakeGraphQL(
            contributions(),
            discussion_pages=[
                discussion_comments(
                    ("2026-10-01T00:00:00Z", "openwisp"),
                    ("2026-11-01T00:00:00Z", "other"),
                    previous_page=True,
                ),
                discussion_comments(
                    ("2026-08-01T00:00:00Z", "openwisp"),
                    ("2026-10-20T00:00:00Z", "openwisp"),
                    previous_page=True,
                ),
            ],
        )
        self.assertEqual(self.last(github), date(2026, 10, 20))
        self.assertEqual(github.calls[-1][1], {"login": "dee077", "before": "prev"})

    def test_contributions_cover_one_year(self, _date):
        github = FakeGraphQL(contributions())
        last_activity(github, "ORG_ID", "openwisp", "dee077", date(2024, 1, 1))
        self.assertEqual(github.calls[0][1]["since"], "2025-11-27T00:00:00+00:00")
