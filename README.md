# OSS Copilot

AI-агент для code review merge request'ов на GitHub и поиска open-source репозитория, в который стоит стать контрибьютором.

Подробный план реализации, архитектура и обоснования технических решений — в [PLAN.md](PLAN.md).
Статус работы по этапам — в [PROGRESS.md](PROGRESS.md).

## Возможности (в разработке)

1. **PR Reviewer** — автоматическое ревью PR/diff с человеческим подтверждением перед публикацией комментария.
2. **Repo Matcher** — подбор open-source репозиториев для контрибьютинга по профилю пользователя.

## Стек

FastAPI, LangGraph, свой MCP-сервер, RAG (Qdrant), LangSmith, Next.js.

## Запуск (локально)

```bash
cp .env.example .env   # заполнить реальными ключами
docker-compose up
```

Backend будет доступен на `http://localhost:8000/health`, Qdrant — на `http://localhost:6333`.

### MCP-сервер

`backend/mcp_server/server.py` — собственный MCP-сервер с read-only GitHub-инструментами:

- `get_pr_diff(owner, repo, pr_number)` — diff и метаданные pull request'а
- `search_github_repos(query, limit)` — поиск репозиториев-кандидатов для контрибьютинга
- `get_repo_health(owner, repo)` — сигналы дружелюбности к новым контрибьюторам (CONTRIBUTING.md, good-first-issues, активность)

Запуск локально (stdio transport):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
PYTHONPATH=. python -m backend.mcp_server.server
```

## Статус

Проект в активной разработке. Архитектурная документация (ARCHITECTURE.md) и результаты evals (EVALS.md) появятся по мере реализации соответствующих этапов — см. PLAN.md, раздел 8.
