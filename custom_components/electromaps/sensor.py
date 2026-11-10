"""One enum sensor per connector (available / occupied / out_of_service /
unknown) and one "free connectors" count per station.

When the API cannot be reached the sensors go unavailable instead of guessing a
status, so "unknown" in history always means Electromaps itself reported it.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MAP_URL, STATUS_AVAILABLE, STATUSES
from .coordinator import ElectromapsConfigEntry, ElectromapsCoordinator
from .models import Connector, Location, count_status


def _device_info(location: Location) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, str(location.id))},
        name=location.name,
        manufacturer="Electromaps",
        model="Charging station",
        configuration_url=MAP_URL.format(location_id=location.id),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectromapsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([FreeConnectorsSensor(coordinator)])
    known: set[int] = set()

    @callback
    def _add_new_connectors() -> None:
        new_ids = [cid for cid in coordinator.data.connectors if cid not in known]
        if new_ids:
            known.update(new_ids)
            async_add_entities(
                ConnectorStatusSensor(coordinator, cid) for cid in new_ids
            )

    _add_new_connectors()
    # A connector added to the station later shows up without a reload.
    entry.async_on_unload(coordinator.async_add_listener(_add_new_connectors))


class ConnectorStatusSensor(CoordinatorEntity[ElectromapsCoordinator], SensorEntity):
    """Status of one connector."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUSES
    _attr_translation_key = "connector_status"

    def __init__(self, coordinator: ElectromapsCoordinator, connector_id: int) -> None:
        super().__init__(coordinator)
        self._connector_id = connector_id
        location = coordinator.data
        self._attr_unique_id = f"{location.id}_{connector_id}"
        self._attr_name = location.connectors[connector_id].name
        self._attr_device_info = _device_info(location)

    @property
    def _connector(self) -> Connector | None:
        return self.coordinator.data.connectors.get(self._connector_id)

    @property
    def available(self) -> bool:
        return super().available and self._connector is not None

    @property
    def native_value(self) -> str | None:
        connector = self._connector
        return connector.status if connector else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        connector = self._connector
        if connector is None:
            return None
        return {
            "status_since": connector.status_since.isoformat()
            if connector.status_since
            else None,
            "plug_type": connector.plug_type,
            "power_kw": connector.power_kw,
            "connector_id": connector.id,
        }


class FreeConnectorsSensor(CoordinatorEntity[ElectromapsCoordinator], SensorEntity):
    """How many connectors of the station are free right now.

    Numeric with a state class, so it gets long-term statistics and works with
    native cards (tile trend graph, statistics graph, numeric_state triggers).
    """

    _attr_has_entity_name = True
    _attr_translation_key = "free_connectors"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ElectromapsCoordinator) -> None:
        super().__init__(coordinator)
        location = coordinator.data
        self._attr_unique_id = f"{location.id}_free_connectors"
        self._attr_device_info = _device_info(location)

    @property
    def native_value(self) -> int:
        return count_status(self.coordinator.data, STATUS_AVAILABLE)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"total": len(self.coordinator.data.connectors)}
