from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import uuid4

import httpx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from ollama import ResponseError

from app.clients.errors import UpstreamError
from app.middleware.metrics import record_llm_call, record_tokens

MAX_ATTEMPTS = 2


def _is_retryable(exc: httpx.HTTPError | ResponseError) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    if isinstance(exc, ResponseError):
        return exc.status_code >= 500
    return isinstance(exc, httpx.TransportError)


class BoundChatModel(Protocol):
    async def ainvoke(self, input: Sequence[BaseMessage]) -> AIMessage: ...


class ChatModel(Protocol):
    def bind_tools(self, tools: Sequence[dict[str, Any]]) -> BoundChatModel: ...

    async def ainvoke(self, input: Sequence[BaseMessage]) -> AIMessage: ...


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class LLMResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    total_tokens: int = 0


class LLMClient:
    """Async chat client backed by a LangChain chat model."""

    def __init__(self, model: ChatModel) -> None:
        self._model = model

    async def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> LLMResponse:
        chat_messages = self._convert_messages(messages)
        model = self._model.bind_tools(tools) if tools else self._model
        last_error: httpx.HTTPError | ResponseError | None = None
        for attempt in range(MAX_ATTEMPTS):
            record_llm_call()
            try:
                response = await model.ainvoke(chat_messages)
                break
            except (httpx.HTTPError, ResponseError) as exc:
                last_error = exc
                if not _is_retryable(exc) or attempt + 1 == MAX_ATTEMPTS:
                    raise UpstreamError(f"model request failed: {exc!r}") from exc
        else:
            if last_error is None:
                raise RuntimeError("model request loop ended without a response or error")
            raise UpstreamError(f"model request failed: {last_error!r}") from last_error

        usage = response.usage_metadata or {}
        total_tokens = int(usage.get("total_tokens", 0))
        record_tokens(total_tokens)
        return LLMResponse(
            content=response.text(),
            tool_calls=[
                ToolCall(
                    id=call.get("id") or str(uuid4()),
                    name=call["name"],
                    arguments=call["args"],
                )
                for call in response.tool_calls
            ],
            total_tokens=total_tokens,
        )

    @staticmethod
    def _convert_messages(messages: Sequence[dict[str, Any]]) -> list[BaseMessage]:
        converted: list[BaseMessage] = []
        for message in messages:
            role = message["role"]
            content = message.get("content") or ""
            if role == "system":
                converted.append(SystemMessage(content=content))
            elif role == "user":
                converted.append(HumanMessage(content=content))
            elif role == "assistant":
                calls = [
                    {"id": call["id"], "name": call["name"], "args": call["arguments"]}
                    for call in message.get("tool_calls") or []
                ]
                converted.append(AIMessage(content=content, tool_calls=calls))
            elif role == "tool":
                converted.append(
                    ToolMessage(
                        content=content,
                        tool_call_id=message["tool_call_id"],
                        name=message.get("name"),
                    )
                )
            else:
                raise ValueError(f"Unsupported message role: {role}")
        return converted
