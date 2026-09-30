# NOVA-Legenden

Windows-Programm, das aus Trimble-Nova-Elektroplänen die Legende der Apparate erzeugt.

Stand: **Phase 1 (Bibliothek)**. Das Programm zeigt alle Symbole aus den Nova-Datensätzen, gruppiert UP/AP-Varianten zu Familien und ordnet sie Kategorien zu. Die Kategorien gelten für die ganze Firma.

Berichte: [Phase 0](docs/PHASE0_BERICHT.md) · [Phase 1](docs/PHASE1.md)

## Installation für die Firma

1. `NOVA-Legenden-Setup-<Version>.exe` doppelklicken.
2. Weiter, Fertig. Adminrechte sind nicht nötig. Das Programm landet im Benutzerprofil, auf dem Desktop erscheint ein Symbol.
3. Beim ersten Start sucht das Programm die Nova-Datensätze selbst. Findet es sie nicht, trägst du den Pfad unter **Einstellungen** ein.
4. Unter **Einstellungen → Firmenordner** tragen alle denselben Ordner ein, zum Beispiel `T:\_CAD\NOVA-Legenden`. Dort liegen die gemeinsamen Kategorien.

Hinweis: Das Setup ist noch nicht digital signiert. Windows zeigt beim ersten Start «Der Computer wurde durch Windows geschützt». Klicke auf «Weitere Informationen» und «Trotzdem ausführen», oder lass die Datei von der IT freigeben.

DWG-Dateien brauchen zusätzlich den kostenlosen ODA File Converter. DXF und N4D funktionieren ohne.

### Woher kommt das Setup?

GitHub baut es bei jeder Änderung automatisch (Reiter **Actions** → «Windows-Setup bauen» → Lauf öffnen → unten unter **Artifacts** herunterladen).

## Start aus dem Quellcode (Entwicklung)

Voraussetzungen: Python 3.11 und Node.js 22.

```
start.bat
```

Der erste Start richtet alles ein und dauert einige Minuten. Danach öffnet sich das Programmfenster.

Nur im Browser: `start.bat --browser`

## Tests

```
.venv\Scripts\activate
python -m pytest backend\tests -q
```

Tests mit echten Nova-Dateien laufen nur, wenn der Ordner `samples` die Beispieldateien enthält. Dieser Ordner und alle Ausgaben stehen in `.gitignore`. So landen keine Trimble- oder Firmendaten im Repository.

## Phase-0-Analyse erneut ausführen

```
set PYTHONPATH=backend
python -m nova_legend.analysis.phase0 --samples samples --out output\phase0
```

## Aufbau

```
backend/nova_legend/
  __main__.py  Programmstart (Server + Fenster)
  config.py    Einstellungen, Datenordner, Suche nach Datensätzen
  api/         REST-Schnittstelle (FastAPI) für die Oberfläche
  parser/      Nova-Datensatz (.nzp): Baumformat, Geometrie, Symbolkatalog
  library/     Bibliotheks-Cache (SQLite) und Symbolfamilien
  categories/  Kategorien und Zuordnungen der Firma (firma.sqlite)
  n4d/         N4D-Analyse (nur Lesen)
  render/      SVG-Ausgabe der Symbole
  analysis/    Phase-0-Skripte
ui/            Oberfläche (React, TypeScript)
packaging/     exe (PyInstaller) und Setup (Inno Setup)
```
