from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.clients.embeddings import EmbeddingClient
from app.clients.llm import LLMClient
from app.config import get_settings
from app.internal.db import create_pool
from app.middleware.metrics import MetricsMiddleware
from app.routers import ask, health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.pool = await create_pool(settings.database_url, max_size=settings.db_pool_max_size)
    llm_http = httpx.AsyncClient(base_url=settings.llm_base_url, timeout=settings.llm_timeout_s)
    embedding_http = httpx.AsyncClient(
        base_url=settings.embedding_base_url, timeout=settings.embedding_timeout_s
    )
    app.state.llm = LLMClient(llm_http)
    app.state.embedder = EmbeddingClient(embedding_http)
    try:
        yield
    finally:
        await llm_http.aclose()
        await embedding_http.aclose()
        await app.state.pool.close()


app = FastAPI(title="Billforge Support Copilot", lifespan=lifespan)
app.add_middleware(MetricsMiddleware)
app.include_router(health.router)
app.include_router(ask.router, prefix="/v1")
