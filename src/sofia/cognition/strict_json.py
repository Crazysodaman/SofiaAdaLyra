"""Strict JSON decoding for non-authoritative model output.

This is parsing only; each production caller still performs its own typed
schema checks and SAFE authorization. Duplicate keys or non-standard JSON
numbers are never silently interpreted as one unambiguous model decision.
"""
from __future__ import annotations

import json


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("ambiguous duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str):
    raise ValueError("non-finite JSON constant is not permitted")


def loads_strict_model_json(raw: str):
    """Decode JSON without last-wins duplicate keys or NaN/Infinity extensions.

    The caller must apply an input byte ceiling before invoking this parser
    on model output and validate the returned type and expected schema.
    """
    if not isinstance(raw, str):
        raise TypeError("model output must be a JSON text string")
    return json.loads(
        raw,
        object_pairs_hook=_unique_object,
        parse_constant=_reject_constant,
    )
