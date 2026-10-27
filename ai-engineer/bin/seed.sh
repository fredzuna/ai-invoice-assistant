#!/usr/bin/env bash
# Load demo data: 3 tenants, ~400 knowledge-base documents (~3,000 chunks) and invoices.
# Everything is generated locally (no network access needed) and the script is idempotent:
# re-running it skips documents that are already ingested.
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose run --rm api python -m app.seed
