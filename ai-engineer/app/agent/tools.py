"""Tools the agent can call. The tenant always comes from the request, never from the model:
every query is scoped by it, so an invoice from another tenant looks like "not found"."""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.services.billing import BillingService


class LookupInvoiceArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice_id: str = Field(pattern=r"^INV-[A-Z0-9]+-\d{4}$", description="Invoice id")


class IssueCreditArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice_id: str = Field(pattern=r"^INV-[A-Z0-9]+-\d{4}$", description="Invoice id")
    amount_cents: int = Field(gt=0, description="Credit amount in minor units")
    reason: str = Field(min_length=3, max_length=200)
    confirmed: bool = Field(default=False, description="True only if the customer confirmed")


def _invoice_view(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "customer_name": row["customer_name"],
        "status": row["status"],
        "amount_cents": row["amount_cents"],
        "credited_cents": row["credited_cents"],
        "currency": row["currency"],
        "issued_date": row["issued_date"].isoformat(),
        "due_date": row["due_date"].isoformat(),
    }


async def lookup_invoice(
    pool: AsyncConnectionPool, tenant_id: str, args: LookupInvoiceArgs
) -> dict[str, Any]:
    async with pool.connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM invoices WHERE id = %s AND tenant_id = %s",
            (args.invoice_id, tenant_id),
        )
        row = await cursor.fetchone()
    if row is None:
        return {"error": f"invoice {args.invoice_id} not found"}
    return {"invoice": _invoice_view(row)}


ToolFunc = Callable[..., Awaitable[dict[str, Any]]]


async def issue_credit(
    billing_service: BillingService,
    tenant_id: str,
    args: IssueCreditArgs,
    idempotency_key: str | None,
) -> dict[str, Any]:
    return await billing_service.issue_credit(
        tenant_id=tenant_id,
        invoice_id=args.invoice_id,
        amount_cents=args.amount_cents,
        reason=args.reason,
        confirmed=args.confirmed,
        idempotency_key=idempotency_key,
    )


TOOLS: dict[str, tuple[type[BaseModel], ToolFunc, str]] = {
    "lookup_invoice": (
        LookupInvoiceArgs,
        lookup_invoice,
        "Look up an invoice of the current tenant by id.",
    ),
    "issue_credit": (
        IssueCreditArgs,
        issue_credit,
        "Issue a credit on an invoice of the current tenant. Requires customer confirmation.",
    ),
}


def tool_schemas(names: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
    selected = names if names is not None else tuple(TOOLS)
    schemas: list[dict[str, Any]] = []
    for name in selected:
        if name not in TOOLS:
            continue
        args_model, _, description = TOOLS[name]
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": args_model.model_json_schema(),
                },
            }
        )
    return schemas


async def execute_tool(
    pool: AsyncConnectionPool,
    tenant_id: str,
    name: str,
    arguments: dict[str, Any],
    *,
    billing_service: BillingService,
    idempotency_key: str | None = None,
    allowed_tools: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Validate and run one tool call. Problems come back as {"error": ...} for the model."""
    if name not in TOOLS:
        return {"error": f"unknown tool {name}"}
    if allowed_tools is not None and name not in allowed_tools:
        return {"error": f"tool {name} is not available for this request"}
    args_model, func, _ = TOOLS[name]
    try:
        args = args_model.model_validate(arguments)
    except ValidationError as exc:
        details = exc.errors(include_url=False, include_context=False, include_input=False)
        return {"error": f"invalid arguments: {json.dumps(details)}"}
    if name == "lookup_invoice":
        return await func(pool, tenant_id, args)
    if name == "issue_credit":
        return await func(billing_service, tenant_id, args, idempotency_key)
    raise ValueError(f"Unknown tool: {name}")
