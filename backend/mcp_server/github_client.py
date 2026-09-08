"""Thin async wrapper around the GitHub REST API used by the MCP tools."""

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

    async def count_good_first_issues(self, owner: str, repo: str) -> int:
        response = await self._get(
            "/search/issues",
            params={
                "q": f'repo:{owner}/{repo} is:issue is:open label:"good first issue"',
                "per_page": 1,
            },
        )
        return response.json().get("total_count", 0)
