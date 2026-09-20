"""Localized strings for the deterministic (non-LLM-generated) parts of user-facing
output — interrupt instructions, status scaffolding, error text. LLM-generated content
(review comments, clarifying questions, judge text) is localized separately by telling
the model what language to answer in — see LANGUAGE_NAME below and its use in
nodes_review.py / nodes_repo_match.py system prompts.

Data pulled straight from GitHub (repo descriptions, filenames, issue titles) is never
translated — only the agent's own scaffolding text is.
"""

from typing import Literal

Language = Literal["ru", "en"]

LANGUAGE_NAME: dict[Language, str] = {"ru": "Russian", "en": "English"}

_STRINGS: dict[str, dict[Language, str]] = {
    "unclear_summary": {
        "en": "Could not determine whether this is a PR review request or a repo-matching "
        "request. Please include a PR URL (owner/repo/pull/number), or describe your skills "
        "and interests for repo matching.",
        "ru": "Не удалось понять, это запрос на ревью PR или на подбор репозитория. "
        "Укажите ссылку на PR (owner/repo/pull/номер) либо опишите свои навыки и интересы "
        "для подбора репозитория.",
    },
    "confirm_instructions": {
        "en": "Reply 'approve' to approve this PR on GitHub, 'merge' to approve it and then "
        "merge it, or 'reject' to discard it.",
        "ru": "Ответьте 'approve', чтобы одобрить этот PR на GitHub, 'merge' — чтобы одобрить "
        "и затем смержить, или 'reject', чтобы отклонить.",
    },
    "confirm_unrecognized": {
        "en": "Unrecognized reply '{decision}'. Reply 'approve', 'merge', or 'reject'.",
        "ru": "Ответ '{decision}' не распознан. Ответьте 'approve', 'merge' или 'reject'.",
    },
    "security_warning": {
        "en": "This PR's diff/description contains text matching known prompt-injection "
        "patterns: {warnings}. Review the draft comment carefully before approving — the "
        "model was instructed to treat this as untrusted content, not as commands.",
        "ru": "В diff'е/описании этого PR найден текст, похожий на попытку prompt injection: "
        "{warnings}. Внимательно прочитайте черновик перед подтверждением — модели было "
        "явно указано относиться к этому как к непроверенному контенту, а не как к командам.",
    },
    "posted_suffix": {"en": "\n\n(Approved on GitHub: {url})", "ru": "\n\n(Одобрено на GitHub: {url})"},
    "self_approval_notice": {
        "en": "✅ **Approved via OSS Copilot** (posted as a comment — GitHub doesn't allow a "
        "formal review status on your own pull request)\n\n",
        "ru": "✅ **Одобрено через OSS Copilot** (опубликовано как комментарий — GitHub не "
        "позволяет формальный статус ревью на собственном PR)\n\n",
    },
    "posted_as_comment_suffix": {
        "en": "\n\n(Approved — posted as a comment, not a formal GitHub review status, since "
        "this is your own PR: {url})",
        "ru": "\n\n(Одобрено — опубликовано как комментарий, а не формальный статус ревью, "
        "так как это ваш собственный PR: {url})",
    },
    "merged_suffix": {"en": "\n\n(Merged: {sha})", "ru": "\n\n(Смержено: {sha})"},
    "not_merged_suffix": {
        "en": "\n\n(Not merged: {message})",
        "ru": "\n\n(Не смержено: {message})",
    },
    "discarded_suffix": {
        "en": "\n\n(Discarded by reviewer — not posted to GitHub.)",
        "ru": "\n\n(Отклонено ревьюером — не опубликовано на GitHub.)",
    },
    "reviewed_with_issues": {
        "en": "Reviewed {n} file(s). Found {m} issue(s):",
        "ru": "Проверено файлов: {n}. Найдено замечаний: {m}:",
    },
    "reviewed_clean": {
        "en": "Reviewed {n} file(s). No issues found.",
        "ru": "Проверено файлов: {n}. Замечаний не найдено.",
    },
    "screenshot_analysis_header": {
        "en": "\n\nScreenshot/attachment analysis:",
        "ru": "\n\nАнализ скриншотов/вложений:",
    },
    "general_comment_label": {"en": "General", "ru": "Общее"},
    "no_repos_found": {
        "en": "No repositories found for query: {query}",
        "ru": "По запросу ничего не найдено: {query}",
    },
    "candidates_header": {"en": "Candidate repositories:", "ru": "Кандидаты:"},
    "candidate_line": {
        "en": "{i}. {full_name} (fit score {score:.1f}, {issues} good-first-issues, {open} open issues) — {desc}",
        "ru": "{i}. {full_name} (оценка {score:.1f}, good-first-issues: {issues}, открытых issues: {open}) — {desc}",
    },
    "no_description": {"en": "no description", "ru": "без описания"},
    "select_instructions": {
        "en": "Reply with the number of the repo to pursue, describe a change to refine the "
        "search (e.g. 'Go instead', 'smaller projects'), or 'skip'.",
        "ru": "Ответьте номером репозитория, который вас заинтересовал, опишите, что изменить "
        "в поиске (например, «на Go», «поменьше проекты»), или 'skip'.",
    },
    "select_unrecognized": {
        "en": "'{answer}' is not a valid choice. Reply with a number from the list, describe a "
        "change to the search, or 'skip'.",
        "ru": "'{answer}' — некорректный выбор. Ответьте номером из списка, опишите изменение "
        "поиска или 'skip'.",
    },
    "refine_nothing_found": {
        "en": "Nothing found for the adjusted search ({query}) — showing the previous results.",
        "ru": "По уточнённому запросу ничего не найдено ({query}) — показываю прежние результаты.",
    },
    "clarify_instructions": {
        "en": "Answer in a few words, or 'skip' to let the agent search with what it has.",
        "ru": "Ответьте в двух словах, либо 'skip', чтобы агент искал с тем, что уже есть.",
    },
    "selected_issues_header": {
        "en": "Selected {full_name}. Good first issues:",
        "ru": "Выбран {full_name}. Открытые good-first-issue:",
    },
    "issues_instructions": {
        "en": "Reply 'back' to return to the candidate list, or 'done' to finish.",
        "ru": "Ответьте 'back', чтобы вернуться к списку кандидатов, или 'done', чтобы закончить.",
    },
    "issues_unrecognized": {
        "en": "Unrecognized reply '{answer}'. Reply 'back' or 'done'.",
        "ru": "Ответ '{answer}' не распознан. Ответьте 'back' или 'done'.",
    },
    "no_open_issues": {"en": "(none open right now)", "ru": "(сейчас открытых нет)"},
}


def t(language: Language | None, key: str, **kwargs: object) -> str:
    lang: Language = language if language in ("ru", "en") else "en"
    template = _STRINGS[key][lang]
    return template.format(**kwargs) if kwargs else template
