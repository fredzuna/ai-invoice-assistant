ALTER TABLE credits
    ADD COLUMN idempotency_key text;

CREATE UNIQUE INDEX credits_tenant_idempotency_key_uq
    ON credits (tenant_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;
