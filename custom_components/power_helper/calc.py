"""Bilanzrechnung von powerHELPER – ohne Home-Assistant-Abhängigkeiten.

Vorzeichen (alle Werte in Watt):
- Netz:  positiv = Bezug, negativ = Einspeisung
- Akku:  positiv = Entladen, negativ = Laden
- PV:    immer >= 0
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BatteryFlow:
    """Lade-/Entladeleistung eines einzelnen Akkus (beide >= 0)."""

    charge: float
    discharge: float
    prio: bool = False

    @classmethod
    def from_net(cls, net: float, prio: bool = False) -> "BatteryFlow":
        """Aus einer Netto-Leistung (positiv = Entladen) erzeugen."""
        return cls(charge=max(-net, 0.0), discharge=max(net, 0.0), prio=prio)


def net_batteries(batteries: list[BatteryFlow]) -> tuple[float, float, float, float]:
    """Alle Akkus miteinander verrechnen.

    Entlädt ein Akku, während ein anderer lädt, fließt diese Leistung nur
    zwischen den Akkus (Akku → Akku). Sie wird zuerst von der Ladeleistung der
    Akkus OHNE Priorität (typisch AC-gekoppelt) abgezogen, danach von denen mit
    Priorität (typisch DC-gekoppelt).

    Rückgabe: (laden_prio, laden_normal, entladen, akku_zu_akku) – netto.
    """
    charge_prio = sum(b.charge for b in batteries if b.prio)
    charge_norm = sum(b.charge for b in batteries if not b.prio)
    discharge = sum(b.discharge for b in batteries)

    shift = min(discharge, charge_prio + charge_norm)
    from_norm = min(shift, charge_norm)
    from_prio = shift - from_norm

    return (
        charge_prio - from_prio,
        charge_norm - from_norm,
        discharge - shift,
        shift,
    )


def compute_flows(*, netz: float, pv: float, batteries: list[BatteryFlow]) -> dict[str, float]:
    """Leistungsflüsse zwischen PV, Netz, Akkus und Haus berechnen."""
    al_prio, al_norm, ae, akku_zu_akku = net_batteries(batteries)
    al = al_prio + al_norm
    akku = ae - al  # Netto aller Akkus (positiv = Entladen)

    haus = netz + pv + akku

    # 1. PV → Akkus mit Priorität (z. B. DC-gekoppelt)
    pv_zu_akku_prio = max(min(pv, al_prio), 0.0)
    pv_rest = max(pv - pv_zu_akku_prio, 0.0)
    # 2. PV → Haus
    pv_zu_haus = max(min(pv_rest, haus), 0.0)
    # 3. PV → übrige Akkus
    pv_zu_akku_norm = max(min(pv_rest - pv_zu_haus, al_norm), 0.0)
    pv_zu_akku = pv_zu_akku_prio + pv_zu_akku_norm
    # 4. PV-Rest → Netz
    pv_zu_netz = max(pv - pv_zu_haus - pv_zu_akku, 0.0)

    akku_zu_haus = max(min(ae, haus - pv_zu_haus), 0.0)
    akku_zu_netz = max(ae - akku_zu_haus, 0.0)

    netz_zu_haus = max(haus - pv_zu_haus - akku_zu_haus, 0.0)
    netz_zu_akku = max(al - pv_zu_akku, 0.0)

    return {
        "haus": haus,
        "akku_leistung": akku,
        "akku_leistung_inv": -akku,
        "akku_laden": al,
        "akku_entladen": ae,
        "akku_zu_akku": akku_zu_akku,
        "pv_zu_haus": pv_zu_haus,
        "pv_zu_akku": pv_zu_akku,
        "pv_zu_netz": pv_zu_netz,
        "netz_zu_haus": netz_zu_haus,
        "netz_zu_akku": netz_zu_akku,
        "akku_zu_haus": akku_zu_haus,
        "akku_zu_netz": akku_zu_netz,
    }


# Unterhalb dieser Leistung (W) ist ein Anteil nicht aussagekräftig → unbekannt
RATIO_MIN_BASE = 0.5


def _percent(part: float, base: float) -> float | None:
    if base <= RATIO_MIN_BASE:
        return None
    return round(min(max(part / base, 0.0), 1.0) * 100, 1)


def compute_ratios(flows: dict[str, float], pv: float) -> dict[str, float | None]:
    """PV-Eigenverbrauch und Autarkiegrad in % (wie die Karte).

    - PV-Eigenverbrauch: Anteil der PV-Leistung, der im Haus oder Akku bleibt.
    - Autarkiegrad wie im Energie-Dashboard: 1 − Netzbezug / Hausverbrauch; zum
      Netzbezug zählt auch das Laden des Akkus aus dem Netz.
    Ohne PV-Leistung bzw. Hausverbrauch ist der Wert unbekannt (None).
    """
    haus = flows.get("haus", 0.0)
    return {
        "pv_eigenverbrauch": _percent(flows.get("pv_zu_haus", 0.0) + flows.get("pv_zu_akku", 0.0), pv),
        "autarkiegrad": _percent(
            haus - flows.get("netz_zu_haus", 0.0) - flows.get("netz_zu_akku", 0.0), haus
        ),
    }
