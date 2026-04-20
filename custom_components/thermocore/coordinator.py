"""Coordinator für HA-ThermoCore – holt alle Daten aus Home Assistant."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_PV_ENTITY,
    CONF_GRID_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    DOMAIN,
)
from .energy_brain import EnergyBrain, EnergyState

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

    async def _async_update_data(self) -> dict:
        """Daten aus HA-Entitäten lesen und EnergyBrain entscheiden lassen."""
        try:
            state = self._read_energy_state()
            decision = self.brain.decide(state)

            _LOGGER.debug(
                "EnergyBrain Entscheidung: %s – %s",
                decision.mode,
                decision.reason,
            )

            return {
                "energy_state": state,
                "decision": decision,
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

        config = {**self.entry.data, **self.entry.options}
        return EnergyState(
            pv_power=get_float(config.get(CONF_PV_ENTITY)),
            grid_power=get_float(config.get(CONF_GRID_ENTITY)),
            battery_soc=get_float(config.get(CONF_BATTERY_SOC_ENTITY)),
        )