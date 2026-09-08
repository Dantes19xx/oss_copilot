"""Automated eval run over the golden dataset (backend/evals/golden_dataset.py).

Calls the SAME review_file() function the production graph uses (backend/graph/
nodes_review.py) — this evaluates the real prompt/model, not a reimplementation.

Two metrics (ТЗ 2.3 requires >= 2):
  1. Detection accuracy — did review_file() produce a non-empty comments list exactly
     when expected_has_issue says it should? (also reports precision/recall/F1, since
     the dataset is imbalanced: 22 issue examples vs 8 clean ones)
  2. LLM-as-judge score (1-5) — a second gpt-4o-mini call grades whether the produced
     comments (or their absence) actually match the expected finding, not just whether
     comments existed. This catches the case detection accuracy can't: right verdict,
     wrong or irrelevant reasoning.

Usage: PYTHONPATH=. python -m backend.evals.run_evals
Writes backend/evals/results.json (raw per-example results, for audit/reproducibility).
"""

import asyncio
import json
from pathlib import Path
from statistics import mean

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv(override=True)

from backend.evals.golden_dataset import GOLDEN_DATASET  # noqa: E402
from backend.evals.schemas import JudgeOutput  # noqa: E402
from backend.graph.nodes_review import review_file  # noqa: E402

JUDGE_SYSTEM_PROMPT = """You are grading an automated code reviewer's output against a known-\
correct expected finding for a diff. Score 1-5:
5 = matches the expected finding, with an accurate, on-target explanation of the actual \
mechanism of the issue. If "Expected: CLEAN", an EMPTY comment list is by itself a perfect 5 —
correctly finding nothing IS the correct output; do not penalize it for not praising the diff or
not explaining why it's fine. Only judge non-empty comments on a CLEAN example for whether they
wrongly invent a problem.
3 = right verdict (flagged vs. not flagged) but the reasoning is vague, partially wrong, or misses \
the specific mechanism of the issue.
1 = wrong verdict (missed a real issue, or invented a problem on a CLEAN diff), or the reasoning \
is unrelated to the actual expected finding.
Be strict about substance, not phrasing: a comment that happens to mention the right file but not \
the actual mechanism of the issue is not a 5."""

CONCURRENCY = 8
RESULTS_PATH = Path(__file__).parent / "results.json"


async def judge(example: dict, predicted_comments: list[str]) -> JudgeOutput:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(JudgeOutput)
    predicted_block = "\n".join(f"- {c}" for c in predicted_comments) if predicted_comments else "(no comments)"
    return await llm.ainvoke(
        [
            ("system", JUDGE_SYSTEM_PROMPT),
            (
                "human",
                f"Diff:\n{example['patch']}\n\n"
                f"Expected: {'ISSUE' if example['expected_has_issue'] else 'CLEAN'} — {example['expected_note']}\n\n"
                f"Model's actual comments:\n{predicted_block}",
            ),
        ]
    )


async def run_one(example: dict, semaphore: asyncio.Semaphore) -> dict:
    async with semaphore:
        result = await review_file(example["filename"], example["status"], example["patch"])
        predicted_has_issue = len(result.comments) > 0
        judge_result = await judge(example, result.comments)
        return {
            "id": example["id"],
            "category": example["category"],
            "expected_has_issue": example["expected_has_issue"],
            "predicted_has_issue": predicted_has_issue,
            "correct": predicted_has_issue == example["expected_has_issue"],
            "predicted_comments": result.comments,
            "judge_score": judge_result.score,
            "judge_reasoning": judge_result.reasoning,
        }


def summarize(results: list[dict]) -> dict:
    total = len(results)
    accuracy = sum(r["correct"] for r in results) / total

    tp = sum(1 for r in results if r["expected_has_issue"] and r["predicted_has_issue"])
    fp = sum(1 for r in results if not r["expected_has_issue"] and r["predicted_has_issue"])
    fn = sum(1 for r in results if r["expected_has_issue"] and not r["predicted_has_issue"])
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else float("nan")

    mean_judge_score = mean(r["judge_score"] for r in results)

    by_category: dict[str, dict] = {}
    for category in sorted({r["category"] for r in results}):
        rows = [r for r in results if r["category"] == category]
        by_category[category] = {
            "n": len(rows),
            "accuracy": sum(r["correct"] for r in rows) / len(rows),
            "mean_judge_score": mean(r["judge_score"] for r in rows),
        }

    return {
        "n": total,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "mean_judge_score": mean_judge_score,
        "by_category": by_category,
    }


async def main() -> None:
    semaphore = asyncio.Semaphore(CONCURRENCY)
    results = await asyncio.gather(*(run_one(ex, semaphore) for ex in GOLDEN_DATASET))
    summary = summarize(results)

    RESULTS_PATH.write_text(json.dumps({"summary": summary, "results": results}, indent=2))

    print(f"n={summary['n']}  accuracy={summary['accuracy']:.2f}  "
          f"precision={summary['precision']:.2f}  recall={summary['recall']:.2f}  f1={summary['f1']:.2f}  "
          f"mean_judge_score={summary['mean_judge_score']:.2f}/5")
    print()
    for category, stats in summary["by_category"].items():
        print(f"  {category:<16} n={stats['n']:<3} accuracy={stats['accuracy']:.2f}  "
              f"mean_judge_score={stats['mean_judge_score']:.2f}/5")
    print()
    for r in results:
        if not r["correct"] or r["judge_score"] < 4:
            print(f"[{r['id']}] expected_has_issue={r['expected_has_issue']} "
                  f"predicted_has_issue={r['predicted_has_issue']} judge={r['judge_score']}/5: {r['judge_reasoning']}")

    print(f"\nWrote {RESULTS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
