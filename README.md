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

### Мониторинг (LangSmith)

Все LLM-вызовы трейсятся в LangSmith — включены через `.env` (`LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`), без дополнительного кода для вызовов через `langchain_openai.ChatOpenAI` (review, vision, intake-классификация). Одно исключение: `langchain_openai.OpenAIEmbeddings`/сырой `openai` SDK не трейсятся LangSmith автоматически (это не `Runnable`) — поэтому `backend/rag/embeddings.py` явно оборачивает вызов декоратором `@traceable(run_type="embedding")` из пакета `langsmith`, чтобы embeddings не оставались слепой зоной.

Дашборд: `https://smith.langchain.com` → проект `oss_copilot`. Каждый запуск графа (`ainvoke`) создаёт корневой трейс `LangGraph` с дочерними спанами по узлам и LLM-вызовам. Human-in-the-loop сценарий (review с `human_confirm`, repo_match с `human_select`) технически состоит из двух отдельных `ainvoke()` — до прерывания и после `Command(resume=...)` — которые попадают в LangSmith как два трейса, но оба помечены одним `thread_id` в метаданных рана; фильтр по `metadata.thread_id` в дашборде показывает полный путь одного пользовательского сценария от начала до публикации/отклонения.

### Evals, A/B, гиперпараметры

Golden dataset (30 примеров), автоматизированные evals (accuracy + LLM-as-judge), A/B (gpt-4o-mini vs gpt-4o) и эксперимент по temperature — в [EVALS.md](EVALS.md).

### Guardrails

`backend/graph/guardrails.py` — PR-диффы и описания приходят от произвольных внешних контрибьюторов, это untrusted input, который течёт прямо в промпт:

- **Prompt injection**: `FILE_REVIEW_SYSTEM_PROMPT` явно инструктирует модель не выполнять команды, встреченные внутри diff'а/описания PR. Дополнительно `scan_for_prompt_injection()` (`fetch_diff`) детектирует известные паттерны ("ignore all previous instructions", "system prompt", "you are now" и т.п.) по заголовку, описанию и патчам каждого файла — при срабатывании `human_confirm` добавляет явный `security_warning` в HITL-запрос, чтобы подозрительный PR не был одобрен вслепую.
- **Утечка секретов**: `redact_secrets()` вырезает похожие на секреты подстроки (OpenAI/GitHub/Stripe/AWS-паттерны) из финального текста комментария в `aggregate_review`, до того как он попадёт человеку на подтверждение или в публичный PR — даже когда ревью корректно указывает на хардкод секрета, сам секрет в комментарий не попадает.

### Кэширование

`backend/graph/cache.py` — точный (не семантический/fuzzy) on-disk кэш в `.cache/` (в `.gitignore`). Осознанно не similarity-based: два похожих на 95% диффа всё равно могут отличаться той самой строкой, где баг, поэтому подмена ревью по "похожести" рискует дать уверенно неверный ответ. Кэшируются два реально повторяющихся вызова:

- **Embeddings** (`backend/rag/embeddings.py`) — детерминированная функция от (модель, текст), кэш безусловный. Основной эффект: `retrieve_style_context` эмбеддит один и тот же фиксированный query на каждый прогон ревью для данного репо.
- **`review_file()` результат** — только на уровне продакшн-узла `analyze_file` (не в самой функции `review_file`, её eval-харнессы вызывают напрямую и всегда получают свежий вызов модели — кэш иначе замаскировал бы run-to-run variance, задокументированную в EVALS.md). Ключ включает hash текущего системного промпта — правка промпта автоматически инвалидирует старые записи.

Проверено вживую: повторный прогон одного и того же PR — 7 вызовов OpenAI на холодном кэше → 1 вызов (только intake-классификация) на тёплом.

## Статус

Проект в активной разработке. Архитектурная документация (ARCHITECTURE.md) появится по мере реализации соответствующих этапов — см. PLAN.md, раздел 8.
