from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.loader import async_get_loaded_integration

from .const import DOMAIN, NAME
from .hub import PowerHelperHub


@dataclass(frozen=True)
class SensorSpec:
    """Welche Entität angelegt wird und wie sie sich standardmäßig verhält."""

    key: str  # Schlüssel in hub.values und Teil der unique_id
    translation_key: str
    enabled: bool = True
    diagnostic: bool = False
    ratio: bool = False  # Anteil in % statt Leistung in W


# =====================================================================
# SETUP
# =====================================================================

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    hub: PowerHelperHub = entry.runtime_data
    # Version nur an einer Stelle pflegen: manifest.json
    sw_version = str(async_get_loaded_integration(hass, DOMAIN).version)
    main_device = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Dennis90BW",
        model=NAME,
        sw_version=sw_version,
    )

    specs: list[SensorSpec] = []

    # ==================== GRID ====================
    if hub.grid_is_split:
        specs += [
            SensorSpec("netz_bezug", "netz_bezug", enabled=False, diagnostic=True),
            SensorSpec("netz_einspeisung", "netz_einspeisung", enabled=False, diagnostic=True),
            SensorSpec("netz_leistung", "netz_leistung"),
        ]
    elif hub.grid_power:
        specs += [
            SensorSpec("netz_leistung", "netz_leistung", enabled=False, diagnostic=True),
            SensorSpec("netz_bezug", "netz_bezug"),
            SensorSpec("netz_einspeisung", "netz_einspeisung"),
        ]

    # ==================== FLOWS ====================
    has_bat = bool(hub.batteries)
    specs.append(SensorSpec("haus", "haus"))

    if hub.pv:
        specs += [
            SensorSpec("pv_leistung", "pv_leistung"),
            SensorSpec("pv_zu_haus", "pv_zu_haus"),
            SensorSpec("pv_zu_netz", "pv_zu_netz"),
        ]
        if has_bat:
            specs.append(SensorSpec("pv_zu_akku", "pv_zu_akku"))

    specs.append(SensorSpec("netz_zu_haus", "netz_zu_haus"))

    # ==================== BATTERY (gesamt) ====================
    if has_bat:
        specs += [
            SensorSpec("akku_leistung", "akku_leistung"),
            SensorSpec("akku_leistung_inv", "akku_leistung_inv", enabled=False),
            SensorSpec("akku_laden", "akku_laden"),
            SensorSpec("akku_entladen", "akku_entladen"),
            SensorSpec("netz_zu_akku", "netz_zu_akku"),
            SensorSpec("akku_zu_haus", "akku_zu_haus"),
            SensorSpec("akku_zu_netz", "akku_zu_netz"),
        ]

    # ==================== KENNZAHLEN (standardmäßig deaktiviert) ====================
    # Wer einen Verlauf möchte, aktiviert sie; die Karte rechnet auch ohne sie.
    if hub.pv:
        specs.append(SensorSpec("pv_eigenverbrauch", "pv_eigenverbrauch", enabled=False, ratio=True))
    if hub.pv or has_bat:
        specs.append(SensorSpec("autarkiegrad", "autarkiegrad", enabled=False, ratio=True))

    main_entities = [
        (PowerHelperRatioSensor if spec.ratio else PowerHelperSensor)(
            hub,
            spec,
            unique_id=f"{DOMAIN}_{entry.entry_id}_{spec.key}",
            device_info=main_device,
        )
        for spec in specs
    ]

    # ==================== PV-ANLAGEN UND AKKUS (je Subentry ein Gerät) ====================
    # Geräte vorab anlegen und per via_device_id unter das Hauptgerät hängen.
    # (`via_device` in DeviceInfo ist ab HA 2026.11 veraltet, `via_device_id`
    # in DeviceInfo gibt es in älteren Versionen noch nicht – dieser Weg geht mit beiden.)
    dev_reg = dr.async_get(hass)
    main_dev = dev_reg.async_get_or_create(config_entry_id=entry.entry_id, **main_device)

    sub_items: list[tuple[str, str, str, list[SensorSpec]]] = [
        (pv.subentry_id, pv.title, f"{NAME} PV", PV_SPECS) for pv in hub.pv
    ] + [
        (bat.subentry_id, bat.title, f"{NAME} Akku", BATTERY_SPECS) for bat in hub.batteries
    ]

    sub_entities: dict[str, list[PowerHelperSensor]] = {}
    for sid, title, model, sub_specs in sub_items:
        device = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{sid}")},
            name=title,
            manufacturer="Dennis90BW",
            model=model,
            sw_version=sw_version,
        )
        sub_dev = dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id, config_subentry_id=sid, **device
        )
        if sub_dev.via_device_id != main_dev.id:
            dev_reg.async_update_device(sub_dev.id, via_device_id=main_dev.id)
        sub_entities[sid] = [
            PowerHelperSensor(
                hub,
                SensorSpec(f"{sid}_{s.key}", s.translation_key, s.enabled, s.diagnostic),
                unique_id=f"{DOMAIN}_{entry.entry_id}_{sid}_{s.key}",
                device_info=device,
            )
            for s in sub_specs
        ]

    # Entitäten entfernen, die nach einer Änderung nicht mehr erzeugt werden
    # (z. B. wenn ein Quellsensor entfernt wurde), damit keine verwaisten Einträge bleiben.
    ent_reg = er.async_get(hass)
    valid_unique_ids = {e.unique_id for e in main_entities}
    for entities in sub_entities.values():
        valid_unique_ids |= {e.unique_id for e in entities}
    for reg_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if reg_entry.unique_id not in valid_unique_ids:
            ent_reg.async_remove(reg_entry.entity_id)

    async_add_entities(main_entities)
    for subentry_id, entities in sub_entities.items():
        async_add_entities(entities, config_subentry_id=subentry_id)


PV_SPECS = [
    SensorSpec("leistung", "pv_anlage_leistung"),
]

BATTERY_SPECS = [
    SensorSpec("leistung", "bat_leistung"),
    SensorSpec("leistung_inv", "bat_leistung_inv", enabled=False),
    SensorSpec("laden", "bat_laden"),
    SensorSpec("entladen", "bat_entladen"),
]


# =====================================================================
# ENTITY
# =====================================================================

class PowerHelperSensor(SensorEntity):
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_icon = "mdi:lightning-bolt-circle"
    _attr_has_entity_name = True

    def __init__(
        self,
        hub: PowerHelperHub,
        spec: SensorSpec,
        *,
        unique_id: str,
        device_info: DeviceInfo,
    ) -> None:
        self._hub = hub
        self._key = spec.key
        self._attr_translation_key = spec.translation_key
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
        self._attr_entity_registry_enabled_default = spec.enabled
        if spec.diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> float | None:
        return self._hub.values.get(self._key, 0.0)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._hub.async_add_listener(self.async_write_ha_state))


class PowerHelperRatioSensor(PowerHelperSensor):
    """PV-Eigenverbrauch bzw. Autarkiegrad in %.

    Standardmäßig deaktiviert – wer einen Verlauf möchte, aktiviert den Sensor
    (die Karte öffnet ihn auch deaktiviert per Klick auf den Ring).
    Unbekannt, solange es keine PV-Leistung bzw. keinen Hausverbrauch gibt.
    """

    _attr_device_class = None
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 0

    def __init__(self, hub: PowerHelperHub, spec: SensorSpec, **kwargs) -> None:
        super().__init__(hub, spec, **kwargs)
        self._attr_icon = (
            "mdi:solar-power-variant" if spec.key == "pv_eigenverbrauch" else "mdi:home-lightning-bolt"
        )

    @property
    def native_value(self) -> float | None:
        return self._hub.values.get(self._key)
