from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from backend.graph.mcp_client import call_tool
from backend.graph.state import ReviewState
from backend.rag.retrieve import retrieve_context

STYLE_CONTEXT_QUERY = "contribution guidelines, coding conventions, and code style requirements"

REVIEW_SYSTEM_PROMPT = """You are a senior software engineer performing a GitHub pull \
request code review. Read the unified diff and produce specific, actionable review \
comments. Check for: bugs and logic errors, security issues (secrets, injection, unsafe \
deserialization), missing tests for new logic, and breaking API changes. Do not comment \
on pure style/formatting unless it hurts readability. If the diff has no real issues, \
return an empty comments list rather than inventing nitpicks.

You may be given excerpts from the project's own README/CONTRIBUTING guide as context. \
Use them to check whether the diff follows this specific project's conventions (e.g. \
required tests, changelog entries, code style). If no excerpts are given, review on \
general engineering merit only."""


class ReviewOutput(BaseModel):
    comments: list[str] = Field(description="Specific, actionable review comments. Empty if the diff looks fine.")
    summary: str = Field(description="One or two sentence overall verdict of the PR.")


async def fetch_diff(state: ReviewState) -> dict:
    pr = await call_tool(
        "get_pr_diff",
        {"owner": state["owner"], "repo": state["repo"], "pr_number": state["pr_number"]},
    )
    return {
        "pr_title": pr["title"],
        "pr_diff": pr["diff"],
        "changed_files": pr["changed_files"],
    }


async def retrieve_style_context(state: ReviewState) -> dict:
    results = await retrieve_context(state["owner"], state["repo"], STYLE_CONTEXT_QUERY, limit=3)
    return {"style_context": [r["text"] for r in results]}


async def analyze_diff(state: ReviewState) -> dict:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2).with_structured_output(ReviewOutput)

    context = state.get("style_context") or []
    context_block = (
        "\n\n".join(f"[project doc excerpt {i + 1}]\n{c}" for i, c in enumerate(context))
        if context
        else "(no project documentation indexed for this repo)"
    )

    result: ReviewOutput = await llm.ainvoke(
        [
            ("system", REVIEW_SYSTEM_PROMPT),
            (
                "human",
                f"PR title: {state['pr_title']}\n\n"
                f"Project conventions:\n{context_block}\n\n"
                f"Diff:\n{state['pr_diff']}",
            ),
        ]
    )
    return {"review_comments": result.comments, "summary": result.summary}


async def aggregate_review(state: ReviewState) -> dict:
    comments = state.get("review_comments", [])
    if comments:
        body = state["summary"] + "\n\n" + "\n".join(f"- {c}" for c in comments)
    else:
        body = state["summary"]
    return {"summary": body}
