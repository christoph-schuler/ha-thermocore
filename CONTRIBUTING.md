# Mitmachen bei HA-ThermoCore

Wir freuen uns über jeden Beitrag! Hier erfährst du, wie du mitmachen kannst.

## 🐛 Bugs melden

Nutze den [Bug Report Template](.github/ISSUE_TEMPLATE/bug_report.md).  
Bitte immer angeben: HA-Version, ThermoCore-Version, verwendete Module, Logausgabe.

## 💡 Features vorschlagen

Nutze den [Feature Request Template](.github/ISSUE_TEMPLATE/feature_request.md).

## 🔧 Code beitragen

1. **Fork** das Repository
2. **Branch** erstellen: `git checkout -b feature/mein-feature`
3. **Entwicklungsumgebung** aufsetzen:
   ```bash
   pip install -r requirements_dev.txt
   pre-commit install
   ```
4. **Tests** schreiben und ausführen:
   ```bash
   pytest tests/
   ```
5. **Pull Request** öffnen gegen `main`

## 📋 Code-Standards

- Python: PEP8, Type Hints, Docstrings
- HA-Konventionen: [HA Developer Docs](https://developers.home-assistant.io)
- Tests: pytest, mindestens 80% Coverage für neue Module
- Commits: [Conventional Commits](https://www.conventionalcommits.org)

## 📖 Dokumentation beitragen

Dokumentation liegt in `/docs/`. DIY-Guides unter `diy/`, Handwerker-Docs unter `handwerker/`.  
Sprache: Deutsch (primär), Englisch (sekundär).

## 🤝 Verhaltenskodex

Wir folgen dem [Contributor Covenant](CODE_OF_CONDUCT.md).  
Respektvoller Umgang ist Pflicht – wir sind eine inklusive Community.
