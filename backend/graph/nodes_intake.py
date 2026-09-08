from langchain_openai import ChatOpenAI

from backend.graph.schemas import IntakeOutput
from backend.graph.state import AgentState

INTAKE_SYSTEM_PROMPT = """You classify a user's request to an OSS contribution assistant into \
one of two workflows:

- "review": the user wants a specific GitHub pull request reviewed. Requires a repo owner, \
repo name, and PR number (parse them out of a URL like github.com/owner/repo/pull/123 or from \
plain text).
- "repo_match": the user wants help finding an open-source repository to contribute to, based \
on their skills/interests. Build a GitHub repository search query using GitHub search \
qualifiers (language:, topic:, stars:>N, etc.) from what they said.

If you cannot confidently determine owner/repo/pr_number for a review request, or the request \
is ambiguous, set mode to "unclear"."""


async def intake(state: AgentState) -> dict:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(IntakeOutput)
    result: IntakeOutput = await llm.ainvoke(
        [
            ("system", INTAKE_SYSTEM_PROMPT),
            ("human", state["user_request"]),
        ]
    )

    if result.mode == "review" and result.owner and result.repo and result.pr_number:
        return {
            "mode": "review",
            "owner": result.owner,
            "repo": result.repo,
            "pr_number": result.pr_number,
        }
    if result.mode == "repo_match" and result.search_query:
        return {"mode": "repo_match", "search_query": result.search_query}
    return {
        "mode": "unclear",
        "summary": "Could not determine whether this is a PR review request or a repo-matching "
        "request. Please include a PR URL (owner/repo/pull/number), or describe your skills "
        "and interests for repo matching.",
    }


def route_after_intake(state: AgentState) -> str:
    return state["mode"]
