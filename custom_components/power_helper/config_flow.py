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
CONF_BAT_INVERTED = "akku_leistung_invertiert"


# ============================================================
# Gemeinsame Basis-Klasse für Config- & Options-Flow
# ============================================================

class PowerHelperFlowBase:
    def __init__(self):
        self._data: dict = {}
        self._title: str | None = None

    def _power_selector(self) -> EntitySelector:
        return EntitySelector(
            EntitySelectorConfig(
                domain="sensor",
                device_class=SensorDeviceClass.POWER,
                multiple=False,
            )
        )
    
    def _power_selector_multi(self) -> EntitySelector:
        return EntitySelector(
            EntitySelectorConfig(
                domain="sensor",
                device_class=SensorDeviceClass.POWER,
                multiple=True,
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

        # split unvollständig
        if not total and (bool(part_a) ^ bool(part_b)):
            raise ValueError("missing_required_sensors")


# ============================================================
# Config Flow (Ersteinrichtung)
# ============================================================

class PowerHelperConfigFlow(
    config_entries.ConfigFlow, PowerHelperFlowBase, domain=DOMAIN
):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return PowerHelperOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._title = user_input[CONF_TITLE]
            return await self.async_step_grid()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TITLE, default="Mein Stromkreis"): str,
                }
            ),
        )

    async def async_step_grid(self, user_input=None):
        errors = {}

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

        return self.async_show_form(
            step_id="grid",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_GRID_POWER): self._power_selector(),
                    vol.Optional(CONF_GRID_IMPORT): self._power_selector(),
                    vol.Optional(CONF_GRID_EXPORT): self._power_selector(),
                }
            ),
            errors=errors,
        )

    async def async_step_pv(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_battery()

        return self.async_show_form(
            step_id="pv",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_PV_POWER): self._power_selector_multi(),
                }
            ),
        )

    async def async_step_battery(self, user_input=None):
        errors = {}

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

        return self.async_show_form(
            step_id="battery",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_BAT_POWER): self._power_selector(),
                    vol.Optional(CONF_BAT_INVERTED, default=False): bool,
                    vol.Optional(CONF_BAT_CHARGE): self._power_selector(),
                    vol.Optional(CONF_BAT_DISCHARGE): self._power_selector(),
                    vol.Optional(CONF_BAT_PRIO, default=False): bool,
                }
            ),
            errors=errors,
        )

# ============================================================
# Options Flow
# ============================================================

class PowerHelperOptionsFlowHandler(
    config_entries.OptionsFlow, PowerHelperFlowBase
):
    def __init__(self, config_entry: config_entries.ConfigEntry):
        PowerHelperFlowBase.__init__(self)
        self._config_entry = config_entry
        self._data = dict(config_entry.options or config_entry.data)

    def _update_optional(self, key, user_input):
        value = user_input.get(key)
        if value in (None, ""):
            self._data.pop(key, None)
        else:
            self._data[key] = value

    async def async_step_init(self, user_input=None):
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        return await self.async_step_select_step()
    
    async def async_step_select_step(self, user_input=None):
        steps = {
            "grid": "Grid Power",
            "pv": "PV Power",
            "battery": "Battery Power"
        }

        if user_input is not None:
            # spring direkt zum ausgewählten Step
            return await getattr(self, f"async_step_{user_input['step']}")()

        return self.async_show_form(
            step_id="select_step",
            data_schema=vol.Schema(
                {vol.Required("step"): vol.In(steps)}
            ),
        )


    async def async_step_grid(self, user_input=None):
        errors = {}

        if user_input is not None:
            try:
                self._validate_either_or(
                    total=user_input.get(CONF_GRID_POWER),
                    part_a=user_input.get(CONF_GRID_IMPORT),
                    part_b=user_input.get(CONF_GRID_EXPORT),
                    allow_empty=True,
                )
            except ValueError as err:
                errors["base"] = err.args[0]
            else:
                for key in [CONF_GRID_POWER, CONF_GRID_IMPORT, CONF_GRID_EXPORT]:
                    self._update_optional(key, user_input)

                return self.async_create_entry(data=self._data)

        return self.async_show_form(
            step_id="grid",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_GRID_POWER,
                        default=self._data.get(CONF_GRID_POWER),
                    ): vol.Maybe(self._power_selector()),
                    vol.Optional(
                        CONF_GRID_IMPORT,
                        default=self._data.get(CONF_GRID_IMPORT),
                    ): vol.Maybe(self._power_selector()),
                    vol.Optional(
                        CONF_GRID_EXPORT,
                        default=self._data.get(CONF_GRID_EXPORT),
                    ): vol.Maybe(self._power_selector()),
                }
            ),
            errors=errors,
        )

    async def async_step_pv(self, user_input=None):
        if user_input is not None:
            for key in [CONF_PV_POWER]:
                self._update_optional(key, user_input)
            return self.async_create_entry(data=self._data)
        # Überprüfen, ob wir bereits eine bestehende Konfiguration haben und den Wert in eine Liste umwandeln
        existing_pv_power = self._data.get(CONF_PV_POWER)    
        if isinstance(existing_pv_power, str):
            self._data[CONF_PV_POWER] = [existing_pv_power]

        return self.async_show_form(
            step_id="pv",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_PV_POWER,
                        default=self._data.get(CONF_PV_POWER),
                    ): vol.Maybe(self._power_selector_multi()),
                }
            ),
        )

    async def async_step_battery(self, user_input=None):
        errors = {}

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
                for key in [
                    CONF_BAT_POWER,
                    CONF_BAT_CHARGE,
                    CONF_BAT_DISCHARGE,
                    CONF_BAT_PRIO,
                    CONF_BAT_INVERTED,
                ]:
                    self._update_optional(key, user_input)
                return self.async_create_entry(data=self._data)


        return self.async_show_form(
            step_id="battery",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_BAT_POWER,
                        default=self._data.get(CONF_BAT_POWER),
                    ): vol.Maybe(self._power_selector()),
                    vol.Optional(
                        CONF_BAT_INVERTED,
                        default=self._data.get(CONF_BAT_INVERTED, False),
                    ): bool,
                    vol.Optional(
                        CONF_BAT_CHARGE,
                        default=self._data.get(CONF_BAT_CHARGE),
                    ): vol.Maybe(self._power_selector()),
                    vol.Optional(
                        CONF_BAT_DISCHARGE,
                        default=self._data.get(CONF_BAT_DISCHARGE),
                    ): vol.Maybe(self._power_selector()),
                    vol.Optional(
                        CONF_BAT_PRIO,
                        default=self._data.get(CONF_BAT_PRIO, False),
                    ): bool,
                }
            ),
            errors=errors,
        )
