from typing import TypedDict


class ReviewState(TypedDict, total=False):
    owner: str
    repo: str
    pr_number: int

    pr_title: str
    pr_diff: str
    changed_files: int

    review_comments: list[str]
    summary: str
