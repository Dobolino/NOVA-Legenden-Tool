# NOVA-Legenden-Tool

Lokales Windows-Werkzeug, das aus Trimble-Nova-Elektroplänen die Legende der Apparate erzeugt.

Aktueller Stand: **Phase 0 (Analyse und Validierung)**. Es gibt noch keine Oberfläche. Phase 0 liefert einen Parser für die Nova-Datensätze, eine Symbol-JSON-Datei, SVG-Vorschauen, HTML-Kontrollseiten und eine Analyse der N4D-Dateien.

Den Bericht zu Phase 0 findest du in [docs/PHASE0_BERICHT.md](docs/PHASE0_BERICHT.md).

## Voraussetzungen

- Windows 10 oder 11, 64 Bit
- Python 3.11 oder neuer (python.org, beim Installieren «Add Python to PATH» anhaken)

## Einrichten (einmalig)

Öffne die Eingabeaufforderung (Windows-Taste, «cmd» tippen) im Projektordner:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r backend\requirements.txt
```

`venv` ist eine abgeschottete Python-Umgebung nur für dieses Projekt. `pip` installiert die Bibliotheken.

## Beispieldateien ablegen

Lege deine Dateien in den Ordner `samples` im Projektordner:

- `Elektroinstallationen.V2.CH.nzp` und `Elektroinstallationen.CH.nzp` (Nova-Datensätze)
- `Legende_edeco20.n4d` und Pläne als `.n4d`
- `Benutzerschablonen.n5q`

Der Ordner `samples` und alle Ausgaben stehen in `.gitignore`. Trimble- und Firmendaten landen so nie im Git-Repository.

## Phase 0 ausführen

```
.venv\Scripts\activate
set PYTHONPATH=backend
python -m nova_legend.analysis.phase0 --samples samples --out output\phase0
```

Danach liegen in `output\phase0`:

| Datei | Inhalt |
|---|---|
| `kontrolle_<Datensatz>.html` | Alle Symbole mit Name, Code, Montageart, Kategorie und Bild. Suche und Filter oben. |
| `familien_<Datensatz>.html` | UP/AP-Familien. Blauer Rahmen = vorgeschlagener UP-Vertreter. |
| `legende_Legende_edeco20.html` | Texte der bestehenden Legende an ihrer Position, dazu alle erkannten Symbole. |
| `symbole_<Datensatz>.json` | Alle Symbole mit Geometrie, Anschlusspunkten und 3D-Verweisen. |
| `familien_<Datensatz>.json` | Familien mit Mitgliedern. |
| `n4d_<Datei>.json` | Analyse jeder N4D-Datei. |
| `zusammenfassung.json` | Kennzahlen. |

Öffne die HTML-Dateien mit Doppelklick im Browser.

## Tests

```
.venv\Scripts\activate
python -m pytest backend\tests -q
```

Tests, die echte Beispieldateien brauchen, werden übersprungen, wenn `samples` fehlt.

## Aufbau

```
backend/nova_legend/
  parser/      Nova-Datensatz (.nzp): Baumformat lesen/schreiben, Geometrie, Symbolkatalog
  n4d/         N4D-Analyse (nur Lesen, Stand Phase 0)
  render/      SVG-Ausgabe der Symbole
  library/     Symbolfamilien (UP-Vertreter)
  categories/  Kategorien der Legende und Zuordnungsregeln
  analysis/    Phase-0-Skript
backend/tests/ Tests
docs/          Berichte
```

Die Module importer, matcher, legend, exporter, api und ui folgen in den Phasen 1 bis 6.
