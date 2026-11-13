#!/bin/sh
# Container entrypoint: apply database migrations, then run the API.
# `exec` replaces the shell so uvicorn is PID 1 and receives SIGTERM directly.
set -e

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
