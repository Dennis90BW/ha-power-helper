# ⚡ powerHELPER

🇩🇪 [Deutsch](README_de.md) | 🇺🇸 [English](README.md)

**powerHELPER** is a custom integration for **Home Assistant** that automatically breaks down electrical power flows between the **PV system, grid, battery, and home**.

Ideal for users of [Solar Forecast ML](https://github.com/Zara-Toorox/ha-solar-forecast-ml) and SFML-Stats. Thanks @Zara-Toorox for these awesome integrations!

---

## ⚠️ Disclaimer
This is my first GitHub project, and the custom integration was created with the help of AI. Despite careful implementation, **errors or inaccuracies may occur**. Feedback, [issues](https://github.com/Dennis90BW/ha-power-helper/issues), and improvement suggestions are always welcome!

---

## ✨ Features

- 🧩 Automatically creates missing **combined or separate power sensors** for **grid** and **battery**
- 🔌 Power flow breakdown (PV, grid, battery, home)
- ➕ Multiple PV systems can be added
- 🔋 Battery power can be inverted
- ⚙️ Easy setup and editing via the UI
- 📊 Output in **watts (W)**
- 🔄 Supports sensors in **W** and **kW**
- 🌍 Multilingual (**DE / EN**)

---

## 📦 Requirements

- Home Assistant **2025.12.x or newer**
- Existing power sensors with `device_class: power`:
  - Required: grid power **or** grid consumption & feed-in
  - Optional: PV power
  - Optional: battery power **or** battery charge & discharge

---

## 🚀 Installation

### 🔹 HACS (recommended)

1. Open **HACS**
2. Search for **powerHELPER**
3. Click **Download**
4. Restart Home Assistant

---

### 🔹 Manual Installation

1. Download the repository
2. Copy the `power_helper` folder to: `config/custom_components/`
3. Restart Home Assistant

---

## ⚙️ Configuration

1. **Settings → Devices & Services**
2. **Add Integration**
3. Select **powerHELPER**
4. Set device name
5. Select your power sensors

---

## 🧠 Created Sensors

### 🔌 Grid
#### Input
- `sensor.netz_leistung` — Grid power
- `sensor.netz_bezug` — Grid consumption
- `sensor.netz_einspeisung` — Grid feed-in
#### Power flow
- `sensor.netz_zu_haus` — Grid → Home
- `sensor.netz_zu_akku` — Grid → Battery

### ☀️ PV
#### Input
- `sensor.pv_leistung` — PV power
#### Power flow
- `sensor.pv_zu_haus` — PV → Home
- `sensor.pv_zu_akku` — PV → Battery
- `sensor.pv_zu_netz` — PV → Grid

### 🔋 Battery
#### Input
- `sensor.akku_leistung` — Battery power
- `sensor.akku_leistung_inv` — Battery power inverted
- `sensor.akku_laden` — Battery charging
- `sensor.akku_entladen` — Battery discharging
#### Power flow
- `sensor.akku_zu_haus` — Battery → Home
- `sensor.akku_zu_netz` — Battery → Grid

### 🏠 Home
- `sensor.haus_leistung` — Home power

All sensors provide **watts (W)** and are fully dashboard-ready.

---

## ❓ FAQ

### Do I need AC or DC sensors?

In general, all sensors for this balance should be AC power sensors, as they represent the actual power flows in the electrical circuit.

DC sensors, such as those coming directly from inverters in the PV system or certain battery storage systems, can also be used. In this case, the DC/AC conversion losses are simply reflected in the **Home Power**, causing the overall consumption of the home to increase, similar to other electrical consumers.

---

## 🧪 Status

Version: **1.0.6**  

Tested with PV + battery systems

---

## 📄 License

MIT License  

Copyright (c) 2026 Dennis

---