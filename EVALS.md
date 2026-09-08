# EVALS.md — Golden dataset, metrics, results

Covers the mandatory ТЗ 2.3 eval requirements: golden dataset ≥30 examples, automated
run, ≥2 metrics. The A/B experiment (also ТЗ 2.3) is a separate section below, added at
the corresponding project stage — see [PROGRESS.md](PROGRESS.md) for what's implemented
when.

## 1. What's being evaluated

`backend/graph/nodes_review.review_file()` — the per-file review call the production
LangGraph `analyze_file` node uses (gpt-4o-mini, structured output, temperature 0.2).
Evals call this exact function, not a reimplementation of the prompt, so results reflect
what the agent actually ships.

## 2. Golden dataset

`backend/evals/golden_dataset.py` — 30 single-file diffs, each with a category and a
ground-truth label (`expected_has_issue`, `expected_note`).

| Category | n | What it tests |
|---|---|---|
| `bug` | 6 | Real logic errors (off-by-one, mutable default arg, wrong operator, swallowed exception, variable shadowing, integer division) |
| `security` | 6 | Hardcoded secret, SQL/shell injection, unsafe `pickle.loads`, `eval()`, missing auth check on a new route |
| `missing_tests` | 5 | New logic (function, edge case, CLI flag, endpoint, bug fix) added with no test change |
| `breaking_change` | 5 | Public API changed in a way that breaks existing callers (renamed param, changed return type, removed default, changed exception type, removed method) |
| `clean` | 8 | No real issue — tests that the model doesn't invent nitpicks (false-positive check) |

**All 30 are hand-crafted, not pulled from real PRs.** A crafted diff lets us pin down
exactly one issue per example with an unambiguous label, instead of hand-labeling a real
PR and then second-guessing that label. The tradeoff is ecological validity — these are
smaller and cleaner than real-world diffs. Augmenting with manually-labeled real PR files
(the project already has `get_pull_request_files` and has pulled dozens of real diffs
for live smoke tests throughout development — see PROGRESS.md) is a documented,
not-yet-done follow-up, not a blocker for the required 30.

Distribution (22 issue / 8 clean) is intentionally imbalanced toward real issues, since
recall on real problems matters more for this product than a balanced split would test —
but it means raw accuracy alone would be a misleading headline number (a reviewer that
flags everything scores 73% accuracy for free). That's why precision/recall/F1 are
reported alongside it, not folded away.

## 3. Metrics

Two required by ТЗ 2.3; both are computed by `backend/evals/run_evals.py`.

**1. Detection accuracy** (+ precision/recall/F1) — did `review_file()` return a
non-empty `comments` list exactly when `expected_has_issue` says it should? Cheap,
deterministic-ish, easy to track over time. **What it doesn't show:** it's a binary
verdict on *whether the model said anything*, blind to whether what it said is actually
right. A reviewer that flags the correct file for a completely wrong reason still counts
as "correct" here.

**2. LLM-as-judge score (1-5)** — a second gpt-4o-mini call, given the diff, the expected
finding, and the model's actual comments, scores whether the comments (or their absence)
substantively match the expected finding — not just whether the verdict was right. This
is what catches "right file, wrong/generic reason," which detection accuracy can't.
**What it doesn't show:** it's graded by the same model family reviewing itself
(gpt-4o-mini judging gpt-4o-mini), a known bias risk — a stronger or different judge
model would be a natural next step, not done here. It's also only as good as its own
prompt: see §5 for a real miscalibration this project hit and fixed.

## 4. Results (n=30, run 2026-09-08)

| Metric | Value |
|---|---|
| Detection accuracy | **0.87** |
| Precision | 0.85 |
| Recall | **1.00** |
| F1 | 0.92 |
| Mean LLM-judge score | **4.20 / 5** |

By category:

| Category | n | Accuracy | Mean judge score |
|---|---|---|---|
| bug | 6 | 1.00 | 4.67 |
| security | 6 | 1.00 | 4.33 |
| breaking_change | 5 | 1.00 | 4.20 |
| missing_tests | 5 | 1.00 | 3.40 |
| clean | 8 | 0.50 | 4.25 |

Raw per-example results (including judge reasoning for every example) are written to
`backend/evals/results.json` on every run — not committed as a static artifact, since a
rerun regenerates it and the repo should reflect the latest run, not a frozen snapshot.

## 5. Findings

- **Recall is perfect (1.00), precision is not (0.85).** The reviewer never misses a
  real issue across bug/security/missing_tests/breaking_change (100% accuracy in all
  four), but flags 4 of 8 clean diffs — clean-category accuracy is only 0.50. It errs
  toward over-flagging rather than under-flagging, which is the safer failure mode for a
  code-review tool, but it's a real, measured false-positive rate, not zero.
- **Detection accuracy and judge score disagree, and that disagreement is the point.**
  `missing_tests` has perfect detection accuracy (1.00) but the lowest judge score
  (3.40) — the model correctly notices *something's* off but its stated reasoning is
  often vague or points at the wrong mechanism (e.g. flagged "type handling" instead of
  "no test covers this new branch"). A single metric would have hidden this.
- **A judge-prompt bug inflated a false signal, caught by rerunning.** The first
  version of the judge prompt scored a *correct* empty `comments` list on a clean diff as
  1/5, because its rubric implicitly expected the model to say something (even "looks
  good") rather than accepting silence as the correct outcome. That miscalibration alone
  dragged `clean`-category judge score down to 2.25. Fixing the judge prompt to treat an
  empty list on a `CLEAN` example as an automatic 5 raised it to 4.25 — same review
  outputs, same dataset, only the grader changed. Lesson kept for next time: an eval
  metric is only as trustworthy as its own prompt, and it's worth spot-checking the
  judge's stated reasoning, not just its number.
- **One dataset example (`clean-08`) has a real ambiguity, left in on purpose.** It adds
  a new function with no test *in that file's diff*, expecting tests exist elsewhere in
  the same PR — but `review_file()` only ever sees one file's patch, so it has no way to
  know that. The model reliably flags it as missing tests, which is a reasonable
  inference from what it can actually see, not a model failure. This is a real limit of
  file-by-file review (vs. reviewing the full PR at once) worth knowing about rather than
  papering over: `analyze_file` (backend/graph/nodes_review.py) has no cross-file
  context beyond the RAG-retrieved style guide.
- **Run-to-run variance exists.** Two runs of the same 30 examples (temperature 0.2 for
  the reviewer, 0 for the judge) produced accuracy 0.90 then 0.87, and mean judge score
  3.20 then 4.20 (the second jump is the prompt fix above, not just noise — but even the
  detection-accuracy delta alone shows the model isn't perfectly deterministic at 0.2).
  A single run's numbers should be read as an estimate, not an exact figure.

## 6. Reproducing

```bash
docker-compose up -d qdrant   # only needed if analyze_file's style-context retrieval is exercised elsewhere; run_evals.py itself doesn't need it
PYTHONPATH=. python -m backend.evals.run_evals
```

Prints a summary to stdout and writes `backend/evals/results.json`.

## 7. A/B experiment

Not yet run — tracked as the next stage in [PROGRESS.md](PROGRESS.md) (PLAN.md §8,
stage 10). Will compare two configurations (candidates per PLAN.md §10: gpt-4o-mini vs.
gpt-4o, or review with vs. without RAG-retrieved style context) on this same golden
dataset and metrics, with a stated hypothesis and a decision recorded here.
