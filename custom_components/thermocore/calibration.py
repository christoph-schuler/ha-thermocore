"""Kalibrierung der PV-Prognose für HA-ThermoCore.

Vergleicht täglich Prognose vs. tatsächlichen Ertrag und berechnet
einen gleitenden Korrekturfaktor über die letzten 7 Tage.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from collections import deque
import json

_LOGGER = logging.getLogger(__name__)

CALIBRATION_STORAGE_KEY = "thermocore_calibration"
MAX_HISTORY_DAYS = 7




class CalibrationEntry:
    """Ein Kalibrierungseintrag für einen Tag."""

    def __init__(self, date: str, forecast_kwh: float, actual_kwh: float):
        self.date = date
        self.forecast_kwh = forecast_kwh
        self.actual_kwh = actual_kwh

    @property
    def factor(self) -> float:
        """Korrekturfaktor für diesen Tag."""
        if self.forecast_kwh <= 0:
            return 1.0
        return round(self.actual_kwh / self.forecast_kwh, 3)

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "forecast_kwh": self.forecast_kwh,
            "actual_kwh": self.actual_kwh,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CalibrationEntry":
        return cls(
            date=data["date"],
            forecast_kwh=data["forecast_kwh"],
            actual_kwh=data["actual_kwh"],
        )


class PVCalibration:
    """Verwaltet die PV-Prognose-Kalibrierung."""

    def __init__(self, hass, storage_path: str = "/config/.storage/thermocore_calibration.json"):
        self.hass = hass
        self.storage_path = storage_path
        self._history: deque[CalibrationEntry] = deque(maxlen=MAX_HISTORY_DAYS)
        self._today_forecast: float = 0.0

    async def async_load(self) -> None:
        """Lädt gespeicherte Kalibrierungsdaten."""
        try:
            import aiofiles
            async with aiofiles.open(self.storage_path, "r") as f:
                data = json.loads(await f.read())
                for entry in data.get("history", []):
                    self._history.append(CalibrationEntry.from_dict(entry))
                self._today_forecast = data.get("today_forecast", 0.0)
                _LOGGER.info("Kalibrierungsdaten geladen: %d Einträge", len(self._history))
        except FileNotFoundError:
            _LOGGER.info("Keine Kalibrierungsdaten gefunden – starte neu")
        except Exception as err:
            _LOGGER.error("Fehler beim Laden der Kalibrierung: %s", err)

    async def async_save(self) -> None:
        """Speichert Kalibrierungsdaten."""
        try:
            import aiofiles
            data = {
                "history": [e.to_dict() for e in self._history],
                "today_forecast": self._today_forecast,
            }
            async with aiofiles.open(self.storage_path, "w") as f:
                await f.write(json.dumps(data, indent=2))
        except Exception as err:
            _LOGGER.error("Fehler beim Speichern der Kalibrierung: %s", err)

    def set_today_forecast(self, forecast_kwh: float) -> None:
        """Setzt die heutige Prognose (wird morgen verglichen)."""
        self._today_forecast = forecast_kwh
        _LOGGER.debug("Heutige PV-Prognose gesetzt: %.1f kWh", forecast_kwh)

    async def record_actual(self, actual_kwh: float) -> None:
        """Speichert den tatsächlichen Tagesertrag und berechnet Faktor."""
        if self._today_forecast <= 0:
            _LOGGER.warning("Keine heutige Prognose gesetzt – überspringe Kalibrierung")
            return

        today = datetime.now().strftime("%Y-%m-%d")
        entry = CalibrationEntry(
            date=today,
            forecast_kwh=self._today_forecast,
            actual_kwh=actual_kwh,
        )
        self._history.append(entry)
        _LOGGER.info(
            "Kalibrierung: %s Prognose=%.1f kWh, Ist=%.1f kWh, Faktor=%.2f",
            today, self._today_forecast, actual_kwh, entry.factor
        )
        await self.async_save()

    @property
    def calibration_factor(self) -> float:
        """Gleitender Korrekturfaktor der letzten Tage."""
        if not self._history:
            return 1.0

        # Gewichteter Durchschnitt – neuere Tage zählen mehr
        total_weight = 0.0
        weighted_sum = 0.0

        for i, entry in enumerate(self._history):
            # Neueste Einträge haben höheres Gewicht
            weight = i + 1
            weighted_sum += entry.factor * weight
            total_weight += weight

        factor = weighted_sum / total_weight if total_weight > 0 else 1.0

        # Faktor begrenzen: 0.5 bis 1.5 (nie mehr als 50% Abweichung)
        factor = max(0.5, min(1.5, factor))

        _LOGGER.debug(
            "Kalibrierungsfaktor: %.2f (aus %d Tagen)",
            factor, len(self._history)
        )
        return round(factor, 3)

    @property
    def history_summary(self) -> str:
        """Zusammenfassung der Kalibrierungshistorie."""
        if not self._history:
            return "Noch keine Daten"
        lines = []
        for entry in self._history:
            lines.append(
                f"{entry.date}: Prognose {entry.forecast_kwh:.1f} kWh, "
                f"Ist {entry.actual_kwh:.1f} kWh, "
                f"Faktor {entry.factor:.2f}"
            )
        return "\n".join(lines)