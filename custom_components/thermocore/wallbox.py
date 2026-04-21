"""Wallbox-Steuerung für HA-ThermoCore.

Unterstützt:
- go-e HOMEfix (11kW, 1-phasig) via goecharger Integration
- cFos PowerBrain (22kW, 3-phasig) via powerbrain Integration

Priorisierung: Haus > Heimspeicher (bis Prio-SOC) > go-e > cFos > Heimspeicher (Rest)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

_LOGGER = logging.getLogger(__name__)

# ── Konstanten ────────────────────────────────────────────────────────
PHASE_VOLTAGE = 230.0          # V

# go-e HOMEfix
GOE_MIN_CURRENT = 6.0          # A – Mindeststrom
GOE_MAX_CURRENT = 16.0         # A – Max (16A Kabel)
GOE_PHASES = 1                 # 1-phasig
GOE_MIN_POWER = GOE_MIN_CURRENT * PHASE_VOLTAGE * GOE_PHASES   # ~1380W

# cFos PowerBrain
CFOS_MIN_CURRENT = 6.0         # A pro Phase
CFOS_MAX_CURRENT = 32.0        # A pro Phase
CFOS_PHASES = 3                # 3-phasig
CFOS_MIN_POWER = CFOS_MIN_CURRENT * PHASE_VOLTAGE * CFOS_PHASES  # ~4140W

# Hysterese
SURPLUS_START_THRESHOLD = 1400  # W – Überschuss nötig für go-e Start
SURPLUS_START_DURATION = 180    # Sekunden – Überschuss muss stabil sein
SURPLUS_STOP_THRESHOLD = 500    # W Netzbezug → Stopp
SURPLUS_STOP_DURATION = 300     # Sekunden – Netzbezug muss stabil sein


class ChargingMode(Enum):
    """Lademodus."""
    OFF = "off"
    PV_ONLY = "pv_only"
    BALANCED = "balanced"      # PV + Akku glätten
    FAST = "fast"              # PV + Netz + Akku


class WallboxStatus(Enum):
    """Status einer Wallbox."""
    STANDBY = "standby"         # Bereit, kein Auto
    VEHICLE_CONNECTED = "connected"  # Auto angeschlossen
    CHARGING = "charging"       # Lädt
    FINISHED = "finished"       # Fertig geladen
    ERROR = "error"             # Fehler


@dataclass
class WallboxDecision:
    """Entscheidung für eine Wallbox."""
    wallbox_id: str
    should_charge: bool = False
    charge_current: float = 0.0
    reason: str = ""
    ev_soc: float | None = None
    ev_soc_target: float = 80.0
    mode: str = ChargingMode.PV_ONLY.value


@dataclass
class WallboxConfig:
    """Konfiguration für beide Wallboxen."""
    # go-e HOMEfix
    goe_status_entity: str = "sensor.goecharger_go_e_charger_aussen_v2_car_status"
    goe_allow_charging_entity: str = "switch.goecharger_go_e_charger_aussen_v2_allow_charging"
    goe_power_entity: str = "sensor.goecharger_go_e_charger_aussen_v2_p_all"
    goe_max_current_entity: str = "sensor.goecharger_go_e_charger_aussen_v2_charger_max_current"

    # cFos PowerBrain
    cfos_status_entity: str = "sensor.wallbox_state"
    cfos_charging_enabled_entity: str = "switch.wallbox_charging_enabled"
    cfos_current_limit_entity: str = "number.wallbox_current_limit_override"
    cfos_power_entity: str = "sensor.wallbox_charging_power"

    # Mercedes
    ev_soc_entity: str = "sensor.rt_eq_295e_state_of_charge"

    # Steuerparameter
    ev_soc_min: float = 20.0        # Sofortladen unter diesem SOC
    ev_soc_target: float = 80.0     # Ziel-SOC
    storage_prio_soc: float = 40.0  # Erst wenn Heimspeicher > X%
    charging_mode: str = ChargingMode.PV_ONLY.value


@dataclass
class WallboxState:
    """Aktueller Zustand beider Wallboxen."""
    goe_status: WallboxStatus = WallboxStatus.STANDBY
    goe_current_power: float = 0.0
    cfos_status: WallboxStatus = WallboxStatus.STANDBY
    cfos_current_power: float = 0.0
    ev_soc: float | None = None
    total_wallbox_power: float = 0.0


class WallboxController:
    """Steuert beide Wallboxen mit PV-Überschuss-Logik."""

    def __init__(self, hass, config: WallboxConfig):
        self.hass = hass
        self.config = config

        # Hysterese-Tracking
        self._surplus_above_threshold_since: datetime | None = None
        self._grid_import_above_threshold_since: datetime | None = None
        self._goe_charging: bool = False
        self._cfos_charging: bool = False
        self._last_goe_current: float = 0.0
        self._last_cfos_current: float = 0.0

    def _get_state(self, entity_id: str | None) -> str | None:
        """Liest einen HA-Zustand."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            return None
        return state.state

    def _get_float(self, entity_id: str | None, default: float = 0.0) -> float:
        """Liest einen numerischen HA-Zustand."""
        val = self._get_state(entity_id)
        if val is None:
            return default
        try:
            return float(val)
        except ValueError:
            return default

    def _parse_goe_status(self, status_str: str | None) -> WallboxStatus:
        """Parst den go-e Status."""
        if not status_str:
            return WallboxStatus.ERROR
        s = status_str.lower()
        if "no vehicle" in s or "ready" in s and "no" in s:
            return WallboxStatus.STANDBY
        if "charging" in s:
            return WallboxStatus.CHARGING
        if "complete" in s or "finished" in s:
            return WallboxStatus.FINISHED
        if "connected" in s or "waiting" in s:
            return WallboxStatus.VEHICLE_CONNECTED
        return WallboxStatus.STANDBY

    def _parse_cfos_status(self, status_str: str | None) -> WallboxStatus:
        """Parst den cFos Status."""
        if not status_str:
            return WallboxStatus.ERROR
        if "1:" in status_str or "standby" in status_str.lower():
            return WallboxStatus.STANDBY
        if "2:" in status_str or "3:" in status_str:
            return WallboxStatus.VEHICLE_CONNECTED
        if "4:" in status_str or "charging" in status_str.lower():
            return WallboxStatus.CHARGING
        if "5:" in status_str:
            return WallboxStatus.FINISHED
        return WallboxStatus.STANDBY

    def read_state(self) -> WallboxState:
        """Liest den aktuellen Zustand beider Wallboxen."""
        goe_status_str = self._get_state(self.config.goe_status_entity)
        cfos_status_str = self._get_state(self.config.cfos_status_entity)

        goe_power = self._get_float(self.config.goe_power_entity) * 1000  # kW → W
        cfos_power = self._get_float(self.config.cfos_power_entity)        # W

        ev_soc_str = self._get_state(self.config.ev_soc_entity)
        ev_soc = None
        if ev_soc_str:
            try:
                ev_soc = float(ev_soc_str)
            except ValueError:
                pass

        return WallboxState(
            goe_status=self._parse_goe_status(goe_status_str),
            goe_current_power=goe_power,
            cfos_status=self._parse_cfos_status(cfos_status_str),
            cfos_current_power=cfos_power,
            ev_soc=ev_soc,
            total_wallbox_power=goe_power + cfos_power,
        )

    def calculate(
        self,
        pv_surplus_w: float,
        grid_power_w: float,     # positiv = Bezug, negativ = Einspeisung
        battery_soc: float,
        wb_state: WallboxState,
    ) -> tuple[WallboxDecision, WallboxDecision]:
        """
        Berechnet optimale Ladestrategie für beide Wallboxen.

        Returns: (goe_decision, cfos_decision)
        """
        now = datetime.now()
        mode = ChargingMode(self.config.charging_mode)
        ev_soc = wb_state.ev_soc

        # Not-Aus: EV SOC >= Ziel
        if ev_soc is not None and ev_soc >= self.config.ev_soc_target:
            return (
                WallboxDecision("goe", False, 0.0,
                    f"Auto voll: {ev_soc:.0f}% >= Ziel {self.config.ev_soc_target:.0f}%",
                    ev_soc, self.config.ev_soc_target),
                WallboxDecision("cfos", False, 0.0,
                    f"Auto voll: {ev_soc:.0f}%",
                    ev_soc, self.config.ev_soc_target),
            )

        # Schnellladen: EV SOC < Minimum → sofort laden unabhängig von PV
        emergency_charge = (
            ev_soc is not None and
            ev_soc < self.config.ev_soc_min and
            mode != ChargingMode.OFF
        )

        # Speicher-Vorrang prüfen
        storage_ready = battery_soc >= self.config.storage_prio_soc

        # ── go-e HOMEfix (Priorität 1) ────────────────────────────────
        goe_decision = self._calculate_goe(
            pv_surplus_w, grid_power_w, battery_soc, wb_state,
            mode, emergency_charge, storage_ready, now
        )

        # Verfügbarer Überschuss nach go-e
        surplus_after_goe = pv_surplus_w - goe_decision.charge_current * PHASE_VOLTAGE * GOE_PHASES

        # ── cFos PowerBrain (Priorität 2) ─────────────────────────────
        cfos_decision = self._calculate_cfos(
            surplus_after_goe, grid_power_w, battery_soc, wb_state,
            mode, emergency_charge, storage_ready, now
        )

        return goe_decision, cfos_decision

    def _calculate_goe(
        self,
        surplus_w: float,
        grid_power_w: float,
        battery_soc: float,
        wb_state: WallboxState,
        mode: ChargingMode,
        emergency_charge: bool,
        storage_ready: bool,
        now: datetime,
    ) -> WallboxDecision:
        """Berechnet go-e Ladestrategie."""
        ev_soc = wb_state.ev_soc

        # Kein Auto angeschlossen
        if wb_state.goe_status == WallboxStatus.STANDBY:
            return WallboxDecision("goe", False, 0.0,
                "go-e: Kein Fahrzeug angeschlossen", ev_soc, self.config.ev_soc_target)

        # Modus AUS
        if mode == ChargingMode.OFF:
            return WallboxDecision("goe", False, 0.0, "go-e: Modus AUS", ev_soc, self.config.ev_soc_target)

        # Notladung
        if emergency_charge:
            current = GOE_MAX_CURRENT
            return WallboxDecision("goe", True, current,
                f"go-e: Notladung – Auto SOC {ev_soc:.0f}% < {self.config.ev_soc_min:.0f}%",
                ev_soc, self.config.ev_soc_target, ChargingMode.FAST.value)

        # Schnellladen
        if mode == ChargingMode.FAST:
            current = GOE_MAX_CURRENT
            return WallboxDecision("goe", True, current,
                "go-e: Schnellladen", ev_soc, self.config.ev_soc_target, mode.value)

        # PV-Modus: Speicher muss erst X% haben
        if mode == ChargingMode.PV_ONLY and not storage_ready:
            return WallboxDecision("goe", False, 0.0,
                f"go-e: Warte auf Speicher ({battery_soc:.0f}% < {self.config.storage_prio_soc:.0f}%)",
                ev_soc, self.config.ev_soc_target)

        # Hysterese Start-Check
        if not self._goe_charging:
            if surplus_w >= SURPLUS_START_THRESHOLD:
                if self._surplus_above_threshold_since is None:
                    self._surplus_above_threshold_since = now
                elapsed = (now - self._surplus_above_threshold_since).total_seconds()
                if elapsed < SURPLUS_START_DURATION:
                    return WallboxDecision("goe", False, 0.0,
                        f"go-e: Warte auf stabilen Überschuss ({elapsed:.0f}/{SURPLUS_START_DURATION}s)",
                        ev_soc, self.config.ev_soc_target)
                # Stabil genug → Start
                self._goe_charging = True
                self._surplus_above_threshold_since = None
            else:
                self._surplus_above_threshold_since = None
                return WallboxDecision("goe", False, 0.0,
                    f"go-e: Überschuss {surplus_w:.0f}W < {SURPLUS_START_THRESHOLD}W",
                    ev_soc, self.config.ev_soc_target)

        # Lädt bereits – Stopp-Check
        if self._goe_charging:
            if grid_power_w > SURPLUS_STOP_THRESHOLD:
                if self._grid_import_above_threshold_since is None:
                    self._grid_import_above_threshold_since = now
                elapsed = (now - self._grid_import_above_threshold_since).total_seconds()
                if elapsed >= SURPLUS_STOP_DURATION:
                    self._goe_charging = False
                    self._grid_import_above_threshold_since = None
                    return WallboxDecision("goe", False, 0.0,
                        f"go-e: Stopp – Netzbezug {grid_power_w:.0f}W für {elapsed:.0f}s",
                        ev_soc, self.config.ev_soc_target)
            else:
                self._grid_import_above_threshold_since = None

        # Ladestrom berechnen
        if mode == ChargingMode.BALANCED:
            # Ausgewogen: Akku kann Schwankungen glätten
            available = surplus_w + min(1000, battery_soc * 10)  # Bis 1kW vom Akku
        else:
            available = surplus_w

        current = available / PHASE_VOLTAGE / GOE_PHASES
        current = round(max(GOE_MIN_CURRENT, min(GOE_MAX_CURRENT, current)), 1)

        return WallboxDecision("goe", True, current,
            f"go-e: PV-Laden {current}A ({available:.0f}W verfügbar)",
            ev_soc, self.config.ev_soc_target, mode.value)

    def _calculate_cfos(
        self,
        surplus_after_goe_w: float,
        grid_power_w: float,
        battery_soc: float,
        wb_state: WallboxState,
        mode: ChargingMode,
        emergency_charge: bool,
        storage_ready: bool,
        now: datetime,
    ) -> WallboxDecision:
        """Berechnet cFos Ladestrategie."""
        ev_soc = wb_state.ev_soc

        # Kein Auto
        if wb_state.cfos_status == WallboxStatus.STANDBY:
            return WallboxDecision("cfos", False, 0.0,
                "cFos: Kein Fahrzeug", ev_soc, self.config.ev_soc_target)

        if mode == ChargingMode.OFF:
            return WallboxDecision("cfos", False, 0.0, "cFos: Modus AUS",
                ev_soc, self.config.ev_soc_target)

        if emergency_charge:
            return WallboxDecision("cfos", True, CFOS_MAX_CURRENT,
                f"cFos: Notladung – Auto SOC {ev_soc:.0f}%",
                ev_soc, self.config.ev_soc_target, ChargingMode.FAST.value)

        if mode == ChargingMode.FAST:
            return WallboxDecision("cfos", True, CFOS_MAX_CURRENT,
                "cFos: Schnellladen", ev_soc, self.config.ev_soc_target, mode.value)

        # Genug Überschuss für 3-phasiges Mindestladen?
        if surplus_after_goe_w < CFOS_MIN_POWER:
            return WallboxDecision("cfos", False, 0.0,
                f"cFos: Überschuss {surplus_after_goe_w:.0f}W < {CFOS_MIN_POWER:.0f}W Minimum",
                ev_soc, self.config.ev_soc_target)

        current_per_phase = surplus_after_goe_w / PHASE_VOLTAGE / CFOS_PHASES
        current_per_phase = round(max(CFOS_MIN_CURRENT, min(CFOS_MAX_CURRENT, current_per_phase)), 1)

        return WallboxDecision("cfos", True, current_per_phase,
            f"cFos: PV-Laden {current_per_phase}A/Phase ({surplus_after_goe_w:.0f}W verfügbar)",
            ev_soc, self.config.ev_soc_target, mode.value)

    async def apply_decisions(
        self,
        goe_decision: WallboxDecision,
        cfos_decision: WallboxDecision,
    ) -> None:
        """Setzt die Entscheidungen in HA um."""
        await self._apply_goe(goe_decision)
        await self._apply_cfos(cfos_decision)

    async def _apply_goe(self, decision: WallboxDecision) -> None:
        """Wendet go-e Entscheidung an."""
        try:
            # Laden ein/aus
            current_on = self._get_state(
                self.config.goe_allow_charging_entity) == "on"

            if decision.should_charge and not current_on:
                await self.hass.services.async_call(
                    "switch", "turn_on",
                    {"entity_id": self.config.goe_allow_charging_entity}
                )
                _LOGGER.info("go-e: Laden aktiviert")

            elif not decision.should_charge and current_on:
                await self.hass.services.async_call(
                    "switch", "turn_off",
                    {"entity_id": self.config.goe_allow_charging_entity}
                )
                _LOGGER.info("go-e: Laden deaktiviert")

            # Ladestrom nur setzen wenn geändert
            if decision.should_charge and decision.charge_current != self._last_goe_current:
                self._last_goe_current = decision.charge_current
                await self.hass.services.async_call(
                    "goecharger", "set_max_current",
                    {"max_current": int(decision.charge_current)}
                )
                _LOGGER.debug("go-e: Ladestrom gesetzt auf %dA", decision.charge_current)

        except Exception as err:
            _LOGGER.warning("go-e Steuerung fehlgeschlagen: %s", err)

    async def _apply_cfos(self, decision: WallboxDecision) -> None:
        """Wendet cFos Entscheidung an."""
        try:
            current_on = self._get_state(
                self.config.cfos_charging_enabled_entity) == "on"

            if decision.should_charge and not current_on:
                await self.hass.services.async_call(
                    "switch", "turn_on",
                    {"entity_id": self.config.cfos_charging_enabled_entity}
                )
                _LOGGER.info("cFos: Laden aktiviert")

            elif not decision.should_charge and current_on:
                await self.hass.services.async_call(
                    "switch", "turn_off",
                    {"entity_id": self.config.cfos_charging_enabled_entity}
                )
                _LOGGER.info("cFos: Laden deaktiviert")

            # Ladestrom setzen
            if decision.should_charge and decision.charge_current != self._last_cfos_current:
                self._last_cfos_current = decision.charge_current
                await self.hass.services.async_call(
                    "number", "set_value",
                    {
                        "entity_id": self.config.cfos_current_limit_entity,
                        "value": decision.charge_current,
                    }
                )
                _LOGGER.debug("cFos: Ladestrom gesetzt auf %.1fA/Phase", decision.charge_current)

        except Exception as err:
            _LOGGER.warning("cFos Steuerung fehlgeschlagen: %s", err)
