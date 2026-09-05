-- ============================================================
-- Track 4 PostgreSQL Schema
-- Steps 19-20: Create tables, constraints, and indexes
--
-- Run with: psql -U postgres -d razorpay_recon -f schema.sql
-- ============================================================

-- Create database (run separately as superuser if needed)
-- CREATE DATABASE razorpay_recon;

-- ── Extensions ─────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- ── Merchants ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS merchants (
    merchant_id         VARCHAR(20)     PRIMARY KEY,
    merchant_name       TEXT            NOT NULL,
    industry            VARCHAR(50),
    gstin               VARCHAR(15)     UNIQUE,
    state               VARCHAR(50),
    city                VARCHAR(50),
    bank_account_number VARCHAR(20),
    bank_ifsc           VARCHAR(11),
    bank_name           VARCHAR(100),
    currency            CHAR(3)         NOT NULL DEFAULT 'INR',
    status              VARCHAR(20)     NOT NULL DEFAULT 'ACTIVE',
    -- Lineage
    lineage_source              VARCHAR(50),
    lineage_source_record_id    VARCHAR(100),
    lineage_source_file_id      VARCHAR(200),
    lineage_source_row          INTEGER,
    lineage_ingested_at         TIMESTAMPTZ,
    lineage_normalizer_ver      VARCHAR(20),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);


-- ── Customers ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customers (
    customer_id         VARCHAR(20)     PRIMARY KEY,
    merchant_id         VARCHAR(20)     NOT NULL REFERENCES merchants(merchant_id),
    name                TEXT,
    email               TEXT,
    phone               VARCHAR(20),
    city                VARCHAR(50),
    state               VARCHAR(50),
    -- Lineage
    lineage_source              VARCHAR(50),
    lineage_source_record_id    VARCHAR(100),
    lineage_source_file_id      VARCHAR(200),
    lineage_source_row          INTEGER,
    lineage_ingested_at         TIMESTAMPTZ,
    lineage_normalizer_ver      VARCHAR(20),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customers_merchant ON customers(merchant_id);


-- ── Orders ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    order_id            VARCHAR(20)     PRIMARY KEY,
    merchant_id         VARCHAR(20)     NOT NULL REFERENCES merchants(merchant_id),
    customer_id         VARCHAR(20)     REFERENCES customers(customer_id),
    order_date          TIMESTAMPTZ,
    subtotal            NUMERIC(15,2),
    discount_rate       NUMERIC(5,4),
    discount            NUMERIC(15,2),
    taxable_amount      NUMERIC(15,2)   NOT NULL,
    cgst                NUMERIC(15,2)   NOT NULL DEFAULT 0,
    sgst                NUMERIC(15,2)   NOT NULL DEFAULT 0,
    igst                NUMERIC(15,2)   NOT NULL DEFAULT 0,
    total_tax           NUMERIC(15,2)   NOT NULL,
    total_amount        NUMERIC(15,2)   NOT NULL CHECK (total_amount >= 0),
    currency            CHAR(3)         NOT NULL DEFAULT 'INR',
    status              VARCHAR(20)     NOT NULL,
    seller_state        VARCHAR(50),
    buyer_state         VARCHAR(50),
    -- Normalized lookup key
    canonical_order_id  VARCHAR(50),
    -- Lineage
    lineage_source              VARCHAR(50),
    lineage_source_record_id    VARCHAR(100),
    lineage_source_file_id      VARCHAR(200),
    lineage_source_row          INTEGER,
    lineage_ingested_at         TIMESTAMPTZ,
    lineage_normalizer_ver      VARCHAR(20),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    -- Constraints
    CONSTRAINT chk_order_total CHECK (total_amount = taxable_amount + total_tax),
    CONSTRAINT chk_order_tax   CHECK (total_tax = cgst + sgst + igst)
);

CREATE INDEX IF NOT EXISTS idx_orders_merchant  ON orders(merchant_id);
CREATE INDEX IF NOT EXISTS idx_orders_customer  ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_date      ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_status    ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_canonical ON orders(canonical_order_id);


-- ── Invoices ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS invoices (
    invoice_id          VARCHAR(20)     PRIMARY KEY,
    order_id            VARCHAR(20)     NOT NULL REFERENCES orders(order_id),
    merchant_id         VARCHAR(20)     NOT NULL REFERENCES merchants(merchant_id),
    customer_id         VARCHAR(20)     REFERENCES customers(customer_id),
    invoice_number      VARCHAR(100)    NOT NULL UNIQUE,
    invoice_date        TIMESTAMPTZ,
    due_date            DATE,
    subtotal            NUMERIC(15,2),
    discount            NUMERIC(15,2),
    taxable_amount      NUMERIC(15,2)   NOT NULL,
    cgst                NUMERIC(15,2)   NOT NULL DEFAULT 0,
    sgst                NUMERIC(15,2)   NOT NULL DEFAULT 0,
    igst                NUMERIC(15,2)   NOT NULL DEFAULT 0,
    total_tax           NUMERIC(15,2)   NOT NULL,
    total_amount        NUMERIC(15,2)   NOT NULL CHECK (total_amount >= 0),
    currency            CHAR(3)         NOT NULL DEFAULT 'INR',
    seller_gstin        VARCHAR(15),
    seller_state        VARCHAR(50),
    buyer_state         VARCHAR(50),
    status              VARCHAR(20),
    -- Normalized
    normalized_invoice_number VARCHAR(100),
    -- Lineage
    lineage_source              VARCHAR(50),
    lineage_source_record_id    VARCHAR(100),
    lineage_source_file_id      VARCHAR(200),
    lineage_source_row          INTEGER,
    lineage_ingested_at         TIMESTAMPTZ,
    lineage_normalizer_ver      VARCHAR(20),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_invoices_order        ON invoices(order_id);
CREATE INDEX IF NOT EXISTS idx_invoices_merchant     ON invoices(merchant_id);
CREATE INDEX IF NOT EXISTS idx_invoices_date         ON invoices(invoice_date);
CREATE INDEX IF NOT EXISTS idx_invoices_inv_num      ON invoices(invoice_number);
CREATE INDEX IF NOT EXISTS idx_invoices_norm_inv_num ON invoices(normalized_invoice_number);


-- ── GST Records ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gst_records (
    gst_record_id       VARCHAR(20)     PRIMARY KEY,
    invoice_id          VARCHAR(20)     NOT NULL REFERENCES invoices(invoice_id),
    invoice_number      VARCHAR(100),
    merchant_id         VARCHAR(20)     NOT NULL REFERENCES merchants(merchant_id),
    seller_gstin        VARCHAR(15)     NOT NULL,
    buyer_gstin         VARCHAR(15),
    supply_type         VARCHAR(20)     NOT NULL,
    taxable_amount      NUMERIC(15,2)   NOT NULL,
    cgst                NUMERIC(15,2)   NOT NULL DEFAULT 0,
    sgst                NUMERIC(15,2)   NOT NULL DEFAULT 0,
    igst                NUMERIC(15,2)   NOT NULL DEFAULT 0,
    total_tax           NUMERIC(15,2)   NOT NULL,
    total_amount        NUMERIC(15,2)   NOT NULL,
    filing_period       VARCHAR(10),
    return_type         VARCHAR(20),
    status              VARCHAR(20),
    -- Lineage
    lineage_source              VARCHAR(50),
    lineage_source_record_id    VARCHAR(100),
    lineage_source_file_id      VARCHAR(200),
    lineage_source_row          INTEGER,
    lineage_ingested_at         TIMESTAMPTZ,
    lineage_normalizer_ver      VARCHAR(20),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gst_invoice   ON gst_records(invoice_id);
CREATE INDEX IF NOT EXISTS idx_gst_merchant  ON gst_records(merchant_id);
CREATE INDEX IF NOT EXISTS idx_gst_gstin     ON gst_records(seller_gstin);
CREATE INDEX IF NOT EXISTS idx_gst_period    ON gst_records(filing_period);


-- ── Payments ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS payments (
    payment_id          VARCHAR(20)     PRIMARY KEY,
    order_id            VARCHAR(20)     NOT NULL REFERENCES orders(order_id),
    merchant_id         VARCHAR(20)     NOT NULL REFERENCES merchants(merchant_id),
    customer_id         VARCHAR(20)     REFERENCES customers(customer_id),
    amount              NUMERIC(15,2)   NOT NULL CHECK (amount >= 0),
    currency            CHAR(3)         NOT NULL DEFAULT 'INR',
    payment_method      VARCHAR(20),
    status              VARCHAR(20)     NOT NULL,
    gateway             VARCHAR(50),
    gateway_reference   VARCHAR(100)    UNIQUE,
    utr                 VARCHAR(50),
    payment_date        TIMESTAMPTZ,
    captured_at         TIMESTAMPTZ,
    card_network        VARCHAR(20),
    card_last4          CHAR(4),
    card_type           VARCHAR(20),
    upi_app             VARCHAR(50),
    upi_id              VARCHAR(100),
    wallet_provider     VARCHAR(50),
    bank_name           VARCHAR(100),
    -- Normalized lookup key
    canonical_payment_id VARCHAR(50),
    -- Lineage
    lineage_source              VARCHAR(50),
    lineage_source_record_id    VARCHAR(100),
    lineage_source_file_id      VARCHAR(200),
    lineage_source_row          INTEGER,
    lineage_ingested_at         TIMESTAMPTZ,
    lineage_normalizer_ver      VARCHAR(20),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payments_order     ON payments(order_id);
CREATE INDEX IF NOT EXISTS idx_payments_merchant  ON payments(merchant_id);
CREATE INDEX IF NOT EXISTS idx_payments_date      ON payments(payment_date);
CREATE INDEX IF NOT EXISTS idx_payments_status    ON payments(status);
CREATE INDEX IF NOT EXISTS idx_payments_utr       ON payments(utr);
CREATE INDEX IF NOT EXISTS idx_payments_canonical ON payments(canonical_payment_id);


-- ── Fees ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fees (
    fee_id              VARCHAR(20)     PRIMARY KEY,
    payment_id          VARCHAR(20)     NOT NULL REFERENCES payments(payment_id),
    merchant_id         VARCHAR(20)     NOT NULL REFERENCES merchants(merchant_id),
    fee_type            VARCHAR(50),
    fee_amount          NUMERIC(15,2)   NOT NULL CHECK (fee_amount >= 0),
    tax_amount          NUMERIC(15,2)   NOT NULL CHECK (tax_amount >= 0),
    total_fee           NUMERIC(15,2)   NOT NULL,
    currency            CHAR(3)         NOT NULL DEFAULT 'INR',
    payment_method      VARCHAR(20),
    -- Lineage
    lineage_source              VARCHAR(50),
    lineage_source_record_id    VARCHAR(100),
    lineage_source_file_id      VARCHAR(200),
    lineage_source_row          INTEGER,
    lineage_ingested_at         TIMESTAMPTZ,
    lineage_normalizer_ver      VARCHAR(20),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fees_payment  ON fees(payment_id);
CREATE INDEX IF NOT EXISTS idx_fees_merchant ON fees(merchant_id);


-- ── Refunds ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS refunds (
    refund_id           VARCHAR(20)     PRIMARY KEY,
    payment_id          VARCHAR(20)     NOT NULL REFERENCES payments(payment_id),
    order_id            VARCHAR(20)     NOT NULL REFERENCES orders(order_id),
    merchant_id         VARCHAR(20)     NOT NULL REFERENCES merchants(merchant_id),
    refund_amount       NUMERIC(15,2)   NOT NULL CHECK (refund_amount >= 0),
    refund_type         VARCHAR(20),
    reason              TEXT,
    status              VARCHAR(20),
    refund_date         TIMESTAMPTZ,
    currency            CHAR(3)         NOT NULL DEFAULT 'INR',
    -- Lineage
    lineage_source              VARCHAR(50),
    lineage_source_record_id    VARCHAR(100),
    lineage_source_file_id      VARCHAR(200),
    lineage_source_row          INTEGER,
    lineage_ingested_at         TIMESTAMPTZ,
    lineage_normalizer_ver      VARCHAR(20),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_refunds_payment  ON refunds(payment_id);
CREATE INDEX IF NOT EXISTS idx_refunds_order    ON refunds(order_id);
CREATE INDEX IF NOT EXISTS idx_refunds_merchant ON refunds(merchant_id);
CREATE INDEX IF NOT EXISTS idx_refunds_date     ON refunds(refund_date);


-- ── Settlements ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS settlements (
    settlement_id       VARCHAR(20)     PRIMARY KEY,
    merchant_id         VARCHAR(20)     NOT NULL REFERENCES merchants(merchant_id),
    settlement_date     TIMESTAMPTZ,
    gross_amount        NUMERIC(15,2)   NOT NULL,
    total_fees          NUMERIC(15,2)   NOT NULL DEFAULT 0,
    total_fee_tax       NUMERIC(15,2)   NOT NULL DEFAULT 0,
    total_refunds       NUMERIC(15,2)   NOT NULL DEFAULT 0,
    total_adjustments   NUMERIC(15,2)   NOT NULL DEFAULT 0,
    net_amount          NUMERIC(15,2)   NOT NULL,
    currency            CHAR(3)         NOT NULL DEFAULT 'INR',
    utr                 VARCHAR(50)     UNIQUE,
    status              VARCHAR(20),
    payment_count       INTEGER,
    -- Normalized lookup key
    canonical_settlement_id VARCHAR(50),
    -- Lineage
    lineage_source              VARCHAR(50),
    lineage_source_record_id    VARCHAR(100),
    lineage_source_file_id      VARCHAR(200),
    lineage_source_row          INTEGER,
    lineage_ingested_at         TIMESTAMPTZ,
    lineage_normalizer_ver      VARCHAR(20),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_settlements_merchant  ON settlements(merchant_id);
CREATE INDEX IF NOT EXISTS idx_settlements_date      ON settlements(settlement_date);
CREATE INDEX IF NOT EXISTS idx_settlements_utr       ON settlements(utr);
CREATE INDEX IF NOT EXISTS idx_settlements_canonical ON settlements(canonical_settlement_id);


-- ── Settlement-Payment Links ──────────────────────────────────
CREATE TABLE IF NOT EXISTS settlement_payments (
    id                  SERIAL          PRIMARY KEY,
    settlement_id       VARCHAR(20)     NOT NULL REFERENCES settlements(settlement_id),
    payment_id          VARCHAR(20)     NOT NULL REFERENCES payments(payment_id),
    allocated_amount    NUMERIC(15,2),
    UNIQUE (settlement_id, payment_id)
);

CREATE INDEX IF NOT EXISTS idx_stlpay_settlement ON settlement_payments(settlement_id);
CREATE INDEX IF NOT EXISTS idx_stlpay_payment    ON settlement_payments(payment_id);


-- ── Bank Records ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bank_records (
    bank_record_id      VARCHAR(30)     PRIMARY KEY,  -- Allow _DUP suffix
    merchant_id         VARCHAR(20)     NOT NULL REFERENCES merchants(merchant_id),
    account_number      VARCHAR(30),
    bank_name           VARCHAR(100),
    transaction_date    DATE,
    value_date          DATE,
    amount              NUMERIC(15,2)   NOT NULL CHECK (amount >= 0),
    currency            CHAR(3)         NOT NULL DEFAULT 'INR',
    transaction_type    VARCHAR(10)     NOT NULL CHECK (transaction_type IN ('CREDIT', 'DEBIT')),
    reference           VARCHAR(100),
    description         TEXT,
    description_normalized TEXT,
    settlement_id       VARCHAR(20)     REFERENCES settlements(settlement_id),
    balance_after       NUMERIC(15,2),
    category            VARCHAR(50),
    -- Normalized keys for matching
    canonical_reference VARCHAR(100),
    -- Lineage
    lineage_source              VARCHAR(50),
    lineage_source_record_id    VARCHAR(100),
    lineage_source_file_id      VARCHAR(200),
    lineage_source_row          INTEGER,
    lineage_ingested_at         TIMESTAMPTZ,
    lineage_normalizer_ver      VARCHAR(20),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bank_merchant    ON bank_records(merchant_id);
CREATE INDEX IF NOT EXISTS idx_bank_date        ON bank_records(transaction_date);
CREATE INDEX IF NOT EXISTS idx_bank_settlement  ON bank_records(settlement_id);
CREATE INDEX IF NOT EXISTS idx_bank_reference   ON bank_records(reference);
CREATE INDEX IF NOT EXISTS idx_bank_canonical   ON bank_records(canonical_reference);


-- ── Books / Ledger ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS books (
    entry_id            VARCHAR(30)     PRIMARY KEY,  -- Allow _DUP suffix
    merchant_id         VARCHAR(20)     NOT NULL REFERENCES merchants(merchant_id),
    entry_date          DATE,
    account_code        VARCHAR(10),
    account_name        VARCHAR(100),
    debit               NUMERIC(15,2)   NOT NULL DEFAULT 0 CHECK (debit >= 0),
    credit              NUMERIC(15,2)   NOT NULL DEFAULT 0 CHECK (credit >= 0),
    reference_type      VARCHAR(30),
    reference_id        VARCHAR(30),
    description         TEXT,
    entry_type          VARCHAR(30),
    -- Normalized
    canonical_reference_id VARCHAR(50),
    -- Lineage
    lineage_source              VARCHAR(50),
    lineage_source_record_id    VARCHAR(100),
    lineage_source_file_id      VARCHAR(200),
    lineage_source_row          INTEGER,
    lineage_ingested_at         TIMESTAMPTZ,
    lineage_normalizer_ver      VARCHAR(20),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_book_debit_credit CHECK (NOT (debit > 0 AND credit > 0))
);

CREATE INDEX IF NOT EXISTS idx_books_merchant   ON books(merchant_id);
CREATE INDEX IF NOT EXISTS idx_books_date       ON books(entry_date);
CREATE INDEX IF NOT EXISTS idx_books_ref        ON books(reference_id);
CREATE INDEX IF NOT EXISTS idx_books_canonical  ON books(canonical_reference_id);
CREATE INDEX IF NOT EXISTS idx_books_account    ON books(account_code);


-- ── Adjustments ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS adjustments (
    adjustment_id       VARCHAR(20)     PRIMARY KEY,
    settlement_id       VARCHAR(20)     NOT NULL REFERENCES settlements(settlement_id),
    merchant_id         VARCHAR(20)     NOT NULL REFERENCES merchants(merchant_id),
    adjustment_type     VARCHAR(50),
    amount              NUMERIC(15,2)   NOT NULL,
    direction           VARCHAR(10)     CHECK (direction IN ('CREDIT', 'DEBIT')),
    reason              TEXT,
    adjustment_date     TIMESTAMPTZ,
    currency            CHAR(3)         NOT NULL DEFAULT 'INR',
    status              VARCHAR(20),
    -- Lineage
    lineage_source              VARCHAR(50),
    lineage_source_record_id    VARCHAR(100),
    lineage_source_file_id      VARCHAR(200),
    lineage_source_row          INTEGER,
    lineage_ingested_at         TIMESTAMPTZ,
    lineage_normalizer_ver      VARCHAR(20),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_adj_settlement ON adjustments(settlement_id);
CREATE INDEX IF NOT EXISTS idx_adj_merchant   ON adjustments(merchant_id);
CREATE INDEX IF NOT EXISTS idx_adj_date       ON adjustments(adjustment_date);


-- ── Quarantine Table ─────────────────────────────────────────
-- Stores records that failed validation/parsing (Step 18)
CREATE TABLE IF NOT EXISTS quarantine_records (
    id                  SERIAL          PRIMARY KEY,
    source              VARCHAR(50)     NOT NULL,
    source_record_id    VARCHAR(200),
    source_file_id      VARCHAR(200),
    source_row_number   INTEGER,
    entity_type         VARCHAR(50),
    raw_record          JSONB,
    error_type          VARCHAR(100)    NOT NULL,
    error_message       TEXT            NOT NULL,
    failed_field        VARCHAR(100),
    quarantined_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    resolved            BOOLEAN         NOT NULL DEFAULT FALSE,
    resolved_at         TIMESTAMPTZ,
    resolution_note     TEXT
);

CREATE INDEX IF NOT EXISTS idx_quarantine_source     ON quarantine_records(source);
CREATE INDEX IF NOT EXISTS idx_quarantine_error_type ON quarantine_records(error_type);
CREATE INDEX IF NOT EXISTS idx_quarantine_resolved   ON quarantine_records(resolved);
CREATE INDEX IF NOT EXISTS idx_quarantine_date       ON quarantine_records(quarantined_at);


-- ── Normalization Source Map ──────────────────────────────────
-- Idempotency table: tracks every (source, source_record_id) processed
-- Used for cross-batch deduplication (Step 19)
CREATE TABLE IF NOT EXISTS normalization_source_map (
    id                  SERIAL          PRIMARY KEY,
    source              VARCHAR(50)     NOT NULL,
    source_record_id    VARCHAR(200)    NOT NULL,
    entity_type         VARCHAR(50)     NOT NULL,
    canonical_record_id VARCHAR(50)     NOT NULL,
    source_file_id      VARCHAR(200),
    ingested_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (source, source_record_id)
);

CREATE INDEX IF NOT EXISTS idx_srcmap_source   ON normalization_source_map(source);
CREATE INDEX IF NOT EXISTS idx_srcmap_entity   ON normalization_source_map(entity_type);
CREATE INDEX IF NOT EXISTS idx_srcmap_ingested ON normalization_source_map(ingested_at);
