# FINDINGS.md

## Prioritization Criteria

Findings are ordered by priority based on financial correctness, performance impact, and maintainability.

- **P1 — High:** Risks involving duplicate financial operations.
- **P2 — Medium:** Performance improvements and request-routing accuracy.
- **P3 — Low:** Improvements to maintainability and future enhancements.

## 1. Prevent Duplicate Credit Operations with Idempotency

- **Severity:** P1 — High
- **Status:** Implemented
- **Location:** `app/api/routes.py` and the credit service implementation (verify exact file and line numbers).

**Finding:** Implemented support for an optional `Idempotency-Key` request header. When the frontend does not provide a key, the backend generates one to help prevent duplicate credit operations.

**Why it matters:** Clients may retry requests because of network failures or timeouts. Idempotency helps prevent the same operation from issuing multiple credits.

**Verification:** Unit tests should cover repeated requests with the same key and confirm that a credit is not issued twice.

## 2. First Performance Approach: Vector Search as a Tool

- **Severity:** P2 — Medium
- **Status:** Evaluated; replaced by the second approach
- **Location:** `app/loop.py` and the vector-search implementation (verify exact file and line numbers).

**Finding:** The initial approach exposed vector search as a tool alongside invoice lookup and credit issuance. The assistant selected the appropriate tool based on the user query.

**Why it matters:** This approach introduced additional tool-selection and execution overhead for general knowledge questions.

**Benchmark results:** After running `bench.sh`, the measured latency and token usage were higher than expected and did not demonstrate the intended performance improvement. The results suggested that this approach needed further optimization.

**Conclusion:** Replaced the initial approach with explicit intent classification and direct routing.

## 3. Second Performance Approach: Code-Based Intent Classification

- **Severity:** P2 — Medium
- **Status:** Implemented
- **Location:** Intent classification module and `app/loop.py` (verify exact file and line numbers).

**Finding:** Implemented code-based intent classification to identify whether a request concerns general knowledge, invoice lookup, or credit issuance. Vector search is no longer exposed as a tool; it is called directly for general knowledge questions. Invoice and credit tools are selected according to the classified intent.

**Why it matters:** Direct routing avoids using tool selection for vector search and provides a predictable execution path based on the request type.

**Limitation and future improvement:** The current intent classifier uses regular expressions and predefined rules. An LLM-based classifier could better interpret natural-language requests and more complex phrasing, provided it is evaluated for accuracy, latency, cost, and safety before replacing the current approach.

**Verification:** Run `bench.sh` again and compare the results against the first approach. Do not claim a performance improvement unless the measured results support it.

## 4. Unit Tests Updated for the New Approaches

- **Severity:** P2 — Medium
- **Status:** Implemented
- **Location:** Relevant unit test modules (verify exact file and line numbers).

**Finding:** Updated unit tests to reflect the new intent-classification and routing behavior, including direct vector search for knowledge questions and the appropriate invoice or credit tool for actionable requests.

**Why it matters:** Tests help ensure that future changes do not break request routing, credit safeguards, or the expected execution flow.

**Verification:** Run the relevant unit tests and record their results alongside the benchmark output.

