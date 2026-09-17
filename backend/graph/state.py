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
    review_comments: list[str]

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
    selected_repo: dict | None
    good_first_issues: list[dict]
