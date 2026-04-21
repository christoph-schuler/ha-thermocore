"""Config Flow für HA-ThermoCore – geführte Einrichtung über die UI."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    MODULE_HEATCORE, MODULE_SOLARCORE, MODULE_STORAGECORE,
    MODULE_WATERCORE, MODULE_AIRCORE,
    CONF_MODULES, CONF_PV_ENTITY, CONF_GRID_ENTITY,
    CONF_BATTERY_SOC_ENTITY, CONF_DYNAMIC_TARIFF, CONF_TARIFF_ENTITY,
)


class ThermoCoreConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Geführte Einrichtung von HA-ThermoCore."""

    VERSION = 1
    @classmethod
    @config_entries.callback
    def async_get_options_flow(cls, config_entry):
        return ThermoCoreOptionsFlow(config_entry)
    _data: dict = {}

    async def async_step_user(self, user_input=None):
        """Schritt 1: Module auswählen."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_entities()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_MODULES, default=[MODULE_SOLARCORE]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": MODULE_HEATCORE,   "label": "🌡️ HeatCore – Heizung & Wärmepumpe"},
                            {"value": MODULE_SOLARCORE,  "label": "☀️ SolarCore – PV-Anlage"},
                            {"value": MODULE_STORAGECORE,"label": "🔋 StorageCore – Batteriespeicher"},
                            {"value": MODULE_WATERCORE,  "label": "💧 WaterCore – Warmwasser & Boiler"},
                            {"value": MODULE_AIRCORE,    "label": "💨 AirCore – Lüftung & Klima"},
                        ],
                        multiple=True,
                    )
                ),
            }),
            description_placeholders={
                "docs_url": "https://github.com/ha-thermocore/ha-thermocore/blob/main/docs/diy/README.md"
            },
        )

    async def async_step_entities(self, user_input=None):
        """Schritt 2: Entitäten zuweisen."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_tariff()

        modules = self._data.get(CONF_MODULES, [])
        schema_dict = {}

        if MODULE_SOLARCORE in modules:
            schema_dict[vol.Required(CONF_PV_ENTITY)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="power")
            )
            schema_dict[vol.Required(CONF_GRID_ENTITY)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="power")
            )

        if MODULE_STORAGECORE in modules:
            schema_dict[vol.Required(CONF_BATTERY_SOC_ENTITY)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="battery")
            )

        return self.async_show_form(
            step_id="entities",
            data_schema=vol.Schema(schema_dict),
        )

    async def async_step_tariff(self, user_input=None):
        """Schritt 3: Dynamischer Stromtarif (optional)."""
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(
                title="HA-ThermoCore",
                data=self._data,
            )

        return self.async_show_form(
            step_id="tariff",
            data_schema=vol.Schema({
                vol.Required(CONF_DYNAMIC_TARIFF, default=False): selector.BooleanSelector(),
                vol.Optional(CONF_TARIFF_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }),
        )
class ThermoCoreOptionsFlow(config_entries.OptionsFlow):
    """Optionen nachträglich ändern."""

    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Schritt 1: Sensoren neu zuweisen."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        config = {**self._config_entry.data, **self._config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_PV_ENTITY,
                    default=config.get(CONF_PV_ENTITY, "")
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(
                    CONF_GRID_ENTITY,
                    default=config.get(CONF_GRID_ENTITY, "")
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(
                    CONF_BATTERY_SOC_ENTITY,
                    default=config.get(CONF_BATTERY_SOC_ENTITY, "")
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }),
        )