from fastapi import Request
from psycopg_pool import AsyncConnectionPool

from app.clients.embeddings import EmbeddingClient
from app.clients.llm import LLMClient


def get_pool(request: Request) -> AsyncConnectionPool:
    return request.app.state.pool


def get_llm(request: Request) -> LLMClient:
    return request.app.state.llm


def get_embedder(request: Request) -> EmbeddingClient:
    return request.app.state.embedder
