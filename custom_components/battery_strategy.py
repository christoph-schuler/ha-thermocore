"""Batterieladestrategie für HA-ThermoCore – LFP-optimiert mit Wetterprognose."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
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
class NightChargeConfig:
    """Konfiguration für die Nachtladung."""
    enabled: bool = False
    start_time: time = field(default_factory=lambda: time(4, 0))
    end_time: time = field(default_factory=lambda: time(5, 0))
    mode: str = "fixed"
    fixed_soc: float = 30.0
    good_weather_threshold_kwh: float = 10.0
    good_weather_soc: float = 20.0
    mid_weather_threshold_kwh: float = 5.0
    mid_weather_soc: float = 40.0
    bad_weather_soc: float = 70.0


@dataclass
class BalancingConfig:
    """Wöchentliche Rekalibrierung für LFP-Zellen."""
    enabled: bool = False
    weekday: int = 6           # 0=Mo, 6=So
    target_soc: float = 100.0
    absorption_soc: float = 95.0
    hold_minutes: int = 90


@dataclass
class TempProtectionConfig:
    """Temperaturschutz für den Batteriespeicher."""
    enabled: bool = False
    min_celsius: float = 5.0
    max_current_cold: float = 2.0  # Max. Ladestrom bei Kälte in Ampere


@dataclass
class BatteryConfig:
    """Batteriekonfiguration."""
    capacity_kwh: float
    min_soc: float = 10.0
    max_soc: float = 95.0
    charge_goals: list[ChargeGoal] = field(default_factory=list)
    pv_strings: list[PVString] = field(default_factory=list)
    calibration_factor: float = 1.0
    night_charge: NightChargeConfig = field(default_factory=NightChargeConfig)
    balancing: BalancingConfig = field(default_factory=BalancingConfig)
    temp_protection: TempProtectionConfig = field(default_factory=TempProtectionConfig)

    @property
    def total_peak_kwp(self) -> float:
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
    recommended_charge_current_amps: float = 4.0
    night_charge_active: bool = False
    night_charge_target_soc: float = 0.0
    balancing_active: bool = False
    temp_limited: bool = False
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
        self._balancing_start_time: datetime | None = None

    def _apply_temp_limit(self, current_amps: float, battery_temp: float | None) -> tuple[float, bool]:
        """Begrenzt Ladestrom bei Kälte."""
        tp = self.config.temp_protection
        if not tp.enabled or battery_temp is None:
            return current_amps, False
        if battery_temp < tp.min_celsius:
            limited = min(current_amps, tp.max_current_cold)
            _LOGGER.warning(
                "Temperaturschutz: %.1f°C < %.1f°C → Ladestrom auf %.1fA begrenzt",
                battery_temp, tp.min_celsius, limited
            )
            return limited, True
        return current_amps, False

    async def _get_string_forecast_kwh(
        self,
        pv_string: PVString,
        from_hour: int,
        until_hour: int,
        forecast_day: int = 0,
    ) -> float:
        """Holt PV-Prognose für einen einzelnen String von Open-Meteo."""
        try:
            params = {
                "latitude": self.latitude,
                "longitude": self.longitude,
                "hourly": "direct_normal_irradiance,diffuse_radiation",
                "forecast_days": 2,
                "timezone": "auto",
                "tilt": pv_string.tilt,
                "azimuth": pv_string.azimuth - 180,
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(OPEN_METEO_URL, params=params) as resp:
                    if resp.status != 200:
                        return 0.0
                    data = await resp.json()

            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            dni = hourly.get("direct_normal_irradiance", [])
            dhi = hourly.get("diffuse_radiation", [])

            now = datetime.now()
            target_date = (now + timedelta(days=forecast_day)).date()
            total_kwh = 0.0

            for i, t in enumerate(times):
                dt = datetime.fromisoformat(t)
                if dt.date() == target_date and from_hour <= dt.hour < until_hour:
                    irradiance = (dni[i] if i < len(dni) else 0) + \
                                 (dhi[i] if i < len(dhi) else 0)
                    kwh = pv_string.power_kwp * (irradiance / 1000) * 0.82
                    total_kwh += kwh

            return round(total_kwh, 2)

        except Exception as err:
            _LOGGER.error("Fehler bei PV-Prognose für String %s: %s", pv_string.name, err)
            return 0.0

    async def get_total_pv_forecast(
        self,
        from_hour: int,
        until_hour: int,
        forecast_day: int = 0,
    ) -> tuple[float, float, dict]:
        """Berechnet Gesamtprognose aller Strings."""
        string_forecasts = {}
        total_raw = 0.0

        for pv_string in self.config.pv_strings:
            kwh = await self._get_string_forecast_kwh(pv_string, from_hour, until_hour, forecast_day)
            string_forecasts[pv_string.name] = kwh
            total_raw += kwh

        total_corrected = round(total_raw * self.config.calibration_factor, 2)
        return round(total_raw, 2), total_corrected, string_forecasts

    async def get_night_charge_target_soc(self) -> float:
        """Berechnet den Ziel-SOC für die Nachtladung."""
        nc = self.config.night_charge
        if nc.mode == "fixed":
            return nc.fixed_soc

        _, pv_tomorrow, _ = await self.get_total_pv_forecast(6, 12, forecast_day=1)

        if pv_tomorrow >= nc.good_weather_threshold_kwh:
            _LOGGER.info("Nachtladung: Gutes Wetter (%.1f kWh) → %d%%", pv_tomorrow, nc.good_weather_soc)
            return nc.good_weather_soc
        elif pv_tomorrow >= nc.mid_weather_threshold_kwh:
            _LOGGER.info("Nachtladung: Mittleres Wetter (%.1f kWh) → %d%%", pv_tomorrow, nc.mid_weather_soc)
            return nc.mid_weather_soc
        else:
            _LOGGER.info("Nachtladung: Schlechtes Wetter (%.1f kWh) → %d%%", pv_tomorrow, nc.bad_weather_soc)
            return nc.bad_weather_soc

    def _check_balancing(self, current_soc: float) -> tuple[bool, str]:
        """Prüft ob heute Balancing-Tag ist."""
        bal = self.config.balancing
        if not bal.enabled:
            return False, ""

        now = datetime.now()
        is_balancing_day = now.weekday() == bal.weekday

        if not is_balancing_day:
            return False, ""

        # Balancing noch nicht abgeschlossen?
        if current_soc < bal.target_soc:
            return True, f"Balancing-Tag: Vollladung auf {bal.target_soc:.0f}%"

        # Absorptionsphase: SOC >= absorption_soc für hold_minutes halten
        if current_soc >= bal.absorption_soc:
            if self._balancing_start_time is None:
                self._balancing_start_time = now
                return True, f"Balancing: Absorptionsphase gestartet ({bal.hold_minutes} Min)"

            elapsed = (now - self._balancing_start_time).seconds / 60
            if elapsed < bal.hold_minutes:
                return True, f"Balancing: Absorptionsphase {elapsed:.0f}/{bal.hold_minutes} Min"
            else:
                self._balancing_start_time = None
                return False, "Balancing abgeschlossen"

        return True, f"Balancing: Lade auf {bal.target_soc:.0f}%"

    async def calculate(
        self,
        current_soc: float,
        battery_temp: float | None = None,
        avg_consumption_kwh_per_hour: float = 0.5,
    ) -> BatteryDecision:
        """Berechnet die optimale Ladeentscheidung."""
        decision = BatteryDecision()
        decision.calibration_factor = self.config.calibration_factor
        now = datetime.now()

        BATTERY_VOLTAGE = 400.0
        MAX_CHARGE_CURRENT = 25.0
        MIN_CHARGE_CURRENT = 4.0

        # ── 1. Wöchentliches Balancing ─────────────────────────────────────
        balancing_active, balancing_reason = self._check_balancing(current_soc)
        if balancing_active:
            bal = self.config.balancing
            needed_kwh = max(0, (bal.target_soc - current_soc) / 100 * self.config.capacity_kwh)
            current_amps = MAX_CHARGE_CURRENT  # Balancing: volle Leistung
            if current_soc >= bal.absorption_soc:
                current_amps = MIN_CHARGE_CURRENT  # Absorptionsphase: sanft laden

            current_amps, temp_limited = self._apply_temp_limit(current_amps, battery_temp)
            decision.balancing_active = True
            decision.recommended_charge_current_amps = current_amps
            decision.temp_limited = temp_limited
            decision.target_soc = bal.target_soc
            decision.energy_needed_kwh = round(needed_kwh, 2)
            decision.reason = balancing_reason
            return decision

        # ── 2. Nachtladung ──────────────────────────────────────────────────
        nc = self.config.night_charge
        if nc.enabled:
            night_start = datetime.combine(now.date(), nc.start_time)
            night_end = datetime.combine(now.date(), nc.end_time)

            if night_start <= now <= night_end:
                target_soc = await self.get_night_charge_target_soc()
                decision.night_charge_target_soc = target_soc

                if current_soc < target_soc:
                    needed_kwh = (target_soc - current_soc) / 100 * self.config.capacity_kwh
                    hours_left = max(0.1, (night_end - now).seconds / 3600)
                    current_amps = (needed_kwh * 1000 / BATTERY_VOLTAGE / hours_left) * 1.2
                    current_amps = round(max(MIN_CHARGE_CURRENT, min(MAX_CHARGE_CURRENT, current_amps)), 1)
                    current_amps, temp_limited = self._apply_temp_limit(current_amps, battery_temp)

                    decision.should_charge_from_grid = True
                    decision.night_charge_active = True
                    decision.energy_needed_kwh = round(needed_kwh, 2)
                    decision.target_soc = target_soc
                    decision.recommended_charge_current_amps = current_amps
                    decision.temp_limited = temp_limited
                    decision.reason = (
                        f"Nachtladung: {current_soc:.0f}% → {target_soc:.0f}% "
                        f"({needed_kwh:.1f} kWh, {current_amps}A)"
                    )
                    return decision
                else:
                    decision.reason = f"Nachtladung: Ziel {target_soc:.0f}% bereits erreicht"
                    decision.recommended_charge_current_amps = 0.0
                    return decision

        # ── 3. Tagesziel ────────────────────────────────────────────────────
        active_goal = None
        for goal in sorted(self.config.charge_goals, key=lambda g: g.target_time):
            goal_dt = datetime.combine(now.date(), goal.target_time)
            if goal_dt > now:
                active_goal = goal
                break

        if active_goal is None:
            decision.reason = "Kein aktives Ladeziel"
            decision.recommended_charge_current_amps = 0.0
            return decision

        needed_soc = max(0, active_goal.target_soc - current_soc)
        needed_kwh = (needed_soc / 100) * self.config.capacity_kwh
        decision.energy_needed_kwh = round(needed_kwh, 2)
        decision.target_soc = active_goal.target_soc

        if needed_kwh <= 0:
            decision.reason = f"Ziel {active_goal.target_soc:.0f}% bereits erreicht"
            decision.recommended_charge_current_amps = 0.0
            return decision

        if not self.config.pv_strings:
            decision.reason = "Keine PV-Strings konfiguriert"
            return decision

        # PV-Prognose
        until_hour = active_goal.target_time.hour
        pv_raw, pv_corrected, string_forecasts = await self.get_total_pv_forecast(now.hour, until_hour)
        decision.pv_forecast_kwh = pv_raw
        decision.pv_forecast_corrected_kwh = pv_corrected
        decision.string_forecasts = string_forecasts

        # Hausverbrauch abziehen
        hours_left = max(0.1, (
            datetime.combine(now.date(), active_goal.target_time) - now
        ).seconds / 3600)
        consumption_kwh = avg_consumption_kwh_per_hour * hours_left
        available_pv = max(0, pv_corrected - consumption_kwh)

        # Optimalen Ladestrom berechnen (prognosebasiert)
        current_amps = (needed_kwh * 1000 / BATTERY_VOLTAGE / hours_left) * 1.2
        current_amps = round(max(MIN_CHARGE_CURRENT, min(MAX_CHARGE_CURRENT, current_amps)), 1)
        current_amps, temp_limited = self._apply_temp_limit(current_amps, battery_temp)
        decision.recommended_charge_current_amps = current_amps
        decision.temp_limited = temp_limited

        grid_needed = max(0, needed_kwh - available_pv)
        decision.grid_charge_kwh = round(grid_needed, 2)

        strings_info = ", ".join(f"{k}: {v:.1f} kWh" for k, v in string_forecasts.items())

        if grid_needed > 0.5:
            decision.should_charge_from_grid = True
            decision.reason = (
                f"Ziel {active_goal.target_soc:.0f}% bis "
                f"{active_goal.target_time.strftime('%H:%M')}: "
                f"Brauche {needed_kwh:.1f} kWh, PV {available_pv:.1f} kWh ({strings_info}), "
                f"Netz: {grid_needed:.1f} kWh, Strom: {current_amps}A"
                + (" ⚠️ Temperaturlimit" if temp_limited else "")
            )
        else:
            decision.reason = (
                f"Ziel {active_goal.target_soc:.0f}% bis "
                f"{active_goal.target_time.strftime('%H:%M')}: "
                f"PV reicht! {available_pv:.1f} kWh, Strom: {current_amps}A"
                + (" ⚠️ Temperaturlimit" if temp_limited else "")
            )

        _LOGGER.info("Batterieentscheidung: %s", decision.reason)
        return decision
