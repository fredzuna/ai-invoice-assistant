"""Seed the database: tenants, ~400 documents (chunked + embedded) and invoices.

Idempotent and offline: content is generated locally; the only service it talks to is the
embedding service on the compose network. Unchanged documents are skipped on re-runs.
"""

import asyncio

import httpx

from app.clients.embeddings import EmbeddingClient
from app.config import get_settings
from app.internal.db import create_pool
from app.rag.ingest import ingest_document
from app.seed.corpus import TENANTS, build_documents, build_invoices

CONCURRENCY = 8


async def _main() -> None:
    settings = get_settings()
    pool = await create_pool(settings.database_url, max_size=CONCURRENCY + 2)
    async with httpx.AsyncClient(base_url=settings.embedding_base_url, timeout=30) as http:
        embedder = EmbeddingClient(http)

        async with pool.connection() as conn, conn.transaction():
            for tenant in TENANTS:
                await conn.execute(
                    "INSERT INTO tenants (id, name) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
                    (tenant.id, tenant.name),
                )
            for invoice in build_invoices():
                await conn.execute(
                    """
                    INSERT INTO invoices (id, tenant_id, customer_name, amount_cents, currency,
                                          status, issued_date, due_date)
                    VALUES (%(id)s, %(tenant_id)s, %(customer_name)s, %(amount_cents)s,
                            %(currency)s, %(status)s, %(issued_date)s, %(due_date)s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    invoice,
                )

        documents = build_documents()
        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def ingest(doc) -> int:
            async with semaphore:
                return await ingest_document(pool, embedder, doc)

        written = await asyncio.gather(*(ingest(doc) for doc in documents))

    await pool.close()
    changed = sum(1 for n in written if n)
    print(
        f"seed done: {len(documents)} documents ({changed} ingested, "
        f"{len(documents) - changed} unchanged), {sum(written)} chunks written"
    )


if __name__ == "__main__":
    asyncio.run(_main())
