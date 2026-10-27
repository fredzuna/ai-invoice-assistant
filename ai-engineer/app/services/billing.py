from typing import Any

from psycopg_pool import AsyncConnectionPool

MAX_CREDIT_CENTS = 50_000


class BillingService:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def issue_credit(
        self,
        *,
        tenant_id: str,
        invoice_id: str,
        amount_cents: int,
        reason: str,
        confirmed: bool,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if not confirmed:
            return {"error": "credit not issued: the customer has not confirmed it"}
        if amount_cents > MAX_CREDIT_CENTS:
            return {"error": f"credit exceeds the maximum of {MAX_CREDIT_CENTS} minor units"}

        async with self._pool.connection() as conn, conn.transaction():
            cursor = await conn.execute(
                "SELECT * FROM invoices WHERE id = %s AND tenant_id = %s FOR UPDATE",
                (invoice_id, tenant_id),
            )
            invoice = await cursor.fetchone()
            if invoice is None:
                return {"error": f"invoice {invoice_id} not found"}
            if idempotency_key is not None:
                cursor = await conn.execute(
                    "SELECT credits.invoice_id, credits.amount_cents, invoices.currency "
                    "FROM credits JOIN invoices ON invoices.id = credits.invoice_id "
                    "WHERE credits.tenant_id = %s AND credits.idempotency_key = %s",
                    (tenant_id, idempotency_key),
                )
                existing_credit = await cursor.fetchone()
                if existing_credit is not None:
                    return {
                        "credit": {
                            "invoice_id": existing_credit["invoice_id"],
                            "amount_cents": existing_credit["amount_cents"],
                            "currency": existing_credit["currency"],
                        }
                    }
            if invoice["status"] == "void":
                return {"error": f"invoice {invoice_id} is void"}
            remaining = invoice["amount_cents"] - invoice["credited_cents"]
            if amount_cents > remaining:
                return {"error": f"credit exceeds the creditable balance ({remaining})"}
            cursor = await conn.execute(
                "INSERT INTO credits "
                "(invoice_id, tenant_id, amount_cents, reason, idempotency_key) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (tenant_id, idempotency_key) "
                "WHERE idempotency_key IS NOT NULL DO NOTHING "
                "RETURNING id",
                (invoice_id, tenant_id, amount_cents, reason, idempotency_key),
            )
            inserted_credit = await cursor.fetchone()
            if inserted_credit is None:
                cursor = await conn.execute(
                    "SELECT credits.invoice_id, credits.amount_cents, invoices.currency "
                    "FROM credits JOIN invoices ON invoices.id = credits.invoice_id "
                    "WHERE credits.tenant_id = %s AND credits.idempotency_key = %s",
                    (tenant_id, idempotency_key),
                )
                existing_credit = await cursor.fetchone()
                if existing_credit is None:
                    raise RuntimeError(
                        "credit idempotency conflict occurred but no matching credit exists"
                    )
                return {
                    "credit": {
                        "invoice_id": existing_credit["invoice_id"],
                        "amount_cents": existing_credit["amount_cents"],
                        "currency": existing_credit["currency"],
                    }
                }
            await conn.execute(
                "UPDATE invoices SET credited_cents = credited_cents + %s WHERE id = %s",
                (amount_cents, invoice_id),
            )
        return {
            "credit": {
                "invoice_id": invoice_id,
                "amount_cents": amount_cents,
                "currency": invoice["currency"],
            }
        }
