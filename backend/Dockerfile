# Build context is the repo root (see docker-compose.yml) — not ./backend — so that
# `backend` stays an importable top-level package inside the image, matching how
# everything is run locally (PYTHONPATH=. from the repo root). Building with
# ./backend as context instead makes `backend.*` imports fail at runtime with
# ModuleNotFoundError: no module named 'backend', even though the image builds fine.

FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/

ENV PYTHONPATH=/app

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
