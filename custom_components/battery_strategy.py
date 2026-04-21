"""Batterieladestrategie für HA-ThermoCore – LFP-optimiert mit Wetterprognose."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time
import aiohttp

_LOGGER = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
MAX_STRINGS = 6


@dataclass
class PVString:
    """Ein PV-String mit Ausrichtung."""
    name: str
    power_kwp: float
    azimuth: float    # 0=Nord, 90=Ost, 180=Süd, 270=West
    tilt: float       # 0=flach, 90=senkrecht


@dataclass
class ChargeGoal:
    """Ein Ladeziel: SOC% bis Uhrzeit."""
    target_soc: float
    target_time: time


@dataclass
class BatteryConfig:
    """Batteriekonfiguration."""
    capacity_kwh: float
    min_soc: float = 10.0
    max_soc: float = 95.0
    charge_goals: list[ChargeGoal] = field(default_factory=list)
    pv_strings: list[PVString] = field(default_factory=list)
    calibration_factor: float = 1.0  # Korrekturfaktor (wird von calibration.py gesetzt)

    @property
    def total_peak_kwp(self) -> float:
        """Gesamte installierte PV-Leistung."""
        return sum(s.power_kwp for s in self.pv_strings)


@dataclass
class BatteryDecision:
    """Entscheidung der Batterieladestrategie."""
    should_charge_from_grid: bool = False
    target_soc: float = 80.0
    reason: str = ""
    pv_forecast_kwh: float = 0.0
    pv_forecast_corrected_kwh: float = 0.0
    energy_needed_kwh: float = 0.0
    grid_charge_kwh: float = 0.0
    calibration_factor: float = 1.0
    string_forecasts: dict = field(default_factory=dict)


class BatteryStrategy:
    """LFP-optimierte Batterieladestrategie mit Multi-String PV-Prognose."""

    def __init__(
        self,
        config: BatteryConfig,
        latitude: float,
        longitude: float,
    ):
        self.config = config
        self.latitude = latitude
        self.longitude = longitude

    async def _get_string_forecast_kwh(
        self,
        pv_string: PVString,
        from_hour: int,
        until_hour: int,
    ) -> float:
        """Holt PV-Prognose für einen einzelnen String von Open-Meteo."""
        try:
            params = {
                "latitude": self.latitude,
                "longitude": self.longitude,
                "hourly": "direct_normal_irradiance,diffuse_radiation",
                "forecast_days": 1,
                "timezone": "auto",
                "tilt": pv_string.tilt,
                "azimuth": pv_string.azimuth - 180,
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(OPEN_METEO_URL, params=params) as resp:
                    if resp.status != 200:
                        _LOGGER.warning("Open-Meteo Fehler für String %s: %s",
                            pv_string.name, resp.status)
                        return 0.0
                    data = await resp.json()

            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            dni = hourly.get("direct_normal_irradiance", [])
            dhi = hourly.get("diffuse_radiation", [])

            now = datetime.now()
            total_kwh = 0.0

            for i, t in enumerate(times):
                dt = datetime.fromisoformat(t)
                if dt.date() == now.date() and from_hour <= dt.hour < until_hour:
                    irradiance = (dni[i] if i < len(dni) else 0) + \
                                 (dhi[i] if i < len(dhi) else 0)
                    kwh = pv_string.power_kwp * (irradiance / 1000) * 0.82
                    total_kwh += kwh

            return round(total_kwh, 2)

        except Exception as err:
            _LOGGER.error("Fehler bei PV-Prognose für String %s: %s",
                pv_string.name, err)
            return 0.0

    async def get_total_pv_forecast(
        self,
        from_hour: int,
        until_hour: int,
    ) -> tuple[float, float, dict]:
        """Berechnet Gesamtprognose aller Strings – roh und kalibriert."""
        string_forecasts = {}
        total_raw = 0.0

        for pv_string in self.config.pv_strings:
            kwh = await self._get_string_forecast_kwh(pv_string, from_hour, until_hour)
            string_forecasts[pv_string.name] = kwh
            total_raw += kwh

        total_corrected = round(total_raw * self.config.calibration_factor, 2)

        _LOGGER.info(
            "PV-Prognose %s-%s Uhr: %.1f kWh roh, %.1f kWh kalibriert (Faktor %.2f)",
            from_hour, until_hour, total_raw, total_corrected,
            self.config.calibration_factor
        )

        return round(total_raw, 2), total_corrected, string_forecasts

    async def calculate(
        self,
        current_soc: float,
        avg_consumption_kwh_per_hour: float = 0.5,
    ) -> BatteryDecision:
        """Berechnet ob Netzladung nötig ist."""
        decision = BatteryDecision()
        decision.calibration_factor = self.config.calibration_factor
        now = datetime.now()

        # Nächstes aktives Ladeziel finden
        active_goal = None
        for goal in sorted(self.config.charge_goals, key=lambda g: g.target_time):
            goal_dt = datetime.combine(now.date(), goal.target_time)
            if goal_dt > now:
                active_goal = goal
                break

        if active_goal is None:
            decision.reason = "Kein aktives Ladeziel"
            return decision

        # Benötigte Energie berechnen
        needed_soc = max(0, active_goal.target_soc - current_soc)
        needed_kwh = (needed_soc / 100) * self.config.capacity_kwh
        decision.energy_needed_kwh = round(needed_kwh, 2)
        decision.target_soc = active_goal.target_soc

        if not self.config.pv_strings:
            decision.reason = "Keine PV-Strings konfiguriert"
            decision.should_charge_from_grid = needed_kwh > 0
            return decision

        # PV-Prognose holen
        until_hour = active_goal.target_time.hour
        pv_raw, pv_corrected, string_forecasts = await self.get_total_pv_forecast(
            now.hour, until_hour
        )
        decision.pv_forecast_kwh = pv_raw
        decision.pv_forecast_corrected_kwh = pv_corrected
        decision.string_forecasts = string_forecasts

        # Hausverbrauch abziehen
        hours_left = max(0, (
            datetime.combine(now.date(), active_goal.target_time) - now
        ).seconds / 3600)
        consumption_kwh = avg_consumption_kwh_per_hour * hours_left
        available_pv = max(0, pv_corrected - consumption_kwh)

        # Netzladung nötig?
        grid_needed = max(0, needed_kwh - available_pv)
        decision.grid_charge_kwh = round(grid_needed, 2)

        if grid_needed > 0.5:
            decision.should_charge_from_grid = True
            strings_info = ", ".join(
                f"{k}: {v:.1f} kWh" for k, v in string_forecasts.items()
            )
            decision.reason = (
                f"Ziel {active_goal.target_soc:.0f}% bis "
                f"{active_goal.target_time.strftime('%H:%M')}: "
                f"Brauche {needed_kwh:.1f} kWh, "
                f"PV liefert {available_pv:.1f} kWh ({strings_info}), "
                f"Netz: {grid_needed:.1f} kWh"
            )
        else:
            decision.reason = (
                f"Ziel {active_goal.target_soc:.0f}% bis "
                f"{active_goal.target_time.strftime('%H:%M')}: "
                f"PV reicht! {available_pv:.1f} kWh verfügbar"
            )

        _LOGGER.info("Batterieentscheidung: %s", decision.reason)
        return decision