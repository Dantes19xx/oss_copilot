from typing import Literal, TypedDict


class AgentState(TypedDict, total=False):
    # input
    user_request: str
    language: Literal["ru", "en"]

    # intake / routing
    mode: Literal["review", "repo_match", "unclear"]

    # --- review branch ---
    owner: str
    repo: str
    pr_number: int

    pr_title: str
    pr_diff: str
    changed_files: int
    style_context: list[str]

    image_urls: list[str]
    image_analysis: list[str]
    injection_warnings: list[str]

    file_diffs: list[dict]
    file_index: int
    review_comments: list[dict]  # {"filename": str, "line": str, "text": str}

    summary: str
    human_decision: Literal["approve", "reject", "merge"]
    posted: bool

    # --- repo_match branch ---
    search_query: str
    clarify_history: list[str]
    clarify_turns: int
    clarify_done: bool
    candidates: list[dict]
    candidate_index: int
    scored_candidates: list[dict]
    candidates_text: str  # the ranked list shown at human_select, kept apart from `summary`
    shown_query: str  # the search query that produced candidates_text
    selected_repo: dict | None
    refinement: str | None  # free-text correction typed at human_select, consumed by refine_search
    notice: str | None  # one-shot message shown with the next candidate list
    good_first_issues: list[dict]
    back_to_results: bool
