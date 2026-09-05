"""Shared utilities for loading normalized data and ground truth."""
import json
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
import difflib
import re

DATA_DIR = "data/normalized"
GT_DIR = "data/ground_truth"

TABLES = ["adjustments", "bank_records", "books", "customers", "fees", "gst_records",
          "invoices", "merchants", "orders", "payments", "refunds",
          "settlement_payments", "settlements"]


def load_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def load_table(name):
    return load_jsonl(f"{DATA_DIR}/{name}.jsonl")


def load_raw_table(name):
    """Loads from data/raw/ (noisy bank-source feed) instead of data/normalized/."""
    return load_jsonl(f"data/raw/{name}.jsonl")


def load_ground_truth(name):
    return load_jsonl(f"{GT_DIR}/{name}.jsonl")


def to_decimal(v):
    """Safe decimal parse; returns None if not parseable."""
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def to_float(v):
    d = to_decimal(v)
    return float(d) if d is not None else None


def parse_dt(v):
    """Parse an ISO date or datetime string; returns a datetime or None."""
    if not v:
        return None
    v = str(v)
    try:
        if "T" in v:
            # handle offsets like +05:30
            return datetime.fromisoformat(v)
        return datetime.fromisoformat(v)
    except ValueError:
        try:
            return datetime.strptime(v[:10], "%Y-%m-%d")
        except ValueError:
            return None


def date_only(v):
    dt = parse_dt(v)
    return dt.date() if dt else None


def days_between(d1, d2):
    """d1, d2 can be datetime/date/str. Returns abs day difference (float) or None."""
    a = d1 if isinstance(d1, (date, datetime)) else parse_dt(d1)
    b = d2 if isinstance(d2, (date, datetime)) else parse_dt(d2)
    if a is None or b is None:
        return None
    if isinstance(a, datetime):
        a = a.date()
    if isinstance(b, datetime):
        b = b.date()
    return abs((a - b).days)


_id_norm_re = re.compile(r"[^A-Za-z0-9]")


def normalize_id(s):
    """Normalize an identifier for fuzzy/exact comparison after format noise (case, separators)."""
    if s is None:
        return ""
    return _id_norm_re.sub("", str(s)).upper()


def str_similarity(a, b):
    """difflib-based similarity ratio in [0, 1]. Stdlib-only substitute for rapidfuzz (no network access to install it)."""
    if a is None or b is None:
        return 0.0
    a, b = str(a), str(b)
    if not a and not b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def token_overlap(a, b):
    if not a or not b:
        return 0.0
    ta = set(re.findall(r"[A-Za-z0-9]+", str(a).upper()))
    tb = set(re.findall(r"[A-Za-z0-9]+", str(b).upper()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)
