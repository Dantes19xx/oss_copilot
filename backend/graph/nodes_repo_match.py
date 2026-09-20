from langchain_openai import ChatOpenAI
from langgraph.types import interrupt

from backend.graph.i18n import LANGUAGE_NAME, t
from backend.graph.mcp_client import call_tool
from backend.graph.schemas import ClarifyOutput, RefineOutput
from backend.graph.state import AgentState

MAX_CLARIFY_TURNS = 2
# Bounded like every other loop in this graph (MAX_FILES, candidate scoring) — a
# conversational back-and-forth that never converges would otherwise block the request
# indefinitely on human input. Two follow-ups is enough to narrow "I know Python" into
# a usable search without turning a quick request into an interrogation.

CONTRIBUTING_BONUS = 2.0
MAX_COUNTED_ISSUES = 10
MAX_FIT_SCORE = CONTRIBUTING_BONUS + MAX_COUNTED_ISSUES * 0.5
# Sent to the frontend so it can draw the fit score as a bar without duplicating the
# scoring formula's constants on its side.


def _repo_view(c: dict, rank: int | None = None) -> dict:
    """Structured repo card for the frontend — the same data present_candidates renders
    as plain text for the CLI, minus the string formatting."""
    view = {
        "full_name": c.get("full_name"),
        "url": c.get("url") or f"https://github.com/{c.get('full_name')}",
        "description": c.get("description"),
        "stars": c.get("stars"),
        "language": c.get("language"),
        "open_issues": c.get("open_issues"),
        "good_first_issues": c.get("good_first_issue_count", 0),
        "license": c.get("license"),
        "pushed_at": c.get("pushed_at"),
        "has_contributing_guide": bool(c.get("has_contributing_guide")),
        "archived": bool(c.get("archived")),
        "fit_score": c.get("fit_score"),
        "topics": (c.get("topics") or [])[:4],
    }
    if rank is not None:
        view["rank"] = rank
    return view


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


REFINE_SYSTEM_PROMPT = """You adjust a GitHub repository search query after the developer saw \
the first results and asked for a change. You'll see their original request, the follow-up \
transcript (including earlier corrections), the search query that produced the results they \
saw, and their new correction.

Return the updated query in GitHub search qualifiers (language:, topic:, stars:>N, \
archived:false, etc.). Apply the correction — it overrides anything in the current query it \
contradicts (e.g. "on Go" replaces language:python; "smaller projects" lowers or caps stars) — \
and keep everything else. If the correction is vague, interpret it in the most useful way; \
never return an empty query."""


async def refine_search(state: AgentState) -> dict:
    refinement = state["refinement"]
    history = state.get("clarify_history", [])
    transcript = "\n".join(history) if history else "(none)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(RefineOutput)
    result: RefineOutput = await llm.ainvoke(
        [
            ("system", REFINE_SYSTEM_PROMPT),
            (
                "human",
                f"Original request: {state['user_request']}\n\n"
                f"Follow-up transcript:\n{transcript}\n\n"
                f"Current search query: {state['search_query']}\n\n"
                f"New correction: {refinement}",
            ),
        ]
    )
    # The correction joins the transcript so a later one ("actually, also add CLI") is
    # interpreted against everything asked for so far, not just the latest message.
    return {
        "search_query": result.refined_query.strip() or state["search_query"],
        "clarify_history": history + [f"Correction after seeing results: {refinement}"],
        "refinement": None,
    }


async def search_repos(state: AgentState) -> dict:
    repos = await call_tool("search_github_repos", {"query": state["search_query"], "limit": 5})
    if not repos:
        message = t(state.get("language"), "no_repos_found", query=state["search_query"])
        if state.get("scored_candidates"):
            # A refinement matched nothing — keep the list the user already has instead of
            # ending the session and throwing it away.
            return {
                "candidates": [],
                "notice": t(state.get("language"), "refine_nothing_found", query=state["search_query"]),
                # the next correction must build on the query behind the list still on screen
                "search_query": state["shown_query"],
            }
        return {"candidates": [], "summary": message}
    return {"candidates": repos, "candidate_index": 0, "scored_candidates": []}


def route_after_search(state: AgentState) -> str:
    if state.get("candidates"):
        return "score"
    return "keep" if state.get("scored_candidates") else "none"


async def score_repo(state: AgentState) -> dict:
    candidates = state["candidates"]
    index = state["candidate_index"]
    candidate = candidates[index]
    owner, repo = candidate["full_name"].split("/", 1)

    health = await call_tool("get_repo_health", {"owner": owner, "repo": repo})

    score = 0.0
    if health.get("has_contributing_guide"):
        score += CONTRIBUTING_BONUS
    score += min(health.get("good_first_issue_count", 0), MAX_COUNTED_ISSUES) * 0.5
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
            open=c.get("open_issues") or 0,
            desc=c.get("description") or t(lang, "no_description"),
        )
        for i, c in enumerate(ranked)
    ]
    summary = t(lang, "candidates_header") + "\n" + "\n".join(lines)
    return {
        "scored_candidates": ranked,
        "summary": summary,
        "candidates_text": summary,
        "shown_query": state["search_query"],
    }


_SKIP_WORDS = {"skip", "пропустить"}


async def human_select(state: AgentState) -> dict:
    lang = state.get("language")
    ranked = state["scored_candidates"]
    # candidates_text, not summary: fetch_good_first_issues overwrites summary with the
    # issues list, and "back" has to re-show the candidates, not the last repo's issues.
    payload = {
        "type": "repo_selection",
        "candidates": state["candidates_text"],
        "candidates_data": [_repo_view(c, i + 1) for i, c in enumerate(ranked)],
        "max_fit_score": MAX_FIT_SCORE,
        "query": state.get("shown_query"),
        "instructions": t(lang, "select_instructions"),
    }
    if state.get("notice"):
        payload["notice"] = state["notice"]

    choice = interrupt(payload)
    # A number picks a repo, "skip" ends, any other text is a correction to the search.
    # Anything else (empty, a number outside the list) re-prompts — same rule as
    # human_confirm/show_issues — rather than silently ending or silently re-searching.
    while True:
        text = str(choice).strip()
        if text.isdigit() and 1 <= int(text) <= len(ranked):
            return {"selected_repo": ranked[int(text) - 1], "refinement": None, "notice": None}
        if text.lower() in _SKIP_WORDS:
            return {"selected_repo": None, "refinement": None, "notice": None}
        if text and not text.isdigit():
            return {"selected_repo": None, "refinement": text, "notice": None}
        choice = interrupt({**payload, "error": t(lang, "select_unrecognized", answer=text)})


def route_after_human_select(state: AgentState) -> str:
    if state.get("selected_repo"):
        return "issues"
    return "refine" if state.get("refinement") else "end"


async def fetch_good_first_issues(state: AgentState) -> dict:
    lang = state.get("language")
    selected = state["selected_repo"]
    owner, repo = selected["full_name"].split("/", 1)
    issues = await call_tool("get_good_first_issues", {"owner": owner, "repo": repo, "limit": 5})
    lines = [f"- #{i['number']} {i['title']} ({i['html_url']})" for i in issues]
    header = t(lang, "selected_issues_header", full_name=selected["full_name"])
    body = "\n".join(lines) if lines else t(lang, "no_open_issues")
    return {"good_first_issues": issues, "summary": header + "\n" + body}


_BACK_WORDS = {"back", "b", "назад"}
_DONE_WORDS = {"done", "d", "finish", "готово"}


async def show_issues(state: AgentState) -> dict:
    lang = state.get("language")
    payload = {
        "type": "repo_issues",
        "issues": state["summary"],
        "repo": _repo_view(state["selected_repo"]),
        "issues_data": [
            {"number": i["number"], "title": i["title"], "url": i["html_url"]}
            for i in state.get("good_first_issues", [])
        ],
        "instructions": t(lang, "issues_instructions"),
    }
    answer = interrupt(payload)
    # Same rule as human_confirm: an unrecognized reply re-prompts instead of silently
    # ending the session and throwing away the candidate list the user meant to go back to.
    while str(answer).strip().lower() not in _BACK_WORDS | _DONE_WORDS:
        answer = interrupt({**payload, "error": t(lang, "issues_unrecognized", answer=answer)})
    return {"back_to_results": str(answer).strip().lower() in _BACK_WORDS}


def route_after_show_issues(state: AgentState) -> str:
    return "back" if state.get("back_to_results") else "end"
