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
    CONF_BATTERY_CAPACITY_KWH, CONF_BATTERY_CHARGE_CURRENT_ENTITY,
    CONF_BATTERY_TEMPERATURE_ENTITY,
    CONF_CHARGE_GOAL_1_SOC, CONF_CHARGE_GOAL_1_TIME,
    CONF_CHARGE_GOAL_2_SOC, CONF_CHARGE_GOAL_2_TIME,
    CONF_CHARGE_GOAL_3_SOC, CONF_CHARGE_GOAL_3_TIME,
    CONF_LATITUDE, CONF_LONGITUDE, CONF_PV_PEAK_POWER,
    CONF_NIGHT_CHARGE_ENABLED, CONF_NIGHT_CHARGE_START, CONF_NIGHT_CHARGE_END,
    CONF_NIGHT_CHARGE_MODE, CONF_NIGHT_CHARGE_FIXED_SOC,
    CONF_NIGHT_CHARGE_GOOD_WEATHER_THRESHOLD, CONF_NIGHT_CHARGE_GOOD_WEATHER_SOC,
    CONF_NIGHT_CHARGE_MID_WEATHER_THRESHOLD, CONF_NIGHT_CHARGE_MID_WEATHER_SOC,
    CONF_NIGHT_CHARGE_BAD_WEATHER_SOC,
    CONF_BALANCING_ENABLED, CONF_BALANCING_WEEKDAY,
    CONF_BALANCING_TARGET_SOC, CONF_BALANCING_ABSORPTION_SOC, CONF_BALANCING_HOLD_MINUTES,
    CONF_TEMP_PROTECTION_ENABLED, CONF_TEMP_MIN_CELSIUS, CONF_TEMP_MAX_CURRENT_COLD,
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
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_charge_goals()

        return self.async_show_form(
            step_id="battery_sensor",
            data_schema=vol.Schema({
                vol.Required(CONF_BATTERY_CAPACITY_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_BATTERY_CHARGE_CURRENT_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="number")
                ),
                vol.Optional(CONF_BATTERY_TEMPERATURE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
            }),
        )

    async def async_step_battery_manual(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_charge_goals()

        return self.async_show_form(
            step_id="battery_manual",
            data_schema=vol.Schema({
                vol.Required(CONF_BATTERY_CAPACITY_KWH, default=10.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=200, step=0.5, unit_of_measurement="kWh")
                ),
                vol.Optional(CONF_BATTERY_CHARGE_CURRENT_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="number")
                ),
                vol.Optional(CONF_BATTERY_TEMPERATURE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
            }),
        )

    async def async_step_charge_goals(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_night_charge()

        return self.async_show_form(
            step_id="charge_goals",
            data_schema=vol.Schema({
                vol.Optional(CONF_CHARGE_GOAL_1_SOC): selector.TextSelector(),
                vol.Optional(CONF_CHARGE_GOAL_1_TIME): selector.TextSelector(),
                vol.Optional(CONF_CHARGE_GOAL_2_SOC): selector.TextSelector(),
                vol.Optional(CONF_CHARGE_GOAL_2_TIME): selector.TextSelector(),
                vol.Optional(CONF_CHARGE_GOAL_3_SOC): selector.TextSelector(),
                vol.Optional(CONF_CHARGE_GOAL_3_TIME): selector.TextSelector(),
            }),
        )

    async def async_step_night_charge(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            if user_input.get(CONF_NIGHT_CHARGE_ENABLED):
                return await self.async_step_night_charge_details()
            else:
                return await self.async_step_balancing()

        return self.async_show_form(
            step_id="night_charge",
            data_schema=vol.Schema({
                vol.Required(CONF_NIGHT_CHARGE_ENABLED, default=False): selector.BooleanSelector(),
            }),
        )

    async def async_step_night_charge_details(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            if user_input.get(CONF_NIGHT_CHARGE_MODE) == "weather":
                return await self.async_step_night_charge_weather()
            else:
                return await self.async_step_balancing()

        return self.async_show_form(
            step_id="night_charge_details",
            data_schema=vol.Schema({
                vol.Required(CONF_NIGHT_CHARGE_START, default="04:00"): selector.TextSelector(),
                vol.Required(CONF_NIGHT_CHARGE_END, default="05:00"): selector.TextSelector(),
                vol.Required(CONF_NIGHT_CHARGE_MODE, default="fixed"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": "fixed", "label": "Fester SOC"},
                            {"value": "weather", "label": "Wetterabhängig"},
                        ]
                    )
                ),
                vol.Optional(CONF_NIGHT_CHARGE_FIXED_SOC, default="30"): selector.TextSelector(),
            }),
        )

    async def async_step_night_charge_weather(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_balancing()

        return self.async_show_form(
            step_id="night_charge_weather",
            data_schema=vol.Schema({
                vol.Required(CONF_NIGHT_CHARGE_GOOD_WEATHER_THRESHOLD, default="10"): selector.TextSelector(),
                vol.Required(CONF_NIGHT_CHARGE_GOOD_WEATHER_SOC, default="20"): selector.TextSelector(),
                vol.Required(CONF_NIGHT_CHARGE_MID_WEATHER_THRESHOLD, default="5"): selector.TextSelector(),
                vol.Required(CONF_NIGHT_CHARGE_MID_WEATHER_SOC, default="40"): selector.TextSelector(),
                vol.Required(CONF_NIGHT_CHARGE_BAD_WEATHER_SOC, default="70"): selector.TextSelector(),
            }),
        )

    async def async_step_balancing(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            if user_input.get(CONF_BALANCING_ENABLED):
                return await self.async_step_balancing_details()
            else:
                return await self.async_step_temp_protection()

        return self.async_show_form(
            step_id="balancing",
            data_schema=vol.Schema({
                vol.Required(CONF_BALANCING_ENABLED, default=True): selector.BooleanSelector(),
            }),
        )

    async def async_step_balancing_details(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_temp_protection()

        return self.async_show_form(
            step_id="balancing_details",
            data_schema=vol.Schema({
                vol.Required(CONF_BALANCING_WEEKDAY, default="6"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": "0", "label": "Montag"},
                            {"value": "1", "label": "Dienstag"},
                            {"value": "2", "label": "Mittwoch"},
                            {"value": "3", "label": "Donnerstag"},
                            {"value": "4", "label": "Freitag"},
                            {"value": "5", "label": "Samstag"},
                            {"value": "6", "label": "Sonntag"},
                        ]
                    )
                ),
                vol.Required(CONF_BALANCING_TARGET_SOC, default="100"): selector.TextSelector(),
                vol.Required(CONF_BALANCING_ABSORPTION_SOC, default="95"): selector.TextSelector(),
                vol.Required(CONF_BALANCING_HOLD_MINUTES, default="90"): selector.TextSelector(),
            }),
        )

    async def async_step_temp_protection(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            if user_input.get(CONF_TEMP_PROTECTION_ENABLED):
                return await self.async_step_temp_protection_details()
            else:
                return await self.async_step_pv_strings()

        return self.async_show_form(
            step_id="temp_protection",
            data_schema=vol.Schema({
                vol.Required(CONF_TEMP_PROTECTION_ENABLED, default=True): selector.BooleanSelector(),
            }),
        )

    async def async_step_temp_protection_details(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_pv_strings()

        return self.async_show_form(
            step_id="temp_protection_details",
            data_schema=vol.Schema({
                vol.Required(CONF_TEMP_MIN_CELSIUS, default="5"): selector.TextSelector(),
                vol.Required(CONF_TEMP_MAX_CURRENT_COLD, default="2"): selector.TextSelector(),
            }),
        )

    async def async_step_pv_strings(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title="HA-ThermoCore", data=self._data)

        return self.async_show_form(
            step_id="pv_strings",
            data_schema=vol.Schema({
                vol.Optional(CONF_LATITUDE): selector.TextSelector(),
                vol.Optional(CONF_LONGITUDE): selector.TextSelector(),
                vol.Optional("pv_string_1_name"): selector.TextSelector(),
                vol.Optional("pv_string_1_kwp"): selector.TextSelector(),
                vol.Optional("pv_string_1_azimuth"): selector.TextSelector(),
                vol.Optional("pv_string_1_tilt"): selector.TextSelector(),
                vol.Optional("pv_string_2_name"): selector.TextSelector(),
                vol.Optional("pv_string_2_kwp"): selector.TextSelector(),
                vol.Optional("pv_string_2_azimuth"): selector.TextSelector(),
                vol.Optional("pv_string_2_tilt"): selector.TextSelector(),
                vol.Optional("pv_string_3_name"): selector.TextSelector(),
                vol.Optional("pv_string_3_kwp"): selector.TextSelector(),
                vol.Optional("pv_string_3_azimuth"): selector.TextSelector(),
                vol.Optional("pv_string_3_tilt"): selector.TextSelector(),
                vol.Optional("pv_string_4_name"): selector.TextSelector(),
                vol.Optional("pv_string_4_kwp"): selector.TextSelector(),
                vol.Optional("pv_string_4_azimuth"): selector.TextSelector(),
                vol.Optional("pv_string_4_tilt"): selector.TextSelector(),
                vol.Optional("pv_string_5_name"): selector.TextSelector(),
                vol.Optional("pv_string_5_kwp"): selector.TextSelector(),
                vol.Optional("pv_string_5_azimuth"): selector.TextSelector(),
                vol.Optional("pv_string_5_tilt"): selector.TextSelector(),
                vol.Optional("pv_string_6_name"): selector.TextSelector(),
                vol.Optional("pv_string_6_kwp"): selector.TextSelector(),
                vol.Optional("pv_string_6_azimuth"): selector.TextSelector(),
                vol.Optional("pv_string_6_tilt"): selector.TextSelector(),
            }),
        )


class ThermoCoreOptionsFlow(config_entries.OptionsFlow):
    """Optionen nachträglich ändern."""

    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        config = {**self._config_entry.data, **self._config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(CONF_PV_ENTITY, default=config.get(CONF_PV_ENTITY, "")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_GRID_ENTITY, default=config.get(CONF_GRID_ENTITY, "")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_BATTERY_SOC_ENTITY, default=config.get(CONF_BATTERY_SOC_ENTITY, "")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_BATTERY_CHARGE_CURRENT_ENTITY, default=config.get(CONF_BATTERY_CHARGE_CURRENT_ENTITY, "")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="number")
                ),
                vol.Optional(CONF_BATTERY_TEMPERATURE_ENTITY, default=config.get(CONF_BATTERY_TEMPERATURE_ENTITY, "")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
            }),
        )
