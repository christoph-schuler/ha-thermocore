# HA-ThermoCore – Dokumentation für Handwerker & Installateure

Diese Dokumentation richtet sich an Fachbetriebe, die HA-ThermoCore im Rahmen
einer professionellen Installation einrichten und konfigurieren.

## 📋 Systemvoraussetzungen

| Komponente | Mindestanforderung |
|---|---|
| Home Assistant OS | Version 2024.1+ |
| Hardware | Raspberry Pi 4 (4GB) oder x86-NUC |
| Netzwerk | Stabile LAN-Verbindung, statische IP empfohlen |
| Speicher | 32GB microSD (Class 10) oder SSD |

## 🔌 Schnittstellenübersicht

### SG-Ready (Wärmepumpe)
Anbindung über potentialfreie Kontakte oder Shelly-Relais:

```
SG-Ready Eingang 1 + Eingang 2:
  00 = Betrieb gesperrt (EVU-Sperre)
  01 = Normalbetrieb  
  10 = Erhöhter Betrieb (PV-Überschuss)
  11 = Maximalbetrieb
```

Empfohlene Hardware: **Shelly Plus 2PM** (2 Relais, Energiemessung)

### Modbus (Wärmepumpen, Wechselrichter)
- RS485 → USB-Adapter oder direkt über LAN-Gateway
- Empfehlung: **Waveshare RS485/ETH** für zuverlässige LAN-Anbindung

### MQTT (universell)
Viele Geräte lassen sich per MQTT anbinden. Mosquitto Add-on vorinstallieren.

## 📝 Inbetriebnahme-Checkliste

- [ ] Home Assistant OS installiert und erreichbar
- [ ] HACS installiert
- [ ] HA-ThermoCore installiert und konfiguriert
- [ ] PV-Wechselrichter-Integration eingerichtet
- [ ] Netzstromzähler (z.B. Shelly EM) eingebunden
- [ ] SG-Ready-Kontakte verdrahtet und getestet
- [ ] Boiler-Steuerung getestet
- [ ] EnergyBrain-Logik im Test-Modus validiert
- [ ] Übergabe-Dokumentation für Kunden erstellt

## 🔧 Typische Installationsszenarien

### Szenario A: PV + Wärmepumpe (SG-Ready)
→ [Anleitung A](scenario_a_pv_heatpump.md)

### Szenario B: PV + Batteriespeicher + Boiler
→ [Anleitung B](scenario_b_pv_battery_boiler.md)

### Szenario C: Vollinstallation (alle Module)
→ [Anleitung C](scenario_c_full.md)

## 📞 Support

- GitHub Issues: https://github.com/ha-thermocore/ha-thermocore/issues
- Community Forum: https://community.home-assistant.io
