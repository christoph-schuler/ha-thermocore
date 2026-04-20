# 🔥 HA-ThermoCore

[![HACS Default](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/ha-thermocore/ha-thermocore.svg)](https://github.com/ha-thermocore/ha-thermocore/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Community Forum](https://img.shields.io/badge/community-forum-brightgreen.svg)](https://community.home-assistant.io)

> **Open-Source Energie- und Thermomanagement für Home Assistant**  
> Für DIY-Enthusiasten und Handwerker-begleitete Installationen gleichermaßen.

---

## 🎯 Was ist HA-ThermoCore?

HA-ThermoCore ist ein modulares Ökosystem für Home Assistant, das alle Aspekte des häuslichen Energie- und Thermomanagements intelligent vernetzt:

- ☀️ **SolarCore** – PV-Überschusssteuerung & Netzeinspeisung
- 🔋 **StorageCore** – Batteriespeicher optimal laden/entladen
- 🌡️ **HeatCore** – Heizung & Wärmepumpe intelligent steuern
- 💧 **WaterCore** – Warmwasser & Boiler effizient managen
- 💨 **AirCore** – Lüftung & Klima bedarfsgerecht regeln
- 🧠 **EnergyBrain** – Die zentrale KI-Logik, die alles koordiniert

---

## 🚀 Schnellstart

### Voraussetzungen
- Home Assistant 2024.1 oder neuer
- HACS installiert

### Installation via HACS

1. HACS öffnen → **Integrationen** → **Erkunden & Herunterladen**
2. Nach `HA-ThermoCore` suchen
3. Herunterladen & Home Assistant neu starten
4. **Einstellungen → Geräte & Dienste → Integration hinzufügen → HA-ThermoCore**

### Manuelle Installation

```bash
# In deinem Home Assistant config-Verzeichnis:
git clone https://github.com/ha-thermocore/ha-thermocore.git
cp -r ha-thermocore/custom_components/thermocore config/custom_components/
```

---

## 🧩 Module

| Modul | Beschreibung | Status |
|-------|-------------|--------|
| [HeatCore](docs/diy/heatcore.md) | Heizung, Wärmepumpe, SG-Ready | 🚧 In Entwicklung |
| [SolarCore](docs/diy/solarcore.md) | PV-Anlage, Wechselrichter | 🚧 In Entwicklung |
| [StorageCore](docs/diy/storagecore.md) | Batteriespeicher | 🚧 In Entwicklung |
| [WaterCore](docs/diy/watercore.md) | Warmwasser, Boiler | 🚧 In Entwicklung |
| [AirCore](docs/diy/aircore.md) | Lüftung, Klimaanlage | 🚧 In Entwicklung |
| [EnergyBrain](docs/diy/energybrain.md) | Zentrale Steuerlogik | 🚧 In Entwicklung |

---

## 📋 Unterstützte Geräte

<details>
<summary><b>Heizung & Wärmepumpen</b></summary>

- Viessmann (Vitoconnect)
- Vaillant (eRELAX / multiMATIC)
- Wolf Heiztechnik
- NIBE (Modbus)
- Stiebel Eltron (ISG web)
- Generisch via SG-Ready (2 Eingänge)
</details>

<details>
<summary><b>PV-Wechselrichter</b></summary>

- Fronius (SolarAPI)
- SMA (Sunny Home Manager)
- Huawei SUN2000
- Kostal (PIKO)
- Solaredge
- Generisch via MQTT / Modbus
</details>

<details>
<summary><b>Batteriespeicher</b></summary>

- BYD Battery-Box
- Pylontech
- Sonnen
- E3/DC
- Generisch via SunSpec / Modbus
</details>

---

## 🏗️ Für Handwerker & Installateure

Wir bieten spezielle Dokumentation für Fachbetriebe:

📖 [Handwerker-Dokumentation](docs/handwerker/README.md)

- Systemanforderungen & Netzwerkplanung
- Inbetriebnahme-Checklisten
- Parameterübersichten für gängige Anlagen
- Fehlerdiagnose & Support

---

## 🤝 Mitmachen

Beiträge sind herzlich willkommen! Bitte lies zuerst unsere:

- [CONTRIBUTING.md](CONTRIBUTING.md) – Wie du beitragen kannst
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) – Unsere Community-Regeln

### Entwicklung starten

```bash
git clone https://github.com/ha-thermocore/ha-thermocore.git
cd ha-thermocore
pip install -r requirements_dev.txt
pre-commit install
```

---

## 📄 Lizenz

MIT License – siehe [LICENSE](LICENSE)

---

## 💬 Community & Support

- [Home Assistant Forum](https://community.home-assistant.io)
- [GitHub Discussions](https://github.com/ha-thermocore/ha-thermocore/discussions)
- [GitHub Issues](https://github.com/ha-thermocore/ha-thermocore/issues)
