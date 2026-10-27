from dataclasses import dataclass

from psycopg_pool import AsyncConnectionPool

from app.internal.db import vector_literal

TOP_K = 4


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    document_id: str
    title: str
    content: str
    score: float


async def search(
    pool: AsyncConnectionPool,
    tenant_id: str,
    query_embedding: list[float],
    top_k: int = TOP_K,
) -> list[RetrievedChunk]:
    """Nearest chunks (cosine) for one tenant. This is the only retrieval path; it always
    filters by tenant_id."""
    if not tenant_id:
        raise ValueError("tenant_id is required")
    vector = vector_literal(query_embedding)
    async with pool.connection() as conn:
        cursor = await conn.execute(
            """
            SELECT c.id, c.document_id, d.title, c.content,
                   1 - (c.embedding <=> %(vec)s::vector) AS score
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.tenant_id = %(tenant_id)s
            ORDER BY c.embedding <=> %(vec)s::vector
            LIMIT %(top_k)s
            """,
            {"vec": vector, "tenant_id": tenant_id, "top_k": top_k},
        )
        rows = await cursor.fetchall()
    return [
        RetrievedChunk(
            chunk_id=row["id"],
            document_id=row["document_id"],
            title=row["title"],
            content=row["content"],
            score=float(row["score"]),
        )
        for row in rows
    ]
