import hashlib
from dataclasses import dataclass

from psycopg_pool import AsyncConnectionPool

from app.clients.embeddings import EmbeddingClient
from app.internal.db import vector_literal
from app.rag.chunker import chunk_text


@dataclass(frozen=True)
class DocumentIn:
    id: str
    tenant_id: str
    kind: str
    title: str
    body: str


async def ingest_document(
    pool: AsyncConnectionPool, embedder: EmbeddingClient, doc: DocumentIn
) -> int:
    """Chunk, embed and store one document. Idempotent: an unchanged document is skipped
    (returns 0); a changed one has its chunks replaced. Returns the chunks written."""
    content_hash = hashlib.sha256(f"{doc.title}\n{doc.body}".encode()).hexdigest()

    async with pool.connection() as conn:
        cursor = await conn.execute("SELECT content_hash FROM documents WHERE id = %s", (doc.id,))
        existing = await cursor.fetchone()
    if existing and existing["content_hash"] == content_hash:
        return 0

    pieces = chunk_text(doc.body)
    embeddings = await embedder.embed(pieces)

    async with pool.connection() as conn, conn.transaction():
        await conn.execute(
            """
            INSERT INTO documents (id, tenant_id, kind, title, body, content_hash)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET kind = EXCLUDED.kind, title = EXCLUDED.title,
                body = EXCLUDED.body, content_hash = EXCLUDED.content_hash
            """,
            (doc.id, doc.tenant_id, doc.kind, doc.title, doc.body, content_hash),
        )
        await conn.execute("DELETE FROM chunks WHERE document_id = %s", (doc.id,))
        async with conn.cursor() as cur:
            await cur.executemany(
                "INSERT INTO chunks (document_id, tenant_id, chunk_index, content, embedding) "
                "VALUES (%s, %s, %s, %s, %s::vector)",
                [
                    (doc.id, doc.tenant_id, index, piece, vector_literal(vector))
                    for index, (piece, vector) in enumerate(zip(pieces, embeddings, strict=True))
                ],
            )
    return len(pieces)
