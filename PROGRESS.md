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

## 2026-09-08 (этап 10)

- [x] Этап 10 (A/B эксперимент): gpt-4o-mini vs gpt-4o на том же golden dataset. Расширил `review_file()` (`backend/graph/nodes_review.py`) опциональными `model` и `return_usage` параметрами (default сохраняет прежнее поведение — продакшн-узел `analyze_file` их не передаёт) — при `return_usage=True` возвращает `(parsed, {"latency_s", "input_tokens", "output_tokens"})` через `with_structured_output(..., include_raw=True)`. `backend/evals/run_ab.py` прогоняет обе модели по 30 примерам, тем же judge'ом, считает стоимость по официальным ценам (`PRICING_PER_1M`, зашито в код — актуализировать перед защитой, если цены OpenAI изменятся).
- **Итоговые числа (n=30 на обе модели):** gpt-4o-mini: accuracy=0.87, precision=0.85, **recall=1.00**, judge=**4.13**/5, latency=1.31s, cost=$0.0022 (30 вызовов). gpt-4o: accuracy=**0.90**, precision=**0.91**, recall=0.95 (пропустил `bug-05` — сдвиг переменной цикла, который gpt-4o-mini поймал), judge=4.07/5, latency=2.18s, cost=$0.0518 (**в ~23 раза дороже**).
- **Решение (задокументировано в EVALS.md §7): оставляем gpt-4o-mini в проде.** gpt-4o чуть точнее по accuracy/precision, но НЕ лучше по judge-score (качество рассуждений) и хуже по recall — а для code-review пропустить реальный баг дороже, чем дать один лишний false positive. Разрыв в accuracy (0.87 vs 0.90) не перекрывает 23-кратную разницу в цене при n=30.
- Честно указал в EVALS.md ограничение: n=30 мало для статистически значимого вывода по accuracy/precision — это первый сигнал, не доказательство; обе модели судил один и тот же gpt-4o-mini judge (self-grading bias влияет на обе руки одинаково, не отменяется).

**Важно (для следующей сессии):**
- `PRICING_PER_1M` в `run_ab.py` захардкожен на момент написания (см. комментарий в коде "re-check before citing these numbers"). Если публичные цены OpenAI изменились к моменту защиты — обновить перед пересчётом для слайдов.
- `backend/evals/ab_results.json` — в `.gitignore`, регенерируется прогоном, не хранится в репо (как и `results.json`).

## 2026-09-10 (этап 11)

- [x] Этап 11 (гиперпараметры): `backend/evals/run_temperature.py` — две отдельные части на golden dataset: (A) качество (accuracy + judge score) при temperature ∈ {0.0, 0.2, 0.7}; (B) устойчивость/детерминированность — 6 примеров x 3 повтора на каждую температуру, доля стабильного вердикта + разброс количества комментариев. Разделил намеренно: одна метрика качества могла бы выглядеть одинаково на двух температурах, пока одна из них тихо гораздо менее воспроизводима.
- **Результаты:** accuracy идентична на всех трёх (0.90); judge score 4.20 на 0.0 и 0.2, падает до 4.00 на 0.7; стабильность вердикта 1.00 везде, но на 0.7 появляется ненулевой разброс числа комментариев (stdev=0.079) при нулевом разбросе на 0.0/0.2.
- **Реальное решение по данным (не постфактум-обоснование уже стоявшего значения):** сменил продакшн-дефолт `FILE_REVIEW_TEMPERATURE` в `backend/graph/nodes_review.py` с 0.2 на **0.0** — та же метрика качества, лучше/равная воспроизводимость, детерминированность бесплатна при этом датасете.
- `max_tokens=500` обоснован не отдельным экспериментом, а реальной статистикой уже собранных 60 вызовов (этапы 9+10): output_tokens 4-125, mean 53.8 — 500 даёт >4x запас, это предохранитель, а не реальное ограничение.
- `top_p` осознанно НЕ тюнили — задокументировал причину (рекомендация OpenAI менять temperature ИЛИ top_p, не оба сразу, иначе эксперимент запутан).
- Область применения эксперимента честно ограничена: только `review_file()`. `intake()` уже использует temperature=0 (согласуется с находкой, отдельно не тестировал), `vision.analyze_image()` остался на 0.2 — не проверял отдельно, явно помечено как незакрытый пробел, а не скрытая непоследовательность.
- Дополнил `EVALS.md` разделом 8 с таблицей, обоснованием и honest caveats.

**Важно (для следующей сессии):**
- **Все обязательные модули ТЗ (раздел 2) теперь реализованы**: 2.1 (LangGraph+ветвления/циклы/HITL, MCP-сервер, Skill) — этапы 2/3/5/7; 2.2 (RAG, документы, мультимодальность) — этапы 4/6; 2.3 (LangSmith, evals, A/B) — этапы 8/9/10; 2.4 (обоснованный выбор LLM и гиперпараметров) — этапы 10/11. Дальше по PLAN.md раздел 8 идут **рекомендуемые** модули (guardrails, кэш, fallback, docker, CI/CD, деплой, auth и т.д.) — не блокируют допуск к защите, но повышают оценку.
- `backend/evals/temperature_results.json` — в `.gitignore`, регенерируется, не хранится в репо.

## 2026-09-10 (этап 12)

- [x] Этап 12 (Guardrails): `backend/graph/guardrails.py` — `scan_for_prompt_injection(text)` (regex-детектор известных паттернов: "ignore all previous instructions", "system prompt", "you are now", DAN и т.п.) и `redact_secrets(text)` (вырезает похожие на секреты подстроки: OpenAI `sk-`/`sk-proj-`, Stripe `sk_live_`, GitHub `gh*_`/`github_pat_`, AWS `AKIA...`, общий 40-символьный base64-паттерн — заменяет на `[REDACTED]`).
- Двухслойная защита от prompt injection: (1) `FILE_REVIEW_SYSTEM_PROMPT` дополнен явной инструкцией не выполнять команды из diff'а/описания PR — это untrusted content от внешнего контрибьютора; (2) `fetch_diff` сканирует title+body+patch каждого файла через `scan_for_prompt_injection`, результат кладёт в `state["injection_warnings"]`; `human_confirm` при непустом списке добавляет явный `security_warning` в HITL payload — подозрительный PR не может быть одобрен вслепую.
- Редакция секретов: `aggregate_review` прогоняет финальный `summary` через `redact_secrets` до того, как он попадёт человеку на подтверждение или в публичный комментарий — даже когда ревью корректно указывает на хардкод секрета (см. sec-01..sec-06 в golden dataset), сам секрет в текст не попадает.
- **Проверено вживую через реальный код графа**, не переписанной копией: (1) регрессия на чистом реальном PR (`pallets/flask#5918`) — `security_warning` в payload отсутствует, как и должно быть; (2) собрал мини-граф из настоящих `aggregate_review`+`human_confirm` (те же функции, что в продакшене) и прогнал через сфабрикованный state с фейковым секретом и текстом-инъекцией — секрет корректно заменился на `[REDACTED]` в `draft_comment`, `security_warning` корректно появился в interrupt payload. Не тестировал на реальном чужом PR — не стал вносить вредоносный контент в чужой публичный репозиторий ради теста.
- Обновил `README.md`: добавил раздел "Guardrails" и "Evals, A/B, гиперпараметры"; заодно поправил баг из более раннего этапа — задвоенный заголовок "### Skill" в конце файла вместо "## Статус" (не связано с этим этапом, просто заметил и починил).

**Важно (для следующей сессии):**
- Детектор инъекций — эвристический regex, не претендует на полноту (задокументировано в docstring `guardrails.py`: "there's no regex that catches every phrasing"). Это defense-in-depth поверх системного промпта, не единственная линия защиты.
- `_SECRET_PATTERNS` включает общий паттерн "40 alnum-символов подряд" (типичная длина AWS secret key) — может при некоторой вероятности зацепить случайную длинную непонятную строку без реального секрета (ложное срабатывание безопаснее, чем пропуск).

## 2026-09-11 (этап 13)

- [x] Этап 13 (кэширование): `backend/graph/cache.py` — `FileCache`, точный (не semantic/fuzzy) on-disk кэш в `.cache/` (JSON, sha256-ключ по канонизированным частям). **Осознанное архитектурное решение задокументировано в docstring**: semantic/similarity-кэш не подходит для code review — два на 95% похожих диффа могут отличаться именно той строкой, где баг, значит similarity-based cache рискует вернуть уверенно неверный кэшированный ревью для другого diff'а. Exact-match по хешу реальных входов полностью убирает этот риск.
- Закэшировано два реально повторяющихся вызова:
  - `backend/rag/embeddings.py`: `embed_texts` теперь кэширует **по каждому тексту отдельно** внутри батча (не по всему батчу целиком), вызывая реальный API только для непопавших в кэш текстов. Разделил на `_embed_uncached` (единственная функция с `@traceable`, вызывается только на реальный промах — cache hit не создаёт лишний трейс) и публичный `embed_texts` (кэш-обёртка). Безусловно кэшируемо — embeddings детерминированы по (модель, текст), в отличие от review_file() тут нет риска замаскировать reproducibility findings.
  - `backend/graph/nodes_review.py`: кэш подключён **только в узле `analyze_file`** (продакшн-путь), НЕ в самой функции `review_file()` — её напрямую вызывают `run_evals.py`/`run_ab.py`/`run_temperature.py`, и они должны получать свежий вызов модели каждый раз, иначе кэш тихо замаскировал бы run-to-run variance, уже задокументированную как находка на этапах 9 и 11. Ключ кэша включает hash текущего `FILE_REVIEW_SYSTEM_PROMPT` — правка промпта в коде автоматически инвалидирует старые записи, не нужно чистить кэш вручную.
- **Проверено вживую, с измерением, а не предположением**: прогнал один и тот же реальный PR (`pallets/flask#5918`) дважды подряд. Холодный кэш — 7 вызовов OpenAI (1 intake + 1 embedding + 5 file reviews). Тёплый кэш — **1 вызов** (только intake, который не кэшируется намеренно — классификация свободного текста пользователя не повторяется between одинаковыми PR-ревью). Итоговый результат ревью идентичен по содержанию. Убедился отдельным импортом, что eval-харнессы (`run_evals`/`run_ab`/`run_temperature`) структурно изолированы от кэша (вызывают `review_file()` напрямую, не `analyze_file`).
- Обновил `README.md` разделом "Кэширование" с конкретными числами.

**Важно (для следующей сессии):**
- `.cache/` — локальный, не в git (аналогично `backend/evals/*.json`). У каждого разработчика/CI-раннера свой холодный кэш при первом запуске — это ожидаемо, не баг.
- Если нужно принудительно сбросить кэш ревью (например, после ощутимой правки логики вне текста промпта, которую version-hash не ловит) — просто удалить `.cache/review_file.json` или всю `.cache/`.
- `intake()` и `vision.analyze_image()` НЕ кэшируются — осознанно не стал: intake обрабатывает произвольный текст пользователя (низкая вероятность точного повтора), vision мог бы кэшироваться по URL картинки, но не сделал в рамках этого этапа (возможное будущее расширение, не входит в обязательный/рекомендуемый чек-лист сверх уже сделанного).

## 2026-09-11 (этап 14, продолжение)

- [x] Этап 14 (fallback между моделями): `backend/graph/nodes_review.py` — `_review_with_fallback()`. `review_file()` дополнен параметром `timeout` (передаётся в `ChatOpenAI(..., timeout=...)`). Primary — gpt-4o-mini с `PRIMARY_TIMEOUT_S=20.0`; при retryable-ошибке (`openai.RateLimitError`, `APITimeoutError`, `APIConnectionError`, `InternalServerError`) — переключение на gpt-4o без таймаута, с `logger.warning`.
- **Сознательно НЕ ловим** `AuthenticationError`/`BadRequestError`/`NotFoundError` — это реальная проблема конфигурации/запроса (обе модели на одном ключе), fallback её не решит, а тихо спрячет баг вместо того чтобы дать ему всплыть. Задокументировано прямо в коде рядом с исключаемым списком, не только в комментарии "на будущее".
- Fallback подключён в `analyze_file` вместо прямого вызова `review_file` — под тем же кэш-слоем этапа 13 (fallback-результат тоже кэшируется, ключ теперь включает оба имени модели: primary и fallback, для инвалидации при их смене).
- **Проверено вживую, реальным сетевым таймаутом, не мок-исключением**: вызвал `_review_with_fallback(..., primary_timeout=0.001)` напрямую — реальный запрос к API physически не может уложиться в 1мс, поймал `OpenAITimeoutError` (langchain_openai обёртка над `openai.APITimeoutError`, попадает в `_RETRYABLE_ERRORS`), увидел `logger.warning` о переключении, получил реальный валидный комментарий от gpt-4o. Обычный путь (реальный PR, primary без принудительной поломки) регрессии не показал.
- Обновил `README.md` разделом "Fallback между моделями".

**Важно (для следующей сессии):**
- `PRIMARY_TIMEOUT_S=20.0` — не экспериментально подобрано (в отличие от temperature на этапе 11), а разумное дефолтное значение; если понадобится точнее — можно откалибровать по реальным latency из `backend/evals/ab_results.json` (mean_latency_s для gpt-4o-mini там ~1.3s, так что 20s — щедрый запас, а не узкое место).
- Fallback работает только для `review_file()`/`analyze_file` (review-ветка). `intake()`, `vision.analyze_image()`, RAG-embeddings fallback не реализован — не входило в этот этап, честно не заявляю обратного.

## 2026-09-11 (этап 15)

- [x] Этап 15 (Docker/docker-compose): проверил (не поверил на слово) сборку с этапа 1 — **нашёл реальный баг**: `docker-compose.yml` собирал `backend` с build context `./backend`, из-за чего внутри образа `COPY . .` клал содержимое `backend/` прямо в `/app/`, а не в `/app/backend/`. Весь код проекта импортирует `from backend.xxx import ...` (рассчитан на запуск с `PYTHONPATH=.` из корня репо) — внутри старого образа это давало `ModuleNotFoundError: No module named 'backend'` при любой реальной попытке использовать граф/MCP/RAG, хотя `docker build` и `docker-compose up` при этом отрабатывали без единой ошибки (health-check не задевает эти импорты, поэтому баг был не виден на поверхности).
- **Исправил**: `docker-compose.yml` → `build: {context: ., dockerfile: backend/Dockerfile}` (контекст — корень репо); `backend/Dockerfile` → `COPY backend/ backend/` + `ENV PYTHONPATH=/app` + `CMD uvicorn backend.app.main:app` (вместо `app.main:app`); Python 3.11 → 3.12 (соответствует локальному venv). Добавил `.dockerignore` в корне (`.venv/`, `.git/`, `.cache/`, `.env`, `qdrant_storage/`, `node_modules/`, `frontend/`).
- **Второй реальный баг**: `QDRANT_URL` по умолчанию (`.env.example`/локальный `.env`) — `http://localhost:6333`, что внутри контейнера backend не достучится до контейнера qdrant (разные network namespace). Добавил в `docker-compose.yml` `environment: QDRANT_URL: http://qdrant:6333` — переопределяет `.env` только внутри compose-сети, обращение по имени сервиса.
- **Проверено вживую поэтапно**, не только "образ собрался": (1) `docker compose run --rm backend python -c "import backend.graph.graph; import backend.mcp_server.server; import backend.rag.embeddings"` — падало до фикса, прошло после; (2) `docker compose up -d` — оба контейнера Up; (3) `curl localhost:8000/health` — ok; (4) `docker compose exec backend python -c "httpx.get('http://qdrant:6333/healthz')"` — 200, подтверждает сетевую связность backend→qdrant по имени сервиса; (5) **полный прогон графа внутри контейнера** (`docker compose exec backend python -m backend.graph.run_agent "Review the pull request https://github.com/pallets/flask/pull/5918"`) — реальный GitHub+OpenAI вызов, корректный результат, идентичный локальному запуску.

**⚠️ Инцидент (для следующей сессии — не повторять):** `docker compose config` разворачивает `env_file: .env` и печатает **все значения переменных окружения в открытом виде** при рендере итогового конфига. Случайно вывел в терминал реальные `OPENAI_API_KEY`, `GITHUB_PERSONAL_ACCESS_TOKEN`, `LANGSMITH_API_KEY`, `RAILWAY_TOKEN`, `VERCEL_TOKEN`. Никуда не утекло (локальный вывод сессии), но пользователь предупреждён, рекомендовано перевыпустить все пять токенов. **Больше никогда не запускать `docker compose config`** (и вообще любую команду, которая явно резолвит/печатает `env_file`) — если нужно проверить итоговый конфиг, читать `docker-compose.yml` напрямую или использовать `docker compose config --no-env` / фильтровать вывод, но проще просто не запускать эту команду.

**Важно (для следующей сессии):**
- Образ по-прежнему запускает только health-check FastAPI (`backend/app/main.py`) — HTTP-обёртка над графом ещё не сделана, это отдельно на этапе 13 (фронтенд). Пока граф вызывается через CLI внутри контейнера, как и локально.
- Если добавлять новые top-level модули в `backend/`, помнить: `COPY backend/ backend/` в Dockerfile копирует всю папку целиком — новые подпапки подхватятся автоматически, ничего вручную добавлять не нужно.

**Следующий шаг (этап 16 из PLAN.md раздел 8):** CI/CD (GitHub Actions) с автозапуском evals на каждый PR — естественно вписывается в тему проекта (сам продукт про code review), хороший demo-эффект. Следующий по приоритету рекомендуемый модуль (PLAN.md раздел 3).

**Открытые вопросы (не блокируют, но влияют на детали):**
- Auth в MVP: пока допущение — без auth, single-user PAT.
- Backend hosting: пока допущение — Railway.
