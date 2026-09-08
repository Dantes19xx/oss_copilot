"""Stage-5 full workflow: branching, loops, and human-in-the-loop.

    intake --(mode: review | repo_match | unclear)-->

  review branch:
    fetch_diff -> retrieve_style_context -> [analyze_file loop over files]
    -> aggregate_review -> human_confirm --(approve|reject)--> post_comment | discard

  repo_match branch:
    search_repos -> [score_repo loop over candidates] -> present_candidates
    -> human_select --(picked|skip)--> fetch_good_first_issues | END

See PLAN.md section 1.1 for the design and PROGRESS.md for what's verified.
"""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph

from backend.graph.nodes_intake import intake, route_after_intake
from backend.graph.nodes_repo_match import (
    fetch_good_first_issues,
    human_select,
    present_candidates,
    route_after_human_select,
    route_after_score_repo,
    route_after_search,
    score_repo,
    search_repos,
)
from backend.graph.nodes_review import (
    aggregate_review,
    analyze_file,
    discard,
    fetch_diff,
    human_confirm,
    post_comment,
    retrieve_style_context,
    route_after_analyze_file,
    route_after_context,
    route_after_human_confirm,
)
from backend.graph.state import AgentState

_graph = StateGraph(AgentState)

_graph.add_node("intake", intake)

_graph.add_node("fetch_diff", fetch_diff)
_graph.add_node("retrieve_style_context", retrieve_style_context)
_graph.add_node("analyze_file", analyze_file)
_graph.add_node("aggregate_review", aggregate_review)
_graph.add_node("human_confirm", human_confirm)
_graph.add_node("post_comment", post_comment)
_graph.add_node("discard", discard)

_graph.add_node("search_repos", search_repos)
_graph.add_node("score_repo", score_repo)
_graph.add_node("present_candidates", present_candidates)
_graph.add_node("human_select", human_select)
_graph.add_node("fetch_good_first_issues", fetch_good_first_issues)

_graph.set_entry_point("intake")
_graph.add_conditional_edges(
    "intake",
    route_after_intake,
    {"review": "fetch_diff", "repo_match": "search_repos", "unclear": END},
)

# --- review branch ---
_graph.add_edge("fetch_diff", "retrieve_style_context")
_graph.add_conditional_edges(
    "retrieve_style_context",
    route_after_context,
    {"analyze": "analyze_file", "skip": "aggregate_review"},
)
_graph.add_conditional_edges(
    "analyze_file",
    route_after_analyze_file,
    {"next": "analyze_file", "done": "aggregate_review"},
)
_graph.add_edge("aggregate_review", "human_confirm")
_graph.add_conditional_edges(
    "human_confirm",
    route_after_human_confirm,
    {"post": "post_comment", "discard": "discard"},
)
_graph.add_edge("post_comment", END)
_graph.add_edge("discard", END)

# --- repo_match branch ---
_graph.add_conditional_edges(
    "search_repos",
    route_after_search,
    {"score": "score_repo", "none": END},
)
_graph.add_conditional_edges(
    "score_repo",
    route_after_score_repo,
    {"next": "score_repo", "present": "present_candidates"},
)
_graph.add_edge("present_candidates", "human_select")
_graph.add_conditional_edges(
    "human_select",
    route_after_human_select,
    {"issues": "fetch_good_first_issues", "end": END},
)
_graph.add_edge("fetch_good_first_issues", END)

review_app = _graph.compile(checkpointer=InMemorySaver())
