"""EnergyBrain – Zentrale Steuerlogik für HA-ThermoCore.

Der EnergyBrain koordiniert alle Module und trifft Entscheidungen basierend auf:
- Aktuellem PV-Ertrag
- Batterieladezustand
- Stromtarif (optional dynamisch)
- Wettervorhersage
- Anwesenheit
- Benutzer-Prioritäten
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from homeassistant.core import HomeAssistant

from .const import (
    DEFAULT_BATTERY_MIN_SOC,
    DEFAULT_PV_SURPLUS_THRESHOLD,
    MODE_AUTO, MODE_ECO, MODE_COMFORT, MODE_AWAY, MODE_BOOST,
    SG_READY_NORMAL, SG_READY_BOOSTED, SG_READY_MAX,
)

_LOGGER = logging.getLogger(__name__)


class Priority(Enum):
    """Priorität der Energieverbraucher."""
    CRITICAL = 0      # Immer aktiv (Kühlschrank, Sicherheit)
    HIGH = 1          # Heizung/WP Grundbetrieb
    MEDIUM = 2        # Warmwasser
    LOW = 3           # Booster-Betrieb, Überschuss-Laden
    OPTIONAL = 4      # Komfort (z.B. Poolheizung)


@dataclass
class EnergyState:
    """Aktueller Energiezustand des Hauses."""
    pv_power: float = 0.0          # W – aktueller PV-Ertrag
    grid_power: float = 0.0        # W – positiv = Bezug, negativ = Einspeisung
    battery_soc: float = 0.0       # % – Batterieladezustand
    battery_power: float = 0.0     # W – positiv = Laden, negativ = Entladen
    house_consumption: float = 0.0 # W – aktueller Hausverbrauch
    tariff_price: float = 0.0      # ct/kWh – aktueller Strompreis
    is_cheap_tariff: bool = False   # True wenn Strom günstig
    forecast_pv_today: float = 0.0 # kWh – PV-Prognose heute

    @property
    def pv_surplus(self) -> float:
        """PV-Überschuss in Watt (positiv = Überschuss vorhanden)."""
        return self.pv_power - self.house_consumption

    @property
    def has_surplus(self) -> bool:
        """True wenn signifikanter PV-Überschuss vorhanden."""
        return self.pv_surplus > DEFAULT_PV_SURPLUS_THRESHOLD

    @property
    def is_exporting(self) -> bool:
        """True wenn gerade ins Netz eingespeist wird."""
        return self.grid_power < -100  # mehr als 100W Export


@dataclass
class EnergyDecision:
    """Entscheidung des EnergyBrains für einen Zeitpunkt."""
    mode: str = MODE_AUTO
    sg_ready_state: int = SG_READY_NORMAL
    boost_boiler: bool = False
    boost_heat_pump: bool = False
    charge_battery: bool = True
    allow_grid_charging: bool = False
    reason: str = ""
    actions: list[str] = field(default_factory=list)


class EnergyBrain:
    """Zentrale Entscheidungslogik für Energie- und Thermomanagement."""

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        self.hass = hass
        self.config = config
        self._last_decision: EnergyDecision | None = None

    def decide(self, state: EnergyState, mode: str = MODE_AUTO) -> EnergyDecision:
        """Trifft eine Energieentscheidung basierend auf dem aktuellen Zustand.

        Entscheidungsbaum:
        1. Niemand zuhause → Eco-Modus
        2. PV-Überschuss → Wärme erzeugen, Batterie laden
        3. Günstiger Strom → Vorheizen, Batterie laden
        4. Normalbetrieb → Effizienz priorisieren
        5. Teurer Strom → Batterie nutzen, Verbrauch reduzieren
        """
        decision = EnergyDecision()

        if mode == MODE_AWAY:
            return self._decide_away(state, decision)

        if mode == MODE_COMFORT:
            return self._decide_comfort(state, decision)

        # AUTO-Modus: intelligente Entscheidung
        if state.has_surplus:
            return self._decide_surplus(state, decision)

        if state.is_cheap_tariff:
            return self._decide_cheap_tariff(state, decision)

        return self._decide_normal(state, decision)

    def _decide_surplus(self, state: EnergyState, d: EnergyDecision) -> EnergyDecision:
        """PV-Überschuss vorhanden – Energie lokal verbrauchen."""
        d.mode = MODE_BOOST
        d.boost_boiler = True
        d.charge_battery = True
        d.reason = f"PV-Überschuss {state.pv_surplus:.0f}W"
        d.actions = []

        surplus = state.pv_surplus
        if surplus > 3000:
            d.sg_ready_state = SG_READY_MAX
            d.boost_heat_pump = True
            d.actions.append("Wärmepumpe: Maximalbetrieb (SG-Ready 4)")
        elif surplus > DEFAULT_PV_SURPLUS_THRESHOLD:
            d.sg_ready_state = SG_READY_BOOSTED
            d.actions.append("Wärmepumpe: erhöhter Betrieb (SG-Ready 3)")

        if state.battery_soc < 95:
            d.actions.append(f"Batterie laden (aktuell {state.battery_soc:.0f}%)")

        d.actions.append("Boiler auf Maximaltemperatur aufheizen")
        _LOGGER.info("EnergyBrain: %s – %s", d.mode, d.reason)
        return d

    def _decide_cheap_tariff(self, state: EnergyState, d: EnergyDecision) -> EnergyDecision:
        """Günstiger Stromtarif – strategisch Energie einkaufen."""
        d.mode = MODE_ECO
        d.allow_grid_charging = True
        d.boost_boiler = True
        d.reason = f"Günstigertarif {state.tariff_price:.1f} ct/kWh"
        d.actions = [
            "Batterie aus Netz laden",
            "Boiler vorheizen (thermische Speicherung)",
            "Wärmepumpe: erhöhter Betrieb",
        ]
        _LOGGER.info("EnergyBrain: %s – %s", d.mode, d.reason)
        return d

    def _decide_normal(self, state: EnergyState, d: EnergyDecision) -> EnergyDecision:
        """Normalbetrieb ohne besondere Bedingungen."""
        d.mode = MODE_AUTO
        d.sg_ready_state = SG_READY_NORMAL
        d.reason = "Normalbetrieb"
        d.actions = ["Standardregelung aller Systeme"]

        if state.battery_soc < DEFAULT_BATTERY_MIN_SOC:
            d.allow_grid_charging = True
            d.actions.append(f"⚠️ Batterie kritisch ({state.battery_soc:.0f}%) – Notladung")

        return d

    def _decide_away(self, state: EnergyState, d: EnergyDecision) -> EnergyDecision:
        """Abwesenheitsmodus – Minimalverbrauch."""
        d.mode = MODE_AWAY
        d.boost_boiler = False
        d.boost_heat_pump = False
        d.reason = "Niemand zuhause"
        d.actions = [
            "Heizung auf Frostschutz reduzieren",
            "Boiler nur bei PV-Überschuss heizen",
        ]
        # Aber: PV-Überschuss trotzdem nutzen
        if state.has_surplus:
            d.boost_boiler = True
            d.actions.append("PV-Überschuss für Boiler nutzen (kostenlos)")
        return d

    def _decide_comfort(self, state: EnergyState, d: EnergyDecision) -> EnergyDecision:
        """Komfortmodus – maximaler Komfort, Effizienz sekundär."""
        d.mode = MODE_COMFORT
        d.sg_ready_state = SG_READY_BOOSTED
        d.boost_boiler = True
        d.reason = "Komfortmodus aktiv"
        d.actions = [
            "Alle Systeme auf Komforttemperatur",
            "Wärmepumpe: erhöhter Betrieb",
        ]
        return d
