"""A/B experiment: gpt-4o-mini vs gpt-4o on the review pipeline (ТЗ 2.3 + 2.4).

Hypothesis (PLAN.md §10, §2.4): gpt-4o-mini gives review quality close enough to
gpt-4o for this task that the ~15-20x cost difference isn't worth paying — i.e. the
production choice of gpt-4o-mini (PLAN.md §2.4) is justified empirically, not just
assumed. If gpt-4o turns out meaningfully better (higher judge score on the SAME golden
dataset, not just a different eyeballed example), that would be a reason to revisit it.

Runs review_file() (backend/graph/nodes_review.py) over the same 30-example golden
dataset used in run_evals.py, once per model, capturing per-call token usage and
latency via the model/return_usage args added there for this purpose. Reuses the same
judge as run_evals.py, run once per arm so both are graded identically.

Usage: PYTHONPATH=. python -m backend.evals.run_ab
Writes backend/evals/ab_results.json (gitignored, regenerated per run).
"""

import asyncio
import json
from pathlib import Path
from statistics import mean

from dotenv import load_dotenv

load_dotenv(override=True)

from backend.evals.golden_dataset import GOLDEN_DATASET  # noqa: E402
from backend.evals.run_evals import CONCURRENCY, judge  # noqa: E402
from backend.graph.nodes_review import review_file  # noqa: E402

MODELS = ["gpt-4o-mini", "gpt-4o"]

# USD per 1M tokens, input/output — https://openai.com/api/pricing (as of this project's
# build; re-check before citing these numbers in a defense months later).
PRICING_PER_1M = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}

RESULTS_PATH = Path(__file__).parent / "ab_results.json"


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = PRICING_PER_1M[model]
    return input_tokens / 1_000_000 * rates["input"] + output_tokens / 1_000_000 * rates["output"]


async def run_one(example: dict, model: str, semaphore: asyncio.Semaphore) -> dict:
    async with semaphore:
        parsed, usage = await review_file(
            example["filename"], example["status"], example["patch"], model=model, return_usage=True
        )
        predicted_has_issue = len(parsed.comments) > 0
        judge_result = await judge(example, parsed.comments)
        return {
            "id": example["id"],
            "category": example["category"],
            "expected_has_issue": example["expected_has_issue"],
            "predicted_has_issue": predicted_has_issue,
            "correct": predicted_has_issue == example["expected_has_issue"],
            "predicted_comments": parsed.comments,
            "judge_score": judge_result.score,
            "latency_s": usage["latency_s"],
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "cost_usd": cost_usd(model, usage["input_tokens"], usage["output_tokens"]),
        }


async def run_arm(model: str) -> list[dict]:
    semaphore = asyncio.Semaphore(CONCURRENCY)
    return list(await asyncio.gather(*(run_one(ex, model, semaphore) for ex in GOLDEN_DATASET)))


def summarize(results: list[dict]) -> dict:
    total = len(results)
    tp = sum(1 for r in results if r["expected_has_issue"] and r["predicted_has_issue"])
    fp = sum(1 for r in results if not r["expected_has_issue"] and r["predicted_has_issue"])
    fn = sum(1 for r in results if r["expected_has_issue"] and not r["predicted_has_issue"])
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    return {
        "n": total,
        "accuracy": sum(r["correct"] for r in results) / total,
        "precision": precision,
        "recall": recall,
        "mean_judge_score": mean(r["judge_score"] for r in results),
        "mean_latency_s": mean(r["latency_s"] for r in results),
        "total_cost_usd": sum(r["cost_usd"] for r in results),
        "mean_cost_usd": mean(r["cost_usd"] for r in results),
    }


async def main() -> None:
    arms: dict[str, dict] = {}
    for model in MODELS:
        print(f"Running {model} over {len(GOLDEN_DATASET)} examples...")
        results = await run_arm(model)
        arms[model] = {"summary": summarize(results), "results": results}

    RESULTS_PATH.write_text(json.dumps(arms, indent=2))

    print()
    header = f"{'metric':<18}" + "".join(f"{m:>16}" for m in MODELS)
    print(header)
    for key in ["accuracy", "precision", "recall", "mean_judge_score", "mean_latency_s", "mean_cost_usd"]:
        row = f"{key:<18}"
        for model in MODELS:
            v = arms[model]["summary"][key]
            row += f"{v:>16.4f}" if key == "mean_cost_usd" else f"{v:>16.3f}"
        print(row)
    print(f"\ntotal_cost_usd: " + "  ".join(f"{m}=${arms[m]['summary']['total_cost_usd']:.4f}" for m in MODELS))
    print(f"\nWrote {RESULTS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
