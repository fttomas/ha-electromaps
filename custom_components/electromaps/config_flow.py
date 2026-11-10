"""Config and options flow: add a station by id or map URL, tune the poll interval."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .api import ElectromapsError, LocationNotFound, fetch_location
from .const import (
    CONF_LOCATION_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .models import parse_location_input

CONF_LOCATION = "location"


class ElectromapsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add an Electromaps charging station."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            location_id = parse_location_input(user_input[CONF_LOCATION])
            if location_id is None:
                errors["base"] = "invalid_location"
            else:
                await self.async_set_unique_id(str(location_id))
                self._abort_if_unique_id_configured()
                try:
                    location = await fetch_location(
                        async_get_clientsession(self.hass), location_id
                    )
                except LocationNotFound:
                    errors["base"] = "not_found"
                except ElectromapsError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=location.name,
                        data={CONF_LOCATION_ID: location_id},
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_LOCATION): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> ElectromapsOptionsFlow:
        return ElectromapsOptionsFlow()


class ElectromapsOptionsFlow(OptionsFlowWithReload):
    """Poll interval; the entry reloads itself when it changes."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])}
            )

        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            step=1,
                            unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    )
                }
            ),
        )
