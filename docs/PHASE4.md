# Phase 4: Legenden-Editor

Stand: 30.09.2026 (Version 3: Symbolachse und Textlinie, eigene Symbolfarben, Ziehen, Drehen, Textfaktor)

## Aufbau der Legende

```
┌───────────────────────── Standard 200 mm, max. 210 mm inkl. Rand ─────────────────────────┐
│ Allgemeinteil (vom Server, gesperrt)                                     │
│ Titel                                                                    │
│ ███ Leuchten ███████████████████████████████████████████████ Kopfleiste  │
│  ○ Text …                ○ Text …                                        │
│ ███ Kraft / Drehstrominstallation ██████████████████████████████████████ │
│  ⊗ Text …                ⊗ Text …                                        │
└──────────────────────────────────────────────────────────────────────────┘
```

- Blattbreite einstellbar im Feld «Legende»: Standard 200 mm, höchstens 210 mm, inklusive 5 mm Rand. 2 oder 3 Spalten teilen die Breite. Bei einem schmaleren Blatt verkleinert sich der Allgemeinteil im gleichen Verhältnis, in Vorschau und Export.
- Kein freies Millimeter-Schieben. Alles sitzt auf dem festen Raster. Einträge ziehst du mit der Maus an einen anderen Platz oder in einen anderen Abschnitt, auf dem Blatt und in der linken Liste. ↑ ↓ und die Pfeiltasten gehen auch.
- Raster «★ Standard»: Zeile 4,55 mm, Text 9,75 mm rechts der Symbolmitte (edeco-Legende). Wählbar: Kompakt, Weit, Gross. «Raster anzeigen» blendet die Platzhalter im gewählten Mass ein. Aus ist der Normalzustand. Die Linien erscheinen nicht im Export.
- In jeder Spalte eines Abschnitts liegen alle Symbole mit ihrem Einfügepunkt auf einer senkrechten Achse. Liegt der Einfügepunkt nicht in der mittleren Hälfte des Symbols (Leitungen, Bus-Taster), gilt die Mitte des Symbols. Beschriftungen wie «2» oder «3» neben der Steckdose zählen nicht zur Mitte. Alle Texte beginnen auf einer zweiten senkrechten Linie rechts vom Symbol, das am weitesten nach rechts reicht. Symbol und Text teilen sich die waagrechte Mitte der Zeile.
- Jeder Eintrag belegt ganze Rasterzeilen. «Raster anzeigen» zeichnet pro Abschnitt genau diese Platzhalter: Zeilen, Spaltenränder, Symbolachse und Textlinie (gestrichelt). Alle Symbole haben denselben Massstab, das Programm verkleinert keines einzeln. Ein hohes Symbol belegt mehr Rasterzeilen. Nur ein Symbol, das breiter als eine halbe Spalte wäre, wird auf diese Breite begrenzt.
- Jedes Symbol hat einen eigenen Faktor «Symbolgrösse» (Voreinstellung 1) auf den gemeinsamen Symbolmassstab. Ein grösseres Symbol belegt mehr Rasterzeilen.
- Ein Symbol dreht sich in Schritten von 90 Grad um seinen Mittelpunkt. Der Text bleibt waagrecht. Die Zeile wird so hoch wie das gedrehte Symbol.
- Texte umbrechen in ihrer Spalte. Die Zeile wird höher, nie liegt ein Text auf dem nächsten Symbol oder in der nächsten Spalte.
- «Abstand zwischen Abschnitten (mm)»: 0 (Voreinstellung) heisst, die Abschnitte stossen aneinander. Der Abstand gilt in Vorschau und Export.
- Die Höhe wächst mit der Anzahl Einträge. Nichts wird abgeschnitten.
- Die Anordnung rechnet das Programm (Backend `legend/layout.py`). Vorschau und DXF-Export nutzen dieselbe Rechnung.

## Abschnitte

Pro Abschnitt (Kategorie) einstellbar: Farbe Kopfleiste, Schrift Kopfleiste, Text, Linien und Hinweise, Hintergrundfarbe (an/aus), Umrandung (an/aus), Innenabstand, Textgrösse der Überschrift.

- Voreinstellung: Kopfleiste in der Planfarbe der Legendenebene (Reiter «Ebenen und Farben»), helle Schrift auf dunkler Leiste, dunkle auf heller. Hintergrund aus, Umrandung aus, Text schwarz, das Papier bleibt weiss.
- Symbole behalten die Farben aus der Nova-Zeichnung, in Vorschau und DXF. Eine eigene Farbe im Symbol bleibt. Was keine eigene Farbe hat, wird schwarz. Einzige Ausnahme: Eine Fläche ohne eigene Farbe in einem Symbol mit farbigen Teilen (schwarze Linien auf Fläche) wird hellgrau, damit die schwarzen Linien sichtbar bleiben. Die Abschnittsfarbe färbt Symbole nie um.
- Legenden aus Version 2 verlieren beim Öffnen Fläche, Umrandung und die Symbolfärbung. Die Kopfleiste bleibt.

## Titel und Umrandung

- Titel anklicken (oder «T Titel» links): Text, Textgrösse als Faktor mit Anzeige in mm, Schriftfarbe, Umrandung an/aus mit Farbe.
- Im Feld «Legende»: «Umrandung der ganzen Legende» an/aus mit Farbe. Der Rahmen liegt in der Mitte des Blattrands.
- Beides ist voreingestellt aus und geht in den DXF-Export.

## Gemeinsame Werte

- Eine Schriftgrösse für alle Texte (Titel, Kopfleisten, Einträge, freier Text). Jeder Text hat zusätzlich einen Faktor (Voreinstellung 1). 1,2 macht nur diesen Text grösser, die Zeile wächst mit. Der Firmen-Standard speichert nur die gemeinsame Grösse.
- Ein Symbolmassstab für alle Symbole. Soll jedes Symbol in eine Rasterzeile passen, wähle einen kleineren Massstab (z. B. 0,6).
- Ein neues Projekt startet mit dem Firmen-Standard (Einstellungen → Legende der Firma). Mit Vorlage kommen Werte und Legende aus der Vorlage.
- Eine Änderung im Projekt gilt nur dort. «Für neue Projekte merken» schreibt die beiden Werte in den Firmen-Standard (nur Admins). Bestehende Projekte bleiben unverändert.

## Freier Text

Freier Text ist ein Zusatztext in der Legende, kein Apparat. Er sitzt im Raster wie ein Eintrag, in einem Abschnitt, und nutzt die gemeinsame Schriftgrösse. Ohne gewählten Abschnitt entsteht ein Abschnitt «Zusatztext». Entfernen über das Mülleimer-Symbol («Text entfernen»). Alte freie Texte (Version 1) wandern beim Öffnen in einen Abschnitt «Zusatztext».

## Allgemeinteil und Admins

- Einstellungen → Legende der Firma → Pfad auf die Servervorlage: DXF, DWG (mit ODA File Converter) oder Ordner eines Vorlagen-Projekts mit Legende.
- N4D geht nicht: Die Einfügepunkte der Symbole sind nicht sicher dekodiert. Das Programm meldet das.
- Der Allgemeinteil steht zuoberst, auf höchstens 190 mm Breite verkleinert, Höhe nach Inhalt. Er ist im Editor nicht änderbar. Anpassen heisst: Datei auf dem Server ersetzen. Das Programm liest sie beim Öffnen neu.
- Apparate, die der Allgemeinteil schon zeigt, kommen nicht in den Vorschlag. Links stehen sie unter «Im Allgemeinteil». Erkennung: Vorlagen-Projekt über das Symbol, DXF/DWG über den Text neben dem Symbol (Firmentext oder Bibliotheksname, ohne Gross-/Kleinschreibung und Satzzeichen, sonst genau gleich). Ähnliche Texte zählen nicht, der Eintrag bleibt sichtbar. Steht ein solcher Eintrag schon in einer Legende, blendet das Programm ihn beim Öffnen aus (nicht gelöscht, Strg+Z holt ihn zurück, «Wieder zeigen» im rechten Feld).
- Admins: Liste von Windows-Benutzernamen. Nur sie ändern Pfad, Admin-Liste und Firmen-Standard. Ist die Liste leer, darf der erste Benutzer sich eintragen. Wer speichert, muss selbst in der Liste stehen.

## Export

Rechts unter «Export» (nichts angewählt):

- «Ganze Legende» oder «Nur Leitungen» usw.
- «Allgemeinteil einschliessen» ist nie gesperrt. Abgewählt enthält die Datei keinen Block «Allgemeinteil». Ohne Servervorlage bleibt der Haken aus.
- Der Export speichert zuerst die aktuelle Legende und lädt dann die Datei.
- DXF R2013 (AC1027), Millimeter. DWG über den ODA File Converter; ohne Converter dieselbe Meldung wie beim Import.
- Farben als Truecolor: Kopfleiste und Hintergrund (Schraffur), Umrandung, Linien, Texte. Symbole als Block mit den Farben der Nova-Zeichnung, gedreht über den Drehwinkel des Einfügens.
- Ebenen: Symbole und Linien auf der Legendenebene der Kategorie, Texte auf X_Text, Kopfleisten und Rahmen auf X_Geometrie. Der Allgemeinteil wird als Block «Allgemeinteil» übernommen.
- Dateiname: `edeco ag-<Bezeichnung>-<Kategorie>.dxf` bzw. `…-Legende.dxf`.
- Kein N4D-Export.

## Prüfung vor der Weitergabe

Reiter «Prüfung» im Projekt. Oben der Stand: «Bereit zur Weitergabe» oder die Zahl der Punkte, die behoben werden müssen (auch als rote Zahl am Reiter). Jeder Punkt hat «Öffnen» und springt in den Reiter, wo er behoben wird.

| Punkt | Stufe | Reiter |
|---|---|---|
| Unbekannte Elemente | muss behoben werden | Unbekannt |
| Noch keine Legende | muss behoben werden | Legende |
| Fehlt in der Legende (nicht im Allgemeinteil) | muss behoben werden | Legende |
| Nur über den Namen erkannt (ohne Katalogcode) | prüfen | Gesamtliste |
| Ebene wählen | prüfen | Ebenen und Farben |
| Symbol ohne Zeichnung | prüfen | Legende |
| Doppelt in der Legende | prüfen | Legende |
| Nicht mehr in den Plänen | prüfen | Legende |
| Legende älter als der letzte Import | prüfen | Legende |

Die Prüfung liest nur, sie ändert nichts. Sie läuft nach jeder Projektänderung und beim Öffnen des Reiters neu.

## Speicherort

Legende: `projekt.nlproj`, Tabelle `legend` (Version 2). Firmenwerte: `edeco ag-Legenden-firma.sqlite`, Tabelle `options` (Schlüssel `legend_*`), Firmentexte in `descriptions`.

## Links im Editor

- «Im Projekt, nicht in der Legende» und «Aus der Bibliothek» zeigen kleine Symbol-Icons. Anklicken fügt hinzu, Ziehen auf einen Abschnitt legt das Symbol dort ab, mit dem Firmentext, sonst dem Bibliotheksnamen.
- Liegt dasselbe Symbol schon in der Legende, steht «doppelt» an der Zeile. Ziehen geht trotzdem. Auf dem Blatt ist das zweite Vorkommen orange gestrichelt markiert.

## So testest du

1. Einstellungen → Legende der Firma: dich als Admin eintragen, Pfad auf eine DXF-Vorlage setzen.
2. Projekt → «Legende bearbeiten» rechts in der Reiterleiste → «Vorschlag aus dem Projekt erstellen».
3. Allgemeinteil oben, darunter farbige Abschnitte. Raster «★ Standard», Spalten 2 und 3 ausprobieren.
4. Schriftgrösse auf 3 setzen, Strg+Z: ein Schritt zurück.
5. Eine Kopfleiste anklicken, Farben ändern, Umrandung aus.
6. Export «Nur Brandmeldeanlage» mit und ohne Allgemeinteil, die DXF in Nova oder einem DXF-Viewer öffnen.
7. «Für neue Projekte merken», neues Projekt anlegen: hat die Werte. Ein anderes bestehendes Projekt: unverändert.

## Bekannte Grenzen

- Textbreiten rechnet das Programm mit einer Arial-Näherung. In Nova kann ein Text minimal breiter oder schmaler sein.
- Symbole aus .nsb-Bibliotheken erscheinen als Rahmen «keine Vorschau» und fehlen im Export.
- DWG-Export und DWG-Allgemeinteil sind ohne Windows mit ODA nicht getestet.
