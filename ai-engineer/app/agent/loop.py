import json
from dataclasses import dataclass, field
from typing import Annotated, Any, TypedDict

import httpx
from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    ToolCallLimitMiddleware,
)
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from ollama import ResponseError
from psycopg_pool import AsyncConnectionPool

from app.agent.intent import Intent, classify_intent
from app.agent.knowledge import KNOWLEDGE_SYSTEM_PROMPT, knowledge_context
from app.agent.prompts import build_messages
from app.agent.tools import create_agent_tools
from app.clients.embeddings import EmbeddingClient
from app.clients.errors import UpstreamError
from app.clients.llm import LLMClient
from app.middleware.metrics import record_llm_call, record_tokens
from app.rag.search import RetrievedChunk
from app.services.billing import BillingService
from app.services.knowledge import retrieve_knowledge

MAX_ITERATIONS = 3
MAX_TOOL_CALLS_PER_ITERATION = 4
FALLBACK_ANSWER = "I could not complete this request. Please contact a human support agent."


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    iterations: int
    intent: Intent
    question: str
    tenant_id: str
    chunks: list[RetrievedChunk]


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
    embedder: EmbeddingClient,
    idempotency_key: str | None = None,
) -> AgentResult:
    billing_service = BillingService(pool)

    def classify_request(state: AgentState) -> dict[str, Any]:
        intent = classify_intent(state["question"])
        if intent is Intent.KNOWLEDGE:
            messages = [
                {"role": "system", "content": KNOWLEDGE_SYSTEM_PROMPT},
                {"role": "user", "content": f"Customer question:\n{state['question']}"},
            ]
        else:
            messages = build_messages(state["question"])
        return {"intent": intent, "messages": messages}

    async def run_tool_agent(
        state: AgentState,
        *,
        tools: list[StructuredTool],
        name: str,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        agent = create_agent(
            model=llm.model,
            tools=tools,
            system_prompt=system_prompt,
            middleware=[
                ModelRetryMiddleware(
                    max_retries=1,
                    retry_on=(httpx.HTTPError, ResponseError),
                    on_failure="error",
                    initial_delay=0,
                    jitter=False,
                ),
                ModelCallLimitMiddleware(run_limit=MAX_ITERATIONS),
                ToolCallLimitMiddleware(
                    run_limit=(
                        1 if name == "knowledge_agent" else MAX_TOOL_CALLS_PER_ITERATION
                    ),
                    exit_behavior="end",
                ),
            ],
            name=name,
        )
        try:
            agent_result = await agent.ainvoke({"messages": state["messages"]})
        except (httpx.HTTPError, ResponseError) as exc:
            raise UpstreamError(f"model request failed: {exc!r}") from exc
        messages = agent_result["messages"][len(state["messages"]) :]
        model_responses = [
            message
            for message in messages
            if isinstance(message, AIMessage) and message.usage_metadata
        ]
        for message in model_responses:
            record_llm_call()
            record_tokens(int(message.usage_metadata.get("total_tokens", 0)))
        return {
            "messages": messages,
            "iterations": min(len(model_responses), MAX_ITERATIONS),
        }

    async def generate_knowledge_response(state: AgentState) -> dict[str, Any]:
        chunks = await retrieve_knowledge(
            pool,
            embedder,
            state["tenant_id"],
            state["question"],
        )
        messages = [
            *state["messages"],
            {"role": "user", "content": knowledge_context(chunks)},
        ]
        response = await llm.chat(messages)
        return {
            "messages": [AIMessage(content=response.content)],
            "iterations": 1,
            "chunks": chunks,
        }

    async def generate_billing_response(state: AgentState) -> dict[str, Any]:
        allowed_tools = {
            Intent.INVOICE: ("lookup_invoice",),
            Intent.CREDIT: ("issue_credit",),
        }
        agent_tools = create_agent_tools(
            pool,
            state["tenant_id"],
            billing_service=billing_service,
            allowed_tools=allowed_tools,
            idempotency_key=idempotency_key,
        )
        return await run_tool_agent(
            state,
            tools=agent_tools,
            name=f"{state['intent'].value}_agent",
        )

    graph = StateGraph(AgentState)
    graph.add_node("classify", classify_request)
    graph.add_node("knowledge_response", generate_knowledge_response)
    graph.add_node("billing_response", generate_billing_response)

    graph.set_entry_point("classify")
    graph.add_conditional_edges(
        "classify",
        lambda state: (
            "knowledge_response"
            if state["intent"] is Intent.KNOWLEDGE
            else "billing_response"
        ),
    )
    graph.add_edge("knowledge_response", END)
    graph.add_edge("billing_response", END)
    result = await graph.compile().ainvoke(
        {
            "messages": [],
            "iterations": 0,
            "intent": Intent.KNOWLEDGE,
            "question": question,
            "tenant_id": tenant_id,
            "chunks": [],
        }
    )
    final_message = result["messages"][-1]
    if not isinstance(final_message, AIMessage):
        raise RuntimeError("agent graph ended without a final assistant message")
    answer = final_message.text() if not final_message.tool_calls else FALLBACK_ANSWER
    executed = _executed_tool_calls(result["messages"])
    return AgentResult(answer, result["chunks"], result["iterations"], executed)


def _executed_tool_calls(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    calls = {
        call["id"]: {"name": call["name"], "arguments": call["args"]}
        for message in messages
        if isinstance(message, AIMessage)
        for call in message.tool_calls
    }
    executed: list[dict[str, Any]] = []
    for message in messages:
        if isinstance(message, ToolMessage):
            call = calls[message.tool_call_id]
            result = (
                {"error": message.text()}
                if message.status == "error"
                else _tool_result(message.text())
            )
            executed.append(
                {"name": call["name"], "arguments": call["arguments"], "result": result}
            )
    return executed


def _tool_result(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"output": content}
