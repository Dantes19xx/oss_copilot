# EVALS.md — Golden dataset, metrics, results

Covers the mandatory ТЗ 2.3 eval requirements: golden dataset ≥30 examples, automated
run, ≥2 metrics. The A/B experiment (also ТЗ 2.3) is a separate section below, added at
the corresponding project stage — see [PROGRESS.md](PROGRESS.md) for what's implemented
when.

## 1. What's being evaluated

`backend/graph/nodes_review.review_file()` — the per-file review call the production
LangGraph `analyze_file` node uses (gpt-4o-mini, structured output, temperature 0.0 —
the current default; it was 0.2 until the §8 experiment changed it). `run_evals.py`
calls `review_file()` without overriding `temperature`, so every eval run here always
reflects whatever the production default currently is, not a fixed historical value —
worth remembering when comparing runs across §8's change (see §5).
Evals call this exact function, not a reimplementation of the prompt, so results reflect
what the agent actually ships.

Since 2026-09-19, `review_file()`'s `comments` are structured (`ReviewComment`: `code_line`
+ `text`), not plain strings — the model quotes the diff line it's commenting on, and
`backend/graph/nodes_review.py` resolves that quote to a real line number deterministically
(parsing the diff itself, not trusting the model's own arithmetic — see PROGRESS.md for
the measured accuracy problem that motivated this). Evals don't score line accuracy —
the metrics below are about `text`, i.e. whether the *substance* of a comment is right —
but `results.json`'s `predicted_comments` now carries `code_line` alongside `text` for
each entry, not a bare string.

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

## 4. Results (n=30, run 2026-09-19 — latest; temperature 0.0, current default)

This run reflects a prompt change from the previous one (2026-09-15): `review_file()`
now anchors each comment to a specific line, so it's a different `FILE_REVIEW_SYSTEM_PROMPT`
(the prompt-version hash used for caching changed too), not the same prompt re-run — see
§5 for what that does and doesn't explain about the numbers moving.

| Metric | Value |
|---|---|
| Detection accuracy | 0.80 |
| Precision | 0.79 |
| Recall | **1.00** |
| F1 | 0.88 |
| Mean LLM-judge score | 3.73 / 5 |

By category:

| Category | n | Accuracy | Mean judge score |
|---|---|---|---|
| bug | 6 | 1.00 | 5.00 |
| security | 6 | 1.00 | 4.33 |
| breaking_change | 5 | 1.00 | 3.80 |
| missing_tests | 5 | 1.00 | 2.60 |
| clean | 8 | 0.25 | 3.00 |

For comparison, the immediately preceding run (n=30, 2026-09-15, same temperature 0.0,
prior prompt version without line-anchoring): accuracy 0.83, precision 0.81, recall 1.00,
F1 0.90, judge 4.13/5; clean-category accuracy 0.38. The first documented run (n=30,
2026-09-08, temperature 0.2 — the default at the time): accuracy 0.87, precision 0.85,
recall 1.00, F1 0.92, judge 4.20/5; clean-category accuracy 0.50. All three runs are
real, all three are kept — see §5 for why the trend isn't simply read as "review quality
is getting worse."

Raw per-example results (including judge reasoning for every example) are written to
`backend/evals/results.json` on every run — not committed as a static artifact, since a
rerun regenerates it and the repo should reflect the latest run, not a frozen snapshot.

## 5. Findings

- **Recall is perfect (1.00) across all three runs, precision is not (0.79 in the
  latest).** The reviewer never misses a real issue across bug/security/missing_tests/
  breaking_change (100% accuracy in all four, in every documented run), but flags 6 of 8
  clean diffs in the latest run (5 of 8 on 2026-09-15, 4 of 8 on 2026-09-08) —
  clean-category accuracy is 0.25, down from 0.38, down from 0.50. It errs toward
  over-flagging rather than under-flagging, which is the safer failure mode for a
  code-review tool, but it's a real, measured false-positive rate, not zero, and it has
  moved in the same direction (worse) on every run so far rather than holding steady or
  bouncing randomly — worth continuing to watch, not yet enough runs to call it a trend
  versus noise (see the variance bullet below, which found no effect from an unrelated
  prompt-length change on this exact category).
- **Detection accuracy and judge score disagree, and that disagreement is the point.**
  `missing_tests` has perfect detection accuracy (1.00) in every run but the lowest judge
  score of any category every time (2.60 latest, 3.00 on 2026-09-15, 3.40 on
  2026-09-08) — the model correctly notices *something's* off but its stated reasoning is
  often vague or points at the wrong mechanism (e.g. flagged "type handling" instead of
  "no test covers this new branch"). A single metric would have hidden this, and it's the
  one finding that has held up identically across all three runs.
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
- **Run-to-run variance exists, and it's larger than it looks at first.** Four data
  points now exist for this exact 30-example set: accuracy 0.87 (2026-09-08, temperature
  0.2, judge prompt bug already fixed by that point), 0.90 (§8's dedicated temperature
  experiment, same day, both temperature 0.0 and 0.2 landed on 0.90), 0.83 (2026-09-15,
  temperature 0.0), and 0.80 (2026-09-19, temperature 0.0, line-anchoring prompt added —
  see §4). Each later run is **confounded** against the earlier ones by more than just
  chance: 2026-09-15 changed the temperature default from 0.2 to 0.0 relative to the
  first run; 2026-09-19 changed the prompt again (line-anchoring) relative to
  2026-09-15. Neither drop can be cleanly attributed to its respective change alone. What
  the four numbers together do show cleanly: even the single controlled comparison in
  §8, which held everything but temperature fixed, produced 0.90 for *both* settings —
  yet none of the three standalone `run_evals.py` runs (0.87, 0.83, 0.80) matched that
  0.90 at all. The spread across all four (0.80-0.90) is real sampling noise in the
  reviewer's own output at n=30, not something to explain away by picking whichever run
  is most recent or most favorable.
  Specifically for the 2026-09-19 drop: before accepting "line-anchoring made review
  quality worse" at face value, a quick control was run — the same 8 clean-category
  examples, once with the shipped anchoring instruction, once with a much shorter
  rewording of the same instruction. Both flagged 6 of 8 (2/8 correct), just a
  *different* 2 out of 8 landing correct between the two wordings — consistent with
  ordinary per-example volatility in this already-volatile category, not a systematic
  effect of the anchoring instruction's length or presence. That doesn't prove the
  0.83 → 0.80 drop is pure noise (no controlled A/B was run holding the prompt version
  literally fixed across two dates, the way §8 did for temperature), but it does rule out
  the most obvious alternative explanation before letting the number stand. A single
  run's numbers should always be read as an estimate with real width, not an exact
  figure — this is the concrete evidence for that, not just a caveat.

## 6. Reproducing

```bash
docker-compose up -d qdrant   # only needed if analyze_file's style-context retrieval is exercised elsewhere; run_evals.py itself doesn't need it
PYTHONPATH=. python -m backend.evals.run_evals
```

Prints a summary to stdout and writes `backend/evals/results.json`.

A/B experiment: `PYTHONPATH=. python -m backend.evals.run_ab` — writes
`backend/evals/ab_results.json`.

## 7. A/B experiment: gpt-4o-mini vs. gpt-4o

**Hypothesis:** gpt-4o-mini gives review quality close enough to gpt-4o on this task
that the cost/latency difference isn't worth paying for — i.e. the model choice already
made for the project (gpt-4o-mini, PLAN.md §2.4) is empirically justified, not just
assumed from general reputation.

**Setup:** `backend/evals/run_ab.py` runs `review_file()` — the same production
function `run_evals.py` uses — over the identical 30-example golden dataset, once with
`model="gpt-4o-mini"`, once with `model="gpt-4o"`, temperature 0.2 for both, same judge
(gpt-4o-mini, same prompt as §3) grading both arms so the grading itself isn't a
variable. Cost is computed from actual per-call token usage (`usage_metadata` on the raw
model response) × published per-token pricing; latency is wall-clock per call.

**Results (n=30 each, run 2026-09-08):**

| Metric | gpt-4o-mini | gpt-4o |
|---|---|---|
| Accuracy | 0.87 | **0.90** |
| Precision | 0.85 | **0.91** |
| Recall | **1.00** | 0.95 |
| Mean judge score | **4.13** | 4.07 |
| Mean latency | **1.31s** | 2.18s |
| Mean cost/call | **$0.0001** | $0.0017 |
| Total cost (30 calls) | **$0.0022** | $0.0518 |

**Findings:**

- gpt-4o edges out gpt-4o-mini on raw detection accuracy (0.90 vs 0.87) and precision
  (0.91 vs 0.85) — it's a bit less prone to flagging clean diffs.
- But on the metric that actually measures review *quality* — the LLM-as-judge score —
  gpt-4o-mini is marginally **higher** (4.13 vs 4.07), not lower. The stronger model
  doesn't produce better-reasoned comments here.
- gpt-4o-mini has **perfect recall (1.00)**; gpt-4o misses one real issue
  (`bug-05`, a loop-variable-shadowing bug) that gpt-4o-mini catches. For a code-review
  tool, missing a real bug is worse than one extra false positive on a clean diff — so
  gpt-4o's precision edge doesn't clearly outweigh gpt-4o-mini's recall edge.
- gpt-4o-mini is **~23x cheaper** ($0.0022 vs $0.0518 for the same 30 calls) and
  **~40% faster** (1.31s vs 2.18s mean latency) per file reviewed.

**Decision:** keep gpt-4o-mini as the production model (already the default in
`review_file()` / `analyze_file`). The accuracy/precision gap gpt-4o showed is real but
small, doesn't show up in judge-graded quality, and doesn't outweigh a 23x cost
difference and a recall regression on a task where missing a real issue is the more
costly failure mode. Revisit if the golden dataset grows enough to make the 0.87 vs 0.90
accuracy gap statistically meaningful, or if a specific category (not seen here) turns
out to need the stronger model.

**What this experiment doesn't show:** n=30 is small enough that a few examples flipping
either way would change which model "wins" on accuracy/precision — this is a first
signal, not a statistically powered result. Both models were graded by the same
gpt-4o-mini judge (see §3's self-grading caveat), so a systematic bias in the judge
would affect both arms' judge scores in the same direction rather than cancel out.

## 8. Hyperparameters: temperature, max_tokens, top_p

`backend/evals/run_temperature.py` — same golden dataset and judge as above, applied to
one hyperparameter directly (ТЗ 2.4: "Подбор температуры, top_p, max_tokens - с
экспериментальным обоснованием").

**Temperature.** Two things were measured, deliberately kept separate: quality (does the
review get better or worse) and consistency (does the same input keep producing the same
verdict). A single quality metric can look identical at two temperatures while one is
quietly far less reproducible — which matters more for a tool that posts its output to a
real PR than one extra accuracy point would.

| Temperature | Accuracy | Judge score | Verdict stability (3 repeats, n=6) | Comment-count stdev |
|---|---|---|---|---|
| 0.0 | 0.90 | 4.20 | 1.00 | 0.000 |
| 0.2 | 0.90 | 4.20 | 1.00 | 0.000 |
| 0.7 | 0.90 | **4.00** | 1.00 | **0.079** |

Accuracy was identical across all three (0.90) on the 30-example set. 0.7 scored lower
on the judge (4.00 vs 4.20) and showed measurable comment-count variance across repeats
of the same 6 examples (0.0 and 0.2 had zero variance — byte-identical verdicts and
comment counts every repeat). Note the verdict itself (flag vs. don't-flag) never
flipped even at 0.7 in this sample — the instability was in exactly *how many* comments
came back, not whether an issue was caught.

**Decision:** switched the production default from 0.2 to **0.0**
(`FILE_REVIEW_TEMPERATURE` in `backend/graph/nodes_review.py`). 0.0 tied 0.2 on both
quality metrics and matched it on reproducibility, so there's no measured quality cost —
and 0.0 gives the strongest determinism guarantee available, which is worth more than
0.2's unrealized potential for variety on a task where "same diff in, same verdict out"
is a property worth having. This was a real change made because of the data, not a
post-hoc justification for the number already in use.

**max_tokens = 500.** Not swept as a range — instead measured from real usage. Across
60 live `review_file()` calls already made for stage 9 (evals) and stage 10 (A/B),
`output_tokens` ranged 4-125 with a mean of 53.8 (see `backend/evals/ab_results.json`).
500 gives >4x headroom over the observed worst case: a safety net against a pathological
runaway generation, not a real constraint on any output seen so far.

**top_p** was left at the API default (1.0), not tuned. OpenAI's own guidance is to
adjust temperature *or* top_p, not both — sweeping both would confound whichever
sampling axis actually caused an observed change. Temperature was chosen as the one axis
to tune since it's the more commonly documented lever and the one already exposed as a
parameter in `review_file()`.

**Scope note:** this experiment covers `review_file()` only (the highest-volume, most
evaluable LLM call in the project). `nodes_intake.intake()` already uses temperature=0
for the same determinism reason (classifying/extracting structured routing info, not
open-ended writing) — consistent with this finding, not separately re-tested.
`vision.analyze_image()` keeps temperature=0.2, since describing an image is a more
open-ended task where some phrasing variation is acceptable; it hasn't been tuned with
its own experiment and that's a documented gap, not a claim that 0.2 was measured there.
