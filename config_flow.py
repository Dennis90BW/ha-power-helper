from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
)

from .const import DOMAIN

CONF_TITLE = "title"

CONF_GRID_POWER = "netz_leistung"
CONF_GRID_IMPORT = "netz_bezug"
CONF_GRID_EXPORT = "netz_einspeisung"

CONF_PV_POWER = "pv_leistung"

CONF_BAT_POWER = "akku_leistung"
CONF_BAT_CHARGE = "akku_laden"
CONF_BAT_DISCHARGE = "akku_entladen"
CONF_BAT_PRIO = "akku_prio"


class PowerHelperConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for power_helper."""

    VERSION = 1

    def __init__(self):
        self._data: dict = {}
        self._title: str | None = None

    async def async_step_user(self, user_input=None):
        """Ask for a name/title of this Power Helper."""
        if user_input is not None:
            self._title = user_input[CONF_TITLE]
            return await self.async_step_grid()

        schema = vol.Schema(
            {
                vol.Required(CONF_TITLE, default="Mein Stromkreis"): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )

    async def async_step_grid(self, user_input=None):
        """Grid configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                self._validate_either_or(
                    total=user_input.get(CONF_GRID_POWER),
                    part_a=user_input.get(CONF_GRID_IMPORT),
                    part_b=user_input.get(CONF_GRID_EXPORT),
                    allow_empty=False,
                )
            except ValueError as err:
                errors["base"] = err.args[0]
            else:
                self._data.update(user_input)
                return await self.async_step_pv()

        schema = vol.Schema(
            {
                vol.Optional(CONF_GRID_POWER): self._power_selector(),
                vol.Optional(CONF_GRID_IMPORT): self._power_selector(),
                vol.Optional(CONF_GRID_EXPORT): self._power_selector(),
            }
        )

        return self.async_show_form(
            step_id="grid",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_pv(self, user_input=None):
        """PV configuration (optional)."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_battery()

        schema = vol.Schema(
            {
                vol.Optional(CONF_PV_POWER): self._power_selector(),
            }
        )

        return self.async_show_form(
            step_id="pv",
            data_schema=schema,
        )

    async def async_step_battery(self, user_input=None):
        """Battery configuration (optional)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                self._validate_either_or(
                    total=user_input.get(CONF_BAT_POWER),
                    part_a=user_input.get(CONF_BAT_CHARGE),
                    part_b=user_input.get(CONF_BAT_DISCHARGE),
                    allow_empty=True,
                )
            except ValueError as err:
                errors["base"] = err.args[0]
            else:
                self._data.update(user_input)
                return self.async_create_entry(
                    title=self._title or "Power Helper",
                    data=self._data,
                )

        schema = vol.Schema(
            {
                vol.Optional(CONF_BAT_POWER): self._power_selector(),
                vol.Optional(CONF_BAT_CHARGE): self._power_selector(),
                vol.Optional(CONF_BAT_DISCHARGE): self._power_selector(),
                vol.Optional(CONF_BAT_PRIO, default=False): bool,
            }
        )

        return self.async_show_form(
            step_id="battery",
            data_schema=schema,
            errors=errors,
        )

    def _power_selector(self) -> EntitySelector:
        return EntitySelector(
            EntitySelectorConfig(
                domain="sensor",
                device_class=SensorDeviceClass.POWER,
                multiple=False,
            )
        )

    def _validate_either_or(
        self,
        *,
        total: str | None,
        part_a: str | None,
        part_b: str | None,
        allow_empty: bool,
    ) -> None:
        # komplett leer
        if not total and not part_a and not part_b:
            if allow_empty:
                return
            raise ValueError("missing_required_sensors")

        # gemischt
        if total and (part_a or part_b):
            raise ValueError("choose_either_total_or_split")

        # split unvollstaendig
        if not total and (bool(part_a) ^ bool(part_b)):
            raise ValueError("missing_required_sensors")
