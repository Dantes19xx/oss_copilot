from langgraph.types import interrupt

from backend.graph.mcp_client import call_tool
from backend.graph.state import AgentState


async def search_repos(state: AgentState) -> dict:
    repos = await call_tool("search_github_repos", {"query": state["search_query"], "limit": 5})
    if not repos:
        return {"candidates": [], "summary": f"No repositories found for query: {state['search_query']}"}
    return {"candidates": repos, "candidate_index": 0, "scored_candidates": []}


def route_after_search(state: AgentState) -> str:
    return "score" if state.get("candidates") else "none"


async def score_repo(state: AgentState) -> dict:
    candidates = state["candidates"]
    index = state["candidate_index"]
    candidate = candidates[index]
    owner, repo = candidate["full_name"].split("/", 1)

    health = await call_tool("get_repo_health", {"owner": owner, "repo": repo})

    score = 0.0
    if health.get("has_contributing_guide"):
        score += 2.0
    score += min(health.get("good_first_issue_count", 0), 10) * 0.5
    if health.get("archived"):
        score -= 100.0

    scored = list(state.get("scored_candidates", []))
    scored.append({**candidate, **health, "fit_score": score})
    return {"scored_candidates": scored, "candidate_index": index + 1}


def route_after_score_repo(state: AgentState) -> str:
    return "next" if state["candidate_index"] < len(state["candidates"]) else "present"


async def present_candidates(state: AgentState) -> dict:
    ranked = sorted(state["scored_candidates"], key=lambda c: c["fit_score"], reverse=True)
    lines = [
        f"{i + 1}. {c['full_name']} (fit score {c['fit_score']:.1f}, "
        f"{c.get('good_first_issue_count', 0)} good-first-issues) — {c.get('description') or 'no description'}"
        for i, c in enumerate(ranked)
    ]
    return {"scored_candidates": ranked, "summary": "Candidate repositories:\n" + "\n".join(lines)}


async def human_select(state: AgentState) -> dict:
    choice = interrupt(
        {
            "type": "repo_selection",
            "candidates": state["summary"],
            "instructions": "Reply with the number of the repo to pursue, or 'skip'.",
        }
    )
    ranked = state["scored_candidates"]
    try:
        index = int(str(choice).strip()) - 1
    except ValueError:
        index = -1
    if 0 <= index < len(ranked):
        return {"selected_repo": ranked[index]}
    return {"selected_repo": None}


def route_after_human_select(state: AgentState) -> str:
    return "issues" if state.get("selected_repo") else "end"


async def fetch_good_first_issues(state: AgentState) -> dict:
    selected = state["selected_repo"]
    owner, repo = selected["full_name"].split("/", 1)
    issues = await call_tool("get_good_first_issues", {"owner": owner, "repo": repo, "limit": 5})
    lines = [f"- #{i['number']} {i['title']} ({i['html_url']})" for i in issues]
    summary = f"Selected {selected['full_name']}. Good first issues:\n" + (
        "\n".join(lines) if lines else "(none open right now)"
    )
    return {"good_first_issues": issues, "summary": summary}
