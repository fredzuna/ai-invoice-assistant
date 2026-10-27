
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )

import hashlib
import json
import os
import uuid
from collections.abc import AsyncIterator, Callable

import httpx
import pytest_asyncio
from psycopg_pool import AsyncConnectionPool

from app.clients.embeddings import EmbeddingClient
from app.clients.llm import LLMClient
from app.config import EMBEDDING_DIM
from app.dependencies import get_embedder, get_llm, get_pool
from app.internal.db import create_pool
from app.internal.migrate import migrate
from app.main import app
from app.rag.ingest import DocumentIn, ingest_document

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://billforge:billforge@127.0.0.1:5432/billforge"
)


def fake_embedding(text: str) -> list[float]:
    """Cheap deterministic embedding: hashed character trigrams, L2-normalised."""
    vector = [0.0] * EMBEDDING_DIM
    padded = f" {text.lower()} "
    for i in range(len(padded) - 2):
        digest = hashlib.blake2b(padded[i : i + 3].encode(), digest_size=4).digest()
        vector[int.from_bytes(digest, "big") % EMBEDDING_DIM] += 1.0
    norm = sum(v * v for v in vector) ** 0.5 or 1.0
    return [v / norm for v in vector]


def embedding_client() -> EmbeddingClient:
    def handler(request: httpx.Request) -> httpx.Response:
        texts = json.loads(request.content)["input"]
        data = [{"index": i, "embedding": fake_embedding(t)} for i, t in enumerate(texts)]
        return httpx.Response(200, json={"data": data})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://embeddings")
    return EmbeddingClient(http)


def llm_client(reply: Callable[[dict], dict]) -> LLMClient:
    """LLM client backed by a scripted gateway: reply(payload) -> assistant message."""

    def handler(request: httpx.Request) -> httpx.Response:
        message = reply(json.loads(request.content))
        return httpx.Response(200, json={"message": message, "usage": {"total_tokens": 42}})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://gateway")
    return LLMClient(http)


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[AsyncConnectionPool]:
    """A pool on a throwaway schema, so tests never touch seeded data."""
    schema = f"test_{uuid.uuid4().hex[:12]}"
    admin = await create_pool(DATABASE_URL, max_size=1)
    async with admin.connection() as conn:
        await conn.execute(f"CREATE SCHEMA {schema}")
    test_pool = await create_pool(DATABASE_URL, max_size=4, search_path=f"{schema},public")
    await migrate(test_pool)
    yield test_pool
    await test_pool.close()
    async with admin.connection() as conn:
        await conn.execute(f"DROP SCHEMA {schema} CASCADE")
    await admin.close()


@pytest_asyncio.fixture
async def embedder() -> EmbeddingClient:
    return embedding_client()


@pytest_asyncio.fixture
async def seeded(pool: AsyncConnectionPool, embedder: EmbeddingClient) -> AsyncConnectionPool:
    """Two tenants with one document each, plus one invoice for the first tenant."""
    async with pool.connection() as conn:
        for tenant in ("acme", "globex"):
            await conn.execute("INSERT INTO tenants (id, name) VALUES (%s, %s)", (tenant, tenant))
        await conn.execute(
            "INSERT INTO invoices (id, tenant_id, customer_name, amount_cents, currency, status,"
            " issued_date, due_date) VALUES ('INV-ACME-0001', 'acme', 'Northwind', 12000, 'USD',"
            " 'open', '2026-01-10', '2026-02-09')"
        )
    docs = [
        DocumentIn(
            "acme-policy-001",
            "acme",
            "policy",
            "Acme refund policy",
            "Refunds are available within 30 days of the invoice date.\n\n"
            "Annual plans are refunded pro rata after the first month.",
        ),
        DocumentIn(
            "globex-policy-001",
            "globex",
            "policy",
            "Globex refund policy",
            "Refunds are available within 45 days of the invoice date.",
        ),
    ]
    for doc in docs:
        await ingest_document(pool, embedder, doc)
    return pool


@pytest_asyncio.fixture
async def client(
    seeded: AsyncConnectionPool, embedder: EmbeddingClient
) -> AsyncIterator[httpx.AsyncClient]:
    """HTTP client against the real app, with a scripted LLM and the throwaway DB."""

    def final_answer(payload: dict) -> dict:
        return {"role": "assistant", "content": "Refunds are available within 30 days."}

    app.dependency_overrides[get_pool] = lambda: seeded
    app.dependency_overrides[get_embedder] = lambda: embedder
    app.dependency_overrides[get_llm] = lambda: llm_client(final_answer)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()
