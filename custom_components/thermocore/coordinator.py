"""Coordinator für HA-ThermoCore – holt alle Daten aus Home Assistant."""
from __future__ import annotations

import logging
from datetime import timedelta, time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_PV_ENTITY, CONF_GRID_ENTITY, CONF_BATTERY_SOC_ENTITY,
    CONF_BATTERY_CAPACITY_ENTITY, CONF_BATTERY_CAPACITY_KWH, CONF_BATTERY_USE_SENSOR,
    CONF_BATTERY_CHARGE_CURRENT_ENTITY, CONF_BATTERY_TEMPERATURE_ENTITY,
    CONF_CHARGE_GOAL_1_SOC, CONF_CHARGE_GOAL_1_TIME,
    CONF_CHARGE_GOAL_2_SOC, CONF_CHARGE_GOAL_2_TIME,
    CONF_CHARGE_GOAL_3_SOC, CONF_CHARGE_GOAL_3_TIME,
    CONF_LATITUDE, CONF_LONGITUDE,
    CONF_NIGHT_CHARGE_ENABLED, CONF_NIGHT_CHARGE_START, CONF_NIGHT_CHARGE_END,
    CONF_NIGHT_CHARGE_MODE, CONF_NIGHT_CHARGE_FIXED_SOC,
    CONF_NIGHT_CHARGE_GOOD_WEATHER_THRESHOLD, CONF_NIGHT_CHARGE_GOOD_WEATHER_SOC,
    CONF_NIGHT_CHARGE_MID_WEATHER_THRESHOLD, CONF_NIGHT_CHARGE_MID_WEATHER_SOC,
    CONF_NIGHT_CHARGE_BAD_WEATHER_SOC,
    CONF_BALANCING_ENABLED, CONF_BALANCING_WEEKDAY,
    CONF_BALANCING_TARGET_SOC, CONF_BALANCING_ABSORPTION_SOC, CONF_BALANCING_HOLD_MINUTES,
    CONF_TEMP_PROTECTION_ENABLED, CONF_TEMP_MIN_CELSIUS, CONF_TEMP_MAX_CURRENT_COLD,
    DOMAIN,
)
from .energy_brain import EnergyBrain, EnergyState
from .battery_strategy import (
    BatteryStrategy, BatteryConfig, ChargeGoal, PVString,
    NightChargeConfig, BalancingConfig, TempProtectionConfig,
)
from .calibration import PVCalibration

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=30)


class ThermoCoreCoodinator(DataUpdateCoordinator):
    """Holt regelmäßig Daten aus HA und füttert den EnergyBrain."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.entry = entry
        self.brain = EnergyBrain(hass, entry.data)
        self._last_valid_state: EnergyState | None = None
        self._battery_strategy: BatteryStrategy | None = None
        self._calibration: PVCalibration | None = None
        self._last_charge_current: float | None = None
        self._setup_battery_strategy()

    def _parse_time(self, time_str: str | None, default: time) -> time:
        try:
            if not time_str:
                return default
            parts = str(time_str).strip().split(":")
            return time(int(parts[0]), int(parts[1]))
        except Exception:
            return default

    def _parse_float(self, val, default: float) -> float:
        try:
            return float(str(val).replace(",", "."))
        except Exception:
            return default

    def _setup_battery_strategy(self) -> None:
        config = {**self.entry.data, **self.entry.options}

        # Kapazität
        capacity_kwh = 10.0
        if not config.get(CONF_BATTERY_USE_SENSOR):
            capacity_kwh = self._parse_float(config.get(CONF_BATTERY_CAPACITY_KWH), 10.0)

        # Tagesziele
        charge_goals = []
        for soc_key, time_key in [
            (CONF_CHARGE_GOAL_1_SOC, CONF_CHARGE_GOAL_1_TIME),
            (CONF_CHARGE_GOAL_2_SOC, CONF_CHARGE_GOAL_2_TIME),
            (CONF_CHARGE_GOAL_3_SOC, CONF_CHARGE_GOAL_3_TIME),
        ]:
            soc_str = config.get(soc_key)
            time_str = config.get(time_key)
            if soc_str and time_str:
                try:
                    soc = float(soc_str)
                    parts = str(time_str).strip().split(":")
                    t = time(int(parts[0]), int(parts[1]))
                    charge_goals.append(ChargeGoal(target_soc=soc, target_time=t))
                except Exception as e:
                    _LOGGER.warning("Ungültiges Ladeziel: %s", e)

        # PV-Strings
        pv_strings = []
        for i in range(1, 7):
            name = config.get(f"pv_string_{i}_name")
            kwp_str = config.get(f"pv_string_{i}_kwp")
            if name and kwp_str:
                try:
                    pv_strings.append(PVString(
                        name=name,
                        power_kwp=self._parse_float(kwp_str, 0),
                        azimuth=self._parse_float(config.get(f"pv_string_{i}_azimuth"), 180.0),
                        tilt=self._parse_float(config.get(f"pv_string_{i}_tilt"), 30.0),
                    ))
                except Exception as e:
                    _LOGGER.warning("Ungültiger PV-String %d: %s", i, e)

        # Koordinaten
        lat = self._parse_float(config.get(CONF_LATITUDE) or 48.0, 48.0)
        lon = self._parse_float(config.get(CONF_LONGITUDE) or 9.0, 9.0)

        # Nachtladung
        night_charge = NightChargeConfig(
            enabled=bool(config.get(CONF_NIGHT_CHARGE_ENABLED, False)),
            start_time=self._parse_time(config.get(CONF_NIGHT_CHARGE_START), time(4, 0)),
            end_time=self._parse_time(config.get(CONF_NIGHT_CHARGE_END), time(5, 0)),
            mode=config.get(CONF_NIGHT_CHARGE_MODE, "fixed"),
            fixed_soc=self._parse_float(config.get(CONF_NIGHT_CHARGE_FIXED_SOC), 30.0),
            good_weather_threshold_kwh=self._parse_float(config.get(CONF_NIGHT_CHARGE_GOOD_WEATHER_THRESHOLD), 10.0),
            good_weather_soc=self._parse_float(config.get(CONF_NIGHT_CHARGE_GOOD_WEATHER_SOC), 20.0),
            mid_weather_threshold_kwh=self._parse_float(config.get(CONF_NIGHT_CHARGE_MID_WEATHER_THRESHOLD), 5.0),
            mid_weather_soc=self._parse_float(config.get(CONF_NIGHT_CHARGE_MID_WEATHER_SOC), 40.0),
            bad_weather_soc=self._parse_float(config.get(CONF_NIGHT_CHARGE_BAD_WEATHER_SOC), 70.0),
        )

        # Balancing
        balancing = BalancingConfig(
            enabled=bool(config.get(CONF_BALANCING_ENABLED, False)),
            weekday=int(self._parse_float(config.get(CONF_BALANCING_WEEKDAY), 6)),
            target_soc=self._parse_float(config.get(CONF_BALANCING_TARGET_SOC), 100.0),
            absorption_soc=self._parse_float(config.get(CONF_BALANCING_ABSORPTION_SOC), 95.0),
            hold_minutes=int(self._parse_float(config.get(CONF_BALANCING_HOLD_MINUTES), 90)),
        )

        # Temperaturschutz
        temp_protection = TempProtectionConfig(
            enabled=bool(config.get(CONF_TEMP_PROTECTION_ENABLED, False)),
            min_celsius=self._parse_float(config.get(CONF_TEMP_MIN_CELSIUS), 5.0),
            max_current_cold=self._parse_float(config.get(CONF_TEMP_MAX_CURRENT_COLD), 2.0),
        )

        battery_config = BatteryConfig(
            capacity_kwh=capacity_kwh,
            charge_goals=charge_goals,
            pv_strings=pv_strings,
            night_charge=night_charge,
            balancing=balancing,
            temp_protection=temp_protection,
        )

        self._calibration = PVCalibration(self.hass)
        self._battery_strategy = BatteryStrategy(
            config=battery_config, latitude=lat, longitude=lon
        )

        _LOGGER.info(
            "BatteryStrategy: %.1f kWh, %d Ziele, %d Strings, Nacht=%s, Balancing=%s, TempSchutz=%s",
            capacity_kwh, len(charge_goals), len(pv_strings),
            night_charge.enabled, balancing.enabled, temp_protection.enabled
        )

    async def _async_update_data(self) -> dict:
        try:
            state = self._read_energy_state()
            decision = self.brain.decide(state)
            config = {**self.entry.data, **self.entry.options}

            # Batteriekapazität aus Sensor
            if config.get(CONF_BATTERY_USE_SENSOR) and self._battery_strategy:
                cap_entity = config.get(CONF_BATTERY_CAPACITY_ENTITY)
                if cap_entity:
                    cap_state = self.hass.states.get(cap_entity)
                    if cap_state and cap_state.state not in ("unavailable", "unknown"):
                        try:
                            self._battery_strategy.config.capacity_kwh = float(cap_state.state)
                        except ValueError:
                            pass

            # Kalibrierungsfaktor
            if self._calibration and self._battery_strategy:
                self._battery_strategy.config.calibration_factor = self._calibration.calibration_factor

            # Batterietemperatur lesen
            battery_temp = None
            temp_entity = config.get(CONF_BATTERY_TEMPERATURE_ENTITY)
            if temp_entity:
                temp_state = self.hass.states.get(temp_entity)
                if temp_state and temp_state.state not in ("unavailable", "unknown"):
                    try:
                        battery_temp = float(temp_state.state)
                    except ValueError:
                        pass

            # Batterieentscheidung
            battery_decision = None
            if self._battery_strategy:
                battery_decision = await self._battery_strategy.calculate(
                    current_soc=state.battery_soc,
                    battery_temp=battery_temp,
                )

            # Ladestrom setzen
            if battery_decision:
                charge_current_entity = config.get(CONF_BATTERY_CHARGE_CURRENT_ENTITY)
                if charge_current_entity:
                    # Nachtladung oder Balancing → aus Netz laden
                    if (battery_decision.night_charge_active and battery_decision.should_charge_from_grid) \
                            or battery_decision.balancing_active:
                        new_current = battery_decision.recommended_charge_current_amps
                    # Tagesziel → nur bei PV-Überschuss
                    elif state.has_surplus and battery_decision.energy_needed_kwh > 0:
                        new_current = battery_decision.recommended_charge_current_amps
                    else:
                        new_current = 0.0

                    if new_current != self._last_charge_current:
                        self._last_charge_current = new_current
                        try:
                            await self.hass.services.async_call(
                                "number", "set_value",
                                {"entity_id": charge_current_entity, "value": new_current},
                            )
                            _LOGGER.debug("Ladestrom gesetzt: %.1fA", new_current)
                        except Exception as err:
                            _LOGGER.warning("Ladestrom konnte nicht gesetzt werden: %s", err)

            return {
                "energy_state": state,
                "decision": decision,
                "battery_decision": battery_decision,
                "battery_temp": battery_temp,
            }

        except Exception as err:
            raise UpdateFailed(f"Fehler: {err}") from err

    def _read_energy_state(self) -> EnergyState:
        def get_float(entity_id: str | None) -> float:
            if not entity_id:
                return 0.0
            state = self.hass.states.get(entity_id)
            if state is None or state.state in ("unavailable", "unknown"):
                return 0.0
            try:
                return float(state.state)
            except ValueError:
                return 0.0

        def is_plausible(new: float, old: float, max_change_pct: float = 0.5) -> bool:
            if old == 0:
                return True
            return abs(new - old) / abs(old) <= max_change_pct

        config = {**self.entry.data, **self.entry.options}
        new_state = EnergyState(
            pv_power=get_float(config.get(CONF_PV_ENTITY)),
            grid_power=get_float(config.get(CONF_GRID_ENTITY)),
            battery_soc=get_float(config.get(CONF_BATTERY_SOC_ENTITY)),
        )

        if self._last_valid_state is not None:
            if not is_plausible(new_state.pv_power, self._last_valid_state.pv_power):
                _LOGGER.warning("PV-Wert unplausibel → behalte alten Wert")
                new_state.pv_power = self._last_valid_state.pv_power
            if not is_plausible(new_state.grid_power, self._last_valid_state.grid_power):
                new_state.grid_power = self._last_valid_state.grid_power

        self._last_valid_state = new_state
        return new_state
