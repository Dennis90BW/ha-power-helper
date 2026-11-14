"""Zentrale Berechnung: beobachtet alle Quellsensoren und rechnet einmal für alle Entitäten."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util.unit_conversion import PowerConverter

from .calc import BatteryFlow, compute_flows, compute_ratios
from .const import (
    CONF_BAT_CHARGE,
    CONF_BAT_DISCHARGE,
    CONF_BAT_INVERTED,
    CONF_BAT_POWER,
    CONF_BAT_PRIO,
    CONF_GRID_EXPORT,
    CONF_GRID_IMPORT,
    CONF_GRID_POWER,
    CONF_PV_POWER,
    SUBENTRY_BATTERY,
    SUBENTRY_PV,
)


def power_in_watt(hass: HomeAssistant, entity_id: str | None, invert: bool = False) -> float:
    """Leistung eines Sensors in Watt, optional mit umgekehrtem Vorzeichen.

    Umrechnung über HAs PowerConverter (mW, W, kW, MW, GW, TW, BTU/h).
    Ohne bzw. mit unbekannter Einheit wird der Wert als Watt behandelt.
    """
    if not entity_id:
        return 0.0
    try:
        state = hass.states.get(entity_id)
        if state is None or state.state in (None, "unknown", "unavailable"):
            return 0.0

        value = float(state.state)
        unit = state.attributes.get("unit_of_measurement")
        if unit in PowerConverter.VALID_UNITS and unit != UnitOfPower.WATT:
            value = PowerConverter.convert(value, unit, UnitOfPower.WATT)
        return -value if invert else value
    except (TypeError, ValueError):
        return 0.0


@dataclass(frozen=True)
class PvConfig:
    """Konfiguration einer PV-Anlage (aus einem Subentry)."""

    subentry_id: str
    title: str
    power: str


@dataclass(frozen=True)
class BatteryConfig:
    """Konfiguration eines Akkus (aus einem Subentry)."""

    subentry_id: str
    title: str
    power: str | None
    inverted: bool
    charge: str | None
    discharge: str | None
    prio: bool

    @property
    def is_split(self) -> bool:
        return not self.power

    @property
    def sources(self) -> list[str]:
        return [e for e in (self.power, self.charge, self.discharge) if e]


class PowerHelperHub:
    """Hält die Konfiguration, beobachtet die Quellen und berechnet alle Werte."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        cfg = entry.options or entry.data

        self.grid_power: str | None = cfg.get(CONF_GRID_POWER)
        self.grid_import: str | None = cfg.get(CONF_GRID_IMPORT)
        self.grid_export: str | None = cfg.get(CONF_GRID_EXPORT)
        self.grid_is_split = not self.grid_power and bool(self.grid_import and self.grid_export)

        self.pv: list[PvConfig] = [
            PvConfig(
                subentry_id=sub.subentry_id,
                title=sub.title,
                power=sub.data[CONF_PV_POWER],
            )
            for sub in entry.subentries.values()
            if sub.subentry_type == SUBENTRY_PV and sub.data.get(CONF_PV_POWER)
        ]

        self.batteries: list[BatteryConfig] = [
            BatteryConfig(
                subentry_id=sub.subentry_id,
                title=sub.title,
                power=sub.data.get(CONF_BAT_POWER),
                inverted=bool(sub.data.get(CONF_BAT_INVERTED, False)),
                charge=sub.data.get(CONF_BAT_CHARGE),
                discharge=sub.data.get(CONF_BAT_DISCHARGE),
                prio=bool(sub.data.get(CONF_BAT_PRIO, False)),
            )
            for sub in entry.subentries.values()
            if sub.subentry_type == SUBENTRY_BATTERY
        ]

        self.values: dict[str, float] = {}
        self._listeners: list[Callable[[], None]] = []

    # ---------------- Beobachtung ----------------

    @property
    def tracked_entities(self) -> list[str]:
        ids = [self.grid_power, self.grid_import, self.grid_export]
        ids += [p.power for p in self.pv]
        for bat in self.batteries:
            ids += bat.sources
        return list(dict.fromkeys(e for e in ids if e))

    @callback
    def async_start(self) -> Callable[[], None]:
        """Quellen beobachten und erste Berechnung. Gibt die Abmeldefunktion zurück."""
        self.update()
        return async_track_state_change_event(
            self.hass, self.tracked_entities, self._handle_state_change
        )

    @callback
    def async_add_listener(self, update_callback: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(update_callback)

        @callback
        def remove() -> None:
            if update_callback in self._listeners:
                self._listeners.remove(update_callback)

        return remove

    @callback
    def _handle_state_change(self, _event: Event) -> None:
        self.update()
        for update_callback in list(self._listeners):
            update_callback()

    # ---------------- Berechnung ----------------

    def update(self) -> None:
        w = lambda eid, inv=False: power_in_watt(self.hass, eid, inv)  # noqa: E731
        values: dict[str, float | None] = {}

        # Netz
        if self.grid_is_split:
            imp, exp = w(self.grid_import), w(self.grid_export)
            netz = imp - exp
        else:
            netz = w(self.grid_power)
            imp, exp = max(netz, 0.0), max(-netz, 0.0)
        values.update(netz_leistung=netz, netz_bezug=imp, netz_einspeisung=exp)

        # PV-Anlagen einzeln und gesamt
        pv = 0.0
        for plant in self.pv:
            plant_power = w(plant.power)
            values[f"{plant.subentry_id}_leistung"] = plant_power
            pv += plant_power
        values["pv_leistung"] = pv

        # Akkus einzeln
        flows: list[BatteryFlow] = []
        for bat in self.batteries:
            if bat.is_split:
                flow = BatteryFlow(w(bat.charge), w(bat.discharge), bat.prio)
            else:
                flow = BatteryFlow.from_net(w(bat.power, bat.inverted), bat.prio)
            flows.append(flow)
            net = flow.discharge - flow.charge
            sid = bat.subentry_id
            values[f"{sid}_leistung"] = net
            values[f"{sid}_leistung_inv"] = -net
            values[f"{sid}_laden"] = flow.charge
            values[f"{sid}_entladen"] = flow.discharge

        # Bilanz (Akkus werden darin zuerst miteinander verrechnet)
        values.update(compute_flows(netz=netz, pv=pv, batteries=flows))
        # PV-Eigenverbrauch und Autarkiegrad in % (None = nicht aussagekräftig)
        values.update(compute_ratios(values, pv))
        # -0.0 (z. B. aus max(-0.0, 0.0) oder -0) als 0.0 ausgeben, sonst zeigt HA "-0.0"
        self.values = {k: (v if v is None or v != 0 else 0.0) for k, v in values.items()}
