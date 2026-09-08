---
name: code-review-checklist
description: Review a diff or pull request against a focused code-review checklist — bugs and logic errors, security issues, missing tests, breaking API changes, and adherence to the target repo's own CONTRIBUTING/style conventions. Use when the user asks to "review this PR", "code review this diff", "review this pull request", "check this MR", or pastes a diff/PR link and asks what's wrong with it.
---

# Code Review Checklist

This is the same checklist OSS Copilot's `analyze_file` LangGraph node applies to
every file in a pull request (`backend/graph/nodes_review.py`, `FILE_REVIEW_SYSTEM_PROMPT`).
It's packaged here as a Skill so the identical standard is available directly in a
Claude Code session — reviewing a diff by hand, on a repo the agent hasn't been
pointed at, or before wiring a project into the agent at all — without re-deriving or
re-typing the criteria, and without the two review paths silently drifting apart.

## What to check, in order

1. **Bugs and logic errors** — off-by-one, incorrect conditionals, wrong operator,
   unhandled edge case, state mutated in a way that breaks a caller's assumption.
2. **Security issues** — hardcoded secrets/credentials, injection (SQL, shell, template),
   unsafe deserialization, missing input validation at a trust boundary, path traversal.
3. **Missing tests** — new logic (a new branch, a new public function, a bug fix) with
   no corresponding test. Don't demand tests for pure refactors or trivial glue code.
4. **Breaking API changes** — a removed/renamed public function, parameter, or return
   shape; a changed default; a route or schema change without a migration path.
5. **Project conventions** — if the repo has a CONTRIBUTING.md/README with stated
   conventions (changelog entries, commit format, required checks), check the diff
   against those specifically. Read the file first if it isn't already in context —
   don't assume conventions from memory or from a different project.

## What not to flag

- Pure style/formatting that a linter would catch and that doesn't hurt readability.
- Nitpicks with no concrete failure mode — every comment should name what breaks and
  under what input/condition, not just express a preference.
- Issues outside the diff's actual change (pre-existing code the PR didn't touch),
  unless the PR's own logic now depends on that pre-existing issue.

If a file's diff has no real issues, say so plainly rather than inventing something to
comment on — an empty, honest review is a valid outcome.

## Output format

For each issue: one line naming the file (and line/hunk if visible) plus the concrete
problem — not a restatement of what the diff does. Close with a one- or two-sentence
overall verdict (would you approve, request changes, or is it fine with minor notes).

## Scope

Applies to any diff or PR the user hands you, in any repository — this is a general
review standard, not specific to the OSS Copilot project itself.
