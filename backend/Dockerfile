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

# Shell form (not exec-form array) so $PORT actually expands — Railway (and most
# PaaS hosts) assign a dynamic port via $PORT and healthcheck that, not 8000.
# Defaults to 8000 when unset, matching docker-compose's local port mapping.
CMD uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}
