"""Identifier normalization for deterministic domain records."""

from __future__ import annotations


def require_nonblank_identifier(value: str, field_name: str | None) -> str:
    stripped = value.strip()
    if not stripped:
        msg = f"{field_name or 'identifier'} is required"
        raise ValueError(msg)
    return stripped


def optional_nonblank_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return stripped
