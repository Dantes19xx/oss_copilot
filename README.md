# OSS Copilot

AI-агент для code review merge request'ов на GitHub и поиска open-source репозитория, в который стоит стать контрибьютором.

Подробный план реализации, архитектура и обоснования технических решений — в [PLAN.md](PLAN.md).
Статус работы по этапам — в [PROGRESS.md](PROGRESS.md).

## Возможности

1. **PR Reviewer** — ревью PR по файлам с человеческим подтверждением перед публикацией комментария в GitHub.
2. **Repo Matcher** — подбор open-source репозиториев для контрибьютинга по профилю пользователя, с выбором из ранжированного списка и good-first-issues.

Один агент, один граф LangGraph — свободный текстовый запрос классифицируется в одну из двух веток.

## Стек

FastAPI, LangGraph, свой MCP-сервер, RAG (Qdrant), LangSmith, Next.js.

## Запуск (локально)

```bash
cp .env.example .env   # заполнить реальными ключами
docker-compose up
```

Backend будет доступен на `http://localhost:8000/health`, Qdrant — на `http://localhost:6333`.

### MCP-сервер

`backend/mcp_server/server.py` — собственный MCP-сервер с GitHub-инструментами:

- `get_pr_diff(owner, repo, pr_number)` — diff и метаданные pull request'а
- `get_pr_files(owner, repo, pr_number, limit)` — patch по каждому файлу PR (для поочерёдного ревью)
- `post_pr_comment(owner, repo, pr_number, body)` — **write**-инструмент, публикует комментарий; граф вызывает его только после подтверждения человеком
- `search_github_repos(query, limit)` — поиск репозиториев-кандидатов для контрибьютинга
- `get_repo_health(owner, repo)` — сигналы дружелюбности к новым контрибьюторам (CONTRIBUTING.md, good-first-issues, активность)
- `get_good_first_issues(owner, repo, limit)` — список открытых good-first-issue

Запуск локально (stdio transport):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
PYTHONPATH=. python -m backend.mcp_server.server
```

### RAG-пайплайн

`backend/rag/` — индексация README/CONTRIBUTING.md репозитория в Qdrant, чтобы ревью PR учитывало конвенции конкретного проекта.

- Chunking: по markdown-заголовкам, с fallback на фиксированные окна в 500 токенов (overlap 50) для длинных секций (`chunking.py`, `tiktoken`)
- Embeddings: `text-embedding-3-small`
- Vector DB: Qdrant, одна коллекция `repo_docs` с фильтрацией по `repo` в payload

Индексация репозитория:

```bash
docker-compose up -d qdrant
PYTHONPATH=. python -m backend.rag.ingest <owner> <repo>
```

После этого `backend/graph/graph.py` автоматически подтягивает релевантный контекст в узле `retrieve_style_context` перед ревью. Если документы для репозитория не проиндексированы, граф не падает — просто ревьюит без грaундинга.

### Граф (LangGraph): ветвления, циклы, human-in-the-loop

`backend/graph/graph.py` — один `StateGraph` с реальной условной логикой:

```
intake --(review | repo_match | unclear)-->

review:      fetch_diff --(есть скриншоты в описании PR?)--> analyze_screenshots ↘
                                                                                    retrieve_style_context
             fetch_diff ------------------------------------------------------------------------------↗
             retrieve_style_context -> [analyze_file loop по файлам] -> aggregate_review
             -> human_confirm --(approve|reject)--> post_comment | discard

repo_match:  search_repos -> [score_repo loop по кандидатам] -> present_candidates
             -> human_select --(выбор|skip)--> fetch_good_first_issues | конец
```

- **Ветвление**: `intake` классифицирует свободный текст (structured output, gpt-4o-mini) и определяет, какая ветка выполняется; внутри review-ветки — есть ли изображения в описании PR.
- **Циклы**: `analyze_file` обходит файлы PR по одному (до 10), `score_repo` считает fit-score для каждого репозитория-кандидата.
- **Human-in-the-loop**: `human_confirm` и `human_select` останавливают граф через `langgraph.types.interrupt()` и ждут реального ответа человека, прежде чем публиковать комментарий в GitHub или переходить к issue выбранного репозитория.
- **Мультимодальность**: `analyze_screenshots` (`backend/graph/vision.py`) находит скриншоты/GIF в описании PR (markdown-синтаксис, `<img>`, известные asset-хосты GitHub) и анализирует их через vision gpt-4o-mini — находки попадают в финальный ревью-комментарий.

Запуск (интерактивно, с реальным вводом в терминале на шаге human-in-the-loop):

```bash
docker-compose up -d qdrant
PYTHONPATH=. python -m backend.graph.run_agent "Review the pull request https://github.com/owner/repo/pull/123"
PYTHONPATH=. python -m backend.graph.run_agent "I know Python and want to contribute to a CLI tool"
```

### Skill

`.claude/skills/code-review-checklist/SKILL.md` — тот же чек-лист ревью (баги, безопасность, тесты, breaking changes, конвенции проекта), что использует `analyze_file` в графе, но упакованный как Claude Skill: подхватывается в любой Claude Code сессии по триггерам вроде "review this PR", "code review this diff", независимо от того, подключён ли этот репозиторий к агенту. Одна и та же формулировка стандарта — не две расходящиеся копии.

## Статус

Проект в активной разработке. Архитектурная документация (ARCHITECTURE.md) и результаты evals (EVALS.md) появятся по мере реализации соответствующих этапов — см. PLAN.md, раздел 8.
