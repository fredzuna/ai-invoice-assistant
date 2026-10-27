#!/usr/bin/env bash
# Build and start the stack, wait until every service is healthy, then apply migrations.
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose up -d --build --wait
docker compose run --rm --no-deps api python -m app.internal.migrate

echo "Ready: http://localhost:${API_PORT:-8000}/health (run bin/seed.sh to load demo data)"
