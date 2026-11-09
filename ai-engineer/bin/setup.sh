#!/usr/bin/env bash
# Build and start the stack, install the chat model, and initialize demo data.
set -euo pipefail
cd "$(dirname "$0")/.."

export LLM_MODEL="${LLM_MODEL:-llama3.1:8b}"

docker compose up -d --build --wait
docker compose exec -T ollama ollama pull "$LLM_MODEL"
docker compose run --rm --no-deps api python -m app.internal.migrate
docker compose run --rm api python -m app.seed

echo "Ready: http://localhost:${API_PORT:-8000}/health (model: $LLM_MODEL; demo data loaded)"
