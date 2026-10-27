"""Per-request instrumentation, exposed as response headers.

Clients call record_* while a request is in flight; the middleware owns the counters
(via a ContextVar, so they follow the request across asyncio.gather) and writes them
into X-LLM-Calls, X-Embed-Calls, X-Tokens and X-Elapsed-Ms.
"""

import time
from contextvars import ContextVar
from dataclasses import dataclass

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


@dataclass
class RequestMetrics:
    llm_calls: int = 0
    embed_calls: int = 0
    tokens: int = 0


_current: ContextVar[RequestMetrics | None] = ContextVar("request_metrics", default=None)


def record_llm_call() -> None:
    metrics = _current.get()
    if metrics is not None:
        metrics.llm_calls += 1


def record_embed_call() -> None:
    metrics = _current.get()
    if metrics is not None:
        metrics.embed_calls += 1


def record_tokens(count: int) -> None:
    metrics = _current.get()
    if metrics is not None:
        metrics.tokens += count


class MetricsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        metrics = RequestMetrics()
        token = _current.set(metrics)
        started = time.perf_counter()

        async def send_with_metrics(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-LLM-Calls"] = str(metrics.llm_calls)
                headers["X-Embed-Calls"] = str(metrics.embed_calls)
                headers["X-Tokens"] = str(metrics.tokens)
                headers["X-Elapsed-Ms"] = str(round((time.perf_counter() - started) * 1000))
            await send(message)

        try:
            await self.app(scope, receive, send_with_metrics)
        finally:
            _current.reset(token)
