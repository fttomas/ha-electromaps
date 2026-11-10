"""Parsing of the Electromaps location payload.

Kept free of Home Assistant and aiohttp imports so it can be tested standalone.
Only the fields that matter for connector status are kept: the coordinator
compares parsed snapshots, and unrelated fields (ratings, comments, ads) would
otherwise produce state writes on every poll.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any

from .const import STATUS_UNKNOWN, STATUSES


@dataclass(frozen=True, slots=True)
class Connector:
    """One plug of a charging station."""

    id: int
    name: str
    status: str
    status_since: datetime | None
    plug_type: str | None
    power_kw: float | None


@dataclass(frozen=True, slots=True)
class Location:
    """A charging station with its connectors, keyed by connector id."""

    id: int
    name: str
    connectors: dict[int, Connector]


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _parse_status(value: Any) -> str:
    status = str(value).lower() if value is not None else STATUS_UNKNOWN
    return status if status in STATUSES else STATUS_UNKNOWN


def parse_location(data: Any) -> Location:
    """Build a Location from the API JSON. Raises ValueError on a malformed payload."""
    if not isinstance(data, dict):
        raise ValueError("location payload is not an object")
    try:
        location_id = int(data["id"])
        raw_connectors = data["connectors"]
    except (KeyError, TypeError, ValueError) as err:
        raise ValueError(f"location payload lacks id/connectors: {err}") from err
    if not isinstance(raw_connectors, list):
        raise ValueError("connectors is not a list")

    connectors: dict[int, Connector] = {}
    for index, raw in enumerate(raw_connectors, start=1):
        if not isinstance(raw, dict) or raw.get("id") is None:
            continue
        connector_id = int(raw["id"])
        kw = raw.get("kw")
        connectors[connector_id] = Connector(
            id=connector_id,
            name=(str(raw.get("visualRef") or "").strip() or f"Connector {index}"),
            status=_parse_status(raw.get("status")),
            status_since=_parse_dt(raw.get("status_updated_at")),
            plug_type=raw.get("type"),
            power_kw=float(kw) if isinstance(kw, (int, float)) else None,
        )

    name = str(data.get("name") or "").strip() or f"Electromaps {location_id}"
    return Location(id=location_id, name=name, connectors=connectors)


# Accepts "123456" or a map URL ending in /p/123456 (any locale, optional query).
_ID_RE = re.compile(r"^(?:\d+|https?://\S*/p/\d+/?(?:[?#]\S*)?)$")
_DIGITS_RE = re.compile(r"(\d+)/?(?:[?#]\S*)?$")


def parse_location_input(value: str) -> int | None:
    """Return the station id from a bare id or a map.electromaps.com URL."""
    value = value.strip()
    if not _ID_RE.match(value):
        return None
    match = _DIGITS_RE.search(value)
    return int(match.group(1)) if match else None
