"""Finds the last activity of a member in the repositories of an organization.

Only the member's own actions count, each with its own date. The "updated"
date of an issue or pull request is never used, since anyone can change
it.
"""

from datetime import date, datetime, time, timedelta, timezone

CONTRIBUTIONS = """
query($login: String!, $org: ID!, $since: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $since, organizationID: $org) {
      issueContributions(first: 1, orderBy: {direction: DESC}) {
        nodes { occurredAt }
      }
      pullRequestContributions(first: 1, orderBy: {direction: DESC}) {
        nodes { occurredAt }
      }
      pullRequestReviewContributions(first: 1, orderBy: {direction: DESC}) {
        nodes { occurredAt }
      }
    }
    repositoryDiscussions(first: 100, orderBy: {field: CREATED_AT, direction: DESC}) {
      nodes { createdAt repository { owner { login } } }
    }
    pullRequests(states: OPEN, first: 50, orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes {
        repository { owner { login } }
        commits(last: 20) {
          nodes {
            commit { committedDate authors(first: 10) { nodes { user { login } } } }
          }
        }
      }
    }
  }
}
"""
# Newest first by the date of the last edit, which is never before the date of
# the comment: once a page reaches an older edit, no later comment follows.
COMMENTS = """
query($login: String!, $after: String) {
  user(login: $login) {
    issueComments(first: 100, after: $after, orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes { createdAt updatedAt repository { owner { login } } }
    }
  }
}
"""
# GitHub lists discussion comments oldest first, so they are read from the end.
DISCUSSION_COMMENTS = """
query($login: String!, $before: String) {
  user(login: $login) {
    repositoryDiscussionComments(last: 100, before: $before) {
      pageInfo { hasPreviousPage startCursor }
      nodes { createdAt discussion { repository { owner { login } } } }
    }
  }
}
"""
# Limits the pages read for a member who comments a lot in other projects.
MAX_PAGES = 10


def parse(timestamp):
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date()


def last_activity(github, org_id, org, login, since):
    """Returns the date of the last activity on or after since, or None."""
    # GitHub returns at most one year of contributions.
    start = max(since, date.today() - timedelta(days=364))
    data = github.graphql(
        CONTRIBUTIONS,
        login=login,
        org=org_id,
        since=datetime.combine(start, time(), timezone.utc).isoformat(),
    )["user"]
    dates = [
        parse(node["occurredAt"])
        for contributions in data["contributionsCollection"].values()
        for node in contributions["nodes"]
    ]
    dates += [
        parse(node["createdAt"])
        for node in data["repositoryDiscussions"]["nodes"]
        if node["repository"]["owner"]["login"] == org
    ]
    for pull in data["pullRequests"]["nodes"]:
        if pull["repository"]["owner"]["login"] != org:
            continue
        for node in pull["commits"]["nodes"]:
            commit = node["commit"]
            authors = {
                (author["user"] or {}).get("login", "").casefold()
                for author in commit["authors"]["nodes"]
            }
            if login.casefold() in authors:
                dates.append(parse(commit["committedDate"]))
    dates += _comments(github, org, login, since)
    dates += _discussion_comments(github, org, login, since)
    dates = [day for day in dates if day >= since]
    return max(dates, default=None)


def _comments(github, org, login, since):
    after = None
    for _page in range(MAX_PAGES):
        comments = github.graphql(COMMENTS, login=login, after=after)["user"][
            "issueComments"
        ]
        for node in comments["nodes"]:
            if parse(node["updatedAt"]) < since:
                return
            if node["repository"]["owner"]["login"] == org:
                yield parse(node["createdAt"])
        if not comments["pageInfo"]["hasNextPage"]:
            return
        after = comments["pageInfo"]["endCursor"]


def _discussion_comments(github, org, login, since):
    before = None
    for _page in range(MAX_PAGES):
        comments = github.graphql(DISCUSSION_COMMENTS, login=login, before=before)[
            "user"
        ]["repositoryDiscussionComments"]
        days = [
            (
                parse(node["createdAt"]),
                node["discussion"]["repository"]["owner"]["login"],
            )
            for node in comments["nodes"]
        ]
        yield from (day for day, owner in days if owner == org)
        if (
            not comments["pageInfo"]["hasPreviousPage"]
            or not days
            or days[0][0] < since
        ):
            return
        before = comments["pageInfo"]["startCursor"]
