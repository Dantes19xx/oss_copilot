import asyncio

from langchain_openai import ChatOpenAI
from langgraph.types import interrupt

from backend.graph.mcp_client import call_tool
from backend.graph.schemas import FileReviewOutput
from backend.graph.state import AgentState
from backend.graph.vision import analyze_image, extract_image_urls
from backend.rag.retrieve import retrieve_context

STYLE_CONTEXT_QUERY = "contribution guidelines, coding conventions, and code style requirements"
MAX_FILES = 10

FILE_REVIEW_SYSTEM_PROMPT = """You are a senior software engineer performing a GitHub pull \
request code review, one file at a time. Check for: bugs and logic errors, security issues \
(secrets, injection, unsafe deserialization), missing tests for new logic, and breaking API \
changes. Do not comment on pure style/formatting unless it hurts readability. If this file's \
diff has no real issues, return an empty comments list rather than inventing nitpicks.

You may be given excerpts from the project's own README/CONTRIBUTING guide as context. Use \
them to check whether the diff follows this specific project's conventions. If no excerpts are \
given, review on general engineering merit only."""


async def fetch_diff(state: AgentState) -> dict:
    pr = await call_tool(
        "get_pr_diff",
        {"owner": state["owner"], "repo": state["repo"], "pr_number": state["pr_number"]},
    )
    files = await call_tool(
        "get_pr_files",
        {"owner": state["owner"], "repo": state["repo"], "pr_number": state["pr_number"], "limit": MAX_FILES},
    )
    return {
        "pr_title": pr["title"],
        "pr_diff": pr["diff"],
        "changed_files": pr["changed_files"],
        "file_diffs": files,
        "file_index": 0,
        "review_comments": [],
        "image_urls": extract_image_urls(pr.get("body")),
    }


def route_after_fetch_diff(state: AgentState) -> str:
    return "vision" if state.get("image_urls") else "context"


async def analyze_screenshots(state: AgentState) -> dict:
    urls = state["image_urls"]
    descriptions = await asyncio.gather(*(analyze_image(url) for url in urls))
    return {"image_analysis": [f"{url}: {desc}" for url, desc in zip(urls, descriptions)]}


async def retrieve_style_context(state: AgentState) -> dict:
    results = await retrieve_context(state["owner"], state["repo"], STYLE_CONTEXT_QUERY, limit=3)
    return {"style_context": [r["text"] for r in results]}


def route_after_context(state: AgentState) -> str:
    return "analyze" if state.get("file_diffs") else "skip"


async def review_file(filename: str, status: str, patch: str, context: list[str] | None = None) -> FileReviewOutput:
    """The actual per-file review call — used by the graph node below AND by
    backend/evals/run_evals.py, so evals score the real production prompt/model, not a
    reimplementation of it."""
    context = context or []
    context_block = (
        "\n\n".join(f"[project doc excerpt {i + 1}]\n{c}" for i, c in enumerate(context))
        if context
        else "(no project documentation indexed for this repo)"
    )
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2).with_structured_output(FileReviewOutput)
    return await llm.ainvoke(
        [
            ("system", FILE_REVIEW_SYSTEM_PROMPT),
            (
                "human",
                f"File: {filename} ({status})\n\nProject conventions:\n{context_block}\n\nPatch:\n{patch}",
            ),
        ]
    )


async def analyze_file(state: AgentState) -> dict:
    files = state["file_diffs"]
    index = state["file_index"]
    file = files[index]
    comments = list(state.get("review_comments", []))

    patch = file.get("patch")
    if patch:
        result = await review_file(file["filename"], file["status"], patch, state.get("style_context"))
        comments.extend(f"{file['filename']}: {c}" for c in result.comments)

    return {"review_comments": comments, "file_index": index + 1}


def route_after_analyze_file(state: AgentState) -> str:
    return "next" if state["file_index"] < len(state["file_diffs"]) else "done"


async def aggregate_review(state: AgentState) -> dict:
    comments = state.get("review_comments", [])
    changed = state.get("changed_files", len(state.get("file_diffs", [])))
    if comments:
        summary = f"Reviewed {changed} file(s). Found {len(comments)} issue(s):\n" + "\n".join(
            f"- {c}" for c in comments
        )
    else:
        summary = f"Reviewed {changed} file(s). No issues found."

    image_notes = state.get("image_analysis") or []
    if image_notes:
        summary += "\n\nScreenshot/attachment analysis:\n" + "\n".join(f"- {n}" for n in image_notes)

    return {"summary": summary}


async def human_confirm(state: AgentState) -> dict:
    decision = interrupt(
        {
            "type": "review_confirmation",
            "pr": f"{state['owner']}/{state['repo']}#{state['pr_number']}",
            "draft_comment": state["summary"],
            "instructions": "Reply 'approve' to post this as a PR comment on GitHub, or 'reject' to discard it.",
        }
    )
    approved = str(decision).strip().lower() in ("approve", "yes", "y")
    return {"human_decision": "approve" if approved else "reject"}


def route_after_human_confirm(state: AgentState) -> str:
    return "post" if state["human_decision"] == "approve" else "discard"


async def post_comment(state: AgentState) -> dict:
    result = await call_tool(
        "post_pr_comment",
        {"owner": state["owner"], "repo": state["repo"], "pr_number": state["pr_number"], "body": state["summary"]},
    )
    return {"posted": True, "summary": state["summary"] + f"\n\n(Posted: {result.get('html_url')})"}


async def discard(state: AgentState) -> dict:
    return {"posted": False, "summary": state["summary"] + "\n\n(Discarded by reviewer — not posted to GitHub.)"}
