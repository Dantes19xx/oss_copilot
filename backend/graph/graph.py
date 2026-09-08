"""Stage-3 happy path: fetch a PR diff -> review it -> aggregate a final summary.

No branching, loops, or human-in-the-loop yet — those are added in stage 5
(see PLAN.md, section 1.1 and section 8).
"""

from langgraph.graph import END, StateGraph

from backend.graph.nodes import aggregate_review, analyze_diff, fetch_diff
from backend.graph.state import ReviewState

_graph = StateGraph(ReviewState)
_graph.add_node("fetch_diff", fetch_diff)
_graph.add_node("analyze_diff", analyze_diff)
_graph.add_node("aggregate_review", aggregate_review)

_graph.set_entry_point("fetch_diff")
_graph.add_edge("fetch_diff", "analyze_diff")
_graph.add_edge("analyze_diff", "aggregate_review")
_graph.add_edge("aggregate_review", END)

review_app = _graph.compile()
