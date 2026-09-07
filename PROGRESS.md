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

**Следующий шаг (этап 2 из PLAN.md раздел 8):** MCP-сервер — базовые read-only tool'ы поверх GitHub API (`get_pr_diff`, `search_github_repos`) в `backend/mcp_server/`.

**Открытые вопросы (не блокируют, но влияют на детали):**
- Auth в MVP: пока допущение — без auth, single-user PAT.
- Backend hosting: пока допущение — Railway.
- Источники для golden dataset: пока не выбраны, нужно подобрать 30 PR-примеров.
