"""Thin async wrapper around the GitHub REST API used by the MCP tools."""

import base64
import os

import httpx

GITHUB_API_URL = "https://api.github.com"


class GitHubError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, token: str | None = None) -> None:
        token = token or os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
        if not token:
            raise GitHubError("GITHUB_PERSONAL_ACCESS_TOKEN is not set")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _get(self, path: str, *, params: dict | None = None, accept: str | None = None) -> httpx.Response:
        headers = dict(self._headers)
        if accept:
            headers["Accept"] = accept
        async with httpx.AsyncClient(base_url=GITHUB_API_URL, headers=headers, timeout=20) as client:
            response = await client.get(path, params=params)
        if response.status_code >= 400:
            raise GitHubError(f"GitHub API {path} failed: {response.status_code} {response.text[:300]}")
        return response

    async def _post(self, path: str, *, json: dict) -> httpx.Response:
        async with httpx.AsyncClient(base_url=GITHUB_API_URL, headers=self._headers, timeout=20) as client:
            response = await client.post(path, json=json)
        if response.status_code >= 400:
            raise GitHubError(f"GitHub API {path} failed: {response.status_code} {response.text[:300]}")
        return response

    async def _put(self, path: str, *, json: dict) -> httpx.Response:
        # Unlike _get/_post, a merge attempt raising on 4xx would swallow GitHub's actual
        # reason (not mergeable, conflicts, missing required reviews/checks) into a generic
        # GitHubError — the caller needs that reason, so this doesn't raise on 4xx/405/409.
        async with httpx.AsyncClient(base_url=GITHUB_API_URL, headers=self._headers, timeout=20) as client:
            response = await client.put(path, json=json)
        return response

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict:
        response = await self._get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
        return response.json()

    async def get_pull_request_diff(self, owner: str, repo: str, pr_number: int) -> str:
        response = await self._get(
            f"/repos/{owner}/{repo}/pulls/{pr_number}",
            accept="application/vnd.github.v3.diff",
        )
        return response.text

    async def search_repositories(self, query: str, limit: int = 10) -> list[dict]:
        response = await self._get(
            "/search/repositories",
            params={"q": query, "sort": "stars", "order": "desc", "per_page": limit},
        )
        return response.json().get("items", [])

    async def get_repository(self, owner: str, repo: str) -> dict:
        response = await self._get(f"/repos/{owner}/{repo}")
        return response.json()

    async def file_exists(self, owner: str, repo: str, path: str) -> bool:
        try:
            await self._get(f"/repos/{owner}/{repo}/contents/{path}")
            return True
        except GitHubError:
            return False

    async def get_file_content(self, owner: str, repo: str, path: str) -> str | None:
        try:
            response = await self._get(f"/repos/{owner}/{repo}/contents/{path}")
        except GitHubError:
            return None
        data = response.json()
        if data.get("encoding") != "base64":
            return None
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")

    async def count_good_first_issues(self, owner: str, repo: str) -> int:
        response = await self._get(
            "/search/issues",
            params={
                "q": f'repo:{owner}/{repo} is:issue is:open label:"good first issue"',
                "per_page": 1,
            },
        )
        return response.json().get("total_count", 0)

    async def search_good_first_issues(self, owner: str, repo: str, limit: int = 5) -> list[dict]:
        response = await self._get(
            "/search/issues",
            params={
                "q": f'repo:{owner}/{repo} is:issue is:open label:"good first issue"',
                "per_page": limit,
            },
        )
        return response.json().get("items", [])

    async def get_pull_request_files(self, owner: str, repo: str, pr_number: int, limit: int = 10) -> list[dict]:
        response = await self._get(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/files",
            params={"per_page": limit},
        )
        return response.json()

    async def create_issue_comment(self, owner: str, repo: str, issue_number: int, body: str) -> dict:
        response = await self._post(
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            json={"body": body},
        )
        return response.json()

    async def create_pr_review(self, owner: str, repo: str, pr_number: int, body: str, event: str) -> dict:
        """Submit a formal GitHub Pull Request Review (a real Approved/Changes-requested
        status attached to the PR, not a plain comment). GitHub hard-blocks approving or
        requesting changes on your own PR — 422 "Can not approve your own pull request"
        — which is an expected, common outcome (verified live against this project's own
        test repo, where the bot token and the PR author are the same account), not a
        bug, so it's reported back as data (blocked_reason), not raised. Any other
        failure still raises normally. Uses a raw POST (not the shared _post() helper,
        which always raises on 4xx) so the self-approval case can be inspected first."""
        async with httpx.AsyncClient(base_url=GITHUB_API_URL, headers=self._headers, timeout=20) as client:
            response = await client.post(
                f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
                json={"body": body, "event": event},
            )
        if response.status_code == 422 and "own pull request" in response.text.lower():
            return {"posted": False, "blocked_reason": "self_approval"}
        if response.status_code >= 400:
            raise GitHubError(
                f"GitHub API /repos/{owner}/{repo}/pulls/{pr_number}/reviews failed: "
                f"{response.status_code} {response.text[:300]}"
            )
        data = response.json()
        return {"posted": True, "id": data.get("id"), "html_url": data.get("html_url")}

    async def merge_pull_request(
        self, owner: str, repo: str, pr_number: int, merge_method: str = "merge"
    ) -> dict:
        """Merge a pull request. The ordinary "can't merge yet" cases — unmergeable,
        conflicts, missing required reviews/checks — come back from GitHub as 405/409,
        so those are reported back as data here, not raised as GitHubError."""
        response = await self._put(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/merge",
            json={"merge_method": merge_method},
        )
        data = response.json() if response.content else {}
        if response.status_code >= 400:
            return {"merged": False, "message": data.get("message", f"HTTP {response.status_code}")}
        return {"merged": data.get("merged", False), "message": data.get("message"), "sha": data.get("sha")}
