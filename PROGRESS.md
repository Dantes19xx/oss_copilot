# PROGRESS.md — Чекпоинт прогресса

Формат: после каждого завершённого шага из PLAN.md (раздел 8) добавляется запись.
При старте новой сессии — сначала читать этот файл, потом PLAN.md, только затем код.

---

## 2026-09-07

- [x] Прочитано техническое_задание.md
- [x] Составлен и записан план в PLAN.md (архитектура, обязательные/рекомендуемые модули, что нужно для интеграций, roadmap, дизайн golden dataset и A/B теста)
- [x] Этап 1 (каркас проекта): `.gitignore`, `.env.example`, структура `backend/{app,graph,mcp_server,rag,evals}`, `frontend/` (пусто), `docker-compose.yml` (Qdrant + backend), `backend/Dockerfile`, минимальный FastAPI-app (`backend/app/main.py`, `/health`), `README.md`
- [x] Репозиторий связан с GitHub: `https://github.com/Dantes19xx/oss_copilot` (существующий репо, история склеена через `git reset origin/main`, ничего не потеряно). Локальный `.env` с ключами не коммитится (проверено `git check-ignore`).
- [x] Первый коммит запушен в `main` (`34612f4`), upstream-tracking настроен.

**Важно (для следующей сессии):** авторизация `git push` через `gh auth git-credential` для этого репо не работает (403 у fine-grained PAT gh CLI). Рабочий способ — Basic auth напрямую с `GITHUB_PERSONAL_ACCESS_TOKEN` из `.env`:
```
set -a; source .env; set +a
git -c credential.helper= push "https://x-access-token:${GITHUB_PERSONAL_ACCESS_TOKEN}@github.com/Dantes19xx/oss_copilot.git" main:main
git fetch origin   # чтобы синхронизировать локальный tracking ref origin/main
```

## 2026-09-08

- [x] Этап 2 (MCP-сервер): `backend/mcp_server/github_client.py` (тонкая обёртка над GitHub REST API) + `backend/mcp_server/server.py` с тремя read-only tool'ами:
  - `get_pr_diff(owner, repo, pr_number)` — diff + метаданные PR
  - `search_github_repos(query, limit)` — поиск репозиториев-кандидатов
  - `get_repo_health(owner, repo)` — CONTRIBUTING.md, good-first-issues, активность, лицензия
  Все три протестированы вживую против реального GitHub API (flask, requests, поиск по topic) и через полный MCP-протокол (`list_tools`/`call_tool`) — работают.

**Важно (для следующей сессии):** установленный пакет `mcp` — версии 2.x, там `FastMCP` переименован в `MCPServer` (`from mcp.server.mcpserver import MCPServer`), API идентичен по духу (`@mcp.tool()`, `.run()`, `.list_tools()`, `.call_tool()`). Если где-то в коде/примерах видите `from mcp.server.fastmcp import FastMCP` — это устаревший (mcp 1.x) синтаксис, не работает с установленной версией.

Локальный venv для бэкенда: `.venv/` в корне проекта (в `.gitignore`, не коммитится). Установка: `pip install -r backend/requirements.txt`. Тестовые скрипты запускать с `PYTHONPATH=.` из корня репозитория (иначе `ModuleNotFoundError: No module named 'backend'`).

## 2026-09-08 (продолжение)

- [x] Этап 3 (LangGraph happy path): `backend/graph/` — `state.py` (ReviewState), `mcp_client.py` (мост LangGraph → собственный MCP-сервер через настоящий MCP-протокол, `mcp.Client(mcp_server_instance)` in-process), `nodes.py` (`fetch_diff` → `analyze_diff` (gpt-4o-mini, structured output через pydantic `ReviewOutput`) → `aggregate_review`), `graph.py` (линейный `StateGraph`, без ветвлений/циклов — это будет в этапе 5), `run_review.py` (ручной smoke-test CLI).
- Прогнан end-to-end на реальном PR (`pallets/flask#5918`): MCP-сервер отдал diff, gpt-4o-mini нашёл реальное замечание (нет обработки исключений в новой view-функции). Полный пайплайн подтверждён живыми вызовами, не моками.

**Важно (для следующей сессии):**
- В `mcp.Client(...).call_tool(...)`: `structured_content` пустой (`None`) для tool'ов с сырой аннотацией `-> dict` (нет JSON-схемы) — у `search_github_repos` (`-> list[dict]`) он есть. `backend/graph/mcp_client.py` уже содержит fallback: парсит JSON из первого текстового content-блока, если `structured_content is None`. Учитывать это при добавлении новых tool'ов.
- OpenAI-ключ в `.env` один раз был невалиден (401 на `/v1/models`) — пользователь перевыпустил, сейчас рабочий. Если снова 401 — сначала проверить ключ напрямую через `curl .../v1/models`, а не считать баг в коде.
- Тестовый запуск: `PYTHONPATH=. python -m backend.graph.run_review <owner> <repo> <pr_number>` (нужен активный `.venv`, см. этап 2).

## 2026-09-08 (этап 4)

- [x] Этап 4 (RAG-пайплайн): `backend/rag/` — `chunking.py` (markdown по заголовкам + fallback на фикс. окна 500 токенов/overlap 50 через `tiktoken`), `embeddings.py` (`text-embedding-3-small`), `vector_store.py` (Qdrant, одна коллекция `repo_docs`, фильтр по `repo` в payload, детерминированные point-id через `uuid5`), `ingest.py` (CLI: `PYTHONPATH=. python -m backend.rag.ingest <owner> <repo>`, читает README/CONTRIBUTING.md через новый `GitHubClient.get_file_content`), `retrieve.py`.
- Граф дополнен узлом `retrieve_style_context` (между `fetch_diff` и `analyze_diff`): подтягивает до 3 релевантных чанков и передаёт их в промпт `analyze_diff` как "Project conventions". Если для репо ничего не проиндексировано — узел возвращает пустой список, ревью идёт без грaундинга (не падает).
- Проверено вживую: `pallets/flask` проиндексирован (6 чанков из README, CONTRIBUTING.md на верхнем уровне нет), retrieval вернул релевантный топ-результат (score 0.629, чанк про Contributing) для запроса "how to install and contribute". Полный граф прогнан на flask (с контекстом) и `octocat/Hello-World` (без индексации, fallback-путь) — оба раза без ошибок.
- Qdrant поднят через `docker-compose up -d qdrant` (образ `qdrant/qdrant:latest`, порт 6333, здоров).

**Важно (для следующей сессии):**
- Требуется запущенный Qdrant (`docker-compose up -d qdrant`) и валидный `OPENAI_API_KEY` для embeddings — без этого `retrieve_style_context` упадёт с ошибкой соединения/401, а не тихо пропустится.
- Reranker (опциональный пункт ТЗ 2.2) пока не реализован — сознательно отложен, не блокирует обязательный чек-лист.
- `requirements.txt` дополнен: `tiktoken`, `openai` (использовались и раньше транзитивно через `langchain-openai`/`mcp`, теперь используются напрямую и указаны явно).

## 2026-09-08 (этап 5)

- [x] Этап 5 (полный граф — ветвления, циклы, human-in-the-loop): реструктурировал `backend/graph/` в модули:
  - `schemas.py` — `IntakeOutput`, `FileReviewOutput` (pydantic, structured output)
  - `state.py` — единый `AgentState` на обе ветки
  - `nodes_intake.py` — `intake` классифицирует свободный текст (gpt-4o-mini, structured output) в `review` (owner/repo/pr_number, парсит PR-ссылку) / `repo_match` (строит GitHub search query из навыков/интересов) / `unclear`
  - `nodes_review.py` — `fetch_diff` (теперь также тянет `get_pr_files`) → `retrieve_style_context` → **цикл** `analyze_file` (по файлам PR, до 10, ревью каждого файла отдельным вызовом LLM) → `aggregate_review` → **HITL** `human_confirm` (`langgraph.types.interrupt()`) → `post_comment` (реальный вызов `post_pr_comment`) | `discard`
  - `nodes_repo_match.py` — `search_repos` → **цикл** `score_repo` (health-метрики + fit-score по каждому кандидату) → `present_candidates` → **HITL** `human_select` → `fetch_good_first_issues` | конец
  - `graph.py` — один `StateGraph(AgentState)`, `compile(checkpointer=InMemorySaver())` (checkpointer обязателен для `interrupt`/`Command(resume=...)`)
  - `run_agent.py` — интерактивный CLI: `ainvoke` → если в результате есть `"__interrupt__"` → печатает payload, читает `input()`, резюмирует через `Command(resume=answer)`, повторяет до финального ответа. Заменил старые `nodes.py`/`run_review.py` (удалены).
  - Добавлены MCP-инструменты: `get_pr_files`, `post_pr_comment` (write), `get_good_first_issues` (+ в `github_client.py`: `get_pull_request_files`, `create_issue_comment`, `search_good_first_issues`, новый `_post` helper).
- **Проверено вживую end-to-end, оба ветвления:**
  - `unclear` — свободный текст без PR/интересов → корректное сообщение, без ошибок.
  - `review` (`pallets/flask#5918`, реальный PR): intake распарсил URL, цикл `analyze_file` прошёл 5 файлов (5 отдельных LLM-вызовов), `human_confirm` прервал граф и дождался реального ввода в терминале, `reject` → `discard` сработал корректно.
  - `post_pr_comment` (write) протестирован на **собственном** тестовом issue в `Dantes19xx/oss_copilot` (issue #1, создан и закрыт после теста) — сознательно не стал постить в чужой `pallets/flask`, чтобы не спамить реальных мейнтейнеров.
  - `repo_match` ("I know Python and want to contribute to a CLI tool"): intake построил query `language:Python topic:CLI stars:>100`, `score_repo` прошёл цикл по 5 кандидатам, `human_select` прервал граф, резюмирован вводом "1" → `fetch_good_first_issues` вернул реальный issue из `yt-dlp/yt-dlp`.

**Важно (для следующей сессии):**
- **Стало известное "грабли":** если в текущем bash-сеансе раньше делали `set -a; source .env; set +a`, переменные остаются экспортированными в shell. `load_dotenv()` по умолчанию НЕ перезаписывает уже установленные os.environ переменные — поэтому Python-процесс может использовать устаревший токен из shell, а не свежий из `.env`, даже после правки файла. Исправлено на уровне кода: все `load_dotenv()` в проекте теперь вызываются с `override=True` (`mcp_server/server.py`, `graph/run_agent.py`, `rag/ingest.py`) — `.env` всегда побеждает. При ручном тестировании в новом bash-сеансе это не проявляется.
- `post_pr_comment` требует у `GITHUB_PERSONAL_ACCESS_TOKEN` право **Issues: Read and write** (отдельно от Contents) — пользователь это добавил. Изменение права на GitHub может применяться не мгновенно (наблюдалась задержка ~1-2 минуты).
- `InMemorySaver` — checkpointer только в памяти процесса; для реального бэкенда (FastAPI, несколько запросов/перезапуски) понадобится персистентный checkpointer (Postgres/SQLite) — пока не нужно, отметить на этапе деплоя (этап 15 PLAN.md).
- `analyze_file` ограничен `MAX_FILES=10` файлов на PR — осознанный бюджет по стоимости/времени, не баг.

**Следующий шаг (этап 6 из PLAN.md раздел 8):** мультимодальность — vision-анализ скриншотов/диаграмм, приложенных к PR/issue (закрывает обязательное требование ТЗ 2.2).

**Открытые вопросы (не блокируют, но влияют на детали):**
- Auth в MVP: пока допущение — без auth, single-user PAT.
- Backend hosting: пока допущение — Railway.
- Источники для golden dataset: пока не выбраны, нужно подобрать 30 PR-примеров.
