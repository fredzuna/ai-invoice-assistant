from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from psycopg_pool import AsyncConnectionPool

from app.agent.intent import Intent, classify_intent
from app.agent.knowledge import answer_knowledge_question
from app.agent.loop import run_agent
from app.clients.embeddings import EmbeddingClient
from app.clients.errors import UpstreamError
from app.clients.llm import LLMClient
from app.dependencies import get_embedder, get_llm, get_pool
from app.rag.search import RetrievedChunk
from app.schemas import AskRequest, AskResponse, Source

router = APIRouter(tags=["ask"])


def _unique_sources(chunks: list[RetrievedChunk]) -> list[Source]:
    """One source per document, in retrieval order (best chunk first)."""
    seen: set[str] = set()
    sources: list[Source] = []
    for chunk in chunks:
        if chunk.document_id in seen:
            continue
        seen.add(chunk.document_id)
        sources.append(
            Source(document_id=chunk.document_id, title=chunk.title, score=round(chunk.score, 4))
        )
    return sources


@router.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    pool: Annotated[AsyncConnectionPool, Depends(get_pool)],
    llm: Annotated[LLMClient, Depends(get_llm)],
    embedder: Annotated[EmbeddingClient, Depends(get_embedder)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AskResponse:
    try:
        intent = classify_intent(body.question)
        if intent is Intent.KNOWLEDGE:
            result = await answer_knowledge_question(
                tenant_id=body.tenant_id,
                question=body.question,
                pool=pool,
                llm=llm,
                embedder=embedder,
            )
        else:
            allowed_tools = (
                ("lookup_invoice",) if intent is Intent.INVOICE else ("issue_credit",)
            )

            result = await run_agent(
                tenant_id=body.tenant_id,
                question=body.question,
                pool=pool,
                llm=llm,
                allowed_tools=allowed_tools,
                idempotency_key=idempotency_key or str(uuid4()),
            )
    except UpstreamError as exc:
        raise HTTPException(status_code=502, detail="model service unavailable") from exc
    return AskResponse(answer=result.answer, sources=_unique_sources(result.sources))
