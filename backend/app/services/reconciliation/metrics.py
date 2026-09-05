"""Comparable identifiers, amounts, dates, and text — matching-v3 compatible."""

from __future__ import annotations

import difflib
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

_ID_NORM = re.compile(r"[^A-Za-z0-9]")


def to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def to_float(value) -> float | None:
    parsed = to_decimal(value)
    return float(parsed) if parsed is not None else None


def normalize_id(value) -> str:
    if value is None:
        return ""
    return _ID_NORM.sub("", str(value)).upper()


def str_similarity(left, right) -> float:
    if left is None or right is None:
        return 0.0
    left_s, right_s = str(left), str(right)
    if not left_s and not right_s:
        return 1.0
    return difflib.SequenceMatcher(None, left_s, right_s).ratio()


def token_overlap(left, right) -> float:
    if not left or not right:
        return 0.0
    left_tokens = set(re.findall(r"[A-Za-z0-9]+", str(left).upper()))
    right_tokens = set(re.findall(r"[A-Za-z0-9]+", str(right).upper()))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        if "T" in text:
            return datetime.fromisoformat(text).date()
        return datetime.fromisoformat(text[:10]).date()
    except ValueError:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def days_between(left, right) -> int | None:
    a = parse_date(left)
    b = parse_date(right)
    if a is None or b is None:
        return None
    return abs((a - b).days)


def amounts_exact(left, right, tolerance: float = 0.01) -> bool:
    a = to_float(left)
    b = to_float(right)
    if a is None or b is None:
        return False
    return abs(a - b) < tolerance
