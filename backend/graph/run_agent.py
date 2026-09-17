"""Interactive CLI for the full agent graph (stage 5): free-text request in, routed
through the review or repo-matching branch, pausing at the human-in-the-loop step for
real terminal input.

Usage: PYTHONPATH=. python -m backend.graph.run_agent "<free-text request>" [ru|en]
"""

import asyncio
import sys
import uuid

from dotenv import load_dotenv
from langgraph.types import Command

load_dotenv(override=True)

from backend.graph.graph import review_app  # noqa: E402


async def main() -> None:
    user_request = sys.argv[1]
    language = sys.argv[2] if len(sys.argv) > 2 else "en"
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    result = await review_app.ainvoke({"user_request": user_request, "language": language}, config=config)

    while "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        print("\n--- human input requested ---")
        for key, value in payload.items():
            print(f"{key}: {value}")
        answer = input("> ")
        result = await review_app.ainvoke(Command(resume=answer), config=config)

    print("\n--- final result ---")
    print(result.get("summary", "(no summary produced)"))


if __name__ == "__main__":
    asyncio.run(main())
