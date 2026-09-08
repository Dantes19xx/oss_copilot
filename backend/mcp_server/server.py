"""OSS Copilot MCP server.

Exposes read-only GitHub tools used by the LangGraph agent:
- get_pr_diff: fetch a pull request's diff and metadata for review
- search_github_repos: find candidate repositories to contribute to
- get_repo_health: contribution-friendliness signals for a repository

Run with: python -m backend.mcp_server.server (stdio transport)
"""

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

from backend.mcp_server.github_client import GitHubClient

load_dotenv()

mcp = MCPServer("oss-copilot-github")


@mcp.tool()
async def get_pr_diff(owner: str, repo: str, pr_number: int) -> dict:
    """Fetch a GitHub pull request's diff plus title/body/file-count metadata for review."""
    client = GitHubClient()
    pr = await client.get_pull_request(owner, repo, pr_number)
    diff = await client.get_pull_request_diff(owner, repo, pr_number)
    return {
        "title": pr.get("title"),
        "body": pr.get("body"),
        "author": pr.get("user", {}).get("login"),
        "changed_files": pr.get("changed_files"),
        "additions": pr.get("additions"),
        "deletions": pr.get("deletions"),
        "base": pr.get("base", {}).get("ref"),
        "head": pr.get("head", {}).get("ref"),
        "diff": diff,
    }


@mcp.tool()
async def search_github_repos(query: str, limit: int = 10) -> list[dict]:
    """Search GitHub repositories (e.g. 'topic:cli language:python stars:>500') for contribution candidates."""
    client = GitHubClient()
    repos = await client.search_repositories(query, limit=limit)
    return [
        {
            "full_name": r.get("full_name"),
            "description": r.get("description"),
            "stars": r.get("stargazers_count"),
            "language": r.get("language"),
            "open_issues": r.get("open_issues_count"),
            "topics": r.get("topics", []),
            "url": r.get("html_url"),
        }
        for r in repos
    ]


@mcp.tool()
async def get_repo_health(owner: str, repo: str) -> dict:
    """Return contribution-friendliness signals for a repo: activity, license, CONTRIBUTING guide, good-first-issue count."""
    client = GitHubClient()
    repo_info = await client.get_repository(owner, repo)
    has_contributing = await client.file_exists(owner, repo, "CONTRIBUTING.md")
    good_first_issues = await client.count_good_first_issues(owner, repo)
    return {
        "full_name": repo_info.get("full_name"),
        "stars": repo_info.get("stargazers_count"),
        "open_issues": repo_info.get("open_issues_count"),
        "license": (repo_info.get("license") or {}).get("spdx_id"),
        "pushed_at": repo_info.get("pushed_at"),
        "has_contributing_guide": has_contributing,
        "good_first_issue_count": good_first_issues,
        "archived": repo_info.get("archived", False),
    }


if __name__ == "__main__":
    mcp.run()
