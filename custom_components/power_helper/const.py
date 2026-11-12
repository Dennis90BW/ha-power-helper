DOMAIN = "power_helper"
NAME = "powerHELPER"

# Hauptkonfiguration
CONF_TITLE = "title"
CONF_GRID_POWER = "netz_leistung"
CONF_GRID_IMPORT = "netz_bezug"
CONF_GRID_EXPORT = "netz_einspeisung"

# PV-Anlage (ab Config-Version 3 als Subentry vom Typ SUBENTRY_PV)
SUBENTRY_PV = "pv"
CONF_PV_NAME = "pv_name"
CONF_PV_POWER = "pv_leistung"

# Akku (ab Config-Version 2 als Subentry vom Typ SUBENTRY_BATTERY)
SUBENTRY_BATTERY = "akku"
CONF_BAT_NAME = "akku_name"
CONF_BAT_POWER = "akku_leistung"
CONF_BAT_CHARGE = "akku_laden"
CONF_BAT_DISCHARGE = "akku_entladen"
CONF_BAT_PRIO = "akku_prio"
CONF_BAT_INVERTED = "akku_leistung_invertiert"

BATTERY_KEYS = (
    CONF_BAT_POWER,
    CONF_BAT_CHARGE,
    CONF_BAT_DISCHARGE,
    CONF_BAT_PRIO,
    CONF_BAT_INVERTED,
)
