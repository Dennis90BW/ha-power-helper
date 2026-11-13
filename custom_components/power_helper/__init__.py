from __future__ import annotations

import logging
from types import MappingProxyType

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .card import async_register_card
from .config_flow import battery_data
from .const import (
    BATTERY_KEYS,
    CONF_BAT_CHARGE,
    CONF_BAT_DISCHARGE,
    CONF_BAT_POWER,
    CONF_PV_POWER,
    DOMAIN,
    SUBENTRY_BATTERY,
    SUBENTRY_PV,
)
from .hub import PowerHelperHub

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]
CURRENT_VERSION = 3

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type PowerHelperConfigEntry = ConfigEntry[PowerHelperHub]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Einmal pro Start: Leistungsfluss-Karte fürs Dashboard bereitstellen."""
    await async_register_card(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PowerHelperConfigEntry) -> bool:
    """Set up power_helper from a config entry."""
    hub = PowerHelperHub(hass, entry)
    entry.runtime_data = hub
    entry.async_on_unload(hub.async_start())

    # Reload bei Änderungen (Optionen sowie PV-Anlagen/Akkus hinzufügen/bearbeiten/löschen)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PowerHelperConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: PowerHelperConfigEntry) -> None:
    """Reload the config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


def _add_subentry(hass: HomeAssistant, entry: ConfigEntry, subentry_type: str, title: str, data: dict) -> None:
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(data),
            subentry_type=subentry_type,
            title=title,
            unique_id=None,
        ),
    )


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migration alter Einträge (Schritt für Schritt bis CURRENT_VERSION).

    Version 1 → 2: Der Akku aus der Hauptkonfiguration wird zum Subentry "Akku".
    Version 2 → 3: Jeder PV-Sensor wird zu einem Subentry ("PV" bzw. "PV 1", "PV 2", …).
    Die Gesamt-Sensoren behalten ihre unique_id (Verlauf bleibt erhalten).
    """
    if entry.version > CURRENT_VERSION:
        return False

    if entry.version == 1:
        cfg = dict(entry.options or entry.data)
        bat = {k: cfg.pop(k) for k in BATTERY_KEYS if k in cfg}
        has_battery = bool(
            bat.get(CONF_BAT_POWER)
            or (bat.get(CONF_BAT_CHARGE) and bat.get(CONF_BAT_DISCHARGE))
        )

        hass.config_entries.async_update_entry(entry, data=cfg, options={}, version=2)
        if has_battery:
            _add_subentry(hass, entry, SUBENTRY_BATTERY, "Akku", battery_data(bat))
        _LOGGER.info(
            "powerHELPER '%s': auf Version 2 migriert (Akku übernommen: %s)",
            entry.title,
            has_battery,
        )

    if entry.version == 2:
        cfg = dict(entry.options or entry.data)
        pv = cfg.pop(CONF_PV_POWER, None) or []
        if isinstance(pv, str):
            pv = [pv]

        hass.config_entries.async_update_entry(entry, data=cfg, options={}, version=3)
        for idx, sensor in enumerate(pv, start=1):
            title = "PV" if len(pv) == 1 else f"PV {idx}"
            _add_subentry(hass, entry, SUBENTRY_PV, title, {CONF_PV_POWER: sensor})
        _LOGGER.info(
            "powerHELPER '%s': auf Version 3 migriert (%d PV-Anlage(n) übernommen)",
            entry.title,
            len(pv),
        )

    return True
