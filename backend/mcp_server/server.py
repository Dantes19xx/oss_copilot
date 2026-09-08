"""OSS Copilot MCP server.

Exposes GitHub tools used by the LangGraph agent:
- get_pr_diff: fetch a pull request's diff and metadata for review
- get_pr_files: fetch a pull request's per-file patches (for a file-by-file review loop)
- post_pr_comment: post a review comment to a pull request (write — only call after
  human confirmation; the graph gates this behind a human-in-the-loop step)
- search_github_repos: find candidate repositories to contribute to
- get_repo_health: contribution-friendliness signals for a repository
- get_good_first_issues: list open good-first-issue candidates for a repository

Run with: python -m backend.mcp_server.server (stdio transport)
"""

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

from backend.mcp_server.github_client import GitHubClient

load_dotenv(override=True)

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
async def get_pr_files(owner: str, repo: str, pr_number: int, limit: int = 10) -> list[dict]:
    """Fetch per-file patches for a pull request, for a file-by-file review loop."""
    client = GitHubClient()
    files = await client.get_pull_request_files(owner, repo, pr_number, limit=limit)
    return [
        {
            "filename": f.get("filename"),
            "status": f.get("status"),
            "additions": f.get("additions"),
            "deletions": f.get("deletions"),
            "patch": f.get("patch"),
        }
        for f in files
    ]


@mcp.tool()
async def post_pr_comment(owner: str, repo: str, pr_number: int, body: str) -> dict:
    """Post a comment to a pull request. WRITE action — call only after human approval."""
    client = GitHubClient()
    comment = await client.create_issue_comment(owner, repo, pr_number, body)
    return {"id": comment.get("id"), "html_url": comment.get("html_url")}


@mcp.tool()
async def get_good_first_issues(owner: str, repo: str, limit: int = 5) -> list[dict]:
    """List open issues labeled 'good first issue' for a repository."""
    client = GitHubClient()
    issues = await client.search_good_first_issues(owner, repo, limit=limit)
    return [
        {
            "number": i.get("number"),
            "title": i.get("title"),
            "html_url": i.get("html_url"),
        }
        for i in issues
    ]


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
