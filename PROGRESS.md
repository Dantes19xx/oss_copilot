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

## 2026-09-08 (этап 6)

- [x] Этап 6 (мультимодальность): `backend/graph/vision.py` — `extract_image_urls()` (markdown `![]()`, `<img src>`, известные GitHub asset-хосты) + `analyze_image()` (vision через `gpt-4o-mini`, `HumanMessage` с `image_url` content block).
- Граф: `fetch_diff` теперь также извлекает `image_urls` из тела PR; новый узел `analyze_screenshots` (условная ветка `route_after_fetch_diff`: "vision" если есть картинки, иначе прямо в "context") анализирует до 3 изображений параллельно (`asyncio.gather`); результат попадает в `aggregate_review` как секция "Screenshot/attachment analysis" финального комментария.
- **Проверено вживую**: нашёл реальный смерженный PR с GIF в описании (`facebook/docusaurus#7036`, demo GIF в Test Plan) — граф прошёл vision-ветку, GIF был проанализирован и описание попало в финальный ревью. Убедился, что PR без изображений (`pallets/flask#5918`) по-прежнему идёт коротким путём "context" без секции screenshot-анализа — регрессии нет.
- Осмысленность (не "для галочки"): это ловит то, что текстовый diff не может — например, скриншот, не соответствующий описанию PR, или явный визуальный баг на демо-гифке.
- `requirements.txt`: добавлен `langchain-core` (использовался транзитивно через `langchain-openai`, теперь импортируется напрямую в `vision.py` для `HumanMessage`).

**Важно (для следующей сессии):**
- Vision-анализ на данный момент рассчитан на PR-описания (markdown/HTML картинки в `pr.body`). Диаграммы внутри самого README (RAG-документы) визуально не анализируются — там RAG работает с текстом. Если понадобится анализ диаграмм в документации — это отдельное расширение `backend/rag/ingest.py`, не блокирует текущий чек-лист (ТЗ требует "как минимум одну" мультимодальную возможность, она есть).
- `MAX_IMAGES` в `analyze_screenshots` — жёстко 3 (через `extract_image_urls(limit=3)`), осознанный бюджет по стоимости/латентности, не баг.

## 2026-09-08 (этап 7)

- [x] Этап 7 (свой Skill): `.claude/skills/code-review-checklist/SKILL.md` — тот же чек-лист (баги, security, тесты, breaking changes, project conventions), что зашит в `FILE_REVIEW_SYSTEM_PROMPT` (`backend/graph/nodes_review.py`), но упакован как переиспользуемый Claude Skill: frontmatter `name` + `description` с явными триггерами ("review this PR", "code review this diff", "check this MR"), тело с чек-листом по категориям + "что НЕ комментировать" + формат вывода + scope (применим к любому диффу, не только к этому репо).
- Структуру сверил с реально установленными skills на этой машине (`~/.claude` проекты `restaurant_search`, `notes/my_own_notes`) — минимальный frontmatter (только `name`+`description`, без `version`/`license`/`tags`) валиден, это подтверждённый паттерн, не догадка.
- Осознанное решение: **не дублировать текст между Skill и промптом графа** отдельным шаблонизатором/импортом — они намеренно держатся в ручной синхронизации как одна и та же формулировка стандарта в двух местах доставки (агент и интерактивная Claude Code сессия). Более сложная связка (например, граф читает `SKILL.md` как источник промпта) — возможное будущее улучшение, не обязательное для чек-листа ТЗ.

## 2026-09-08 (этап 8)

- [x] Этап 8 (LangSmith): подтвердил, что трейсинг работает "из коробки" для всех `langchain_openai.ChatOpenAI` вызовов (граф, vision, intake) — достаточно `.env` (`LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT=oss_copilot`), уже настроенных с этапа 1. Никакого доп. кода не понадобилось для chat-вызовов.
- **Нашёл слепую зону и закрыл её**: `langchain_openai.OpenAIEmbeddings`/сырой `openai` SDK НЕ трейсятся LangSmith автоматически — это не `Runnable`, а прямой вызов клиента (проверил исходник `OpenAIEmbeddings.aembed_documents` — там нет ни `@traceable`, ни callback-менеджера). Сначала попробовал переключить `backend/rag/embeddings.py` на `langchain_openai.OpenAIEmbeddings` — не помогло (трейс не появился). Откатил на сырой `openai.AsyncOpenAI` + обернул вызов декоратором `@traceable(run_type="embedding", name="text-embedding-3-small")` из пакета `langsmith` — трейс появился, проверено через `Client().list_runs(project_name="oss_copilot")`.
- **Проверено вживую через LangSmith API** (не только "должно работать"): прогнал review-сценарий и retrieval-вызов, затем запросом `langsmith.Client().list_runs(project_name="oss_copilot")` увидел реальные записи — по узлам графа (`chain`), по LLM (`llm | ChatOpenAI`), по embeddings (`embedding | text-embedding-3-small`), с корневым `LangGraph` run на каждый `ainvoke()`.
- **Полезная находка для защиты**: у каждого рана в `extra.metadata` автоматически проставлен `thread_id` (из `config.configurable.thread_id`, который передаёт `run_agent.py`) и `revision_id` (текущий git commit SHA, LangSmith сам подхватил git). Human-in-the-loop сценарий технически делится на 2 `ainvoke()`-вызова (до `interrupt()` и после `Command(resume=...)`) — это 2 отдельных root-трейса в LangSmith, но с одинаковым `thread_id`, так что фильтр по `metadata.thread_id` в дашборде склеивает их в один пользовательский сценарий для демонстрации.

**Важно (для следующей сессии):**
- Если добавлять новые прямые вызовы `openai`/другого не-LangChain SDK — не забывать `@traceable`, иначе будет тихая слепая зона в мониторинге (как было с embeddings).
- `list_runs()`/`get_run_url()` в установленной версии `langsmith` (0.12.2) помечены deprecated в пользу `client.runs.query()`/`client.runs.get_url()` — работают, но при следующей крупной правке кода вокруг LangSmith стоит свериться с актуальным API.
- Дашборд для защиты: `smith.langchain.com` → проект `oss_copilot`, там уже реальные трейсы со всех прогонов этой сессии (review, repo_match, vision, retrieval).

## 2026-09-08 (этап 9)

- [x] Этап 9 (golden dataset + evals): `backend/evals/golden_dataset.py` — 30 hand-crafted single-file diффов (6 bug, 6 security, 5 missing_tests, 5 breaking_change, 8 clean), каждый с `expected_has_issue`/`expected_note`. Рефакторинг: вынес `review_file()` из `analyze_file` в `backend/graph/nodes_review.py` — evals вызывают ту же функцию, что и продакшн-граф, а не копию промпта.
- `backend/evals/schemas.py` (`JudgeOutput`) + `backend/evals/run_evals.py` — прогоняет все 30 примеров через `review_file()`, считает 2 метрики: (1) detection accuracy + precision/recall/F1 (бинарно: есть ли комментарии, когда ожидается issue), (2) LLM-as-judge score 1-5 (gpt-4o-mini оценивает, совпадает ли суть комментария с `expected_note`, а не только факт наличия). Пишет `backend/evals/results.json` (в `.gitignore` — регенерируется, не коммитится статикой).
- **Прогнано вживую дважды.** Первый прогон вскрыл реальный баг в промпте judge'а: пустой список комментариев на "чистом" примере (правильный вердикт) получал judge=1/5, потому что рубрика неявно ожидала "похвалы" вместо признания правильной тишины — это утянуло `clean`-категорию до 2.25/5. Починил промпт judge'а (явно: пустой список на CLEAN = автоматически 5), перепрогнал — `clean` поднялась до 4.25/5, общий mean_judge_score вырос с 3.20 до 4.20 при тех же самых review-выводах. Оставил это как задокументированную находку в EVALS.md, а не тихо исправил и забыл.
- **Итоговые числа (n=30):** accuracy=0.87, precision=0.85, **recall=1.00** (реальную проблему не пропустил ни разу), f1=0.92, mean_judge_score=4.20/5. По категориям: bug/security/breaking_change/missing_tests — 100% accuracy; clean — только 0.50 (4 из 8 чистых диффов ложно помечены). `missing_tests` при 100% accuracy имеет самый низкий judge-score (3.40) — модель замечает "что-то не так", но часто указывает не на тот механизм. Полная разбивка и обсуждение — в `EVALS.md`.
- Написан `EVALS.md` (обязательный артефакт ТЗ раздел 4) — методология датасета, обе метрики с explicit "что они НЕ показывают", таблицы результатов, находки (включая баг judge'а и его починку), раздел 7 — заготовка под A/B (этап 10).

**Важно (для следующей сессии):**
- Датасет полностью синтетический (не из реальных PR) — осознанный выбор ради точной разметки, задокументирован trade-off в EVALS.md §2. Не путать с ранними допущениями плана про "30 PR-примеров" — решили в пользу точности разметки.
- `clean-08` в датасете намеренно неоднозначен (модель не видит тестовый файл в том же PR) — не баг, а зафиксированный предел file-by-file ревью (у `analyze_file` нет кросс-файлового контекста, кроме RAG style-context).
- Numbers наблюдается run-to-run variance (temperature=0.2 у ревьюера) — при пересчёте для презентации/слайдов не удивляться небольшим отклонениям от чисел в EVALS.md, перезапустить `run_evals.py` для актуальных.

**Следующий шаг (этап 10 из PLAN.md раздел 8):** A/B эксперимент — сравнение двух конфигураций (кандидаты: gpt-4o-mini vs gpt-4o, или ревью с RAG-контекстом vs без) на этом же golden dataset, с гипотезой и выводом. Закрывает обязательное требование ТЗ 2.3.

**Открытые вопросы (не блокируют, но влияют на детали):**
- Auth в MVP: пока допущение — без auth, single-user PAT.
- Backend hosting: пока допущение — Railway.
