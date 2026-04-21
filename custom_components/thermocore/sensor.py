"""Sensoren für HA-ThermoCore – zeigt EnergyBrain-Daten in Home Assistant."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ThermoCoreCoodinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sensoren einrichten."""
    coordinator: ThermoCoreCoodinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        EnergyBrainModeSensor(coordinator),
        EnergyBrainReasonSensor(coordinator),
        PVSurplusSensor(coordinator),
        BatteryDecisionSensor(coordinator),  # NEU
    ])


class ThermoCoreSensorBase(CoordinatorEntity, SensorEntity):
    """Basis-Klasse für alle ThermoCore Sensoren."""

    def __init__(self, coordinator: ThermoCoreCoodinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"thermocore_{key}"

    @property
    def _decision(self):
        return self.coordinator.data.get("decision")

    @property
    def _state(self):
        return self.coordinator.data.get("energy_state")


class EnergyBrainModeSensor(ThermoCoreSensorBase):
    """Zeigt den aktuellen EnergyBrain-Modus."""

    def __init__(self, coordinator: ThermoCoreCoodinator) -> None:
        super().__init__(coordinator, "mode")
        self._attr_name = "ThermoCore Modus"
        self._attr_icon = "mdi:brain"

    @property
    def native_value(self) -> str | None:
        if self._decision:
            return self._decision.mode
        return None


class EnergyBrainReasonSensor(ThermoCoreSensorBase):
    """Zeigt warum der EnergyBrain so entschieden hat."""

    def __init__(self, coordinator: ThermoCoreCoodinator) -> None:
        super().__init__(coordinator, "reason")
        self._attr_name = "ThermoCore Begründung"
        self._attr_icon = "mdi:comment-text"

    @property
    def native_value(self) -> str | None:
        if self._decision:
            return self._decision.reason
        return None


class PVSurplusSensor(ThermoCoreSensorBase):
    """Zeigt den aktuellen PV-Überschuss in Watt."""

    def __init__(self, coordinator: ThermoCoreCoodinator) -> None:
        super().__init__(coordinator, "pv_surplus")
        self._attr_name = "ThermoCore PV-Überschuss"
        self._attr_icon = "mdi:solar-power"
        self._attr_native_unit_of_measurement = "W"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        if self._state:
            return round(self._state.pv_surplus, 1)
        return None
    

class BatteryDecisionSensor(ThermoCoreSensorBase):
    """Zeigt die Batterieladestrategie-Entscheidung."""

    def __init__(self, coordinator: ThermoCoreCoodinator) -> None:
        super().__init__(coordinator, "battery_decision")
        self._attr_name = "ThermoCore Batterie Entscheidung"
        self._attr_icon = "mdi:battery-charging"

    @property
    def native_value(self) -> str | None:
        decision = self.coordinator.data.get("battery_decision")
        if decision:
            return "Netzladung" if decision.should_charge_from_grid else "PV reicht"
        return None

    @property
    def extra_state_attributes(self) -> dict:
        decision = self.coordinator.data.get("battery_decision")
        if decision:
            return {
                "reason": decision.reason,
                "pv_forecast_kwh": decision.pv_forecast_kwh,
                "pv_forecast_corrected_kwh": decision.pv_forecast_corrected_kwh,
                "energy_needed_kwh": decision.energy_needed_kwh,
                "grid_charge_kwh": decision.grid_charge_kwh,
                "calibration_factor": decision.calibration_factor,
            }
        return {}