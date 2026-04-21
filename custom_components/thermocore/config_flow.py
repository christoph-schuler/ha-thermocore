"""Config Flow für HA-ThermoCore – geführte Einrichtung über die UI."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    MODULE_HEATCORE, MODULE_SOLARCORE, MODULE_STORAGECORE,
    MODULE_WATERCORE, MODULE_AIRCORE,
    CONF_MODULES, CONF_PV_ENTITY, CONF_GRID_ENTITY,
    CONF_BATTERY_SOC_ENTITY, CONF_DYNAMIC_TARIFF, CONF_TARIFF_ENTITY,
    CONF_BATTERY_USE_SENSOR, CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CAPACITY_KWH,
    CONF_CHARGE_GOAL_1_SOC, CONF_CHARGE_GOAL_1_TIME,
    CONF_CHARGE_GOAL_2_SOC, CONF_CHARGE_GOAL_2_TIME,
    CONF_CHARGE_GOAL_3_SOC, CONF_CHARGE_GOAL_3_TIME,
    CONF_LATITUDE, CONF_LONGITUDE, CONF_PV_PEAK_POWER,
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
                "docs_url": "https://github.com/christoph-schuler/ha-thermocore/blob/main/docs/diy/README.md"
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
            return await self.async_step_battery()

        return self.async_show_form(
            step_id="tariff",
            data_schema=vol.Schema({
                vol.Required(CONF_DYNAMIC_TARIFF, default=False): selector.BooleanSelector(),
                vol.Optional(CONF_TARIFF_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }),
        )

    async def async_step_battery(self, user_input=None):
        """Schritt 4: Kapazität automatisch oder manuell?"""
        if user_input is not None:
            self._data.update(user_input)
            if user_input.get(CONF_BATTERY_USE_SENSOR):
                return await self.async_step_battery_sensor()
            else:
                return await self.async_step_battery_manual()

        return self.async_show_form(
            step_id="battery",
            data_schema=vol.Schema({
                vol.Required(CONF_BATTERY_USE_SENSOR, default=True): selector.BooleanSelector(),
            }),
        )

    async def async_step_battery_sensor(self, user_input=None):
        """Schritt 4a: Batteriekapazität aus Sensor."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_charge_goals()

        return self.async_show_form(
            step_id="battery_sensor",
            data_schema=vol.Schema({
                vol.Required(CONF_BATTERY_CAPACITY_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }),
        )

    async def async_step_battery_manual(self, user_input=None):
        """Schritt 4b: Batteriekapazität manuell eingeben."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_charge_goals()

        return self.async_show_form(
            step_id="battery_manual",
            data_schema=vol.Schema({
                vol.Required(CONF_BATTERY_CAPACITY_KWH, default=10.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=200, step=0.5,
                        unit_of_measurement="kWh"
                    )
                ),
            }),
        )

    async def async_step_charge_goals(self, user_input=None):
        """Schritt 5: Ladeziele eingeben (Format: HH:MM)."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_pv_strings()

        return self.async_show_form(
            step_id="charge_goals",
            data_schema=vol.Schema({
                vol.Optional(CONF_CHARGE_GOAL_1_SOC): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10, max=100, step=5, unit_of_measurement="%")
                ),
                vol.Optional(CONF_CHARGE_GOAL_1_TIME): selector.TextSelector(),
                vol.Optional(CONF_CHARGE_GOAL_2_SOC): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10, max=100, step=5, unit_of_measurement="%")
                ),
                vol.Optional(CONF_CHARGE_GOAL_2_TIME): selector.TextSelector(),
                vol.Optional(CONF_CHARGE_GOAL_3_SOC): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10, max=100, step=5, unit_of_measurement="%")
                ),
                vol.Optional(CONF_CHARGE_GOAL_3_TIME): selector.TextSelector(),
            }),
        )

    async def async_step_pv_strings(self, user_input=None):
        """Schritt 6: PV-Strings konfigurieren (bis zu 6)."""
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(
                title="HA-ThermoCore",
                data=self._data,
            )

        return self.async_show_form(
            step_id="pv_strings",
            data_schema=vol.Schema({
                vol.Optional(CONF_LATITUDE): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-90, max=90, step=0.0001)
                ),
                vol.Optional(CONF_LONGITUDE): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-180, max=180, step=0.0001)
                ),
                vol.Optional("pv_string_1_name"): selector.TextSelector(),
                vol.Optional("pv_string_1_kwp"): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.1, max=50, step=0.1, unit_of_measurement="kWp")
                ),
                vol.Optional("pv_string_1_azimuth"): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=360, step=1, unit_of_measurement="°")
                ),
                vol.Optional("pv_string_1_tilt"): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=90, step=1, unit_of_measurement="°")
                ),
                vol.Optional("pv_string_2_name"): selector.TextSelector(),
                vol.Optional("pv_string_2_kwp"): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.1, max=50, step=0.1, unit_of_measurement="kWp")
                ),
                vol.Optional("pv_string_2_azimuth"): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=360, step=1, unit_of_measurement="°")
                ),
                vol.Optional("pv_string_2_tilt"): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=90, step=1, unit_of_measurement="°")
                ),
                vol.Optional("pv_string_3_name"): selector.TextSelector(),
                vol.Optional("pv_string_3_kwp"): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.1, max=50, step=0.1, unit_of_measurement="kWp")
                ),
                vol.Optional("pv_string_3_azimuth"): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=360, step=1, unit_of_measurement="°")
                ),
                vol.Optional("pv_string_3_tilt"): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=90, step=1, unit_of_measurement="°")
                ),
                vol.Optional("pv_string_4_name"): selector.TextSelector(),
                vol.Optional("pv_string_4_kwp"): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.1, max=50, step=0.1, unit_of_measurement="kWp")
                ),
                vol.Optional("pv_string_4_azimuth"): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=360, step=1, unit_of_measurement="°")
                ),
                vol.Optional("pv_string_4_tilt"): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=90, step=1, unit_of_measurement="°")
                ),
                vol.Optional("pv_string_5_name"): selector.TextSelector(),
                vol.Optional("pv_string_5_kwp"): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.1, max=50, step=0.1, unit_of_measurement="kWp")
                ),
                vol.Optional("pv_string_5_azimuth"): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=360, step=1, unit_of_measurement="°")
                ),
                vol.Optional("pv_string_5_tilt"): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=90, step=1, unit_of_measurement="°")
                ),
                vol.Optional("pv_string_6_name"): selector.TextSelector(),
                vol.Optional("pv_string_6_kwp"): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.1, max=50, step=0.1, unit_of_measurement="kWp")
                ),
                vol.Optional("pv_string_6_azimuth"): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=360, step=1, unit_of_measurement="°")
                ),
                vol.Optional("pv_string_6_tilt"): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=90, step=1, unit_of_measurement="°")
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