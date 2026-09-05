"""
Entity Relationship Graph for Track 4 Synthetic Financial Data.

Defines the DAG of entities and their cardinalities.
Used to enforce generation order and validate referential integrity.
"""

# Generation order — entities must be generated in this sequence
GENERATION_ORDER = [
    "merchants",
    "customers",
    "orders",
    "invoices",
    "gst_records",
    "payments",
    "fees",
    "refunds",
    "settlements",      # Also produces settlement_payments
    "bank_records",
    "books",
    "adjustments",
]

# Relationship definitions
# Format: (parent_entity, child_entity, cardinality, foreign_key_in_child)
RELATIONSHIPS = [
    ("merchants", "customers",    "1:N",  "merchant_id"),
    ("merchants", "orders",       "1:N",  "merchant_id"),
    ("customers", "orders",       "1:N",  "customer_id"),
    ("orders",    "invoices",     "1:1",  "order_id"),
    ("orders",    "payments",     "1:1",  "order_id"),
    ("invoices",  "gst_records",  "1:1",  "invoice_id"),
    ("payments",  "fees",         "1:N",  "payment_id"),
    ("payments",  "refunds",      "0:N",  "payment_id"),
    ("payments",  "settlements",  "N:1",  "settlement_id"),  # via settlement_payments
    ("settlements", "bank_records", "1:N", "settlement_id"),
]

# ID prefixes for each entity
ID_PREFIXES = {
    "merchants":           "MER",
    "customers":           "CUS",
    "orders":              "ORD",
    "invoices":            "INV",
    "payments":            "PAY",
    "fees":                "FEE",
    "refunds":             "REF",
    "settlements":         "STL",
    "bank_records":        "BNK",
    "books":               "LED",
    "gst_records":         "GST",
    "adjustments":         "ADJ",
}

# External/reference identifier types
EXTERNAL_ID_TYPES = [
    "gateway_reference",
    "invoice_number",
    "UTR",
    "bank_reference",
    "PO_number",
]

# Target counts for initial development scale
TARGET_COUNTS = {
    "merchants":       5,
    "customers":     500,
    "orders":       2000,
    "invoices":     1800,
    "payments":     2000,
    "fees":         2000,
    "refunds":       150,
    "settlements":   200,
    "bank_records": 2200,
    "books":        4000,
    "gst_records":  1800,
    "adjustments":    50,
}


def generate_id(entity: str, sequence: int) -> str:
    """Generate a stable ID for an entity.
    
    Args:
        entity: Entity type name (e.g., 'merchants')
        sequence: Sequence number (1-indexed)
    
    Returns:
        Formatted ID string like 'MER_000001'
    """
    prefix = ID_PREFIXES[entity]
    return f"{prefix}_{sequence:06d}"


def get_parent_entities(entity: str) -> list:
    """Get all parent entities for a given entity type."""
    parents = []
    for parent, child, _, fk in RELATIONSHIPS:
        if child == entity:
            parents.append((parent, fk))
    return parents


def get_child_entities(entity: str) -> list:
    """Get all child entities for a given entity type."""
    children = []
    for parent, child, cardinality, fk in RELATIONSHIPS:
        if parent == entity:
            children.append((child, cardinality, fk))
    return children
