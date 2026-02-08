from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .config_flow import PowerHelperOptionsFlowHandler  # OptionsFlow aus config_flow importieren


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up power_helper from a config entry."""
    # Domain-Datenspeicher sicherstellen
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    # Reload bei Options-Änderungen
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Plattformen weiterleiten (z. B. Sensoren)
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
