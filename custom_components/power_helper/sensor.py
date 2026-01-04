from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.const import UnitOfPower

from .const import DOMAIN

# =====================================================================
# HELPERS
# =====================================================================

def power_in_watt(hass: HomeAssistant, entry: ConfigEntry, entity_id: str) -> float:
    """Return power in Watt, normalized from W / kW."""
    data = entry.data
    try:
        state = hass.states.get(entity_id)
        if state is None or state.state in (None, "unknown", "unavailable"):
            return 0.0

        value = float(state.state)
        unit = state.attributes.get("unit_of_measurement")

        if unit in (UnitOfPower.KILO_WATT, "kW"):
            return value * 1000
        
        # Akku-Invertierung
        if entity_id == data.get("akku_leistung"):
            invert = data.get("akku_leistung_invertiert", False)
            if invert:
                return -value

        return value
    except Exception:
        return 0.0


# =====================================================================
# SETUP
# =====================================================================

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    sensors: list[SensorEntity] = []
    data = entry.data

    # ==================== GRID ====================

    if data.get("netz_leistung") and not (data.get("netz_bezug") and data.get("netz_einspeisung")):
        sensors += [
            ProxyPowerSensor(hass, source_entity=data["netz_leistung"], entry=entry, key="netz_leistung", name="Netz Leistung"),
            SplitPowerSensor(
                hass,
                source_entity=data["netz_leistung"],
                entry=entry,
                key="netz_bezug",
                name="Netzbezug",
                positive=True,
            ),
            SplitPowerSensor(
                hass,
                source_entity=data["netz_leistung"],
                entry=entry,
                key="netz_einspeisung",
                name="Netzeinspeisung",
                positive=False,
            ),
        ]

    if not data.get("netz_leistung") and (data.get("netz_bezug") and data.get("netz_einspeisung")):
        sensors += [
            ProxyPowerSensor(hass, source_entity=data["netz_bezug"], entry=entry, key="netz_bezug", name="Netz Bezug"),
            ProxyPowerSensor(hass, source_entity=data["netz_einspeisung"], entry=entry, key="netz_einspeisung", name="Netz Einspeisung"),
            CombinedPowerSensor(
                hass,
                pos_entity=data["netz_bezug"],
                neg_entity=data["netz_einspeisung"],
                entry=entry,
                key="netz_leistung",
                name="Netzleistung",
            ),
        ]

    # ==================== BATTERY ====================

    if data.get("akku_leistung") and not (data.get("akku_laden") and data.get("akku_entladen")):
        sensors += [
            ProxyPowerSensor(hass, source_entity=data["akku_leistung"], entry=entry, key="akku_leistung", name="Akku Leistung"),
            SplitPowerSensor(
                hass,
                source_entity=data["akku_leistung"],
                entry=entry,
                key="akku_entladen",
                name="Akku entladen",
                positive=True,
            ),
            SplitPowerSensor(
                hass,
                source_entity=data["akku_leistung"],
                entry=entry,
                key="akku_laden",
                name="Akku laden",
                positive=False,
            ),
        ]

    if not data.get("akku_leistung") and (data.get("akku_laden") and data.get("akku_entladen")):
        sensors += [
            ProxyPowerSensor(hass, source_entity=data["akku_laden"], entry=entry, key="akku_laden", name="Akku Laden"),
            ProxyPowerSensor(hass, source_entity=data["akku_entladen"], entry=entry, key="akku_entladen", name="Akku Entladen"),
            CombinedPowerSensor(
                hass,
                pos_entity=data["akku_entladen"],
                neg_entity=data["akku_laden"],
                entry=entry,
                key="akku_leistung",
                name="Akkuleistung",
            ),
        ]

    # ==================== FLOWS ====================

    flows = {
        "netz": data.get("netz_leistung"),
        "akku": data.get("akku_leistung"),
        "pv": data.get("pv_leistung"),
        "netz_bezug": data.get("netz_bezug"),
        "netz_einspeisung": data.get("netz_einspeisung"),
        "akku_laden": data.get("akku_laden"),
        "akku_entladen": data.get("akku_entladen"),
    }

    sensors.append(FlowPowerSensor(hass, entry, "haus", "Haus Leistung", flows))

    if data.get("pv_leistung"):
        sensors.append(ProxyPowerSensor(hass, source_entity=data["pv_leistung"], entry=entry, key="pv_leistung", name="PV Leistung"))
        sensors.append(FlowPowerSensor(hass, entry, "pv_zu_haus", "PV zu Haus", flows))
        sensors.append(FlowPowerSensor(hass, entry, "pv_zu_netz", "PV zu Netz", flows))

        if data.get("akku_leistung") or (data.get("akku_laden") and data.get("akku_entladen")):
            sensors.append(FlowPowerSensor(hass, entry, "pv_zu_akku", "PV zu Akku", flows))

    sensors.append(FlowPowerSensor(hass, entry, "netz_zu_haus", "Netz zu Haus", flows))

    if data.get("akku_leistung") or (data.get("akku_laden") and data.get("akku_entladen")):
        sensors.append(FlowPowerSensor(hass, entry, "netz_zu_akku", "Netz zu Akku", flows))
        sensors.append(FlowPowerSensor(hass, entry, "akku_zu_haus", "Akku zu Haus", flows))
        sensors.append(FlowPowerSensor(hass, entry, "akku_zu_netz", "Akku zu Netz", flows))

    async_add_entities(sensors)


# =====================================================================
# BASE
# =====================================================================

class BasePhSensor(SensorEntity):
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_icon = "mdi:lightning-bolt-circle"

    def __init__(self, *, entry: ConfigEntry, key: str, name: str):
        self._entry = entry
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Dennis90BW",
            model="powerHELPER",
            sw_version="1.0.1",
        )


# =====================================================================
# PROXY
# =====================================================================

class ProxyPowerSensor(BasePhSensor):
    def __init__(self, hass, *, source_entity, entry, key, name):
        super().__init__(entry=entry, key=key, name=name)
        self.hass = hass
        self._source = source_entity
        self._attr_entity_registry_enabled_default = False
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_added_to_hass(self):
        async_track_state_change_event(self.hass, [self._source], self._changed)
        self._update()

    @callback
    def _changed(self, event):
        self._update()

    def _update(self):
        self._attr_native_value = power_in_watt(self.hass, self._entry, self._source)
        self.async_write_ha_state()


# =====================================================================
# SPLIT / COMBINE
# =====================================================================

class SplitPowerSensor(BasePhSensor):
    def __init__(self, hass, *, source_entity, entry, key, name, positive):
        super().__init__(entry=entry, key=key, name=name)
        self.hass = hass
        self._source = source_entity
        self._positive = positive

    async def async_added_to_hass(self):
        async_track_state_change_event(self.hass, [self._source], self._changed)
        self._update()

    @callback
    def _changed(self, event):
        self._update()

    def _update(self):
        value = power_in_watt(self.hass, self._entry, self._source)
        self._attr_native_value = max(value, 0) if self._positive else max(-value, 0)
        self.async_write_ha_state()


class CombinedPowerSensor(BasePhSensor):
    def __init__(self, hass, *, pos_entity, neg_entity, entry, key, name):
        super().__init__(entry=entry, key=key, name=name)
        self.hass = hass
        self._pos = pos_entity
        self._neg = neg_entity

    async def async_added_to_hass(self):
        async_track_state_change_event(self.hass, [self._pos, self._neg], self._changed)
        self._update()

    @callback
    def _changed(self, event):
        self._update()

    def _update(self):
        pos = power_in_watt(self.hass, self._entry, self._pos)
        neg = power_in_watt(self.hass, self._entry, self._neg)
        self._attr_native_value = pos - neg
        self.async_write_ha_state()


# =====================================================================
# FLOW SENSORS
# =====================================================================

class FlowPowerSensor(BasePhSensor):
    def __init__(self, hass, entry, key, name, sources):
        super().__init__(entry=entry, key=key, name=name)
        self.hass = hass
        self._key = key
        self._sources = sources

    async def async_added_to_hass(self):
        async_track_state_change_event(
            self.hass,
            [e for e in self._sources.values() if e],
            self._update,
        )
        self._update()

    @callback
    def _update(self, event=None):
        def val(e):
            return power_in_watt(self.hass, self._entry, e) if e else 0.0

        netz = val(self._sources["netz"])
        pv = val(self._sources["pv"])
        akku = val(self._sources["akku"])
        nb = val(self._sources["netz_bezug"])
        ne = val(self._sources["netz_einspeisung"])
        al = val(self._sources["akku_laden"])
        ae = val(self._sources["akku_entladen"])

        if netz != 0 and nb == 0 and ne == 0:
            nb = max(netz, 0)
            ne = max(-netz, 0)

        if netz == 0 and (nb != 0 or ne != 0):
            netz = nb - ne

        if akku != 0 and al == 0 and ae == 0:
            ae = max(akku, 0)
            al = max(-akku, 0)

        if akku == 0 and (al != 0 or ae != 0):
            akku = ae - al

        haus = netz + pv + akku
        akku_prio = self._entry.data.get("akku_prio", False)

        if akku_prio:
            pv_zu_akku = max(min(pv, al),0)
            pv_zu_haus = max(min(max(pv - pv_zu_akku, 0), haus),0)
        else:
            pv_zu_haus = max(min(pv, haus),0)
            pv_zu_akku = max(min(max(pv - pv_zu_haus, 0), al),0)

        pv_zu_netz = max(pv - pv_zu_haus - pv_zu_akku, 0)

        akku_zu_haus = max(min(ae, haus - pv_zu_haus),0)
        akku_zu_netz = max(ae - akku_zu_haus, 0)

        netz_zu_haus = max(haus - pv_zu_haus - akku_zu_haus, 0)
        netz_zu_akku = max(al - pv_zu_akku, 0)

        mapping = {
            "haus": haus,
            "pv_zu_haus": pv_zu_haus,
            "pv_zu_akku": pv_zu_akku,
            "pv_zu_netz": pv_zu_netz,
            "netz_zu_haus": netz_zu_haus,
            "netz_zu_akku": netz_zu_akku,
            "akku_zu_haus": akku_zu_haus,
            "akku_zu_netz": akku_zu_netz,
        }

        self._attr_native_value = mapping.get(self._key, 0)
        self.async_write_ha_state()
