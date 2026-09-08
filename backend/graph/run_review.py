"""Manual smoke-test entry point for the stage-3 review graph.

Usage: PYTHONPATH=. python -m backend.graph.run_review <owner> <repo> <pr_number>
"""

import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()

from backend.graph.graph import review_app  # noqa: E402


async def main() -> None:
    owner, repo, pr_number = sys.argv[1], sys.argv[2], int(sys.argv[3])
    result = await review_app.ainvoke({"owner": owner, "repo": repo, "pr_number": pr_number})
    print(f"PR: {result['pr_title']} ({result['changed_files']} files changed)\n")
    print(result["summary"])


if __name__ == "__main__":
    asyncio.run(main())
