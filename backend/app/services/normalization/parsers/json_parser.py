"""
JSON/JSONL Parser — Step 4

Parses raw JSON and JSONL source files into Python dicts.

Also handles:
- Single JSON object
- JSON array
- JSONL (one object per line)
- API/webhook JSON events

Validates before parsing (Step 2).
"""

import json
import os
from typing import Iterator, Optional


class ParseError(Exception):
    """Raised when a record cannot be parsed."""
    pass


def validate_json_file(filepath: str) -> dict:
    """
    Validate a JSON/JSONL file before parsing.

    Checks:
    - File exists
    - File size > 0
    - Valid extension

    Returns:
        {"valid": True, "format": "jsonl"|"json"}
    Raises:
        ParseError for invalid files
    """
    if not os.path.exists(filepath):
        raise ParseError(f"File not found: {filepath}")

    if os.path.getsize(filepath) == 0:
        raise ParseError(f"File is empty: {filepath}")

    ext = os.path.splitext(filepath)[1].lower()
    if ext not in (".json", ".jsonl"):
        raise ParseError(f"Unexpected extension '{ext}' for JSON parser")

    return {"valid": True, "format": "jsonl" if ext == ".jsonl" else "json"}


def parse_jsonl(filepath: str) -> Iterator[dict]:
    """
    Parse a JSONL file, yielding one record dict per line.

    Skips blank lines. Quarantines (yields error dict) for malformed lines.

    Yields:
        dict with parsed record, or
        {"__parse_error__": True, "line": N, "raw": "...", "error": "..."}
    """
    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                yield {
                    "__parse_error__": True,
                    "line": line_num,
                    "raw": line[:200],
                    "error": str(e),
                    "filepath": filepath,
                }


def parse_json_file(filepath: str) -> list:
    """
    Parse a single JSON file (object or array).

    Returns:
        List of record dicts (wraps single object in a list)

    Raises:
        ParseError if file is not valid JSON
    """
    with open(filepath, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise ParseError(f"Invalid JSON in {filepath}: {e}")

    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        return [data]
    else:
        raise ParseError(f"Expected dict or list, got {type(data)} in {filepath}")


def parse_webhook_event(raw_body: str) -> dict:
    """
    Parse a Razorpay webhook event JSON body.

    Validates required top-level fields:
    - event
    - entity
    - payload

    Args:
        raw_body: Raw JSON string from webhook

    Returns:
        Parsed event dict

    Raises:
        ParseError for invalid structure
    """
    try:
        event = json.loads(raw_body)
    except json.JSONDecodeError as e:
        raise ParseError(f"Webhook body is not valid JSON: {e}")

    required_fields = ["event", "entity", "payload"]
    missing = [f for f in required_fields if f not in event]
    if missing:
        raise ParseError(f"Webhook missing required fields: {missing}")

    return event


def parse_api_response(raw_body: str, entity_type: str = None) -> dict:
    """
    Parse a Razorpay API response JSON.

    Args:
        raw_body: Raw JSON response string
        entity_type: Expected entity type (optional, for validation)

    Returns:
        Parsed response dict
    """
    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError as e:
        raise ParseError(f"API response is not valid JSON: {e}")

    if "error" in data:
        raise ParseError(
            f"API returned error: {data['error'].get('description', 'Unknown error')}"
        )

    return data
