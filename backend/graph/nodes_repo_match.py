from langchain_openai import ChatOpenAI
from langgraph.types import interrupt

from backend.graph.i18n import LANGUAGE_NAME, t
from backend.graph.mcp_client import call_tool
from backend.graph.schemas import ClarifyOutput
from backend.graph.state import AgentState

MAX_CLARIFY_TURNS = 2
# Bounded like every other loop in this graph (MAX_FILES, candidate scoring) — a
# conversational back-and-forth that never converges would otherwise block the request
# indefinitely on human input. Two follow-ups is enough to narrow "I know Python" into
# a usable search without turning a quick request into an interrogation.

CLARIFY_SYSTEM_PROMPT = """You help match a developer to an open-source repository worth \
contributing to. You'll see their original request and, if any, a transcript of follow-up \
questions you already asked and their answers.

Decide: does this already have enough signal to build a good GitHub search query (language, \
rough topic/interest, any stated preference on project size or activity)? If yes, set \
ask_question=False and write refined_query using GitHub search qualifiers (language:, topic:, \
stars:>N, archived:false, etc.) — combine everything learned across the whole conversation, \
not just the latest answer.

If one more short, conversational question would meaningfully narrow the results (e.g. which \
language they're most comfortable with, whether they want a well-known project or something \
smaller and quieter, how much time they can commit, a specific domain/topic they care about), \
set ask_question=True and write a single, natural question — not a form, not multiple \
questions at once. Never ask something already answered in the transcript."""


async def clarify_repo_match(state: AgentState) -> dict:
    lang = state.get("language")
    turns = state.get("clarify_turns", 0)
    history = state.get("clarify_history", [])
    force_finalize = turns >= MAX_CLARIFY_TURNS

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(ClarifyOutput)
    transcript = "\n".join(history) if history else "(no follow-up questions asked yet)"
    human_prompt = (
        f"Original request: {state['user_request']}\n\n"
        f"Follow-up transcript:\n{transcript}\n\n"
        f"Target language for the question (if any): {LANGUAGE_NAME.get(lang, 'English')}."
        + (
            "\n\nYou have already asked the maximum number of follow-up questions — "
            "you MUST set ask_question=False and finalize refined_query now with "
            "whatever signal you have."
            if force_finalize
            else ""
        )
    )
    result: ClarifyOutput = await llm.ainvoke([("system", CLARIFY_SYSTEM_PROMPT), ("human", human_prompt)])

    if not force_finalize and result.ask_question and result.question:
        answer = interrupt(
            {
                "type": "clarifying_question",
                "question": result.question,
                "instructions": t(lang, "clarify_instructions"),
            }
        )
        if str(answer).strip().lower() == "skip":
            return {"clarify_done": True}
        new_history = history + [f"Q: {result.question}\nA: {answer}"]
        return {"clarify_history": new_history, "clarify_turns": turns + 1}

    return {"search_query": result.refined_query or state["search_query"], "clarify_done": True}


def route_after_clarify(state: AgentState) -> str:
    return "search" if state.get("clarify_done") else "ask_again"


async def search_repos(state: AgentState) -> dict:
    repos = await call_tool("search_github_repos", {"query": state["search_query"], "limit": 5})
    if not repos:
        summary = t(state.get("language"), "no_repos_found", query=state["search_query"])
        return {"candidates": [], "summary": summary}
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
    lang = state.get("language")
    ranked = sorted(state["scored_candidates"], key=lambda c: c["fit_score"], reverse=True)
    lines = [
        t(
            lang,
            "candidate_line",
            i=i + 1,
            full_name=c["full_name"],
            score=c["fit_score"],
            issues=c.get("good_first_issue_count", 0),
            desc=c.get("description") or t(lang, "no_description"),
        )
        for i, c in enumerate(ranked)
    ]
    summary = t(lang, "candidates_header") + "\n" + "\n".join(lines)
    return {"scored_candidates": ranked, "summary": summary}


async def human_select(state: AgentState) -> dict:
    choice = interrupt(
        {
            "type": "repo_selection",
            "candidates": state["summary"],
            "instructions": t(state.get("language"), "select_instructions"),
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
    lang = state.get("language")
    selected = state["selected_repo"]
    owner, repo = selected["full_name"].split("/", 1)
    issues = await call_tool("get_good_first_issues", {"owner": owner, "repo": repo, "limit": 5})
    lines = [f"- #{i['number']} {i['title']} ({i['html_url']})" for i in issues]
    header = t(lang, "selected_issues_header", full_name=selected["full_name"])
    body = "\n".join(lines) if lines else t(lang, "no_open_issues")
    return {"good_first_issues": issues, "summary": header + "\n" + body}
