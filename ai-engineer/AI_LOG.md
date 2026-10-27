## Main Prompts Used During Development

The following prompts summarize the main steps used to analyze the existing implementation and develop the three approaches.

### 1. Analyze the Existing Workflow and Code

**Goal:** Understand the current architecture, request flow, tool execution, and performance before making changes.

**Prompt:**

> Analyze the existing codebase and explain the complete workflow of the Support Copilot. Trace how a user request is received, how the system decides what action to perform, how tools are selected and executed, and how the response is returned.
>
> Review the relevant API endpoints, agent or orchestration logic, invoice lookup, credit issuance, vector search, database interactions, and existing tests.
>
> Identify potential issues with duplicate financial operations, tool selection, request routing, and performance. Do not modify the code yet. First, explain the current workflow and recommend improvements based on the existing implementation.

### 2. First Approach: Idempotency and Vector Search as a Tool

**Goal:** Prevent duplicate operations and explore whether exposing vector search as a tool improves performance.

**Prompt:**

> Implement idempotency for the Support Copilot API using an `Idempotency-Key` request header to help prevent duplicate operations, especially credit issuance. Review the existing API and database workflow and integrate the solution consistently with the current architecture.
>
> As a separate performance experiment, expose vector search as a tool alongside the invoice lookup and credit issuance tools. Allow the agent to select the appropriate tool based on the user's request.
>
> Update the relevant tests and run the existing benchmark script (`bench.sh`) to evaluate the changes. Compare the benchmark results with the previous implementation and document whether this approach demonstrates a performance improvement.

**Evaluation:** The benchmark results were higher than expected and did not demonstrate the intended performance improvement. This led to exploring a different routing strategy rather than assuming that exposing vector search as a tool would make the workflow faster.

### 3. Second Approach: Code-Based Intent Classification

**Goal:** Select the appropriate operation by identifying the user's intention before executing tools.

**Prompt:**

> Refactor the Support Copilot workflow to classify the user's query intent before selecting an action.
>
> Implement code-based intent classification to identify whether the request is related to general knowledge, invoice lookup, or credit issuance.
>
> - For general knowledge questions, call the vector search service directly instead of exposing vector search as an agent tool.
> - For invoice-related requests, select the invoice lookup tool.
> - For credit-related requests, select the credit issuance tool, while preserving the existing confirmation and financial safety requirements.
> - Ensure that credit-related requests are classified correctly even when they also contain an invoice ID.
>
> Update the unit tests to cover the new routing behavior, including invoice queries, credit requests, general knowledge questions, and ambiguous or overlapping intents. Run the tests and benchmark to evaluate the new implementation.

**Evaluation:** This approach makes tool selection explicit in application code and removes vector search from the agent's tool-selection process. However, the intent classifier relies on predefined rules and regular expressions, which can be less flexible when users phrase requests in unexpected ways.

### 4. Potential Improvement: LLM-Based Intent Classification

**Goal:** Explore a more flexible alternative to rule-based classification.

**Prompt:**

> Evaluate whether an LLM could classify user intent instead of relying exclusively on regular expressions and predefined rules. Design an approach that returns a structured intent, such as `knowledge`, `invoice`, or `credit`, and validates the result before routing the request.
>
> Consider classification accuracy, ambiguous requests, latency, cost, reliability, and financial safety. Ensure that credit issuance still requires explicit customer confirmation and that the LLM cannot bypass application-level validation or authorization.
>
> Compare the LLM-based approach with the existing code-based classifier using representative test cases and benchmark results before deciding whether to adopt it.

**Note:** LLM-based intent classification is a potential improvement to evaluate, not an implemented feature in the current approach.

### 5. Unit Test Updates

**Goal:** Keep the tests aligned with the changes introduced by the approaches.

**Prompt:**

> Update the unit tests to reflect the idempotency implementation and the revised intent-based routing workflow. Verify that general knowledge queries use the vector search service directly, invoice queries invoke invoice lookup, and confirmed credit requests invoke the credit issuance tool.
>
> Add coverage for duplicate requests, credit confirmation requirements, overlapping invoice and credit references, and fallback behavior. Run the relevant tests and report any failures.

