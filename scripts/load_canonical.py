"""
Canonical PostgreSQL Loader — Phase 5
======================================
Loads all canonical normalized JSONL files into PostgreSQL.

Key guarantees:
  - NO FK bypass (no session_replication_role = replica)
  - Strict dependency order (parents before children)
  - Records with unsatisfied FKs are quarantined, not force-loaded
  - ON CONFLICT DO NOTHING for idempotency
  - Transaction per table with rollback on failure
  - Full lineage preserved
  - Clear error reporting

Dependency order:
  merchants → customers → orders → invoices → payments → fees →
  refunds → settlements → settlement_payments → bank_records →
  books → gst_records → adjustments

Usage:
    python scripts/load_canonical.py [--dbname razorpay_recon]
    python scripts/load_canonical.py --dbname razorpay_recon_test
"""

import json
import os
import sys
import argparse
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import execute_values

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NORMALIZED_DIR = os.path.join(PROJECT_ROOT, "data", "normalized")
QUARANTINE_DIR = os.path.join(PROJECT_ROOT, "data", "normalized", "quarantine")

# ── Config ─────────────────────────────────────────────────────────────────
BASE_DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "user":     "postgres",
    "password": "123",
}


def get_db_config(dbname: str) -> dict:
    cfg = BASE_DB_CONFIG.copy()
    cfg["dbname"] = dbname
    return cfg


# ── Helpers ─────────────────────────────────────────────────────────────────

def load_jsonl(path: str) -> list:
    """Load JSONL file, returns list of dicts."""
    records = []
    if not os.path.exists(path):
        return records
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def lineage(record: dict):
    """Extract lineage tuple from _lineage nested dict."""
    L = record.get("_lineage", {})
    return (
        L.get("source"),
        L.get("source_record_id"),
        L.get("source_file_id"),
        L.get("source_row_number"),
        L.get("ingested_at"),
        L.get("normalizer_version"),
    )


def log_quarantine(quar_records: list, entity_type: str, record: dict,
                   reason: str, field: str = None):
    """Add a record to the runtime quarantine list."""
    quar_records.append({
        "quarantined_at": datetime.now(timezone.utc).isoformat(),
        "entity_type": entity_type,
        "source": record.get("_lineage", {}).get("source", "UNKNOWN"),
        "reason": reason,
        "failed_field": field,
        "record_id": record.get(list(record.keys())[0]) if record else None,
        "raw_record": record,
    })


def load_table(conn, table_name: str, records: list, sql: str,
               row_builder, skip_on_fk_error: bool = False) -> tuple:
    """
    Load records into a table within a transaction.
    Returns (inserted_count, error_count).
    """
    if not records:
        return 0, 0

    rows = []
    errors = 0
    for rec in records:
        try:
            row = row_builder(rec)
            rows.append(row)
        except Exception as e:
            errors += 1

    if not rows:
        return 0, errors

    try:
        with conn.cursor() as cur:
            execute_values(cur, sql, rows, page_size=500)
        conn.commit()
        return len(rows), errors
    except psycopg2.errors.ForeignKeyViolation as e:
        conn.rollback()
        if skip_on_fk_error:
            print(f"    [FK ERROR] {table_name}: {e} — skipping batch")
            return 0, len(rows)
        raise
    except Exception as e:
        conn.rollback()
        raise


# ── Per-table loader functions ───────────────────────────────────────────────

def load_merchants(conn, records):
    sql = """
    INSERT INTO merchants (
        merchant_id, merchant_name, industry, gstin, state, city,
        bank_account_number, bank_ifsc, bank_name, currency, status,
        lineage_source, lineage_source_record_id, lineage_source_file_id,
        lineage_source_row, lineage_ingested_at, lineage_normalizer_ver
    ) VALUES %s
    ON CONFLICT (merchant_id) DO NOTHING
    """
    def build(r):
        ls, lsid, lsfid, lsrow, liat, lnv = lineage(r)
        return (
            r.get("merchant_id"), r.get("merchant_name"), r.get("industry"),
            r.get("gstin"), r.get("state"), r.get("city"),
            r.get("bank_account_number"), r.get("bank_ifsc"), r.get("bank_name"),
            r.get("currency", "INR"), r.get("status", "ACTIVE"),
            ls, lsid, lsfid, lsrow, liat, lnv,
        )
    return load_table(conn, "merchants", records, sql, build)


def load_customers(conn, records):
    sql = """
    INSERT INTO customers (
        customer_id, merchant_id, name, email, phone, city, state,
        lineage_source, lineage_source_record_id, lineage_source_file_id,
        lineage_source_row, lineage_ingested_at, lineage_normalizer_ver
    ) VALUES %s
    ON CONFLICT (customer_id) DO NOTHING
    """
    def build(r):
        ls, lsid, lsfid, lsrow, liat, lnv = lineage(r)
        return (
            r.get("customer_id"), r.get("merchant_id"), r.get("name"),
            r.get("email"), r.get("phone"), r.get("city"), r.get("state"),
            ls, lsid, lsfid, lsrow, liat, lnv,
        )
    return load_table(conn, "customers", records, sql, build)


def load_orders(conn, records):
    sql = """
    INSERT INTO orders (
        order_id, merchant_id, customer_id, order_date,
        subtotal, discount_rate, discount, taxable_amount,
        cgst, sgst, igst, total_tax, total_amount, currency, status,
        seller_state, buyer_state, canonical_order_id,
        lineage_source, lineage_source_record_id, lineage_source_file_id,
        lineage_source_row, lineage_ingested_at, lineage_normalizer_ver
    ) VALUES %s
    ON CONFLICT (order_id) DO NOTHING
    """
    def build(r):
        ls, lsid, lsfid, lsrow, liat, lnv = lineage(r)
        return (
            r.get("order_id"), r.get("merchant_id"), r.get("customer_id"),
            r.get("order_date"),
            r.get("subtotal"), r.get("discount_rate"), r.get("discount"),
            r.get("taxable_amount"), r.get("cgst", "0"), r.get("sgst", "0"),
            r.get("igst", "0"), r.get("total_tax"), r.get("total_amount"),
            r.get("currency", "INR"), r.get("status"),
            r.get("seller_state"), r.get("buyer_state"),
            r.get("canonical_order_id", r.get("order_id")),
            ls, lsid, lsfid, lsrow, liat, lnv,
        )
    return load_table(conn, "orders", records, sql, build)


def load_invoices(conn, records):
    sql = """
    INSERT INTO invoices (
        invoice_id, order_id, merchant_id, customer_id,
        invoice_number, invoice_date, due_date,
        subtotal, discount, taxable_amount,
        cgst, sgst, igst, total_tax, total_amount, currency,
        seller_gstin, seller_state, buyer_state, status,
        normalized_invoice_number,
        lineage_source, lineage_source_record_id, lineage_source_file_id,
        lineage_source_row, lineage_ingested_at, lineage_normalizer_ver
    ) VALUES %s
    ON CONFLICT (invoice_id) DO NOTHING
    """
    def build(r):
        ls, lsid, lsfid, lsrow, liat, lnv = lineage(r)
        return (
            r.get("invoice_id"), r.get("order_id"), r.get("merchant_id"),
            r.get("customer_id"), r.get("invoice_number"), r.get("invoice_date"),
            r.get("due_date"), r.get("subtotal"), r.get("discount"),
            r.get("taxable_amount"), r.get("cgst", "0"), r.get("sgst", "0"),
            r.get("igst", "0"), r.get("total_tax"), r.get("total_amount"),
            r.get("currency", "INR"), r.get("seller_gstin"),
            r.get("seller_state"), r.get("buyer_state"), r.get("status"),
            r.get("normalized_invoice_number"),
            ls, lsid, lsfid, lsrow, liat, lnv,
        )
    return load_table(conn, "invoices", records, sql, build)


def load_payments(conn, records):
    sql = """
    INSERT INTO payments (
        payment_id, order_id, merchant_id, customer_id,
        amount, currency, payment_method, status,
        gateway, gateway_reference, utr, payment_date, captured_at,
        card_network, card_last4, card_type, upi_app, upi_id,
        wallet_provider, bank_name, canonical_payment_id,
        lineage_source, lineage_source_record_id, lineage_source_file_id,
        lineage_source_row, lineage_ingested_at, lineage_normalizer_ver
    ) VALUES %s
    ON CONFLICT (payment_id) DO NOTHING
    """
    def build(r):
        ls, lsid, lsfid, lsrow, liat, lnv = lineage(r)
        return (
            r.get("payment_id"), r.get("order_id"), r.get("merchant_id"),
            r.get("customer_id"), r.get("amount"), r.get("currency", "INR"),
            r.get("payment_method"), r.get("status"),
            r.get("gateway"), r.get("gateway_reference"), r.get("utr"),
            r.get("payment_date"), r.get("captured_at"),
            r.get("card_network"), r.get("card_last4"), r.get("card_type"),
            r.get("upi_app"), r.get("upi_id"), r.get("wallet_provider"),
            r.get("bank_name"), r.get("canonical_payment_id", r.get("payment_id")),
            ls, lsid, lsfid, lsrow, liat, lnv,
        )
    return load_table(conn, "payments", records, sql, build)


def load_fees(conn, records):
    sql = """
    INSERT INTO fees (
        fee_id, payment_id, merchant_id,
        fee_type, fee_amount, tax_amount, total_fee, currency, payment_method,
        lineage_source, lineage_source_record_id, lineage_source_file_id,
        lineage_source_row, lineage_ingested_at, lineage_normalizer_ver
    ) VALUES %s
    ON CONFLICT (fee_id) DO NOTHING
    """
    def build(r):
        ls, lsid, lsfid, lsrow, liat, lnv = lineage(r)
        return (
            r.get("fee_id"), r.get("payment_id"), r.get("merchant_id"),
            r.get("fee_type"), r.get("fee_amount"), r.get("tax_amount"),
            r.get("total_fee"), r.get("currency", "INR"), r.get("payment_method"),
            ls, lsid, lsfid, lsrow, liat, lnv,
        )
    return load_table(conn, "fees", records, sql, build)


def load_refunds(conn, records):
    sql = """
    INSERT INTO refunds (
        refund_id, payment_id, order_id, merchant_id,
        refund_amount, refund_type, reason, status, refund_date, currency,
        lineage_source, lineage_source_record_id, lineage_source_file_id,
        lineage_source_row, lineage_ingested_at, lineage_normalizer_ver
    ) VALUES %s
    ON CONFLICT (refund_id) DO NOTHING
    """
    def build(r):
        ls, lsid, lsfid, lsrow, liat, lnv = lineage(r)
        return (
            r.get("refund_id"), r.get("payment_id"), r.get("order_id"),
            r.get("merchant_id"), r.get("refund_amount"), r.get("refund_type"),
            r.get("reason"), r.get("status"), r.get("refund_date"),
            r.get("currency", "INR"),
            ls, lsid, lsfid, lsrow, liat, lnv,
        )
    return load_table(conn, "refunds", records, sql, build)


def load_settlements(conn, records):
    sql = """
    INSERT INTO settlements (
        settlement_id, merchant_id, settlement_date,
        gross_amount, total_fees, total_fee_tax, total_refunds,
        total_adjustments, net_amount, currency, utr, status, payment_count,
        canonical_settlement_id,
        lineage_source, lineage_source_record_id, lineage_source_file_id,
        lineage_source_row, lineage_ingested_at, lineage_normalizer_ver
    ) VALUES %s
    ON CONFLICT (settlement_id) DO NOTHING
    """
    def build(r):
        ls, lsid, lsfid, lsrow, liat, lnv = lineage(r)
        return (
            r.get("settlement_id"), r.get("merchant_id"), r.get("settlement_date"),
            r.get("gross_amount"), r.get("total_fees", "0"),
            r.get("total_fee_tax", "0"), r.get("total_refunds", "0"),
            r.get("total_adjustments", "0"), r.get("net_amount"),
            r.get("currency", "INR"), r.get("utr"), r.get("status"),
            r.get("payment_count"),
            r.get("canonical_settlement_id", r.get("settlement_id")),
            ls, lsid, lsfid, lsrow, liat, lnv,
        )
    return load_table(conn, "settlements", records, sql, build)


def load_settlement_payments(conn, records):
    sql = """
    INSERT INTO settlement_payments (settlement_id, payment_id, allocated_amount)
    VALUES %s
    ON CONFLICT (settlement_id, payment_id) DO NOTHING
    """
    def build(r):
        return (
            r.get("settlement_id"), r.get("payment_id"),
            r.get("allocated_amount"),
        )
    return load_table(conn, "settlement_payments", records, sql, build)


def load_bank_records(conn, records):
    sql = """
    INSERT INTO bank_records (
        bank_record_id, merchant_id, account_number, bank_name,
        transaction_date, value_date, amount, currency, transaction_type,
        reference, description, description_normalized,
        settlement_id, balance_after, category, canonical_reference,
        lineage_source, lineage_source_record_id, lineage_source_file_id,
        lineage_source_row, lineage_ingested_at, lineage_normalizer_ver
    ) VALUES %s
    ON CONFLICT (bank_record_id) DO NOTHING
    """
    def build(r):
        ls, lsid, lsfid, lsrow, liat, lnv = lineage(r)
        return (
            r.get("bank_record_id"), r.get("merchant_id"),
            r.get("account_number"), r.get("bank_name"),
            r.get("transaction_date"), r.get("value_date"),
            r.get("amount"), r.get("currency", "INR"),
            r.get("transaction_type"), r.get("reference"),
            r.get("description"), r.get("description_normalized"),
            r.get("settlement_id"), r.get("balance_after"),
            r.get("category"), r.get("canonical_reference"),
            ls, lsid, lsfid, lsrow, liat, lnv,
        )
    return load_table(conn, "bank_records", records, sql, build)


def load_books(conn, records):
    sql = """
    INSERT INTO books (
        entry_id, merchant_id, entry_date, account_code, account_name,
        debit, credit, reference_type, reference_id, description, entry_type,
        canonical_reference_id,
        lineage_source, lineage_source_record_id, lineage_source_file_id,
        lineage_source_row, lineage_ingested_at, lineage_normalizer_ver
    ) VALUES %s
    ON CONFLICT (entry_id) DO NOTHING
    """
    def build(r):
        ls, lsid, lsfid, lsrow, liat, lnv = lineage(r)
        return (
            r.get("entry_id"), r.get("merchant_id"), r.get("entry_date"),
            r.get("account_code"), r.get("account_name"),
            r.get("debit", "0"), r.get("credit", "0"),
            r.get("reference_type"), r.get("reference_id"),
            r.get("description"), r.get("entry_type"),
            r.get("canonical_reference_id"),
            ls, lsid, lsfid, lsrow, liat, lnv,
        )
    return load_table(conn, "books", records, sql, build)


def load_gst_records(conn, records):
    sql = """
    INSERT INTO gst_records (
        gst_record_id, invoice_id, invoice_number, merchant_id,
        seller_gstin, buyer_gstin, supply_type,
        taxable_amount, cgst, sgst, igst, total_tax, total_amount,
        filing_period, return_type, status,
        lineage_source, lineage_source_record_id, lineage_source_file_id,
        lineage_source_row, lineage_ingested_at, lineage_normalizer_ver
    ) VALUES %s
    ON CONFLICT (gst_record_id) DO NOTHING
    """
    def build(r):
        ls, lsid, lsfid, lsrow, liat, lnv = lineage(r)
        return (
            r.get("gst_record_id"), r.get("invoice_id"), r.get("invoice_number"),
            r.get("merchant_id"), r.get("seller_gstin"), r.get("buyer_gstin"),
            r.get("supply_type"), r.get("taxable_amount"),
            r.get("cgst", "0"), r.get("sgst", "0"), r.get("igst", "0"),
            r.get("total_tax"), r.get("total_amount"),
            r.get("filing_period"), r.get("return_type"), r.get("status"),
            ls, lsid, lsfid, lsrow, liat, lnv,
        )
    return load_table(conn, "gst_records", records, sql, build)


def load_adjustments(conn, records):
    sql = """
    INSERT INTO adjustments (
        adjustment_id, settlement_id, merchant_id,
        adjustment_type, amount, direction, reason, adjustment_date,
        currency, status,
        lineage_source, lineage_source_record_id, lineage_source_file_id,
        lineage_source_row, lineage_ingested_at, lineage_normalizer_ver
    ) VALUES %s
    ON CONFLICT (adjustment_id) DO NOTHING
    """
    def build(r):
        ls, lsid, lsfid, lsrow, liat, lnv = lineage(r)
        return (
            r.get("adjustment_id"), r.get("settlement_id"), r.get("merchant_id"),
            r.get("adjustment_type"), r.get("amount"), r.get("direction"),
            r.get("reason"), r.get("adjustment_date"),
            r.get("currency", "INR"), r.get("status"),
            ls, lsid, lsfid, lsrow, liat, lnv,
        )
    return load_table(conn, "adjustments", records, sql, build)


def load_quarantine_records(conn, records):
    """Load quarantine records into the DB quarantine table."""
    if not records:
        return 0
    sql = """
    INSERT INTO quarantine_records (
        source, source_record_id, source_file_id, source_row_number,
        entity_type, raw_record, error_type, error_message, failed_field
    ) VALUES %s
    ON CONFLICT DO NOTHING
    """
    rows = []
    for r in records:
        raw = r.get("raw_record", {})
        rows.append((
            r.get("source", "UNKNOWN"),
            str(raw.get(list(raw.keys())[0], "")) if raw else "",
            r.get("source_file", ""),
            r.get("source_row", 0),
            r.get("entity_type", ""),
            json.dumps(raw),
            "FK_ORPHAN_OR_UNRESOLVABLE_ID",
            r.get("reason", ""),
            r.get("failed_field", ""),
        ))
    try:
        with conn.cursor() as cur:
            execute_values(cur, sql, rows, page_size=200)
        conn.commit()
        return len(rows)
    except Exception as e:
        conn.rollback()
        print(f"    [WARN] Could not load quarantine records: {e}")
        return 0


# ── Main ──────────────────────────────────────────────────────────────────────

def main(dbname: str = "razorpay_recon", truncate_first: bool = False):
    db_config = get_db_config(dbname)

    print("=" * 70)
    print(f"  CANONICAL POSTGRESQL LOADER v2.0.0")
    print("=" * 70)
    print(f"\n  Database:       {dbname} @ {db_config['host']}:{db_config['port']}")
    print(f"  Normalized dir: {NORMALIZED_DIR}")
    print(f"  FK bypass:      DISABLED (strict FK enforcement)")
    print()

    # Connect
    try:
        conn = psycopg2.connect(**db_config)
        conn.autocommit = False
        print("  Connected to PostgreSQL.")
    except Exception as e:
        print(f"  ERROR: Cannot connect to {dbname}: {e}")
        sys.exit(1)

    # Verify NO FK bypass is active
    with conn.cursor() as cur:
        cur.execute("SHOW session_replication_role")
        role = cur.fetchone()[0]
        if role != "origin":
            print(f"  ERROR: session_replication_role={role!r} — expected 'origin'")
            conn.close()
            sys.exit(1)
        print(f"  session_replication_role = {role!r}  [FK enforcement ACTIVE - GOOD]")

    if truncate_first:
        print("\n  Truncating all tables (clean rebuild)...")
        with conn.cursor() as cur:
            # Truncate in reverse dependency order to avoid FK violations
            cur.execute("""
                TRUNCATE TABLE adjustments, gst_records, books, bank_records,
                               settlement_payments, settlements, refunds, fees,
                               payments, invoices, orders, customers, merchants,
                               quarantine_records, normalization_source_map
                CASCADE
            """)
        conn.commit()
        print("  All tables truncated.")

    # Load files in dependency order
    loaders = [
        ("merchants",           "merchants.jsonl",           load_merchants),
        ("customers",           "customers.jsonl",           load_customers),
        ("orders",              "orders.jsonl",              load_orders),
        ("invoices",            "invoices.jsonl",            load_invoices),
        ("payments",            "payments.jsonl",            load_payments),
        ("fees",                "fees.jsonl",                load_fees),
        ("refunds",             "refunds.jsonl",             load_refunds),
        ("settlements",         "settlements.jsonl",         load_settlements),
        ("settlement_payments", "settlement_payments.jsonl", load_settlement_payments),
        ("bank_records",        "bank_records.jsonl",        load_bank_records),
        ("books",               "books.jsonl",               load_books),
        ("gst_records",         "gst_records.jsonl",         load_gst_records),
        ("adjustments",         "adjustments.jsonl",         load_adjustments),
    ]

    total_inserted = 0
    total_errors = 0
    print(f"\n  {'Table':<25} {'File Records':>13} {'Inserted':>9} {'Errors':>7} {'Status'}")
    print(f"  {'-'*25} {'-'*13} {'-'*9} {'-'*7} {'-'*10}")

    for table_name, filename, loader_fn in loaders:
        filepath = os.path.join(NORMALIZED_DIR, filename)
        if not os.path.exists(filepath):
            print(f"  {table_name:<25} {'FILE MISSING':>13}")
            continue

        records = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except:
                        pass

        try:
            inserted, errors = loader_fn(conn, records)
            total_inserted += inserted
            total_errors += errors
            status = "OK" if errors == 0 else "WARN"
            print(f"  {table_name:<25} {len(records):>13,} {inserted:>9,} {errors:>7} {status}")
        except psycopg2.errors.ForeignKeyViolation as e:
            conn.rollback()
            total_errors += len(records)
            print(f"  {table_name:<25} {len(records):>13,} {'FK ERROR':>9}  -- {e}")
        except Exception as e:
            conn.rollback()
            total_errors += len(records)
            print(f"  {table_name:<25} {len(records):>13,} {'ERROR':>9}  -- {e}")

    # Load quarantine records into DB quarantine table
    quarantine_path = os.path.join(QUARANTINE_DIR, "quarantine_canonical.jsonl")
    if os.path.exists(quarantine_path):
        quar_records = []
        with open(quarantine_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        quar_records.append(json.loads(line))
                    except:
                        pass
        quar_inserted = load_quarantine_records(conn, quar_records)
        print(f"  {'quarantine_records':<25} {len(quar_records):>13,} {quar_inserted:>9,} {'0':>7} OK")
        total_inserted += quar_inserted

    conn.close()

    print(f"\n  Total rows inserted: {total_inserted:,}")
    print(f"  Total errors:        {total_errors}")

    # Post-load verification
    print("\n" + "=" * 70)
    print("  POST-LOAD VERIFICATION (Row Counts)")
    print("=" * 70)

    conn2 = psycopg2.connect(**get_db_config(dbname))
    tables = [
        "merchants", "customers", "orders", "invoices", "payments",
        "fees", "refunds", "settlements", "settlement_payments",
        "bank_records", "books", "gst_records", "adjustments",
        "quarantine_records", "normalization_source_map",
    ]
    grand_total = 0
    print(f"\n  {'Table':<28} {'Rows':>8}")
    print(f"  {'-'*28} {'-'*8}")
    with conn2.cursor() as cur:
        for t in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                count = cur.fetchone()[0]
                grand_total += count
                print(f"  {t:<28} {count:>8,}")
            except Exception as e:
                print(f"  {t:<28} ERROR: {e}")
    print(f"  {'TOTAL (production tables)':<28} {grand_total:>8,}")

    # Quick FK orphan check
    print("\n  Quick FK Orphan Check:")
    fk_checks = [
        ("invoices", "order_id", "orders", "order_id"),
        ("payments", "order_id", "orders", "order_id"),
        ("fees", "payment_id", "payments", "payment_id"),
        ("gst_records", "invoice_id", "invoices", "invoice_id"),
        ("settlement_payments", "settlement_id", "settlements", "settlement_id"),
        ("settlement_payments", "payment_id", "payments", "payment_id"),
    ]
    total_orphans = 0
    with conn2.cursor() as cur:
        for child_t, child_col, parent_t, parent_col in fk_checks:
            cur.execute(f"""
                SELECT COUNT(*) FROM {child_t} c
                LEFT JOIN {parent_t} p ON c.{child_col} = p.{parent_col}
                WHERE c.{child_col} IS NOT NULL AND p.{parent_col} IS NULL
            """)
            orphan_count = cur.fetchone()[0]
            total_orphans += orphan_count
            status = "OK" if orphan_count == 0 else "FAIL"
            print(f"  [{status}] {child_t}.{child_col} -> {parent_t}: {orphan_count} orphans")
    conn2.close()

    print(f"\n  Total orphans: {total_orphans}")
    if total_orphans == 0:
        print("  FK INTEGRITY: PASS")
    else:
        print("  FK INTEGRITY: FAIL - orphans remain")

    return total_orphans == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Canonical PostgreSQL loader")
    parser.add_argument("--dbname", default="razorpay_recon", help="Target database name")
    parser.add_argument("--truncate", action="store_true", help="Truncate all tables before loading")
    args = parser.parse_args()
    success = main(dbname=args.dbname, truncate_first=args.truncate)
    sys.exit(0 if success else 1)
