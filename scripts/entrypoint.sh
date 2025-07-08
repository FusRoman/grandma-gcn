#!/bin/sh
set -e

echo "[entrypoint] Running Alembic migrations..."
python -m alembic upgrade head

exec "$@"
