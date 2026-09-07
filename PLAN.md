# PLAN.md — План реализации проекта

**Тема:** AI-агент для code review merge request'ов на GitHub + поиск open-source репозитория для контрибьютинга
**Дата составления плана:** 2026-09-07
**Модель:** gpt-4o-mini (OpenAI API), ключ у пользователя есть
**Статус:** план составлен, реализация ещё не начата (см. PROGRESS.md для актуального статуса на момент чтения)

---

## 0. Формулировка продукта

Один агент — две связанные функции (общая инфраструктура: RAG по код-стайлам, MCP-сервер вокруг GitHub API, один LangGraph):

1. **PR Reviewer** — принимает ссылку на PR/diff, анализирует изменения (код, стиль, потенциальные баги, security-паттерны), формирует ревью-комментарии, **требует подтверждения человека** перед публикацией в GitHub.
2. **Repo Matcher** — по описанию навыков/интересов пользователя ищет и ранжирует open-source репозитории, подходящие для контрибьютинга (активность, good-first-issues, health метрики, соответствие стеку), объясняет выбор через RAG по README/CONTRIBUTING.md.

Название рабочее: **OSS Copilot** (можно поменять).

### Целевой пользователь (для критерия "бизнес-ценность", 5%)
Разработчик, который (а) хочет получить качественное автоматическое ревью своего PR до того, как звать живого ревьюера, и (б) хочет начать контрибьютить в open source, но не знает, с какого репозитория начать и тонет в поиске "good first issue".

---

## 1. Архитектура — высокий уровень

```
User (веб-фронтенд)
   │
   ▼
FastAPI backend
   │
   ▼
LangGraph StateGraph  ──uses──►  MCP-сервер (свой) ──► GitHub REST/GraphQL API
   │        │                                            │
   │        ├─uses──► RAG (Qdrant/Chroma) ◄─embeddings───┘ (README, CONTRIBUTING, style-guides)
   │        ├─uses──► Vision-модель (мультимодальность: скриншоты/диаграммы в PR)
   │        └─uses──► Skill (code-review checklist, оформлен как SKILL.md)
   │
   ▼
LangSmith (трейсинг всех вызовов LLM)
```

### 1.1 Граф LangGraph (обязательное требование: ветвления, циклы, human-in-the-loop)

Узлы (черновая версия, уточнится в процессе):

1. `intake` — определить режим: review PR или найти репозиторий (**ветвление**).
2. **Ветка Review:**
   - `fetch_diff` (MCP tool) → `chunk_diff` → `analyze_file` (**цикл** по файлам diff'а)
   - `low_confidence?` — если модель не уверена → `fetch_related_context` (доп. файлы из репо) → назад в `analyze_file` (**цикл**)
   - `vision_check` — если в PR/issue есть скриншоты/диаграммы → анализ через vision-модель
   - `aggregate_review` → `human_confirm` (**human-in-the-loop**, прерывание графа, ждёт подтверждения/правки от пользователя)
   - `post_comment` (MCP tool, только после подтверждения) / `discard`
3. **Ветка Repo Matcher:**
   - `search_repos` (MCP tool) → `score_repo` (RAG по README/CONTRIBUTING + метрики health) → **цикл** по кандидатам
   - `present_candidates` → `human_select` (human-in-the-loop)
   - `fetch_good_first_issues` (MCP tool) → `draft_intro_comment` (опционально)

---

## 2. Обязательные модули из ТЗ и как они закрываются

| # | Требование | Реализация |
|---|---|---|
| 2.1 | Оркестрация (LangGraph) | Граф выше: ветвления (intake), циклы (analyze_file, score_repo), human-in-the-loop (human_confirm, human_select) |
| 2.1 | Свой MCP-сервер, 2-3+ tool'а | `get_pr_diff`, `post_pr_comment`, `search_github_repos`, `get_repo_health`, `get_good_first_issues` — сервер на Python (FastMCP/mcp SDK) поверх GitHub REST/GraphQL |
| 2.1 | Свой Skill | `SKILL.md` — "code-review-checklist": триггеры на "проверь PR", "code review", описание чеклиста (security, стиль, тесты, breaking changes) |
| 2.2 | RAG | Индексация README/CONTRIBUTING.md/style-guides. Chunking: по markdown-заголовкам + fallback fixed-size (500 токенов, overlap 50). Embeddings: `text-embedding-3-small` (баланс цена/качество). Vector DB: **Qdrant** (docker, легко поднять локально + прод). Reranker: опционально `bge-reranker` через API/локально |
| 2.2 | Документы/веб | Парсинг README.md, CONTRIBUTING.md (markdown), HTML-страниц repo (GitHub API отдаёт уже структурировано — доп. скрапинг issue-страниц при необходимости) |
| 2.2 | Мультимодальность | Vision-анализ скриншотов/диаграмм, приложенных к PR/issue (осмысленно: UI-баги, архитектурные диаграммы в README) через vision-способности модели |
| 2.3 | LangSmith | Обёртка всех LLM-вызовов трейсами, отдельный project name, дашборд на защиту |
| 2.3 | Evals | Golden dataset ≥30 примеров (реальные PR с известными issues + ожидаемые вердикты по repo-matching). Метрики: (1) issue-detection accuracy/recall, (2) LLM-as-judge — качество и релевантность комментария |
| 2.3 | A/B тест | Сравнение: (a) gpt-4o-mini vs gpt-4o на подвыборке golden dataset, (b) review с RAG-контекстом vs без него. Метрики + выводы → EVALS.md |
| 2.4 | Выбор LLM | gpt-4o-mini — обоснование: низкая стоимость на сотни ревью-запросов, приемлемая латентность, качество на code review задачах "достаточно хорошее" по сравнению с gpt-4o; описать конкретные цифры (цена/1K токенов, замеренная латентность) |
| 2.4 | Гиперпараметры | Эксперимент по temperature (0 / 0.3 / 0.7) на golden dataset — ожидание: низкая temp лучше для детерминированного ревью; top_p, max_tokens подобрать по длине типичного diff |

---

## 3. Рекомендуемые модули — что берём в первую очередь

Приоритет (по influence/effort):

1. **Guardrails** — особенно важно: diff/PR-контент — untrusted input, риск prompt injection из чужого кода/комментариев. Фильтрация PII в исходниках, защита от инструкций внутри diff'а.
2. **CI/CD (GitHub Actions)** — естественно вписывается в тему (сам продукт про code review), автозапуск evals на PR — хороший demo-эффект на защите.
3. **Docker / docker-compose** — backend + Qdrant + (опц.) frontend.
4. **Fallback между моделями** — gpt-4o-mini → gpt-4o при ошибке/таймауте.
5. **Кэширование** — семантический кэш повторных diff-ревью (снижение стоимости).
6. **Деплой** — backend на Railway/Render/Fly.io (не Vercel — см. п.4), фронтенд можно на Vercel.
7. Опционально позже: auth (GitHub OAuth), голосовой интерфейс, кастомный eval-фреймворк.

---

## 4. Что нужно предоставить для интеграций

| Сервис | Что нужно | Зачем | Как получить |
|---|---|---|---|
| **OpenAI** | API key (есть) | LLM-вызовы (gpt-4o-mini, embeddings, опц. vision) | platform.openai.com → API keys |
| **GitHub** | Personal Access Token (fine-grained), права: `contents:read`, `pull_requests:write` (для комментариев), `metadata:read` | MCP-сервер обращается к GitHub API от имени агента | github.com/settings/tokens |
| **GitHub OAuth App** (если будет логин пользователей) | Client ID + Client Secret | Пользователь логинится своим GitHub-аккаунтом, ревью идёт от его имени | github.com/settings/developers |
| **LangSmith** | API key + project name | Трейсинг всех LLM-вызовов, дашборд для защиты | smith.langchain.com |
| **Qdrant** | Ничего внешнего не нужно — поднимается локально в docker-compose. Если захотите Qdrant Cloud — API key + cluster URL | Векторное хранилище для RAG | docker или cloud.qdrant.io |
| **Vercel** | Аккаунт + `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` (для CI/CD автодеплоя) | Хостинг **фронтенда** (Vercel — serverless, для тяжёлого backend с LangGraph+Qdrant не лучший выбор) | vercel.com, `vercel login` |
| **Railway / Render / Fly.io** | Аккаунт + токен проекта | Хостинг **backend** (FastAPI + LangGraph + MCP + Qdrant-контейнер) | railway.app / render.com / fly.io |
| **GitHub repo secrets** (для CI/CD) | `OPENAI_API_KEY`, `LANGSMITH_API_KEY`, `GITHUB_TOKEN` (бот-токен агента, отдельный от токена CI), `VECTOR_DB_URL`, `VERCEL_TOKEN` и т.п. | GitHub Actions пайплайн (тесты + evals на каждый PR) | Settings → Secrets and variables → Actions |

**Важно:** токен GitHub-бота (которым агент оставляет комментарии) должен быть отдельным от личного токена — иначе комментарии будут выглядеть как от вас лично. Рекомендуется завести отдельный GitHub-аккаунт/App для бота, если планируется публичное демо.

---

## 5. Возможные дополнения темы

- **Security-фокус**: отдельный под-агент, который специально ищет security-паттерны (hardcoded secrets, SQL injection, небезопасный eval и т.п.) — легко встраивается в существующий review-граф как ещё один узел.
- **Weekly digest**: агент раз в неделю подбирает 3-5 новых good-first-issues под профиль пользователя (демонстрирует scheduled/автономный сценарий).
- **Style-guide personalization**: пользователь загружает свой style-guide (PDF/DOCX) → парсится в RAG → ревью подстраивается под конкретный проект.
- **Черновик первого PR**: после выбора репозитория и issue — агент предлагает черновой патч/план решения (не автопостит, только предложение).

Эти пункты — опциональны, не блокируют защиту, добавляются при наличии времени.

---

## 6. Технологический стек (черновой)

- **Backend**: Python, FastAPI
- **Orchestration**: LangGraph
- **MCP**: `mcp` Python SDK (FastMCP)
- **LLM**: OpenAI gpt-4o-mini через `langchain-openai` (или SDK напрямую)
- **Vector DB**: Qdrant (docker)
- **Embeddings**: `text-embedding-3-small`
- **Monitoring**: LangSmith
- **Frontend**: Next.js (React) — деплой на Vercel
- **CI/CD**: GitHub Actions
- **Контейнеризация**: Docker + docker-compose

---

## 7. Структура репозитория (план)

```
final_project/
├── backend/
│   ├── app/                 # FastAPI
│   ├── graph/                # LangGraph nodes/edges
│   ├── mcp_server/            # свой MCP-сервер
│   ├── rag/                   # индексация, retrieval, reranker
│   └── evals/                 # golden dataset, скрипты прогона
├── frontend/                 # Next.js
├── .claude/skills/code-review-checklist/SKILL.md
├── docker-compose.yml
├── .github/workflows/ci.yml
├── README.md
├── ARCHITECTURE.md
├── EVALS.md
├── PLAN.md                   # этот файл
└── PROGRESS.md               # чекпоинт прогресса между сессиями
```

---

## 8. Этапы работы (roadmap)

1. **Каркас проекта** — репозиторий, структура папок, docker-compose (Qdrant), .env.example
2. **MCP-сервер** — базовые tool'ы поверх GitHub API (сначала read-only: get_pr_diff, search_github_repos)
3. **LangGraph — happy path без ветвлений** — простой review одного diff'а от начала до конца
4. **RAG-пайплайн** — индексация README/CONTRIBUTING, retrieval, интеграция в граф
5. **Ветвления + циклы + human-in-the-loop** — доработка графа до полной версии из п.1.1
6. **Мультимодальность** — vision-анализ скриншотов/диаграмм
7. **Skill (SKILL.md)** — оформление code-review чеклиста как Skill
8. **LangSmith** — трейсинг, дашборд
9. **Golden dataset (30 примеров) + evals** — сбор реальных PR-примеров, метрики, автопрогон
10. **A/B эксперимент** — gpt-4o-mini vs gpt-4o, с RAG vs без — анализ, выводы
11. **Гиперпараметры** — эксперимент по temperature/top_p, документирование
12. **Guardrails** — защита от prompt injection в diff'ах, PII-фильтр
13. **Фронтенд** — минимальный веб-интерфейс (submit PR link, показать ревью, подтвердить/отклонить)
14. **CI/CD** — GitHub Actions с автозапуском evals на PR
15. **Деплой** — backend (Railway/Render/Fly), frontend (Vercel)
16. **Документация** — README, ARCHITECTURE.md, EVALS.md
17. **Презентация** — 10-15 слайдов

Реализация будет идти итеративно, с обновлением PROGRESS.md после каждого значимого шага.

---

## 9. Golden dataset — план сбора (30 примеров)

Категории (~по 5-10 каждая, чтобы покрыть edge cases для критерия "качество LLM-инженерии"):
- Явные баги (off-by-one, null-checks, неверная логика условий)
- Security-проблемы (hardcoded secrets, injection-паттерны)
- Стилевые нарушения (naming, форматирование, дублирование кода)
- "Чистые" PR без проблем (проверка на false positives)
- Repo-matching кейсы: профиль пользователя → ожидаемый top-N репозиториев

Источники: публичные PR из выбранных open-source репозиториев (с уже известным исходом ревью — можно свериться с реальными комментариями мейнтейнеров).

---

## 10. A/B эксперимент — дизайн

- **Гипотеза A**: gpt-4o переоценивает стоимость в сравнении с gpt-4o-mini для этой задачи (разница в качестве review небольшая).
- **Гипотеза B**: добавление RAG-контекста (style-guide/CONTRIBUTING) статистически значимо повышает релевантность комментариев (LLM-as-judge score).
- Метрики: accuracy обнаружения issues, LLM-as-judge score (1-5), стоимость за запрос, латентность.
- Результаты и вывод — в EVALS.md.

---

## 11. Механизм сохранения прогресса

Файл `PROGRESS.md` в корне репозитория обновляется после каждого завершённого этапа из раздела 8: что сделано, что в процессе, какой файл/шаг следующий. Если в сессии заканчиваются токены — прогресс уже зафиксирован в файле, новую сессию можно начинать с чтения PROGRESS.md вместо повторного анализа с нуля.

---

## 12. Открытые вопросы к пользователю

- Нужна ли аутентификация пользователей (GitHub OAuth) в MVP, или сначала single-user демо с одним PAT?
- Deploy backend — Railway, Render или Fly.io (нет явного предпочтения в ТЗ, Vercel для backend с LangGraph+Qdrant не подходит из-за serverless-ограничений)?
- Есть ли уже конкретные open-source репозитории на примете для golden dataset, или подобрать самостоятельно?

Ответы можно дать в любой момент — план будет скорректирован соответственно, дальнейшая работа не блокируется этими вопросами (будут приняты разумные допущения по умолчанию: без auth в MVP, backend на Railway).
