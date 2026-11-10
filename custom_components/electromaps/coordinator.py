"""Polling coordinator: one request per interval for the whole station."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ElectromapsError, LocationNotFound, RateLimited, fetch_location
from .const import (
    CONF_LOCATION_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    MAX_BACKOFF,
)
from .models import Location

_LOGGER = logging.getLogger(__name__)

type ElectromapsConfigEntry = ConfigEntry[ElectromapsCoordinator]


class ElectromapsCoordinator(DataUpdateCoordinator[Location]):
    """Fetches the location and hands entities a parsed snapshot.

    always_update=False: listeners run only when the snapshot differs from the
    previous one, so an unchanged station causes no state writes at all.
    """

    config_entry: ElectromapsConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ElectromapsConfigEntry) -> None:
        self.location_id: int = entry.data[CONF_LOCATION_ID]
        self._interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"Electromaps {self.location_id}",
            update_interval=timedelta(seconds=self._interval),
            always_update=False,
        )
        self._session = async_get_clientsession(hass)
        self._failures = 0

    def _backoff(self, hint: float | None = None) -> float:
        """Seconds until the next try: doubles per consecutive failure, capped."""
        self._failures += 1
        delay = min(self._interval * 2**self._failures, MAX_BACKOFF)
        if hint is not None:
            delay = max(delay, min(hint, MAX_BACKOFF))
        return delay

    async def _async_update_data(self) -> Location:
        try:
            location = await fetch_location(self._session, self.location_id)
        except LocationNotFound as err:
            raise UpdateFailed(str(err), retry_after=MAX_BACKOFF) from err
        except RateLimited as err:
            delay = self._backoff(err.retry_after)
            raise UpdateFailed(f"{err}, next try in {delay:.0f}s", retry_after=delay) from err
        except ElectromapsError as err:
            delay = self._backoff()
            raise UpdateFailed(f"{err}, next try in {delay:.0f}s", retry_after=delay) from err
        self._failures = 0
        return location
