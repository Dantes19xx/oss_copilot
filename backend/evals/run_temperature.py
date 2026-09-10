"""Temperature experiment for review_file() (ТЗ 2.4: "Подбор температуры... с
экспериментальным обоснованием").

Two parts, because temperature affects two different things that a single quality
metric would conflate:

  A. Quality across temperatures — full golden dataset, one pass per temperature,
     same 2 metrics as run_evals.py (detection accuracy, LLM-as-judge score).
  B. Consistency/determinism — what temperature actually controls. Repeats a subset of
     examples 3x per temperature and measures how often the verdict (has_issue) and the
     comment count are stable across repeats. Quality metrics alone can look identical
     at two temperatures while one is quietly far less reproducible than the other —
     that instability matters for a tool whose output gets posted to a real PR.

top_p is deliberately not swept here — OpenAI's guidance is to alter temperature or
top_p, not both, so this project picks one axis (temperature) rather than run a
confounded grid. See EVALS.md stage-11 section for the writeup.

Usage: PYTHONPATH=. python -m backend.evals.run_temperature
Writes backend/evals/temperature_results.json (gitignored).
"""

import asyncio
import json
from pathlib import Path
from statistics import mean, pstdev

from dotenv import load_dotenv

load_dotenv(override=True)

from backend.evals.golden_dataset import GOLDEN_DATASET  # noqa: E402
from backend.evals.run_evals import CONCURRENCY, judge  # noqa: E402
from backend.graph.nodes_review import review_file  # noqa: E402

TEMPERATURES = [0.0, 0.2, 0.7]
CONSISTENCY_REPEATS = 3
# Mix of categories, including borderline/harder ones from run_evals.py's low-judge-score
# tail (test-02, break-02) and a clean example prone to false positives (clean-05).
CONSISTENCY_EXAMPLE_IDS = ["bug-01", "sec-02", "test-02", "break-02", "clean-05", "clean-08"]

RESULTS_PATH = Path(__file__).parent / "temperature_results.json"


# --------------------------------------------------------------------------- part A ---
async def run_quality_one(example: dict, temperature: float, semaphore: asyncio.Semaphore) -> dict:
    async with semaphore:
        result = await review_file(example["filename"], example["status"], example["patch"], temperature=temperature)
        predicted_has_issue = len(result.comments) > 0
        judge_result = await judge(example, result.comments)
        return {
            "id": example["id"],
            "correct": predicted_has_issue == example["expected_has_issue"],
            "judge_score": judge_result.score,
        }


async def run_quality(temperature: float) -> dict:
    semaphore = asyncio.Semaphore(CONCURRENCY)
    results = list(await asyncio.gather(*(run_quality_one(ex, temperature, semaphore) for ex in GOLDEN_DATASET)))
    return {
        "accuracy": sum(r["correct"] for r in results) / len(results),
        "mean_judge_score": mean(r["judge_score"] for r in results),
    }


# --------------------------------------------------------------------------- part B ---
async def run_consistency_one(example: dict, temperature: float, semaphore: asyncio.Semaphore) -> dict:
    async with semaphore:
        result = await review_file(example["filename"], example["status"], example["patch"], temperature=temperature)
        return {"has_issue": len(result.comments) > 0, "n_comments": len(result.comments)}


async def run_consistency(temperature: float) -> dict:
    examples = [ex for ex in GOLDEN_DATASET if ex["id"] in CONSISTENCY_EXAMPLE_IDS]
    semaphore = asyncio.Semaphore(CONCURRENCY)
    per_example: dict[str, list[dict]] = {}
    for example in examples:
        repeats = await asyncio.gather(
            *(run_consistency_one(example, temperature, semaphore) for _ in range(CONSISTENCY_REPEATS))
        )
        per_example[example["id"]] = list(repeats)

    stable_verdicts = 0
    comment_count_spreads = []
    for example_id, repeats in per_example.items():
        verdicts = [r["has_issue"] for r in repeats]
        stable_verdicts += 1 if len(set(verdicts)) == 1 else 0
        counts = [r["n_comments"] for r in repeats]
        comment_count_spreads.append(max(counts) - min(counts))

    return {
        "verdict_stability_rate": stable_verdicts / len(per_example),
        "mean_comment_count_spread": mean(comment_count_spreads),
        "mean_comment_count_stdev": mean(pstdev([r["n_comments"] for r in repeats]) for repeats in per_example.values()),
        "raw": per_example,
    }


async def main() -> None:
    quality = {}
    consistency = {}
    for temperature in TEMPERATURES:
        print(f"Quality pass @ temperature={temperature} ({len(GOLDEN_DATASET)} examples)...")
        quality[temperature] = await run_quality(temperature)
        print(f"Consistency pass @ temperature={temperature} "
              f"({len(CONSISTENCY_EXAMPLE_IDS)} examples x {CONSISTENCY_REPEATS} repeats)...")
        consistency[temperature] = await run_consistency(temperature)

    RESULTS_PATH.write_text(json.dumps({"quality": quality, "consistency": consistency}, indent=2))

    print("\n--- Part A: quality across temperature ---")
    print(f"{'temperature':<14}{'accuracy':>12}{'judge_score':>14}")
    for t in TEMPERATURES:
        print(f"{t:<14}{quality[t]['accuracy']:>12.3f}{quality[t]['mean_judge_score']:>14.3f}")

    print("\n--- Part B: verdict stability across 3 repeats (n=6 examples) ---")
    print(f"{'temperature':<14}{'stability_rate':>16}{'comment_count_stdev':>22}")
    for t in TEMPERATURES:
        c = consistency[t]
        print(f"{t:<14}{c['verdict_stability_rate']:>16.3f}{c['mean_comment_count_stdev']:>22.3f}")

    print(f"\nWrote {RESULTS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
