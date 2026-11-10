"""Minimal client for the public Electromaps location endpoint."""

from __future__ import annotations

import aiohttp

from .const import API_URL, REQUEST_TIMEOUT
from .models import Location, parse_location

_HEADERS = {"Accept": "application/json", "App-platform": "web"}


class ElectromapsError(Exception):
    """The location could not be fetched or understood."""


class LocationNotFound(ElectromapsError):
    """The API does not know this location id."""


class RateLimited(ElectromapsError):
    """The API asked us to slow down."""

    def __init__(self, message: str, retry_after: float | None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def _retry_after(response: aiohttp.ClientResponse) -> float | None:
    try:
        return float(response.headers["Retry-After"])
    except (KeyError, ValueError):
        return None


async def fetch_location(session: aiohttp.ClientSession, location_id: int) -> Location:
    """Fetch one location. One request, no retries: the coordinator schedules those."""
    url = API_URL.format(location_id=location_id)
    try:
        async with session.get(
            url,
            headers=_HEADERS,
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        ) as response:
            if response.status in (429, 503):
                raise RateLimited(f"HTTP {response.status}", _retry_after(response))
            if response.status == 403:
                # Unknown ids come back as 403 with LOCATION_NOT_FOUND; any other
                # 403 is treated as a block and backed off like a rate limit.
                try:
                    body = await response.json(content_type=None)
                except ValueError:
                    body = None
                if isinstance(body, dict) and body.get("error_code") == "LOCATION_NOT_FOUND":
                    raise LocationNotFound(f"location {location_id} not found")
                raise RateLimited("HTTP 403", _retry_after(response))
            if response.status != 200:
                raise ElectromapsError(f"HTTP {response.status}")
            data = await response.json(content_type=None)
    except ElectromapsError:
        raise
    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
        raise ElectromapsError(f"{type(err).__name__}: {err}") from err

    try:
        return parse_location(data)
    except ValueError as err:
        raise ElectromapsError(f"unexpected payload: {err}") from err
