# OSS Copilot

AI-агент для code review merge request'ов на GitHub и поиска open-source репозитория, в который стоит стать контрибьютором.

**Живое демо:** [oss-copilot-dmitriy-solo.vercel.app](https://oss-copilot-dmitriy-solo.vercel.app) (frontend, Vercel) → [osscopilot-production.up.railway.app](https://osscopilot-production.up.railway.app) (backend, Railway) → Qdrant (Railway, приватная сеть).

**Как пользоваться** (фичи, примеры, мультимодальность, свой style-guide) — [TUTORIAL.md](TUTORIAL.md).
Подробный план реализации и обоснования технических решений — в [PLAN.md](PLAN.md).
Архитектурная диаграмма, путь одного запроса от пользователя до ответа, независимость компонентов и trade-off'ы — в [ARCHITECTURE.md](ARCHITECTURE.md).
Статус работы по этапам — в [PROGRESS.md](PROGRESS.md).
Презентация защиты (15 слайдов) — [presentation/oss-copilot-slides.pdf](presentation/oss-copilot-slides.pdf) (исходник: [presentation/slides.html](presentation/slides.html)).

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

`docker-compose up` поднимает все три сервиса: Qdrant (`:6333`), backend (`:8000`), frontend (`:3000`) — открыть `http://localhost:3000` и пользоваться веб-интерфейсом. Проверить граф и без UI, внутри уже собранного контейнера:

```bash
docker compose exec backend python -m backend.graph.run_agent "Review the pull request https://github.com/owner/repo/pull/123"
```

Оба образа собираются из корня репозитория (не из `backend/`/`frontend/`) — чтобы `backend.*` импорты внутри контейнера резолвились так же, как при локальном запуске с `PYTHONPATH=.`. Внутри compose-сети backend обращается к Qdrant по имени сервиса (`QDRANT_URL=http://qdrant:6333`, переопределяется поверх `.env`).

### Веб-интерфейс (Next.js)

`frontend/` — UI на Next.js 16 (App Router, без стейт-менеджеров, без CSS-фреймворка — своя тёмная тема на CSS-переменных, JetBrains Mono/IBM Plex Sans+Mono, та же палитра, что в презентации защиты): лендинг с двумя карточками режимов (PR Review/Repo Match, teal/violet — та же палитра, что и у интерраптов ниже), блоком "как это работает" (3 шага) и опциональной полосой с реальными eval-цифрами (accuracy/F1/recall/judge из EVALS.md, ссылка на файл) над формой запроса — полоса скрыта по умолчанию, включается флагом `NEXT_PUBLIC_SHOW_EVAL_STATS=true` (билд-тайм переменная, числа статичные, не живой вызов), одно текстовое поле для свободного запроса ("review this PR" или "I know Python, want to contribute to a CLI tool"), переключатель языка ответа (RU/EN, сохраняется в `localStorage`, передаётся один раз при старте запроса), кнопка "?" с онбординг-модалкой (кратко — что агент умеет, оба режима, мультимодальность, автоматическая безопасность — на RU/EN, закрывается по Escape/клику на фон), карточка human-in-the-loop с быстрыми кнопками под тип прерывания (Approve/Approve & merge/Reject для ревью, номера кандидатов + Skip для подбора репозитория, Skip для уточняющего вопроса) плюс свободный текстовый ответ как запасной путь, кнопка "New request". Поверх `backend/app/main.py`, который оборачивает `review_app` (LangGraph) в HTTP:

- `POST /api/agent/start {"message": str}` — стартует граф, возвращает `{status: "interrupt", thread_id, payload}` или `{status: "done", summary}`
- `POST /api/agent/resume {"thread_id": str, "answer": str}` — резюмирует через `Command(resume=answer)`

CORS настроен на `FRONTEND_ORIGIN` (по умолчанию `http://localhost:3000`). Локальный запуск без Docker:

```bash
# backend (из корня репо)
PYTHONPATH=. uvicorn backend.app.main:app --reload --port 8000

# frontend
cd frontend && cp .env.local.example .env.local && npm install && npm run dev
```

Требует Node 20.9+ (Next.js 16 больше не поддерживает Node 18). Проверено вживую настоящим браузером через Playwright: полный сценарий (submit → interrupt → reject → результат → New request) отработал на реальном PR через задеплоенный в Docker стек, без единой правки логики после первого честного прогона (нашёл и починил два реальных бага по пути — см. PROGRESS.md).

### MCP-сервер

`backend/mcp_server/server.py` — собственный MCP-сервер с GitHub-инструментами:

- `get_pr_diff(owner, repo, pr_number)` — diff и метаданные pull request'а
- `get_pr_files(owner, repo, pr_number, limit)` — patch по каждому файлу PR (для поочерёдного ревью)
- `post_pr_comment(owner, repo, pr_number, body)` — **write**-инструмент, публикует комментарий; граф вызывает его только после подтверждения человеком
- `merge_pull_request(owner, repo, pr_number)` — **write**-инструмент, мержит PR; граф вызывает его только после подтверждения человеком (`merge`), и только вслед за публикацией комментария. Если GitHub отказывает в мерже (конфликты, обязательные ревью/чеки не пройдены) — это не ошибка, а обычный результат: `merged: false` с объяснением от GitHub, комментарий при этом уже опубликован
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

**Свой PDF/DOCX style-guide** (`backend/rag/document_ingest.py`) — команда часто держит внутренние стандарты кодирования отдельным документом (PDF/DOCX), а не в `CONTRIBUTING.md` целевого репозитория. Загружается в ту же коллекцию `repo_docs`, тем же `retrieve_style_context` — без единой правки в графе или ретривале:

```bash
PYTHONPATH=. python -m backend.rag.document_ingest <owner> <repo> path/to/style-guide.pdf   # или .docx
```

### Граф (LangGraph): ветвления, циклы, human-in-the-loop

`backend/graph/graph.py` — один `StateGraph` с реальной условной логикой:

```
intake --(review | repo_match | unclear)-->

review:      fetch_diff --(есть скриншоты в описании PR?)--> analyze_screenshots ↘
                                                                                    retrieve_style_context
             fetch_diff ------------------------------------------------------------------------------↗
             retrieve_style_context -> [analyze_file loop по файлам] -> aggregate_review
             -> human_confirm --(approve|merge|reject)--> post_comment [--(merge)--> merge_pr] | discard

repo_match:  [clarify_repo_match loop: до 2 уточняющих вопросов] -> search_repos
             -> [score_repo loop по кандидатам] -> present_candidates
             -> human_select --(выбор|skip)--> fetch_good_first_issues | конец
```

- **Ветвление**: `intake` классифицирует свободный текст (structured output, gpt-4o-mini) и определяет, какая ветка выполняется; внутри review-ветки — есть ли изображения в описании PR.
- **Циклы**: `analyze_file` обходит файлы PR по одному (до 10), `score_repo` считает fit-score для каждого репозитория-кандидата.
- **Human-in-the-loop**: `human_confirm` и `human_select` останавливают граф через `langgraph.types.interrupt()` и ждут реального ответа человека, прежде чем публиковать комментарий в GitHub или переходить к issue выбранного репозитория. Ответ на `human_confirm` строго парсится (`approve`/`merge`/`reject` и явные синонимы) — нераспознанный текст не трактуется молча как `reject`, а переспрашивает через новый `interrupt()` с пояснением, что не понято.
- **Уточняющие вопросы (`clarify_repo_match`)**: перед поиском репозиториев граф решает (structured output, gpt-4o-mini), достаточно ли сигнала в запросе для хорошего поиска — если нет, задаёт один короткий уточняющий вопрос через `interrupt()` (предпочитаемый язык, размер проекта, тема) и зацикливается сам на себя, пока не наберёт достаточно контекста или не исчерпает лимит (`MAX_CLARIFY_TURNS = 2`, ограниченный цикл — как и остальные циклы в графе). Ответ `skip` в любой момент завершает уточнение немедленно и идёт в поиск с тем, что уже есть.
- **Язык ответа**: `language` (`ru`/`en`) передаётся один раз в начале (`AgentState["language"]`) и используется во всех узлах графа — как в детерминированных строках (инструкции, статусы), так и в системных промптах LLM-вызовов (ревью файлов, уточняющие вопросы). Данные, пришедшие напрямую из GitHub API (имена репозиториев, описания, файлы), не переводятся — переводится только собственный текст агента.
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

### CI/CD

`.github/workflows/ci.yml` — на каждый PR и push в `main`: job `smoke-test` (импорт ключевых модулей) → job `evals` (полный прогон `backend.evals.run_evals` на golden dataset, результат — build artifact `eval-results`). Нужен только секрет `OPENAI_API_KEY` (репозиторий не трогает GitHub API или Qdrant для evals — датасет полностью синтетический). Также доступен ручной запуск через `workflow_dispatch`.

### Guardrails

`backend/graph/guardrails.py` — PR-диффы и описания приходят от произвольных внешних контрибьюторов, это untrusted input, который течёт прямо в промпт:

- **Prompt injection**: `FILE_REVIEW_SYSTEM_PROMPT` явно инструктирует модель не выполнять команды, встреченные внутри diff'а/описания PR. Дополнительно `scan_for_prompt_injection()` (`fetch_diff`) детектирует известные паттерны ("ignore all previous instructions", "system prompt", "you are now" и т.п.) по заголовку, описанию и патчам каждого файла — при срабатывании `human_confirm` добавляет явный `security_warning` в HITL-запрос, чтобы подозрительный PR не был одобрен вслепую.
- **Утечка секретов**: `redact_secrets()` вырезает похожие на секреты подстроки (OpenAI/GitHub/Stripe/AWS-паттерны) из финального текста комментария в `aggregate_review`, до того как он попадёт человеку на подтверждение или в публичный PR — даже когда ревью корректно указывает на хардкод секрета, сам секрет в комментарий не попадает.

### Кэширование

`backend/graph/cache.py` — точный (не семантический/fuzzy) on-disk кэш в `.cache/` (в `.gitignore`). Осознанно не similarity-based: два похожих на 95% диффа всё равно могут отличаться той самой строкой, где баг, поэтому подмена ревью по "похожести" рискует дать уверенно неверный ответ. Кэшируются два реально повторяющихся вызова:

- **Embeddings** (`backend/rag/embeddings.py`) — детерминированная функция от (модель, текст), кэш безусловный. Основной эффект: `retrieve_style_context` эмбеддит один и тот же фиксированный query на каждый прогон ревью для данного репо.
- **`review_file()` результат** — только на уровне продакшн-узла `analyze_file` (не в самой функции `review_file`, её eval-харнессы вызывают напрямую и всегда получают свежий вызов модели — кэш иначе замаскировал бы run-to-run variance, задокументированную в EVALS.md). Ключ включает hash текущего системного промпта — правка промпта автоматически инвалидирует старые записи.

Проверено вживую: повторный прогон одного и того же PR — 7 вызовов OpenAI на холодном кэше → 1 вызов (только intake-классификация) на тёплом.

### Fallback между моделями

`backend/graph/nodes_review.py` (`_review_with_fallback`) — если primary-модель (gpt-4o-mini) не отвечает за `PRIMARY_TIMEOUT_S=20s` или падает с retryable-ошибкой (`RateLimitError`, `APITimeoutError`, `APIConnectionError`, `InternalServerError`), граф переключается на gpt-4o для этого файла. Осознанно НЕ ловим `AuthenticationError`/`BadRequestError`/`NotFoundError` — это признак реальной проблемы конфигурации (обе модели используют один и тот же ключ), которую fallback не решит, а только скроет.

Проверено вживую: принудительно занизил таймаут primary до 0.001с (реальный timeout против живого API), граф поймал `OpenAITimeoutError` и успешно переключился на gpt-4o, вернув валидный комментарий.

### Деплой

- **Frontend** — Vercel, проект `oss-copilot`: [oss-copilot-dmitriy-solo.vercel.app](https://oss-copilot-dmitriy-solo.vercel.app). `NEXT_PUBLIC_API_URL` указывает на backend; `NEXT_PUBLIC_SHOW_EVAL_STATS` — опциональный фича-флаг (по умолчанию выключен) для полосы eval-цифр на лендинге. Оба — переменные проекта Vercel (`vercel env add ... production`), не одноразовые build-аргументы — переживают будущие деплои.
- **Backend** — Railway, сервис `oss_copilot`: [osscopilot-production.up.railway.app](https://osscopilot-production.up.railway.app) (health: `/health`). Собирается по `backend/Dockerfile` (build context — корень репо), слушает `$PORT` (Railway назначает динамически, не 8000).
- **Qdrant** — Railway, сервис `qdrant`, образ `qdrant/qdrant:latest`, persistent volume на `/qdrant/storage`, доступен backend'у по приватной сети (`QDRANT_URL=http://qdrant.railway.internal:6333`), публично не открыт.

CORS на backend настроен через `FRONTEND_ORIGIN` = актуальный Vercel-домен.

Дошли до рабочего деплоя не с первой попытки — реальные проблемы и их починки задокументированы в PROGRESS.md (в т.ч. Railway CLI требует разные токены/права под разные операции, приложение должно слушать `$PORT`, Qdrant-сервис существовал в проекте, но ни разу не был задеплоен, Vercel по умолчанию закрывает деплой SSO-аутентификацией).

## Статус

Проект в активной разработке. Архитектурная документация (ARCHITECTURE.md) появится по мере реализации соответствующих этапов — см. PLAN.md, раздел 8.
