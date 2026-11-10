"""One enum sensor per connector: available / occupied / out_of_service / unknown.

When the API cannot be reached the sensors go unavailable instead of guessing a
status, so "unknown" in history always means Electromaps itself reported it.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MAP_URL, STATUSES
from .coordinator import ElectromapsConfigEntry, ElectromapsCoordinator
from .models import Connector


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectromapsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(location.id))},
            name=location.name,
            manufacturer="Electromaps",
            model="Charging station",
            configuration_url=MAP_URL.format(location_id=location.id),
        )

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
