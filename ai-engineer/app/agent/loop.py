import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from psycopg_pool import AsyncConnectionPool

from app.agent.prompts import build_messages
from app.agent.tools import execute_tool, tool_schemas
from app.clients.llm import LLMClient
from app.rag.search import RetrievedChunk
from app.services.billing import BillingService

MAX_ITERATIONS = 3
MAX_TOOL_CALLS_PER_ITERATION = 4
FALLBACK_ANSWER = "I could not complete this request. Please contact a human support agent."


@dataclass
class AgentResult:
    answer: str
    sources: list[RetrievedChunk]
    iterations: int
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


async def run_agent(
    *,
    tenant_id: str,
    question: str,
    pool: AsyncConnectionPool,
    llm: LLMClient,
    allowed_tools: tuple[str, ...],
    idempotency_key: str | None = None,
) -> AgentResult:
    messages = build_messages(question)
    executed: list[dict[str, Any]] = []
    chunks: list[RetrievedChunk] = []
    billing_service = BillingService(pool)

    for iteration in range(1, MAX_ITERATIONS + 1):
        # The last iteration offers no tools, so the model has to produce a final answer.
        tools = tool_schemas(allowed_tools) if iteration < MAX_ITERATIONS else None
        response = await llm.chat(messages, tools=tools)

        if not response.tool_calls:
            return AgentResult(response.content, chunks, iteration, executed)

        calls = response.tool_calls[:MAX_TOOL_CALLS_PER_ITERATION]
        messages.append(
            {
                "role": "assistant",
                "content": response.content,
                "tool_calls": [
                    {"id": c.id, "name": c.name, "arguments": c.arguments} for c in calls
                ],
            }
        )
        # Tool calls in one turn are independent of each other: run them concurrently.
        results = await asyncio.gather(
            *(
                execute_tool(
                    pool,
                    tenant_id,
                    call.name,
                    call.arguments,
                    billing_service=billing_service,
                    idempotency_key=idempotency_key,
                    allowed_tools=allowed_tools,
                )
                for call in calls
            )
        )
        for call, result in zip(calls, results, strict=True):
            executed.append({"name": call.name, "arguments": call.arguments, "result": result})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.name,
                    "content": json.dumps(result),
                }
            )

    return AgentResult(FALLBACK_ANSWER, chunks, MAX_ITERATIONS, executed)
