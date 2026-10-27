-- Installed in "public" explicitly so it survives per-schema setups (e.g. test schemas).
CREATE EXTENSION IF NOT EXISTS vector SCHEMA public;

CREATE TABLE tenants (
    id   text PRIMARY KEY,
    name text NOT NULL
);

CREATE TABLE documents (
    id           text PRIMARY KEY,
    tenant_id    text NOT NULL REFERENCES tenants (id),
    kind         text NOT NULL,
    title        text NOT NULL,
    body         text NOT NULL,
    content_hash text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX documents_tenant_idx ON documents (tenant_id);

-- tenant_id is denormalised onto chunks so retrieval filters without a join.
-- Search is an exact scan of one tenant's rows (~1k each), so no ANN index is needed.
CREATE TABLE chunks (
    id          bigserial PRIMARY KEY,
    document_id text NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    tenant_id   text NOT NULL REFERENCES tenants (id),
    chunk_index int  NOT NULL,
    content     text NOT NULL,
    embedding   vector(512) NOT NULL,
    UNIQUE (document_id, chunk_index)
);
CREATE INDEX chunks_tenant_idx ON chunks (tenant_id);

CREATE TABLE invoices (
    id              text PRIMARY KEY,
    tenant_id       text NOT NULL REFERENCES tenants (id),
    customer_name   text NOT NULL,
    amount_cents    int  NOT NULL CHECK (amount_cents > 0),
    credited_cents  int  NOT NULL DEFAULT 0 CHECK (credited_cents >= 0),
    currency        text NOT NULL,
    status          text NOT NULL CHECK (status IN ('draft', 'open', 'paid', 'overdue', 'void')),
    issued_date     date NOT NULL,
    due_date        date NOT NULL
);
CREATE INDEX invoices_tenant_idx ON invoices (tenant_id);

CREATE TABLE credits (
    id           bigserial PRIMARY KEY,
    invoice_id   text NOT NULL REFERENCES invoices (id),
    tenant_id    text NOT NULL REFERENCES tenants (id),
    amount_cents int  NOT NULL CHECK (amount_cents > 0),
    reason       text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now()
);
