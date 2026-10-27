#!/usr/bin/env bash
# Benchmark POST /v1/ask: 20 requests, concurrency 8. Needs only curl, bash and xargs.
# Prints median and p95 latency plus mean LLM calls, embedding calls and tokens per request
# (read from the X-LLM-Calls / X-Embed-Calls / X-Tokens / X-Elapsed-Ms response headers).
set -euo pipefail

URL="${API_URL:-http://localhost:${API_PORT:-8000}}/v1/ask"
REQUESTS=20
CONCURRENCY=8

# tenant|question — a mix of knowledge questions and invoice lookups.
QUESTIONS=(
  "acme|What is the refund policy for annual plans?"
  "globex|How do I download invoices?"
  "initech|What are the payment processing fees in the EU region?"
  "acme|What is the status of invoice INV-ACME-0007?"
  "globex|What does the dunning schedule say about failed payments?"
  "initech|How do I export usage reports?"
  "acme|Show me the price table for core billing monthly pricing"
  "globex|What is the status of invoices INV-GLOBEX-0003 and INV-GLOBEX-0012?"
)

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
printf '%s\n' "${QUESTIONS[@]}" >"$TMP/questions"

# Usage: one_request <index> <url> <tmpdir>; request i uses question (i mod number of questions).
one_request() {
  local index="$1" url="$2" tmp="$3" total item tenant question payload
  total=$(wc -l <"$tmp/questions")
  item=$(sed -n "$((index % total + 1))p" "$tmp/questions")
  tenant="${item%%|*}"
  question="${item#*|}"
  payload=$(printf '{"tenant_id":"%s","question":"%s"}' "$tenant" "$question")
  curl -s -o /dev/null -D "$tmp/headers.$index" -w '%{time_total}' \
    -H 'Content-Type: application/json' -d "$payload" "$url" >"$tmp/time.$index"
}
export -f one_request

# Warm-up (connection pool, imports); not counted.
curl -s -o /dev/null -H 'Content-Type: application/json' \
  -d '{"tenant_id":"acme","question":"warm up"}' "$URL" || {
  echo "API not reachable at $URL (run bin/setup.sh first)" >&2
  exit 1
}

seq 0 $((REQUESTS - 1)) | xargs -P "$CONCURRENCY" -I{} bash -c 'one_request {} "$0" "$1"' "$URL" "$TMP"

for i in $(seq 0 $((REQUESTS - 1))); do
  header() { grep -i "^$1:" "$TMP/headers.$i" | tr -d '\r' | awk '{print $2}'; }
  status=$(head -1 "$TMP/headers.$i" | awk '{print $2}')
  printf '%s %s %s %s %s %s\n' \
    "$status" "$(awk '{printf "%.0f", $1 * 1000}' "$TMP/time.$i")" \
    "$(header x-elapsed-ms)" "$(header x-llm-calls)" "$(header x-embed-calls)" "$(header x-tokens)"
done >"$TMP/rows"

awk '
  function pct(arr, n, p,   idx) { idx = int(p * n + 0.999999); if (idx < 1) idx = 1; return arr[idx] }
  { if ($1 != 200) errors++; lat[NR] = $2; llm += $4; emb += $5; tok += $6; n = NR }
  END {
    # insertion sort of client-side latencies
    for (i = 2; i <= n; i++) { v = lat[i]; j = i - 1; while (j > 0 && lat[j] > v) { lat[j+1] = lat[j]; j-- } lat[j+1] = v }
    median = (n % 2) ? lat[(n + 1) / 2] : (lat[n / 2] + lat[n / 2 + 1]) / 2
    printf "requests:               %d (concurrency %d, errors %d)\n", n, '"$CONCURRENCY"', errors
    printf "latency p50:            %.0f ms\n", median
    printf "latency p95:            %d ms\n", pct(lat, n, 0.95)
    printf "LLM calls / request:    %.2f\n", llm / n
    printf "embed calls / request:  %.2f\n", emb / n
    printf "tokens / request:       %.0f\n", tok / n
  }' "$TMP/rows"
