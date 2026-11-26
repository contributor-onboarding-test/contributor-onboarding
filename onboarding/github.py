import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API = "https://api.github.com"


class NotFound(Exception):
    pass


class TemporaryError(Exception):
    """GitHub could not answer now; the row is checked again on the next run."""


class InviteError(Exception):
    """GitHub refused the invite, so retrying it would not help."""


class RemovalError(Exception):
    """GitHub refused to remove the member, so retrying it would not help."""


class GitHub:
    def __init__(self, token=None, membership_token=None, session=None):
        if session is None:
            session = requests.Session()
            retry = Retry(total=3, backoff_factor=1, status_forcelist=(502, 503, 504))
            session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session = session
        self.token = token
        self.membership_token = membership_token or token

    def _request(
        self, path, token=None, raw=False, params=None, method="GET", json=None
    ):
        headers = {"X-GitHub-Api-Version": "2022-11-28"}
        headers["Accept"] = (
            "application/vnd.github.raw" if raw else "application/vnd.github+json"
        )
        token = token or self.token
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = self.session.request(
                method,
                f"{API}{path}",
                headers=headers,
                params=params,
                json=json,
                timeout=30,
            )
        except requests.RequestException as error:
            raise TemporaryError(str(error)) from error
        if response.status_code == 404:
            raise NotFound(path)
        if response.status_code in (403, 429) or response.status_code >= 500:
            raise TemporaryError(f"{path}: HTTP {response.status_code}")
        response.raise_for_status()
        return response

    def user(self, username):
        return self._request(f"/users/{username}").json()

    def login(self, user_id):
        """Returns the current username of an account, which its owner can change."""
        return self._request(f"/user/{user_id}").json()["login"]

    def graphql(self, query, token=None, **variables):
        response = self._request(
            "/graphql",
            token=token,
            method="POST",
            json={"query": query, "variables": variables},
        ).json()
        errors = response.get("errors")
        if errors:
            if all(error.get("type") == "NOT_FOUND" for error in errors):
                raise NotFound(errors[0].get("message", ""))
            # GraphQL reports rate limits and timeouts as errors with HTTP 200.
            raise TemporaryError(errors[0].get("message", "GraphQL error"))
        return response["data"]

    def organization_id(self, org):
        query = "query($org: String!) { organization(login: $org) { id } }"
        return self.graphql(query, org=org)["organization"]["id"]

    def teams(self, org, username):
        query = """
            query($org: String!, $login: String!) {
              organization(login: $org) {
                teams(first: 100, userLogins: [$login]) { nodes { slug } }
              }
            }
        """
        data = self.graphql(query, token=self.membership_token, org=org, login=username)
        return [team["slug"] for team in data["organization"]["teams"]["nodes"]]

    def profile_readme(self, username):
        try:
            return self._request(f"/repos/{username}/{username}/readme", raw=True).text
        except NotFound:
            return ""

    def starred_repos(self, username):
        page = 1
        while True:
            repos = self._request(
                f"/users/{username}/starred", params={"per_page": 100, "page": page}
            ).json()
            yield from (repo["full_name"] for repo in repos)
            if len(repos) < 100:
                return
            page += 1

    def pull_request(self, owner, repo, number):
        return self._request(f"/repos/{owner}/{repo}/pulls/{number}").json()

    def invite(self, org, team, username):
        """Adds the user to the team; GitHub emails an invitation to non-members."""
        try:
            self._request(
                f"/orgs/{org}/teams/{team}/memberships/{username}",
                token=self.membership_token,
                method="PUT",
                json={"role": "member"},
            )
        except NotFound as error:
            raise InviteError("the user or the team was not found") from error
        except requests.HTTPError as error:
            raise InviteError(
                f"GitHub refused the invite (HTTP {error.response.status_code})"
            ) from error

    def remove_member(self, org, username):
        try:
            self._request(
                f"/orgs/{org}/memberships/{username}",
                token=self.membership_token,
                method="DELETE",
            )
        except requests.HTTPError as error:
            raise RemovalError(
                f"GitHub refused the removal (HTTP {error.response.status_code})"
            ) from error

    def membership(self, org, username):
        """Returns None when the user is neither a member nor invited."""
        try:
            return self._request(
                f"/orgs/{org}/memberships/{username}", token=self.membership_token
            ).json()
        except NotFound:
            return None
