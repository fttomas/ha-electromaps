"""Polling coordinator: one request per interval for the whole station."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ElectromapsError, LocationNotFound, RateLimited, fetch_location
from .const import (
    CONF_LOCATION_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_STATION_CHANGED,
    EVENT_STATUS_CHANGED,
    MAX_BACKOFF,
    STATUS_AVAILABLE,
)
from .models import Location, connector_changes, count_status

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
        # self.data is the last successful snapshot (kept through outages), so a
        # recovery or a restart (data is None) never reports a fake transition.
        if self.data is not None:
            self._fire_status_events(self.data, location)
        return location

    def _fire_status_events(self, old: Location, new: Location) -> None:
        changes = connector_changes(old, new)
        if not changes:
            return
        device = dr.async_get(self.hass).async_get_device(
            identifiers={(DOMAIN, str(new.id))}
        )
        entities = er.async_get(self.hass)
        for before, after in changes:
            self.hass.bus.async_fire(
                EVENT_STATUS_CHANGED,
                {
                    "device_id": device.id if device else None,
                    "entity_id": entities.async_get_entity_id(
                        "sensor", DOMAIN, f"{new.id}_{after.id}"
                    ),
                    "location_id": new.id,
                    "location_name": new.name,
                    "connector_id": after.id,
                    "connector_name": after.name,
                    "from_status": before.status,
                    "to_status": after.status,
                    "from_since": _iso(before.status_since),
                    "since": _iso(after.status_since),
                },
            )
        self.hass.bus.async_fire(
            EVENT_STATION_CHANGED,
            {
                "device_id": device.id if device else None,
                "location_id": new.id,
                "location_name": new.name,
                "free": count_status(new, STATUS_AVAILABLE),
                "free_before": count_status(old, STATUS_AVAILABLE),
                "total": len(new.connectors),
                "statuses": {c.name: c.status for c in new.connectors.values()},
            },
        )


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
