"""Leistungsfluss-Karte fürs Dashboard bereitstellen.

Die Karte (frontend/power-helper-card.js) wird unter einer statischen URL
ausgeliefert und dem Frontend als zusätzliches Modul gemeldet. Nutzer müssen
sie dadurch nicht selbst als Dashboard-Ressource eintragen.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_loaded_integration

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

URL_BASE = f"/{DOMAIN}_static"
CARD_FILE = "power-helper-card.js"
FRONTEND_DIR = Path(__file__).parent / "frontend"
DATA_CARD_URL = f"{DOMAIN}_card_url"


def card_url(version: str, digest: str) -> str:
    """URL der Karte mit Version und Fingerabdruck der Datei.

    HA liefert statische Dateien mit langem Browser-Cache aus (31 Tage).
    Ändert sich die Datei, ändert sich der Fingerabdruck und damit die URL –
    Browser laden die neue Karte dann zuverlässig, auch ohne Versionssprung.
    """
    return f"{URL_BASE}/{CARD_FILE}?v={version}-{digest}"


def _file_digest() -> str:
    return hashlib.sha256((FRONTEND_DIR / CARD_FILE).read_bytes()).hexdigest()[:8]


async def async_register_card(hass: HomeAssistant) -> None:
    """Karte einmalig registrieren (statischer Pfad + Frontend-Modul)."""
    if DATA_CARD_URL in hass.data:
        return
    if getattr(hass, "http", None) is None:
        # z. B. in Tests ohne HTTP-Server
        _LOGGER.debug("Kein HTTP-Server – Leistungsfluss-Karte wird nicht registriert")
        return

    from homeassistant.components.http import StaticPathConfig

    await hass.http.async_register_static_paths(
        [StaticPathConfig(URL_BASE, str(FRONTEND_DIR), True)]
    )

    digest = await hass.async_add_executor_job(_file_digest)
    url = card_url(str(async_get_loaded_integration(hass, DOMAIN).version), digest)
    if "frontend" in hass.config.components:
        from homeassistant.components.frontend import add_extra_js_url

        add_extra_js_url(hass, url)
    hass.data[DATA_CARD_URL] = url
    _LOGGER.debug("Leistungsfluss-Karte registriert: %s", url)
