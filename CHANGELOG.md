# Changelog

🇩🇪 [Deutsch](#deutsch) | 🇺🇸 [English](#english)

---

## English

### 2.1.1

#### ✨ Card improvements

- 🔋 **Battery state of charge:** optional SOC sensor in the card settings. The battery icon follows the charge level in four steps (high, medium, low and empty below 10 %), the SOC is shown above the icon.
- 🏷️ **Custom names** for the four circles and the two ratios – leave empty for the default name, enter `-` to hide a name.
- 🟢 **Self-consumption and self-sufficiency (optional):** two rings in the top right of the card – outer green: share of PV power used in the home or battery, inner yellow: self-sufficiency like the energy dashboard (1 − grid import ÷ home consumption; charging the battery from the grid counts as grid import).
- ⚙️ **Card settings grouped like the Home Assistant cards:** Content, Names, Interactions.
- 👆 **Clickable lines (optional, on by default):** clicking a line opens the sensor of that power flow.
- 📐 Triangle layout: the grid ↔ battery value now sits just below its line.
- 🔗 Footer links now use the Home Assistant button, just like the energy distribution card.

#### ✨ New

- 📊 **New sensors "Self-consumption" and "Self-sufficiency"** (in %) on the main device – disabled by default, enable them if you want a history. Clicking a ring in the card opens its sensor.
- 🎨 **New logo** following the Home Assistant brand guidelines, shipped with the integration.

### 2.1.0

#### ✨ New

- 🗺️ **Dashboard card "powerHELPER Power Flow"** – styled after the energy dashboard, shows the current power of PV, grid, battery and home and **the power of each flow right next to its line**. Animated dots show the direction, a ring around the home shows where the power comes from.
- 🔀 **Three layouts:** Classic (like the energy dashboard), Round (home in the center, connections as arcs) and Triangle (home in the center, straight connections).
- 📐 **Same size as the original:** circles always 80 px, only the distances and lines adapt to the card width.
- ⚙️ **Visual editor:** device selection, title prefilled with the device name, show "0 W" on lines and in the circles, optional links to the energy dashboard and to powerHELPER.
- 🔌 The card is registered automatically – no dashboard resource needed. After updates, browsers load the new card version automatically.

### 2.0.0

#### ⚠️ Important – please read before updating

- **Create a backup before updating.** Existing powerHELPER entries are converted to a new format automatically on the first start. Batteries and PV systems become separate devices (sub-entries).
- **No easy downgrade.** After the update, version 1.0.x can no longer load the converted entry. To go back, restore your backup.
- **Your existing sensors keep their entity IDs.** History, statistics and dashboards are preserved. The existing battery becomes the device "Akku", the existing PV sensor(s) become the device(s) "PV" (or "PV 1", "PV 2", …). You can rename them via **Edit battery** / **Edit PV system**.
- **PV Power, Battery Power, Battery Charging and Battery Discharging are now totals** over all PV systems and batteries. In earlier versions some of them were disabled diagnostic copies of your source sensor, and Home Assistant keeps them disabled after the update – enable them in the entity settings if you need them.
- **PV systems and batteries are no longer configured in the options dialog.** Use **Add PV system** / **Add battery** on the integration page instead; edit or delete them via the menu of each system. The options dialog now only contains the grid.

#### ✨ New

- **Multiple batteries** – each with its own sensors (total sensor **or** charge/discharge), its own "change sign" setting and **its own priority**. Typical use case: a DC-coupled battery (priority, gets PV first) plus an AC-coupled battery.
- **Batteries are netted against each other first.** If one battery charges while another discharges, that power only flows between the batteries and no longer shows up incorrectly as "Battery to Grid" / "Grid to Battery".
- **Multiple PV systems as separate devices**, each with its own power sensor.
- **Own device per PV system and per battery**, grouped below the main device.
- **All power units are supported** (mW, W, kW, MW, …) via Home Assistant's built-in unit converter.

#### 🐛 Fixes

- No more Home Assistant warning about the deprecated `via_device` parameter (HA 2026.11+).
- Values of exactly 0 W are no longer shown as "-0.0".
- The grid can no longer be saved empty in the options dialog.

#### 🔧 Internal

- Central calculation for all sensors instead of one calculation per sensor.
- The version is now maintained only in `manifest.json`.
- CI: `actions/checkout` updated to v7.

### 1.0.8

- Fixed: state listeners were not removed on reload (memory leak, log warnings).
- Fixed: power flow sensors did not update when only the PV power changed.
- Fixed: "change sign" for the battery did not work for sensors in kW.
- Fixed: sensors could not be removed in the options dialog; entities that are no longer needed are now removed automatically.

---

## Deutsch

### 2.1.1

#### ✨ Verbesserungen der Karte

- 🔋 **Akku-Ladestand:** optionaler SOC-Sensor in den Karteneinstellungen. Das Akku-Icon passt sich dem Ladestand in vier Stufen an (hoch, mittel, niedrig und leer unter 10 %), der Ladestand steht über dem Icon.
- 🏷️ **Eigene Bezeichnungen** für die vier Kreise und die beiden Kennzahlen – leer lassen für den Standardnamen, `-` blendet einen Namen aus.
- 🟢 **Eigenverbrauch und Autarkiegrad (optional):** zwei Ringe oben rechts in der Karte – außen grün: Anteil der PV-Leistung, der im Haus oder Akku bleibt, innen gelb: Autarkiegrad wie im Energie-Dashboard (1 − Netzbezug ÷ Hausverbrauch; Laden des Akkus aus dem Netz zählt als Netzbezug).
- ⚙️ **Karteneinstellungen gruppiert wie bei den Home-Assistant-Karten:** Inhalt, Bezeichnungen, Interaktionen.
- 👆 **Anklickbare Linien (optional, standardmäßig an):** Ein Klick auf eine Linie öffnet den Sensor des Leistungsflusses.
- 📐 Dreieck: Die Leistung Netz ↔ Akku steht jetzt knapp unter ihrer Linie.
- 🔗 Die Links in der Fußzeile nutzen jetzt den Home-Assistant-Button – wie bei der Energieverteilung.

#### ✨ Neu

- 📊 **Neue Sensoren „PV-Eigenverbrauch“ und „Autarkiegrad“** (in %) am Hauptgerät – standardmäßig deaktiviert, wer einen Verlauf möchte, aktiviert sie. Ein Klick auf einen Ring in der Karte öffnet den Sensor.
- 🎨 **Neues Logo** nach den Home-Assistant-Vorgaben, direkt in der Integration enthalten.

### 2.1.0

#### ✨ Neu

- 🗺️ **Dashboard-Karte „powerHELPER Leistungsfluss“** – angelehnt an das Energie-Dashboard, zeigt die aktuellen Leistungen von PV, Netz, Akku und Haus und **die Leistung jedes Flusses direkt an der Linie**. Animierte Punkte zeigen die Richtung, ein Ring ums Haus zeigt, woher die Leistung kommt.
- 🔀 **Drei Darstellungen:** Klassisch (wie das Energie-Dashboard), Rund (Haus in der Mitte, Verbindungen als Bögen) und Dreieck (Haus in der Mitte, gerade Verbindungen).
- 📐 **Gleiche Größe wie das Original:** Kreise immer 80 px, nur Abstände und Linien passen sich der Kartenbreite an.
- ⚙️ **Visueller Editor:** Geräteauswahl, Titel mit dem Gerätenamen vorausgefüllt, „0 W“ an Linien und in den Kreisen anzeigen, optionale Links zum Energie-Dashboard und zu powerHELPER.
- 🔌 Die Karte wird automatisch registriert – keine Dashboard-Ressource nötig. Nach Updates laden Browser die neue Kartenversion automatisch.

### 2.0.0

#### ⚠️ Wichtig – bitte vor dem Update lesen

- **Vor dem Update ein Backup erstellen.** Bestehende powerHELPER-Einträge werden beim ersten Start automatisch auf ein neues Format umgestellt. Akkus und PV-Anlagen werden dabei zu eigenen Geräten (Untereinträgen).
- **Kein einfaches Downgrade.** Nach dem Update kann Version 1.0.x den umgestellten Eintrag nicht mehr laden. Zurück geht es nur über das Backup.
- **Deine bestehenden Sensoren behalten ihre Entity-IDs.** Verlauf, Statistiken und Dashboards bleiben erhalten. Der bisherige Akku wird zum Gerät „Akku“, der bisherige PV-Sensor bzw. die PV-Sensoren zum Gerät „PV“ (bzw. „PV 1“, „PV 2“, …). Umbenennen kannst du sie über **Akku bearbeiten** / **PV-Anlage bearbeiten**.
- **PV Leistung, Akku Leistung, Akku laden und Akku entladen sind jetzt Summen** über alle PV-Anlagen bzw. Akkus. In früheren Versionen waren einige davon deaktivierte Diagnose-Kopien deines Quellsensors, und Home Assistant lässt sie nach dem Update deaktiviert – bei Bedarf in den Entitäts-Einstellungen aktivieren.
- **PV-Anlagen und Akkus werden nicht mehr im Options-Dialog eingestellt.** Stattdessen auf der Integrationsseite über **PV-Anlage hinzufügen** / **Akku hinzufügen**; bearbeiten und löschen über das Menü der jeweiligen Anlage. Der Options-Dialog enthält nur noch das Netz.

#### ✨ Neu

- **Mehrere Akkus** – jeweils mit eigenen Sensoren (Gesamtsensor **oder** Laden/Entladen), eigenem „Vorzeichen ändern“ und **eigener Priorität**. Typischer Fall: ein DC-gekoppelter Akku (Priorität, bekommt PV zuerst) plus ein AC-gekoppelter Akku.
- **Akkus werden zuerst miteinander verrechnet.** Lädt ein Akku, während ein anderer entlädt, fließt diese Leistung nur zwischen den Akkus und erscheint nicht mehr fälschlich als „Akku zu Netz“ / „Netz zu Akku“.
- **Mehrere PV-Anlagen als eigene Geräte**, jeweils mit eigenem Leistungssensor.
- **Eigenes Gerät je PV-Anlage und je Akku**, gruppiert unter dem Hauptgerät.
- **Alle Leistungseinheiten werden unterstützt** (mW, W, kW, MW, …) über den eingebauten Einheiten-Umrechner von Home Assistant.

#### 🐛 Fehlerbehebungen

- Keine Home-Assistant-Warnung mehr zum veralteten Parameter `via_device` (HA 2026.11+).
- Werte von genau 0 W werden nicht mehr als „-0.0“ angezeigt.
- Das Netz kann im Options-Dialog nicht mehr leer gespeichert werden.

#### 🔧 Intern

- Zentrale Berechnung für alle Sensoren statt einer Berechnung pro Sensor.
- Die Version wird nur noch in `manifest.json` gepflegt.
- CI: `actions/checkout` auf v7 aktualisiert.

### 1.0.8

- Behoben: State-Listener wurden beim Reload nicht abgemeldet (Speicherleck, Warnungen im Log).
- Behoben: Fluss-Sensoren aktualisierten sich nicht, wenn sich nur die PV-Leistung änderte.
- Behoben: „Vorzeichen ändern“ beim Akku funktionierte nicht bei Sensoren in kW.
- Behoben: Sensoren ließen sich im Options-Dialog nicht entfernen; nicht mehr benötigte Entitäten werden jetzt automatisch gelöscht.
