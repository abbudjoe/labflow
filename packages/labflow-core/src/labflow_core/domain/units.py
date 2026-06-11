"""Canonical unit constants and liquid-handling defaults."""

from __future__ import annotations

CANONICAL_CONCENTRATION_UNIT = "ng_per_ul"
CANONICAL_VOLUME_UNIT = "ul"
CANONICAL_MASS_UNIT = "ng"

MINIMUM_TRANSFER_VOLUME_UL = 1.0
SOURCE_RESIDUAL_DEAD_VOLUME_UL = 2.0
ROBOT_ASPIRATION_SAFETY_MARGIN_UL = 1.0
DEFAULT_MAX_DESTINATION_VOLUME_UL = 999.0


def required_source_volume_ul(sample_transfer_volume_ul: float) -> float:
    """Return transfer plus residual dead volume and aspiration safety margin."""
    return (
        sample_transfer_volume_ul
        + SOURCE_RESIDUAL_DEAD_VOLUME_UL
        + ROBOT_ASPIRATION_SAFETY_MARGIN_UL
    )


def assert_supported_units(unit: str, expected: str) -> None:
    """Raise if a configured unit does not match a canonical LabFlow unit."""
    if unit != expected:
        msg = f"Unsupported unit {unit!r}; expected canonical unit {expected!r}."
        raise ValueError(msg)
