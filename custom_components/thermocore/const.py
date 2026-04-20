"""Constants for HA-ThermoCore."""

DOMAIN = "thermocore"

PLATFORMS = ["sensor"]

# Module names
MODULE_HEATCORE = "heatcore"
MODULE_SOLARCORE = "solarcore"
MODULE_STORAGECORE = "storagecore"
MODULE_WATERCORE = "watercore"
MODULE_AIRCORE = "aircore"
MODULE_ENERGYBRAIN = "energybrain"

# EnergyBrain operating modes
MODE_AUTO = "auto"
MODE_ECO = "eco"
MODE_COMFORT = "comfort"
MODE_AWAY = "away"
MODE_BOOST = "boost"  # PV-Überschuss vorhanden

# SG-Ready states (Wärmepumpe)
SG_READY_BLOCKED = 1       # Betrieb gesperrt
SG_READY_NORMAL = 2        # Normalbetrieb
SG_READY_BOOSTED = 3       # Erhöhter Betrieb (PV-Überschuss)
SG_READY_MAX = 4           # Maximalbetrieb

# Config entry keys
CONF_MODULES = "modules"
CONF_PV_ENTITY = "pv_power_entity"
CONF_GRID_ENTITY = "grid_power_entity"
CONF_BATTERY_SOC_ENTITY = "battery_soc_entity"
CONF_HEAT_PUMP_ENTITY = "heat_pump_entity"
CONF_BOILER_ENTITY = "boiler_entity"
CONF_DYNAMIC_TARIFF = "dynamic_tariff_enabled"
CONF_TARIFF_ENTITY = "tariff_entity"

# Thresholds (Watt)
DEFAULT_PV_SURPLUS_THRESHOLD = 1000   # ab 1kW Überschuss → Boiler/WP hochregeln
DEFAULT_PV_EXPORT_THRESHOLD = 500     # ab 500W Export → Maßnahmen einleiten
DEFAULT_BATTERY_MIN_SOC = 20          # Batterie nie unter 20% entladen
DEFAULT_BATTERY_TARGET_SOC = 80       # Normales Ladeziel
