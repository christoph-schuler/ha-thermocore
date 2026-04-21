"""Coordinator für HA-ThermoCore – holt alle Daten aus Home Assistant."""
from __future__ import annotations

import logging
from datetime import timedelta, time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_PV_ENTITY,
    CONF_GRID_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_BATTERY_CAPACITY_ENTITY,
    CONF_BATTERY_CAPACITY_KWH,
    CONF_BATTERY_USE_SENSOR,
    CONF_BATTERY_CHARGE_CURRENT_ENTITY,
    CONF_CHARGE_GOAL_1_SOC, CONF_CHARGE_GOAL_1_TIME,
    CONF_CHARGE_GOAL_2_SOC, CONF_CHARGE_GOAL_2_TIME,
    CONF_CHARGE_GOAL_3_SOC, CONF_CHARGE_GOAL_3_TIME,
    CONF_LATITUDE, CONF_LONGITUDE,
    DOMAIN,
)
from .energy_brain import EnergyBrain, EnergyState
from .battery_strategy import BatteryStrategy, BatteryConfig, ChargeGoal, PVString
from .calibration import PVCalibration

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


class ThermoCoreCoodinator(DataUpdateCoordinator):
    """Holt regelmäßig Daten aus HA und füttert den EnergyBrain."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.entry = entry
        self.brain = EnergyBrain(hass, entry.data)
        self._last_valid_state: EnergyState | None = None
        self._battery_strategy: BatteryStrategy | None = None
        self._calibration: PVCalibration | None = None
        self._setup_battery_strategy()

    def _setup_battery_strategy(self) -> None:
        """Richtet die Batterieladestrategie ein."""
        config = {**self.entry.data, **self.entry.options}

        # Batteriekapazität ermitteln
        capacity_kwh = 10.0
        if config.get(CONF_BATTERY_USE_SENSOR):
            capacity_kwh = 10.0
        else:
            try:
                capacity_kwh = float(config.get(CONF_BATTERY_CAPACITY_KWH, 10.0))
            except (ValueError, TypeError):
                capacity_kwh = 10.0

        # Ladeziele einlesen
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
                    parts = time_str.strip().split(":")
                    t = time(int(parts[0]), int(parts[1]))
                    charge_goals.append(ChargeGoal(target_soc=soc, target_time=t))
                except (ValueError, IndexError) as e:
                    _LOGGER.warning("Ungültiges Ladeziel: %s / %s – %s", soc_str, time_str, e)

        # PV-Strings einlesen
        pv_strings = []
        for i in range(1, 7):
            name = config.get(f"pv_string_{i}_name")
            kwp_str = config.get(f"pv_string_{i}_kwp")
            azimuth_str = config.get(f"pv_string_{i}_azimuth")
            tilt_str = config.get(f"pv_string_{i}_tilt")
            if name and kwp_str:
                try:
                    pv_strings.append(PVString(
                        name=name,
                        power_kwp=float(kwp_str.replace(",", ".")),
                        azimuth=float(azimuth_str.replace(",", ".")) if azimuth_str else 180.0,
                        tilt=float(tilt_str.replace(",", ".")) if tilt_str else 30.0,
                    ))
                except (ValueError, AttributeError) as e:
                    _LOGGER.warning("Ungültiger PV-String %d: %s", i, e)

        # Koordinaten
        lat = float(config.get(CONF_LATITUDE, 48.0) or 48.0)
        lon = float(config.get(CONF_LONGITUDE, 9.0) or 9.0)

        battery_config = BatteryConfig(
            capacity_kwh=capacity_kwh,
            charge_goals=charge_goals,
            pv_strings=pv_strings,
        )

        self._calibration = PVCalibration(self.hass)
        self._battery_strategy = BatteryStrategy(
            config=battery_config,
            latitude=lat,
            longitude=lon,
        )

        _LOGGER.info(
            "BatteryStrategy eingerichtet: %.1f kWh, %d Ladeziele, %d PV-Strings",
            capacity_kwh, len(charge_goals), len(pv_strings)
        )

    async def _async_update_data(self) -> dict:
        """Daten aus HA-Entitäten lesen und EnergyBrain entscheiden lassen."""
        try:
            state = self._read_energy_state()
            decision = self.brain.decide(state)

            config = {**self.entry.data, **self.entry.options}

            # Batteriekapazität aus Sensor aktualisieren
            if config.get(CONF_BATTERY_USE_SENSOR) and self._battery_strategy:
                cap_entity = config.get(CONF_BATTERY_CAPACITY_ENTITY)
                if cap_entity:
                    cap_state = self.hass.states.get(cap_entity)
                    if cap_state and cap_state.state not in ("unavailable", "unknown"):
                        try:
                            self._battery_strategy.config.capacity_kwh = float(cap_state.state)
                        except ValueError:
                            pass

            # Kalibrierungsfaktor aktualisieren
            if self._calibration and self._battery_strategy:
                self._battery_strategy.config.calibration_factor = (
                    self._calibration.calibration_factor
                )

            # Batterieentscheidung berechnen
            battery_decision = None
            if self._battery_strategy:
                battery_decision = await self._battery_strategy.calculate(
                    current_soc=state.battery_soc
                )

            # Ladestrom am Deye setzen
            if battery_decision:
                charge_current_entity = config.get(CONF_BATTERY_CHARGE_CURRENT_ENTITY)
                if charge_current_entity:
                    try:
                        await self.hass.services.async_call(
                            "number",
                            "set_value",
                            {
                                "entity_id": charge_current_entity,
                                "value": battery_decision.recommended_charge_current_amps,
                            },
                        )
                        _LOGGER.debug(
                            "Ladestrom gesetzt: %.1fA",
                            battery_decision.recommended_charge_current_amps
                        )
                    except Exception as err:
                        _LOGGER.warning("Ladestrom konnte nicht gesetzt werden: %s", err)

            _LOGGER.debug(
                "EnergyBrain: %s – %s",
                decision.mode,
                decision.reason,
            )
            if battery_decision:
                _LOGGER.debug("BatteryStrategy: %s", battery_decision.reason)

            return {
                "energy_state": state,
                "decision": decision,
                "battery_decision": battery_decision,
            }

        except Exception as err:
            raise UpdateFailed(f"Fehler beim Datenabruf: {err}") from err

    def _read_energy_state(self) -> EnergyState:
        """Liest alle relevanten Sensoren aus Home Assistant."""
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
            change = abs(new - old) / abs(old)
            return change <= max_change_pct

        config = {**self.entry.data, **self.entry.options}
        new_state = EnergyState(
            pv_power=get_float(config.get(CONF_PV_ENTITY)),
            grid_power=get_float(config.get(CONF_GRID_ENTITY)),
            battery_soc=get_float(config.get(CONF_BATTERY_SOC_ENTITY)),
        )

        if self._last_valid_state is not None:
            if not is_plausible(new_state.pv_power, self._last_valid_state.pv_power):
                _LOGGER.warning("PV-Wert unplausibel: %sW → behalte %sW",
                    new_state.pv_power, self._last_valid_state.pv_power)
                new_state.pv_power = self._last_valid_state.pv_power

            if not is_plausible(new_state.grid_power, self._last_valid_state.grid_power):
                new_state.grid_power = self._last_valid_state.grid_power

        self._last_valid_state = new_state
        return new_state