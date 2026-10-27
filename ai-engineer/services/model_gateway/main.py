"""Model gateway simulation.

Pretends to be an LLM provider: ~800 ms per call, deterministic rule-based
replies, and token counts in every response. No real model is involved.
"""

import asyncio
import json
import os
import re
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

LATENCY_S = int(os.environ.get("GATEWAY_LATENCY_MS", "800")) / 1000

INVOICE_RE = re.compile(r"\bINV-[A-Z0-9]+-\d{4}\b")
AMOUNT_RE = re.compile(r"\$\s?(\d+(?:\.\d{1,2})?)")
FIRST_EXCERPT_RE = re.compile(r"\[1\][^\n]*\n(.*?)(?:\n\[2\]|</retrieved_data>)", re.DOTALL)
QUESTION_PREFIX = "Customer question:\n"

app = FastAPI(title="model-gateway")


class Message(BaseModel):
    role: str
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class ChatRequest(BaseModel):
    messages: list[Message]
    tools: list[dict[str, Any]] | None = None


def _question(messages: list[Message]) -> str:
    for message in reversed(messages):
        if message.role == "user" and (message.content or "").startswith(QUESTION_PREFIX):
            return message.content[len(QUESTION_PREFIX) :].strip()
    return ""


def _context_answer(messages: list[Message]) -> str:
    for message in messages:
        if message.role == "user" and "<retrieved_data>" in (message.content or ""):
            match = FIRST_EXCERPT_RE.search(message.content)
            if match:
                excerpt = " ".join(match.group(1).split())[:320]
                return f"Based on our documentation: {excerpt}"
    return "I could not find anything relevant in the knowledge base for this question."


def _summarize_tool_results(tool_messages: list[Message]) -> str:
    parts = []
    for message in tool_messages:
        result = json.loads(message.content or "{}")
        if result.get("error"):
            parts.append(f"I could not complete the action: {result['error']}")
        elif message.name == "lookup_invoice":
            inv = result["invoice"]
            parts.append(
                f"Invoice {inv['id']} is {inv['status']}: total {inv['amount_cents'] / 100:.2f} "
                f"{inv['currency']}, due {inv['due_date']}."
            )
        elif message.name == "issue_credit":
            credit = result["credit"]
            parts.append(
                f"Issued a credit of {credit['amount_cents'] / 100:.2f} on invoice "
                f"{credit['invoice_id']}."
            )
    return " ".join(parts)


def decide(messages: list[Message], available_tools: set[str]) -> dict[str, Any]:
    """Return the assistant message for this conversation state."""
    question = _question(messages)
    tool_messages = [m for m in messages if m.role == "tool"]
    called = {m.name for m in tool_messages}
    invoice_ids = list(dict.fromkeys(INVOICE_RE.findall(question)))

    if "lookup_invoice" in available_tools and invoice_ids:
        if "lookup_invoice" not in called:
            calls = [
                {"id": f"call_{i}", "name": "lookup_invoice", "arguments": {"invoice_id": inv}}
                for i, inv in enumerate(invoice_ids)
            ]
            return {"role": "assistant", "content": "", "tool_calls": calls}
    if "lookup_invoice" in available_tools and not invoice_ids and not tool_messages:
        return {
            "role": "assistant",
            "content": "Please provide the invoice id so I can look it up.",
        }

    if "issue_credit" in available_tools and "issue_credit" not in called:
        amount = AMOUNT_RE.search(question)
        if invoice_ids and amount:
            arguments = {
                "invoice_id": invoice_ids[0],
                "amount_cents": round(float(amount.group(1)) * 100),
                "reason": "Credit requested through a support ticket",
                "confirmed": "confirm" in question.lower(),
            }
            call = {"id": "call_credit", "name": "issue_credit", "arguments": arguments}
            return {"role": "assistant", "content": "", "tool_calls": [call]}
        return {
            "role": "assistant",
            "content": "Please provide the invoice id and confirm the specific credit amount.",
        }

    if tool_messages:
        return {"role": "assistant", "content": _summarize_tool_results(tool_messages)}
    return {"role": "assistant", "content": _context_answer(messages)}


def _tokens(text: str) -> int:
    return max(1, len(text) // 4)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/chat")
async def chat(body: ChatRequest) -> dict[str, Any]:
    await asyncio.sleep(LATENCY_S)
    available_tools = {
        tool["function"]["name"] for tool in body.tools or []
    }
    message = decide(body.messages, available_tools=available_tools)
    prompt_tokens = sum(_tokens(json.dumps(m.model_dump(exclude_none=True))) for m in body.messages)
    prompt_tokens += _tokens(json.dumps(body.tools)) if body.tools else 0
    completion_tokens = _tokens(json.dumps(message))
    return {
        "message": message,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }
