from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
)

from .const import (
    CONF_BAT_CHARGE,
    CONF_BAT_DISCHARGE,
    CONF_BAT_INVERTED,
    CONF_BAT_NAME,
    CONF_BAT_POWER,
    CONF_BAT_PRIO,
    CONF_GRID_EXPORT,
    CONF_GRID_IMPORT,
    CONF_GRID_POWER,
    CONF_PV_NAME,
    CONF_PV_POWER,
    CONF_TITLE,
    DOMAIN,
    SUBENTRY_BATTERY,
    SUBENTRY_PV,
)

DEFAULT_BATTERY_NAME = "Akku"
DEFAULT_PV_NAME = "PV"


# ============================================================
# Gemeinsame Helfer
# ============================================================

def _power_selector() -> EntitySelector:
    return EntitySelector(
        EntitySelectorConfig(
            domain="sensor",
            device_class=SensorDeviceClass.POWER,
            multiple=False,
        )
    )


def _suggested(value: Any) -> dict:
    """Vorbelegung ohne `default`.

    Mit `default=` würde voluptuous einen geleerten Selector (Key fehlt im
    user_input) wieder mit dem alten Wert auffüllen – Sensoren ließen sich
    dann nicht entfernen. `suggested_value` füllt nur das Formular vor.
    """
    return {"suggested_value": value}


def _count_subentries(entry: config_entries.ConfigEntry, subentry_type: str) -> int:
    return sum(1 for s in entry.subentries.values() if s.subentry_type == subentry_type)


def validate_either_or(
    *,
    total: str | None,
    part_a: str | None,
    part_b: str | None,
    allow_empty: bool,
) -> None:
    """Entweder ein Gesamtsensor ODER beide Einzelsensoren."""
    # komplett leer
    if not total and not part_a and not part_b:
        if allow_empty:
            return
        raise ValueError("missing_required_sensors")

    # gemischt
    if total and (part_a or part_b):
        raise ValueError("choose_either_total_or_split")

    # split unvollständig
    if not total and (bool(part_a) ^ bool(part_b)):
        raise ValueError("missing_required_sensors")


# ---------------- Netz ----------------

def _grid_schema(current: dict | None = None) -> vol.Schema:
    current = current or {}
    return vol.Schema(
        {
            vol.Optional(
                key, description=_suggested(current.get(key))
            ): vol.Maybe(_power_selector())
            for key in (CONF_GRID_POWER, CONF_GRID_IMPORT, CONF_GRID_EXPORT)
        }
    )


def _validate_grid(user_input: dict) -> None:
    validate_either_or(
        total=user_input.get(CONF_GRID_POWER),
        part_a=user_input.get(CONF_GRID_IMPORT),
        part_b=user_input.get(CONF_GRID_EXPORT),
        allow_empty=False,
    )


# ---------------- PV-Anlage ----------------

def pv_schema(
    current: dict | None = None, name: str | None = None, required: bool = True
) -> vol.Schema:
    """Formular für eine PV-Anlage. Bei der Ersteinrichtung ist sie optional."""
    current = current or {}
    key = vol.Required if required else vol.Optional
    return vol.Schema(
        {
            key(CONF_PV_NAME, description=_suggested(name)): str,
            key(CONF_PV_POWER, description=_suggested(current.get(CONF_PV_POWER))): (
                _power_selector()
            ),
        }
    )


def pv_data(user_input: dict) -> dict:
    return {CONF_PV_POWER: user_input[CONF_PV_POWER]}


# ---------------- Akku ----------------

def battery_schema(
    current: dict | None = None, name: str | None = None, name_required: bool = True
) -> vol.Schema:
    """Formular für einen Akku (Ersteinrichtung, Hinzufügen, Bearbeiten).

    Bei der Ersteinrichtung ist der Akku optional – dann auch der Name.
    """
    current = current or {}
    name_key = vol.Required if name_required else vol.Optional
    return vol.Schema(
        {
            name_key(CONF_BAT_NAME, description=_suggested(name)): str,
            vol.Optional(
                CONF_BAT_POWER, description=_suggested(current.get(CONF_BAT_POWER))
            ): _power_selector(),
            vol.Optional(
                CONF_BAT_INVERTED, default=current.get(CONF_BAT_INVERTED, False)
            ): bool,
            vol.Optional(
                CONF_BAT_CHARGE, description=_suggested(current.get(CONF_BAT_CHARGE))
            ): _power_selector(),
            vol.Optional(
                CONF_BAT_DISCHARGE,
                description=_suggested(current.get(CONF_BAT_DISCHARGE)),
            ): _power_selector(),
            vol.Optional(CONF_BAT_PRIO, default=current.get(CONF_BAT_PRIO, False)): bool,
        }
    )


def validate_battery(user_input: dict, *, allow_empty: bool) -> None:
    validate_either_or(
        total=user_input.get(CONF_BAT_POWER),
        part_a=user_input.get(CONF_BAT_CHARGE),
        part_b=user_input.get(CONF_BAT_DISCHARGE),
        allow_empty=allow_empty,
    )


def battery_data(user_input: dict) -> dict:
    """Nur relevante, gesetzte Felder speichern (Name wird zum Subentry-Titel)."""
    data: dict[str, Any] = {
        CONF_BAT_PRIO: bool(user_input.get(CONF_BAT_PRIO, False)),
    }
    if user_input.get(CONF_BAT_POWER):
        data[CONF_BAT_POWER] = user_input[CONF_BAT_POWER]
        data[CONF_BAT_INVERTED] = bool(user_input.get(CONF_BAT_INVERTED, False))
    else:
        data[CONF_BAT_CHARGE] = user_input[CONF_BAT_CHARGE]
        data[CONF_BAT_DISCHARGE] = user_input[CONF_BAT_DISCHARGE]
    return data


def has_battery_input(user_input: dict) -> bool:
    return bool(
        user_input.get(CONF_BAT_POWER)
        or user_input.get(CONF_BAT_CHARGE)
        or user_input.get(CONF_BAT_DISCHARGE)
    )


# ============================================================
# Config Flow (Ersteinrichtung)
# ============================================================

class PowerHelperConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    # Version 2: Akkus als Subentries, Version 3: PV-Anlagen als Subentries
    # (siehe async_migrate_entry)
    VERSION = 3

    def __init__(self) -> None:
        self._data: dict = {}
        self._title: str | None = None
        self._subentries: list[config_entries.ConfigSubentryData] = []

    @staticmethod
    def async_get_options_flow(config_entry):
        return PowerHelperOptionsFlowHandler(config_entry)

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: config_entries.ConfigEntry
    ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
        return {
            SUBENTRY_PV: PvSubentryFlowHandler,
            SUBENTRY_BATTERY: BatterySubentryFlowHandler,
        }

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._title = user_input[CONF_TITLE]
            return await self.async_step_grid()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TITLE, default="powerHELPER"): str,
                }
            ),
        )

    async def async_step_grid(self, user_input=None):
        errors = {}

        if user_input is not None:
            try:
                _validate_grid(user_input)
            except ValueError as err:
                errors["base"] = err.args[0]
            else:
                self._data.update({k: v for k, v in user_input.items() if v})
                return await self.async_step_pv()

        return self.async_show_form(
            step_id="grid",
            data_schema=_grid_schema(user_input),
            errors=errors,
        )

    async def async_step_pv(self, user_input=None):
        """Optional: erste PV-Anlage. Weitere später über 'PV-Anlage hinzufügen'."""
        if user_input is not None:
            if user_input.get(CONF_PV_POWER):
                self._subentries.append(
                    config_entries.ConfigSubentryData(
                        data=pv_data(user_input),
                        subentry_type=SUBENTRY_PV,
                        title=user_input.get(CONF_PV_NAME) or DEFAULT_PV_NAME,
                        unique_id=None,
                    )
                )
            return await self.async_step_battery()

        return self.async_show_form(
            step_id="pv",
            data_schema=pv_schema(name=f"{DEFAULT_PV_NAME} 1", required=False),
        )

    async def async_step_battery(self, user_input=None):
        """Optional: erster Akku. Weitere Akkus später über 'Akku hinzufügen'."""
        errors = {}

        if user_input is not None:
            try:
                validate_battery(user_input, allow_empty=True)
            except ValueError as err:
                errors["base"] = err.args[0]
            else:
                if has_battery_input(user_input):
                    self._subentries.append(
                        config_entries.ConfigSubentryData(
                            data=battery_data(user_input),
                            subentry_type=SUBENTRY_BATTERY,
                            title=user_input.get(CONF_BAT_NAME) or DEFAULT_BATTERY_NAME,
                            unique_id=None,
                        )
                    )
                return self.async_create_entry(
                    title=self._title or "Power Helper",
                    data=self._data,
                    subentries=self._subentries,
                )

        return self.async_show_form(
            step_id="battery",
            data_schema=battery_schema(
                user_input,
                name=(user_input or {}).get(CONF_BAT_NAME, f"{DEFAULT_BATTERY_NAME} 1"),
                name_required=False,
            ),
            errors=errors,
        )


# ============================================================
# Subentry Flow: PV-Anlage hinzufügen / bearbeiten
# ============================================================

class PvSubentryFlowHandler(config_entries.ConfigSubentryFlow):
    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_PV_NAME], data=pv_data(user_input)
            )

        count = _count_subentries(self._get_entry(), SUBENTRY_PV)
        return self.async_show_form(
            step_id="user",
            data_schema=pv_schema(name=f"{DEFAULT_PV_NAME} {count + 1}"),
        )

    async def async_step_reconfigure(self, user_input=None):
        subentry = self._get_reconfigure_subentry()

        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                title=user_input[CONF_PV_NAME],
                data=pv_data(user_input),
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=pv_schema(dict(subentry.data), name=subentry.title),
        )


# ============================================================
# Subentry Flow: Akku hinzufügen / bearbeiten
# ============================================================

class BatterySubentryFlowHandler(config_entries.ConfigSubentryFlow):
    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            try:
                validate_battery(user_input, allow_empty=False)
            except ValueError as err:
                errors["base"] = err.args[0]
            else:
                return self.async_create_entry(
                    title=user_input[CONF_BAT_NAME],
                    data=battery_data(user_input),
                )

        count = _count_subentries(self._get_entry(), SUBENTRY_BATTERY)
        return self.async_show_form(
            step_id="user",
            data_schema=battery_schema(
                user_input,
                name=(user_input or {}).get(CONF_BAT_NAME, f"{DEFAULT_BATTERY_NAME} {count + 1}"),
            ),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None):
        subentry = self._get_reconfigure_subentry()
        errors = {}

        if user_input is not None:
            try:
                validate_battery(user_input, allow_empty=False)
            except ValueError as err:
                errors["base"] = err.args[0]
            else:
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    title=user_input[CONF_BAT_NAME],
                    data=battery_data(user_input),
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=battery_schema(
                user_input or dict(subentry.data),
                name=(user_input or {}).get(CONF_BAT_NAME, subentry.title),
            ),
            errors=errors,
        )


# ============================================================
# Options Flow: Netz ändern (PV-Anlagen und Akkus über Subentries)
# ============================================================

class PowerHelperOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry):
        self._data = dict(config_entry.options or config_entry.data)

    async def async_step_init(self, user_input=None):
        return await self.async_step_grid()

    async def async_step_grid(self, user_input=None):
        errors = {}

        if user_input is not None:
            try:
                _validate_grid(user_input)
            except ValueError as err:
                errors["base"] = err.args[0]
            else:
                for key in (CONF_GRID_POWER, CONF_GRID_IMPORT, CONF_GRID_EXPORT):
                    value = user_input.get(key)
                    if value:
                        self._data[key] = value
                    else:
                        self._data.pop(key, None)
                return self.async_create_entry(data=self._data)

        return self.async_show_form(
            step_id="grid",
            data_schema=_grid_schema(self._data),
            errors=errors,
        )
