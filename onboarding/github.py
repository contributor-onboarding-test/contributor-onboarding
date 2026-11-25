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

    def is_member(self, org, username):
        try:
            self._request(
                f"/orgs/{org}/memberships/{username}", token=self.membership_token
            )
        except NotFound:
            return False
        return True
