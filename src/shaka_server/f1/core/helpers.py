"""Serial and BB/SB helpers — MUST NEVER invent serial numbers."""

from __future__ import annotations

from typing import Any

from shaka_server.f1.core.types import Asset, SerialNumber, Side
from shaka_server.f1.core.validators import ValidationError


def normalize_serial(input_value: Any) -> SerialNumber:
    """Absent / blank / null → \"unknown\". Never invent."""
    if input_value is None:
        return "unknown"
    if not isinstance(input_value, str):
        return "unknown"
    trimmed = input_value.strip()
    if trimmed == "" or trimmed.lower() == "unknown" or trimmed in {"?", "-"}:
        return "unknown"
    return trimmed


def assign_serial_from_evidence(
    documented: SerialNumber | None,
    hints: dict[str, Any] | None = None,
) -> SerialNumber:
    """Refuse to invent a serial from side, asset type, or sibling."""
    if hints is not None and hints.get("guess") is not None:
        raise ValidationError("Refusing to invent serial from guess", "NO_SERIAL_GUESS")
    return normalize_serial(documented)


def side_from_quantity_alone(_qty: int) -> Side | str:
    """Impeller qty without side evidence → unknown side (never BB/SB from qty alone)."""
    return "unknown"


def assert_bb_sb_not_merged(a: Asset, b: Asset) -> None:
    """BB and SB must never merge into one Asset identity."""
    if a.side == "BB" and b.side == "SB" and a.id == b.id:
        raise ValidationError("BB/SB must never share Asset id", "BB_SB_INTEGRITY")
    if (
        a.side != b.side
        and a.serial != "unknown"
        and b.serial != "unknown"
        and a.serial == b.serial
    ):
        raise ValidationError(
            "Same serial on different sides requires explicit conflict",
            "BB_SB_INTEGRITY",
        )
