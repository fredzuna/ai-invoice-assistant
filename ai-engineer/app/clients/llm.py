from dataclasses import dataclass, field
from typing import Any

import httpx

from app.clients.errors import UpstreamError
from app.middleware.metrics import record_llm_call, record_tokens

MAX_ATTEMPTS = 2  # one call plus a single retry


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


def _is_retryable(exc: httpx.HTTPError) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)  # includes timeouts


class LLMClient:
    """Async client for the model gateway. Timeout lives on the httpx client; one retry."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> LLMResponse:
        payload: dict[str, Any] = {"messages": messages}
        if tools:
            payload["tools"] = tools

        last_error: httpx.HTTPError | None = None
        for _ in range(MAX_ATTEMPTS):
            record_llm_call()
            try:
                response = await self._client.post("/v1/chat", json=payload)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                last_error = exc
                if not _is_retryable(exc):
                    break
                continue
            return self._parse(response.json())
        raise UpstreamError(f"model gateway failed: {last_error!r}") from last_error

    @staticmethod
    def _parse(body: dict[str, Any]) -> LLMResponse:
        message = body["message"]
        total_tokens = int(body["usage"]["total_tokens"])
        record_tokens(total_tokens)
        return LLMResponse(
            content=message.get("content") or "",
            tool_calls=[
                ToolCall(id=c["id"], name=c["name"], arguments=c.get("arguments") or {})
                for c in message.get("tool_calls") or []
            ],
            total_tokens=total_tokens,
        )
