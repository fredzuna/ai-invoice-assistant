from psycopg_pool import AsyncConnectionPool

from app.clients.embeddings import EmbeddingClient
from app.rag.search import RetrievedChunk, search


async def retrieve_knowledge(
    pool: AsyncConnectionPool,
    embedder: EmbeddingClient,
    tenant_id: str,
    query: str,
) -> list[RetrievedChunk]:
    """Embed a query and retrieve only chunks belonging to the requested tenant."""
    embeddings = await embedder.embed([query])
    if len(embeddings) != 1:
        raise ValueError("embedding service returned an unexpected number of vectors")
    return await search(pool, tenant_id, embeddings[0])
