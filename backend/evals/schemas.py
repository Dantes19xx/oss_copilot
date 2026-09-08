from pydantic import BaseModel, Field


class JudgeOutput(BaseModel):
    score: int = Field(
        description="1-5. 5 = the model's output correctly matches the expected finding for this "
        "diff (caught the real issue with an accurate explanation, or correctly found nothing when "
        "nothing was expected). 1 = missed the issue entirely, or flagged something wrong/irrelevant."
    )
    reasoning: str = Field(description="One sentence justifying the score.")
