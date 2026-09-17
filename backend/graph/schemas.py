from typing import Literal

from pydantic import BaseModel, Field


class IntakeOutput(BaseModel):
    """Classifies a free-text user request and extracts the parameters needed to route it."""

    mode: Literal["review", "repo_match", "unclear"] = Field(
        description="'review' if the user wants a specific PR reviewed, 'repo_match' if they "
        "want help finding an open-source repo to contribute to, 'unclear' otherwise."
    )
    owner: str | None = Field(None, description="Repo owner/org, for mode='review'")
    repo: str | None = Field(None, description="Repo name, for mode='review'")
    pr_number: int | None = Field(None, description="Pull request number, for mode='review'")
    search_query: str | None = Field(
        None,
        description="A GitHub repository search query built from the user's stated skills/interests "
        "(GitHub search qualifiers like language:, topic:, stars:>N), for mode='repo_match'.",
    )


class FileReviewOutput(BaseModel):
    comments: list[str] = Field(description="Specific, actionable comments about this file's diff. Empty if fine.")


class ClarifyOutput(BaseModel):
    """Decides whether the repo-matching request has enough signal to search GitHub yet,
    or whether one more guiding question would meaningfully narrow the results."""

    ask_question: bool = Field(
        description="True if a follow-up question would meaningfully narrow the search "
        "(e.g. preferred language, project size, time commitment, area of interest). False "
        "if the request already has enough signal, or further questions wouldn't help."
    )
    question: str | None = Field(
        None, description="A single, short, conversational follow-up question, in the target "
        "language. Required if ask_question is True."
    )
    refined_query: str | None = Field(
        None,
        description="A GitHub repository search query using GitHub search qualifiers "
        "(language:, topic:, stars:>N, etc.) built from everything learned so far. Required "
        "if ask_question is False.",
    )
