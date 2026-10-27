import httpx
import pytest
from psycopg_pool import AsyncConnectionPool

from app.agent.intent import Intent, classify_intent
from app.agent.knowledge import answer_knowledge_question
from app.agent.loop import MAX_ITERATIONS, run_agent
from app.agent.tools import (
    IssueCreditArgs,
    LookupInvoiceArgs,
    execute_tool,
    tool_schemas,
)
from app.clients.embeddings import EmbeddingClient
from app.dependencies import get_embedder, get_llm, get_pool
from app.main import app
from app.rag.chunker import chunk_text
from app.rag.ingest import DocumentIn, ingest_document
from app.rag.search import TOP_K, search
from app.services.billing import BillingService
from tests.conftest import fake_embedding, llm_client


async def test_ask_contract(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/v1/ask", json={"tenant_id": "acme", "question": "What is the refund policy?"}
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"answer", "sources"}
    assert isinstance(body["answer"], str) and body["answer"]
    assert body["sources"], "expected at least one source"
    assert set(body["sources"][0]) == {"document_id", "title", "score"}
    assert all(s["document_id"].startswith("acme-") for s in body["sources"])


async def test_agent_result_shape(seeded: AsyncConnectionPool) -> None:
    calls = []

    def reply(payload: dict) -> dict:
        calls.append(payload)
        if len(calls) == 1:
            tool_call = {
                "id": "c1",
                "name": "lookup_invoice",
                "arguments": {"invoice_id": "INV-ACME-0001"},
            }
            return {"role": "assistant", "content": "", "tool_calls": [tool_call]}
        return {"role": "assistant", "content": "Invoice INV-ACME-0001 is open."}

    result = await run_agent(
        tenant_id="acme",
        question="What is the status of INV-ACME-0001?",
        pool=seeded,
        llm=llm_client(reply),
        allowed_tools=("lookup_invoice",),
    )
    assert isinstance(result.answer, str) and result.answer
    assert result.iterations == 2
    assert [c["name"] for c in result.tool_calls] == ["lookup_invoice"]
    assert result.tool_calls[0]["result"]["invoice"]["status"] == "open"
    system, question = calls[0]["messages"]
    assert "lookup_invoice whenever" in system["content"]
    assert [tool["function"]["name"] for tool in calls[0]["tools"]] == ["lookup_invoice"]
    assert question["content"] == "Customer question:\nWhat is the status of INV-ACME-0001?"
    assert result.sources == []


async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chunker_keeps_all_text() -> None:
    paragraphs = [f"Paragraph {i}. " + "Billing detail sentence. " * 3 for i in range(12)]
    table = "\n".join(
        ["| Plan | Price |", "| --- | --- |"] + [f"| Plan {i} | {i}.00 |" for i in range(30)]
    )
    text = "\n\n".join(paragraphs[:6] + [table] + paragraphs[6:])

    chunks = chunk_text(text, max_chars=200, overlap=40)

    joined = "\n\n".join(chunks)
    for paragraph in (p.strip() for p in paragraphs):
        assert paragraph in joined
    assert any(table in chunk for chunk in chunks), "a table must never be split"
    assert set(text.split()) <= set(joined.split())


async def test_tool_schemas_are_validated(
    seeded: AsyncConnectionPool,
) -> None:
    schemas = {s["function"]["name"]: s["function"]["parameters"] for s in tool_schemas()}
    assert set(schemas) == {"lookup_invoice", "issue_credit"}
    assert [schema["function"]["name"] for schema in tool_schemas(("lookup_invoice",))] == [
        "lookup_invoice"
    ]
    assert [schema["function"]["name"] for schema in tool_schemas(("issue_credit",))] == [
        "issue_credit"
    ]
    assert set(schemas["issue_credit"]["required"]) == {"invoice_id", "amount_cents", "reason"}
    assert "idempotency_key" not in schemas["issue_credit"]["properties"]
    billing_service = BillingService(seeded)

    # Invalid arguments never reach the database; they come back as an error for the model.
    for name, arguments in [
        ("lookup_invoice", {}),
        ("lookup_invoice", {"invoice_id": "not-an-invoice"}),
        ("lookup_invoice", {"invoice_id": "INV-ACME-0001", "tenant_id": "globex"}),
        ("issue_credit", {"invoice_id": "INV-ACME-0001", "amount_cents": -5, "reason": "oops"}),
        ("nonexistent_tool", {}),
    ]:
        result = await execute_tool(
            seeded,
            "acme",
            name,
            arguments,
            billing_service=billing_service,
        )
        assert "error" in result, (name, arguments)

    assert LookupInvoiceArgs(invoice_id="INV-ACME-0001").invoice_id == "INV-ACME-0001"
    assert IssueCreditArgs(invoice_id="INV-ACME-0001", amount_cents=100, reason="goodwill")
    # Another tenant's invoice is indistinguishable from a missing one.
    other = await execute_tool(
        seeded,
        "globex",
        "lookup_invoice",
        {"invoice_id": "INV-ACME-0001"},
        billing_service=billing_service,
    )
    assert "not found" in other["error"]
    forbidden = await execute_tool(
        seeded,
        "acme",
        "issue_credit",
        {
            "invoice_id": "INV-ACME-0001",
            "amount_cents": 100,
            "reason": "goodwill",
            "confirmed": True,
        },
        billing_service=billing_service,
        allowed_tools=("lookup_invoice",),
    )
    assert "not available" in forbidden["error"]


async def test_knowledge_path_searches_tenant_context_and_calls_llm_once(
    seeded: AsyncConnectionPool, embedder: EmbeddingClient
) -> None:
    calls = []

    def reply(payload: dict) -> dict:
        calls.append(payload)
        return {"role": "assistant", "content": "Refunds are available within 30 days."}

    result = await answer_knowledge_question(
        tenant_id="acme",
        question="What is the refund policy?",
        pool=seeded,
        llm=llm_client(reply),
        embedder=embedder,
    )

    assert result.iterations == 1
    assert result.tool_calls == []
    assert len(calls) == 1
    assert "tools" not in calls[0]
    assert result.sources and {chunk.document_id for chunk in result.sources} == {
        "acme-policy-001"
    }
    first_messages = calls[0]["messages"]
    assert first_messages[1]["content"] == "Customer question:\nWhat is the refund policy?"
    context = first_messages[2]["content"]
    assert "Refunds are available within 30 days" in context
    assert "45 days" not in context


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What is the refund policy?", Intent.KNOWLEDGE),
        ("Can I receive a credit under the refund policy?", Intent.KNOWLEDGE),
        ("How do I apply for a credit?", Intent.KNOWLEDGE),
        ("Can you give me information about the credit policy?", Intent.KNOWLEDGE),
        ("What is the status of invoice INV-ACME-0007?", Intent.INVOICE),
        ("Show me my latest invoice", Intent.INVOICE),
        ("Where is my invoice?", Intent.INVOICE),
        ("Please issue a $20 credit for this invoice.", Intent.CREDIT),
        ("I want a credit for this invoice.", Intent.CREDIT),
        ("Could you apply a $20 credit?", Intent.CREDIT),
    ],
)
def test_intent_classification(question: str, expected: Intent) -> None:
    assert classify_intent(question) is expected


async def test_ingest_is_idempotent(pool: AsyncConnectionPool, embedder: EmbeddingClient) -> None:
    async with pool.connection() as conn:
        await conn.execute("INSERT INTO tenants (id, name) VALUES ('acme', 'Acme')")
    doc = DocumentIn("acme-faq-001", "acme", "faq", "Acme FAQ", "First answer.\n\nSecond answer.")

    first = await ingest_document(pool, embedder, doc)
    second = await ingest_document(pool, embedder, doc)

    async with pool.connection() as conn:
        cursor = await conn.execute("SELECT count(*) AS n FROM chunks")
        chunk_count = (await cursor.fetchone())["n"]
        cursor = await conn.execute("SELECT count(*) AS n FROM documents")
        document_count = (await cursor.fetchone())["n"]
    assert first > 0 and second == 0
    assert (document_count, chunk_count) == (1, first)


async def test_search_returns_results_for_tenant(
    seeded: AsyncConnectionPool,
) -> None:
    query = fake_embedding("refund policy within days of the invoice")

    results = await search(seeded, "acme", query)

    assert 0 < len(results) <= TOP_K
    assert {r.document_id for r in results} == {"acme-policy-001"}
    assert results == sorted(results, key=lambda r: r.score, reverse=True)
    assert await search(seeded, "unknown-tenant", query) == []


async def test_metrics_headers_present(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/v1/ask", json={"tenant_id": "acme", "question": "What is the refund policy?"}
    )
    assert response.headers["X-LLM-Calls"] == "1"
    assert response.headers["X-Embed-Calls"] == "1"
    assert response.headers["X-Tokens"] == "42"
    assert int(response.headers["X-Elapsed-Ms"]) >= 0

    health = await client.get("/health")
    assert {"x-llm-calls", "x-embed-calls", "x-tokens", "x-elapsed-ms"} <= set(health.headers)


async def test_invalid_input_returns_4xx(client: httpx.AsyncClient) -> None:
    empty = {"tenant_id": "acme", "question": ""}
    assert (await client.post("/v1/ask", json=empty)).status_code == 422
    assert (await client.post("/v1/ask", json={"question": "hello there"})).status_code == 422
    bad_tenant = {"tenant_id": "ACME; DROP TABLE", "question": "hello there"}
    assert (await client.post("/v1/ask", json=bad_tenant)).status_code == 422
    assert (await client.post("/v1/ask", content=b"not json")).status_code in (400, 422)


async def test_agent_terminates_for_simple_query(
    seeded: AsyncConnectionPool,
) -> None:
    llm_calls = []

    def answer(payload: dict) -> dict:
        llm_calls.append(payload)
        return {"role": "assistant", "content": "Refunds take up to 30 days."}

    result = await run_agent(
        tenant_id="acme",
        question="How long do refunds take?",
        pool=seeded,
        llm=llm_client(answer),
        allowed_tools=("lookup_invoice",),
    )
    assert result.iterations == 1 and len(llm_calls) == 1
    assert [tool["function"]["name"] for tool in llm_calls[0]["tools"]] == ["lookup_invoice"]
    assert result.tool_calls == []

    # Even a model that keeps asking for tools is cut off at MAX_ITERATIONS.
    def always_tool(payload: dict) -> dict:
        call = {"id": "c", "name": "lookup_invoice", "arguments": {"invoice_id": "INV-ACME-0001"}}
        return {"role": "assistant", "content": "", "tool_calls": [call]}

    stuck = await run_agent(
        tenant_id="acme",
        question="Loop forever",
        pool=seeded,
        llm=llm_client(always_tool),
        allowed_tools=("lookup_invoice",),
    )
    assert stuck.iterations == MAX_ITERATIONS
