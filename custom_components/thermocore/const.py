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
MODE_BOOST = "boost"

# SG-Ready states
SG_READY_BLOCKED = 1
SG_READY_NORMAL = 2
SG_READY_BOOSTED = 3
SG_READY_MAX = 4

# Sensoren
CONF_MODULES = "modules"
CONF_PV_ENTITY = "pv_power_entity"
CONF_GRID_ENTITY = "grid_power_entity"
CONF_BATTERY_SOC_ENTITY = "battery_soc_entity"
CONF_HEAT_PUMP_ENTITY = "heat_pump_entity"
CONF_BOILER_ENTITY = "boiler_entity"
CONF_DYNAMIC_TARIFF = "dynamic_tariff_enabled"
CONF_TARIFF_ENTITY = "tariff_entity"

# Batterie
CONF_BATTERY_USE_SENSOR = "battery_use_capacity_sensor"
CONF_BATTERY_CAPACITY_ENTITY = "battery_capacity_entity"
CONF_BATTERY_CAPACITY_KWH = "battery_capacity_kwh"
CONF_BATTERY_CHARGE_CURRENT_ENTITY = "battery_charge_current_entity"
CONF_BATTERY_TEMPERATURE_ENTITY = "battery_temperature_entity"

# Tagesziele
CONF_CHARGE_GOAL_1_SOC = "charge_goal_1_soc"
CONF_CHARGE_GOAL_1_TIME = "charge_goal_1_time"
CONF_CHARGE_GOAL_2_SOC = "charge_goal_2_soc"
CONF_CHARGE_GOAL_2_TIME = "charge_goal_2_time"
CONF_CHARGE_GOAL_3_SOC = "charge_goal_3_soc"
CONF_CHARGE_GOAL_3_TIME = "charge_goal_3_time"

# Nachtladung
CONF_NIGHT_CHARGE_ENABLED = "night_charge_enabled"
CONF_NIGHT_CHARGE_START = "night_charge_start"
CONF_NIGHT_CHARGE_END = "night_charge_end"
CONF_NIGHT_CHARGE_MODE = "night_charge_mode"
CONF_NIGHT_CHARGE_FIXED_SOC = "night_charge_fixed_soc"
CONF_NIGHT_CHARGE_GOOD_WEATHER_THRESHOLD = "night_charge_good_weather_kwh"
CONF_NIGHT_CHARGE_GOOD_WEATHER_SOC = "night_charge_good_weather_soc"
CONF_NIGHT_CHARGE_MID_WEATHER_THRESHOLD = "night_charge_mid_weather_kwh"
CONF_NIGHT_CHARGE_MID_WEATHER_SOC = "night_charge_mid_weather_soc"
CONF_NIGHT_CHARGE_BAD_WEATHER_SOC = "night_charge_bad_weather_soc"

# Wöchentliches Balancing
CONF_BALANCING_ENABLED = "balancing_enabled"
CONF_BALANCING_WEEKDAY = "balancing_weekday"  # 0=Mo, 6=So
CONF_BALANCING_TARGET_SOC = "balancing_target_soc"  # z.B. 100
CONF_BALANCING_ABSORPTION_SOC = "balancing_absorption_soc"  # z.B. 95
CONF_BALANCING_HOLD_MINUTES = "balancing_hold_minutes"  # z.B. 90

# Temperaturschutz
CONF_TEMP_PROTECTION_ENABLED = "temp_protection_enabled"
CONF_TEMP_MIN_CELSIUS = "temp_min_celsius"  # z.B. 5
CONF_TEMP_MAX_CURRENT_COLD = "temp_max_current_cold"  # z.B. 2 (Ampere bei Kälte)

# Wetter & PV
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_PV_PEAK_POWER = "pv_peak_power_kwp"

# Thresholds
DEFAULT_PV_SURPLUS_THRESHOLD = 1000
DEFAULT_PV_EXPORT_THRESHOLD = 500
DEFAULT_BATTERY_MIN_SOC = 10
DEFAULT_BATTERY_TARGET_SOC = 80
DEFAULT_TEMP_MIN_CELSIUS = 5
DEFAULT_TEMP_MAX_CURRENT_COLD = 2.0
