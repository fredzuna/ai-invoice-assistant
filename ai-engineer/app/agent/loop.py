import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from psycopg_pool import AsyncConnectionPool

from app.agent.prompts import build_messages
from app.agent.tools import execute_tool, tool_schemas
from app.clients.llm import LLMClient
from app.rag.search import RetrievedChunk
from app.services.billing import BillingService

MAX_ITERATIONS = 3
MAX_TOOL_CALLS_PER_ITERATION = 4
FALLBACK_ANSWER = "I could not complete this request. Please contact a human support agent."


class AgentState(TypedDict):
    messages: list[dict[str, Any]]
    iterations: int
    executed: list[dict[str, Any]]


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
    chunks: list[RetrievedChunk] = []
    billing_service = BillingService(pool)

    async def call_model(state: AgentState) -> dict[str, Any]:
        # The final model call has no tools and must produce a user-facing answer.
        tools = tool_schemas(allowed_tools) if state["iterations"] < MAX_ITERATIONS else None
        response = await llm.chat(state["messages"], tools=tools)
        assistant_message = {
            "role": "assistant",
            "content": response.content,
            "tool_calls": [
                {"id": call.id, "name": call.name, "arguments": call.arguments}
                for call in response.tool_calls
            ],
        }
        return {
            "messages": [*state["messages"], assistant_message],
            "iterations": state["iterations"] + 1,
        }

    async def run_tools(state: AgentState) -> dict[str, Any]:
        calls = state["messages"][-1].get("tool_calls", [])[:MAX_TOOL_CALLS_PER_ITERATION]
        results = await asyncio.gather(
            *(
                execute_tool(
                    pool,
                    tenant_id,
                    call["name"],
                    call["arguments"],
                    billing_service=billing_service,
                    idempotency_key=idempotency_key,
                    allowed_tools=allowed_tools,
                )
                for call in calls
            )
        )
        tool_messages = [
            {
                "role": "tool",
                "tool_call_id": call["id"],
                "name": call["name"],
                "content": json.dumps(result),
            }
            for call, result in zip(calls, results, strict=True)
        ]
        executed = [
            {"name": call["name"], "arguments": call["arguments"], "result": result}
            for call, result in zip(calls, results, strict=True)
        ]
        return {
            "messages": [*state["messages"], *tool_messages],
            "executed": [*state["executed"], *executed],
        }

    def route_after_model(state: AgentState) -> str:
        last_message = state["messages"][-1]
        if last_message["tool_calls"] and state["iterations"] < MAX_ITERATIONS:
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("model", call_model)
    graph.add_node("tools", run_tools)
    graph.set_entry_point("model")
    graph.add_conditional_edges("model", route_after_model)
    graph.add_edge("tools", "model")
    result = await graph.compile().ainvoke(
        {"messages": build_messages(question), "iterations": 0, "executed": []}
    )
    final_message = result["messages"][-1]
    answer = final_message["content"] if not final_message["tool_calls"] else FALLBACK_ANSWER
    return AgentResult(answer, chunks, result["iterations"], result["executed"])
