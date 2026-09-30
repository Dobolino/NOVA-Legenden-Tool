# Phase 4: Legenden-Editor

Stand: 30.09.2026 (Version 2: festes Raster, farbige Abschnitte, Allgemeinteil, DXF/DWG-Export)

## Aufbau der Legende

```
┌───────────────────────── max. 200 mm inkl. Rand ─────────────────────────┐
│ Allgemeinteil (vom Server, gesperrt)                                     │
│ Titel                                                                    │
│ ███ Leuchten ███████████████████████████████████████████████ Kopfleiste  │
│  ○ Text …                ○ Text …                                        │
│ ███ Kraft / Drehstrominstallation ██████████████████████████████████████ │
│  ⊗ Text …                ⊗ Text …                                        │
└──────────────────────────────────────────────────────────────────────────┘
```

- Blatt höchstens 200 mm breit (Rand 5 mm). 2 oder 3 Spalten teilen die Breite.
- Nichts ist frei verschiebbar. Alles sitzt auf dem sichtbaren Raster. Reihenfolge: ↑ ↓ im rechten Feld oder Pfeiltasten. Am Rand eines Abschnitts wandert der Eintrag in den Nachbarabschnitt.
- Raster «★ Standard»: Zeile 4,55 mm, Text 9,75 mm rechts der Symbolmitte (edeco-Legende). Wählbar: Kompakt, Weit, Gross.
- Texte umbrechen in ihrer Spalte. Die Zeile wird höher, nie liegt ein Text auf dem nächsten Symbol oder in der nächsten Spalte.
- Die Höhe wächst mit der Anzahl Einträge. Nichts wird abgeschnitten.
- Die Anordnung rechnet das Programm (Backend `legend/layout.py`). Vorschau und DXF-Export nutzen dieselbe Rechnung.

## Abschnitte

Pro Abschnitt (Kategorie) einstellbar: Farbe Kopfleiste, Schrift Kopfleiste, Hintergrund, Symbole und Linien, Text, Umrandung (Farbe, an/aus), Innenabstand. Voreinstellung aus der Planfarbe der Legendenebene der Kategorie (Reiter «Ebenen und Farben»). Die Farben liegen im Legenden-Dokument und gehen in den Export.

## Gemeinsame Werte

- Eine Schriftgrösse für alle Texte (Titel, Kopfleisten, Einträge, freier Text).
- Ein Symbolmassstab für alle Symbole. Sehr grosse Symbole werden zusätzlich auf die Zeilenhöhe begrenzt.
- Ein neues Projekt startet mit dem Firmen-Standard (Einstellungen → Legende der Firma). Mit Vorlage kommen Werte und Legende aus der Vorlage.
- Eine Änderung im Projekt gilt nur dort. «Für neue Projekte merken» schreibt die beiden Werte in den Firmen-Standard (nur Admins). Bestehende Projekte bleiben unverändert.

## Freier Text

Freier Text ist ein Zusatztext in der Legende, kein Apparat. Er sitzt im Raster wie ein Eintrag, in einem Abschnitt, und nutzt die gemeinsame Schriftgrösse. Ohne gewählten Abschnitt entsteht ein Abschnitt «Zusatztext». Entfernen über das Mülleimer-Symbol («Text entfernen»). Alte freie Texte (Version 1) wandern beim Öffnen in einen Abschnitt «Zusatztext».

## Allgemeinteil und Admins

- Einstellungen → Legende der Firma → Pfad auf die Servervorlage: DXF, DWG (mit ODA File Converter) oder Ordner eines Vorlagen-Projekts mit Legende.
- N4D geht nicht: Die Einfügepunkte der Symbole sind nicht sicher dekodiert. Das Programm meldet das.
- Der Allgemeinteil steht zuoberst, auf höchstens 190 mm Breite verkleinert, Höhe nach Inhalt. Er ist im Editor nicht änderbar. Anpassen heisst: Datei auf dem Server ersetzen. Das Programm liest sie beim Öffnen neu.
- Admins: Liste von Windows-Benutzernamen. Nur sie ändern Pfad, Admin-Liste und Firmen-Standard. Ist die Liste leer, darf der erste Benutzer sich eintragen. Wer speichert, muss selbst in der Liste stehen.

## Export

Rechts unter «Export» (nichts angewählt):

- «Ganze Legende» oder «Nur «Kategorie»».
- «Allgemeinteil einschliessen».
- DXF R2013 (AC1027), Millimeter. DWG über den ODA File Converter; ohne Converter dieselbe Meldung wie beim Import.
- Farben als Truecolor: Kopfleiste und Hintergrund (Schraffur), Umrandung, Symbole (Block, Farbe am Einfügen), Linien, Texte.
- Ebenen: Symbole und Linien auf der Legendenebene der Kategorie, Texte auf X_Text, Kopfleisten und Rahmen auf X_Geometrie. Der Allgemeinteil wird als Block «Allgemeinteil» übernommen.
- Dateiname: `edeco ag-<Bezeichnung>-<Kategorie>.dxf` bzw. `…-Legende.dxf`.
- Kein N4D-Export.

## Speicherort

Legende: `projekt.nlproj`, Tabelle `legend` (Version 2). Firmenwerte: `edeco ag-Legenden-firma.sqlite`, Tabelle `options` (Schlüssel `legend_*`), Firmentexte in `descriptions`.

## So testest du

1. Einstellungen → Legende der Firma: dich als Admin eintragen, Pfad auf eine DXF-Vorlage setzen.
2. Projekt → Gesamtliste → «Legende bearbeiten →» → «Vorschlag aus dem Projekt erstellen».
3. Allgemeinteil oben, darunter farbige Abschnitte. Raster «★ Standard», Spalten 2 und 3 ausprobieren.
4. Schriftgrösse auf 3 setzen, Strg+Z: ein Schritt zurück.
5. Eine Kopfleiste anklicken, Farben ändern, Umrandung aus.
6. Export «Nur Brandmeldeanlage» mit und ohne Allgemeinteil, die DXF in Nova oder einem DXF-Viewer öffnen.
7. «Für neue Projekte merken», neues Projekt anlegen: hat die Werte. Ein anderes bestehendes Projekt: unverändert.

## Bekannte Grenzen

- Textbreiten rechnet das Programm mit einer Arial-Näherung. In Nova kann ein Text minimal breiter oder schmaler sein.
- Symbole aus .nsb-Bibliotheken erscheinen als Rahmen «keine Vorschau» und fehlen im Export.
- DWG-Export und DWG-Allgemeinteil sind ohne Windows mit ODA nicht getestet.
