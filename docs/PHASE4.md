# Phase 4: Legenden-Editor

Stand: 04.10.2026 (Version 4: gleiche Kacheln, Symbolfarbe nach Abschnitt, Spiegeln und 45 Grad, mehrere Legenden, PDF)

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
- Ziehen auf dem Blatt: Jede Rasterzelle ist ein Ablageplatz, auch die leeren. Die Zielzelle ist blau hinterlegt, und das Blatt zeigt schon beim Ziehen, wie die Legende danach aussieht.
  - Auf eine belegte Zelle: Wie beim iPhone rücken die anderen Einträge um einen Platz weiter, bis zur nächsten leeren Zelle.
  - Auf eine leere Zelle: Der Eintrag liegt genau dort, die anderen bleiben stehen. So setzt du z. B. in einer dreispaltigen Legende ein Symbol zuunterst in die dritte Spalte. Die Plätze darüber bleiben leer (im Dokument als «leere Zelle» gespeichert, im Export unsichtbar).
  - Leere Zellen am Ende eines Abschnitts entfernt das Programm.
- Raster «★ Standard»: Zeile 4,55 mm, Text 9,75 mm rechts der Symbolmitte (edeco-Legende). Wählbar: Kompakt, Weit, Gross. «Raster anzeigen» blendet die Platzhalter im gewählten Mass ein. Aus ist der Normalzustand. Die Linien erscheinen nicht im Export.
- Symbolgrösse im Feld «Legende», zwei Arten:
  - «Gleiche Kacheln (75 % gefüllt)», Voreinstellung: Jedes Symbol bekommt eine gleich grosse quadratische Kachel. Ihre Grösse richtet sich nach der Schriftgrösse (Schriftgrösse × 3,6 × Symbolmassstab, höchstens 46 % der Spaltenbreite). Das Symbol füllt 75 % der Kachel, so bleibt Luft rundherum. Alle Zeilen sind gleich hoch, ausser ein Text braucht mehr Zeilen.
  - «Echte Grösse (Massstab)»: Alle Symbole im gemeinsamen Massstab, ausgerichtet am Einfügepunkt (siehe unten).
- «Raster anzeigen» zeichnet im Kachelmodus die Kachel jedes Symbols grün und den Abstand zwischen den Einträgen orange.
- In jeder Spalte eines Abschnitts liegen alle Symbole mit ihrem Einfügepunkt auf einer senkrechten Achse. Liegt der Einfügepunkt nicht in der mittleren Hälfte des Symbols (Leitungen, Bus-Taster), gilt die Mitte des Symbols. Beschriftungen wie «2» oder «3» neben der Steckdose zählen nicht zur Mitte. Alle Texte beginnen auf einer zweiten senkrechten Linie rechts vom Symbol, das am weitesten nach rechts reicht. Symbol und Text teilen sich die waagrechte Mitte der Zeile.
- Jeder Eintrag belegt ganze Rasterzeilen. «Raster anzeigen» zeichnet pro Abschnitt genau diese Platzhalter: Zeilen, Spaltenränder, Symbolachse und Textlinie (gestrichelt). Alle Symbole haben denselben Massstab, das Programm verkleinert keines einzeln. Ein hohes Symbol belegt mehr Rasterzeilen. Nur ein Symbol, das breiter als eine halbe Spalte wäre, wird auf diese Breite begrenzt.
- Jedes Symbol hat einen eigenen Faktor «Symbolgrösse» (Voreinstellung 1) auf den gemeinsamen Symbolmassstab. Ein grösseres Symbol belegt mehr Rasterzeilen.
- Ein Symbol dreht sich mit «↻ 45°» oder «↻ 90°» um seinen Mittelpunkt. «⇋ Spiegeln» spiegelt es an der senkrechten Achse. Beides gilt in Vorschau, DXF und PDF. Der Text bleibt waagrecht. Die Zeile wird so hoch wie das gedrehte Symbol.
- Texte umbrechen in ihrer Spalte. Die Zeile wird höher, nie liegt ein Text auf dem nächsten Symbol oder in der nächsten Spalte. «Textzeilen» 0 (automatisch) schneidet nie Text ab.
- Im DXF steht die Texthöhe als Höhe der Grossbuchstaben (Schriftgrösse × 0,716). So ist der Text in CAD gleich gross wie im Editor und bleibt in seiner Spalte.
- «Abstand zwischen Abschnitten (mm)»: 0 (Voreinstellung) heisst, die Abschnitte stossen aneinander. Der Abstand gilt in Vorschau und Export.
- Die Höhe wächst mit der Anzahl Einträge. Nichts wird abgeschnitten.
- Die Anordnung rechnet das Programm (Backend `legend/layout.py`). Vorschau, DXF- und PDF-Export nutzen dieselbe Rechnung.

## Abschnitte

Pro Abschnitt (Kategorie) einstellbar: Farbe Kopfleiste, Schrift Kopfleiste, Text, Linien und Hinweise, Hintergrundfarbe (an/aus), Umrandung (an/aus), Innenabstand, Textgrösse der Überschrift.

- Voreinstellung: Kopfleiste in der Planfarbe der Legendenebene (Reiter «Ebenen und Farben»), helle Schrift auf dunkler Leiste, dunkle auf heller. Hintergrund aus, Umrandung aus, Text schwarz, das Papier bleibt weiss.
- Symbole zeichnet das Programm in der Farbe des Abschnitts, also der Planfarbe der Legendenebene. Hat die Kategorie keine Planfarbe, sind sie schwarz. Eine eigene Farbe im Nova-Symbol bleibt. Eine Fläche ohne eigene Farbe in einem Symbol mit farbigen Teilen wird ein heller Ton der Abschnittsfarbe (45 %), damit die Linien sichtbar bleiben. Gilt in Vorschau, DXF und PDF.
- Im Feld «Legende» zwei Schalter für alle Symbole: «Weiche Schraffur aus» entfernt Schraffuren und helle Flächen hinter Linien. «Volle Flächen aus» entfernt ganz ausgefüllte Teile, z. B. den Anschlusspunkt. Die Umrisse bleiben. Beide gelten in Vorschau, DXF und PDF. Der Firmen-Standard für neue Projekte steht in Einstellungen → Legende der Firma. Das alte «Symbol-Hintergründe/Schraffuren entfernen» wird zu beiden Schaltern.
- Legenden aus Version 3 übernehmen beim Öffnen die Abschnittsfarbe für die Symbole.
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

## Texte der Einträge und Firmentexte

- Der Vorschlag nimmt den Firmentext. Ohne Firmentext nimmt er die Bezeichnung aus der Nova-Schablone (Bauteil-Bezeichnung ohne UP/AP), z. B. «Stellantrieb» statt des Grafiknamens «1», «UKV Rack» statt «Kreuz».
- Grafiknamen, die nur eine Variante bezeichnen («Kreuz», «Gefüllt», «1»), bilden zusammen mit ihrem Bauteil eine Familie. UKV Rack und Verteiler teilen sich so keine Familie mehr.
- Firmentext speichern: im Editor einen Eintrag anklicken, Text ändern, «Als Firmentext speichern». Er gilt für die ganze Symbolfamilie in allen neuen Legenden, egal ob der Apparat über Katalogcode oder Namen erkannt wird.
- Liste: Einstellungen → Firmentexte. Suchen, ändern, entfernen. «Für Excel exportieren (CSV)» schreibt `edeco ag-Firmentexte.csv` (Semikolon, UTF-8). In Excel die Spalte «Firmentext» ändern, als CSV speichern, mit «Aus CSV übernehmen» einlesen. Ein leerer Text entfernt den Firmentext.
- Speicherort: Firmenordner (Einstellungen → Firmenordner), Datei `edeco ag-Legenden-firma.sqlite`, Tabelle `descriptions`.
- Verteiler (UV, HV, ZV, HAK, Hausanschluss) gehören in den Allgemeinteil. Der Vorschlag lässt sie weg, die Prüfung meldet sie nicht als fehlend. Links lassen sie sich trotzdem einfügen.
- NUP und andere Montagearten: ein Eintrag pro Funktion. Was NUP bedeutet, steht im Allgemeinteil.

## Benutzerschablone (Nova-Schablonen)

- Einstellungen → Benutzerschablonen: Ordner der .n5q-Dateien. Voreinstellung `%USERPROFILE%\OneDrive - edeco AG\Dokumente\Trimble\nova{nova}\Stencils`. `{nova}` ersetzt das Programm durch die Nova-Version des Projekts (19 für 19.2, 20 für 20). Die Einstellung gilt für diesen Computer und Benutzer.
- Der Legenden-Editor zeigt links «Benutzerschablone» mit Sätzen und Registerkarten wie in Nova. Einträge mit Katalogsymbol lassen sich anklicken oder ziehen. Der Text ist der Firmentext, sonst der Name des Eintrags.
- Makros (Plankopf, Planrahmen, eigene Symbole) stehen mit dem Nova-Vorschaubild in der Liste, lassen sich aber noch nicht in die Legende ziehen.
- Vorschlag: Firmentext, sonst die Bezeichnung aus der Benutzerschablone (die häufigste für dieses Symbol, ohne UP/AP), sonst die Bauteil-Bezeichnung aus dem Trimble-Katalog.
- Die Schablone verweist auf einen bestimmten Datensatz (heute meist Elektroinstallationen.CH). Bei Plänen aus V2 greifen ihre Namen nur, wo die Symbolfamilie gleich heisst.

## Freier Text

Freier Text ist ein Zusatztext in der Legende, kein Apparat. Er sitzt im Raster wie ein Eintrag, in einem Abschnitt, und nutzt die gemeinsame Schriftgrösse. Ohne gewählten Abschnitt entsteht ein Abschnitt «Zusatztext». Entfernen über das Mülleimer-Symbol («Text entfernen»). Alte freie Texte (Version 1) wandern beim Öffnen in einen Abschnitt «Zusatztext».

## Allgemeinteil in Zeilen (DWG/DXF)

- Die Servervorlage (DWG oder DXF) bleibt die Quelle. Das Programm zerlegt sie beim Lesen in Zeilen: Symbolgrafik links, Text in der Textspalte. Ein Text ohne Grafik ausserhalb der Spalte ist eine Überschrift (z. B. «Farbcodes»).
- Die Zeilen fliessen in die Spalten der Legende. Beim Wechsel von 2 auf 3 Spalten ordnet sich der Allgemeinteil sofort neu. Die Texte haben die Schriftgrösse der Legende und umbrechen in ihrer Spalte.
- Im DXF-Export ist jede Zeilengrafik ein eigener Block (`Allgemeinteil_g0` …), die Texte sind normale Texte auf X_Text.
- Symbole in der Zeichnung (Nova-Blocknamen, z. B. «Steigleitung_ nach oben») blenden ihre Familien in den Projektabschnitten aus. Im Allgemeinteil bleiben sie sichtbar.
- Einstellungen → Allgemeinteil bearbeiten (nur Admins): Text ändern, Zeile ausblenden, Zeile mit weiteren Symbolen verknüpfen. Diese Änderungen liegen in der Firmendatenbank neben der Zeichnung, die DWG bleibt unverändert. Neue Symbole und Reihenfolge: DWG in Nova anpassen, dann «Neu laden». Das Programm liest die Datei auch von selbst neu, wenn sie sich ändert.
- Eine Zeichnung ohne klare Textspalte bleibt eine gesperrte Zeichnung wie bisher.

## Linientypen

- Musterlinien in der Legende sind kurz (5 bis 12 mm). Regel: mindestens 2,5 Wiederholungen des Musters, Striche mindestens 0,8 mm, Lücken mindestens 0,45 mm auf Papier.
- Linien in Abschnitten nutzen eigene Linientypen mit Muster in mm (NL_STRICH, NL_PUNKT, NL_STRICHPUNKT) und 0,35 mm Strichstärke. Editor, DXF und PDF rechnen gleich.
- Im Allgemeinteil berechnet das Programm den Linientypfaktor jeder gemusterten Linie neu, auch in Blöcken. Linientypen mit leeren Formflags werden zu einfachen Strichmustern. So unterscheiden sich UP-Decke, -Hohldecke, -Wand und -Boden.

## Allgemeinteil und Admins

- Einstellungen → Legende der Firma → Pfad auf die Servervorlage: DXF, DWG (mit ODA File Converter) oder Ordner eines Vorlagen-Projekts mit Legende.
- N4D geht nicht: Die Einfügepunkte der Symbole sind nicht sicher dekodiert. Das Programm meldet das.
- Der Allgemeinteil steht zuoberst, auf höchstens 190 mm Breite verkleinert, Höhe nach Inhalt. Er ist im Editor nicht änderbar. Anpassen heisst: Datei auf dem Server ersetzen. Das Programm liest sie beim Öffnen neu.
- Apparate, die der Allgemeinteil schon zeigt, kommen nicht in den Vorschlag. Links stehen sie unter «Im Allgemeinteil». Erkennung: Vorlagen-Projekt über das Symbol, DXF/DWG über den Text neben dem Symbol (Firmentext oder Bibliotheksname, ohne Gross-/Kleinschreibung und Satzzeichen, sonst genau gleich). Ähnliche Texte zählen nicht, der Eintrag bleibt sichtbar. Steht ein solcher Eintrag schon in einer Legende, blendet das Programm ihn beim Öffnen aus (nicht gelöscht, Strg+Z holt ihn zurück, «Wieder zeigen» im rechten Feld).
- Admins: Liste von Windows-Benutzernamen. Nur sie ändern Pfad, Admin-Liste und Firmen-Standard. Ist die Liste leer, darf der erste Benutzer sich eintragen. Wer speichert, muss selbst in der Liste stehen.

## Mehrere Legenden

Ein Projekt hat eine oder mehrere benannte Legenden, z. B. «Legende» und «Brandmelder». Die Auswahl steht oben im Reiter «Legende».

- «+ Neue Legende»: Name, dann «Vorschlag aus gewählten Kategorien» (z. B. nur Brandmeldeanlage), «Vorschlag aus allen Kategorien», «Kopie» der gewählten Legende oder «Leer».
- «Umbenennen» und «Löschen» wirken auf die gewählte Legende. Die letzte Legende bleibt bestehen.
- Jede Legende speichert sich selbst. Wechselst du die Legende, speichert das Programm zuerst die offene.
- Der Export nimmt die gewählte Legende. Bei mehreren Legenden steht ihr Name im Dateinamen statt «Legende».
- Die Prüfung schaut alle Legenden zusammen an. Ein Apparat fehlt nur, wenn ihn keine Legende zeigt.
- Ein neues Projekt mit Vorlage übernimmt alle Legenden der Vorlage mit ihren Namen.

## Export

Rechts unter «Export» (nichts angewählt):

- «Ganze Legende» oder «Nur Leitungen» usw.
- «Allgemeinteil einschliessen» ist nie gesperrt. Abgewählt enthält die Datei keinen Block «Allgemeinteil». Ohne Servervorlage bleibt der Haken aus.
- Der Export speichert zuerst die aktuelle Legende und lädt dann die Datei.
- DXF R2013 (AC1027), Millimeter. DWG über den ODA File Converter; ohne Converter dieselbe Meldung wie beim Import.
- Farben als Truecolor: Kopfleiste und Hintergrund (Schraffur), Umrandung, Linien, Texte. Symbole als Block mit den Farben der Nova-Zeichnung, gedreht über den Drehwinkel des Einfügens.
- Ebenen: Symbole und Linien auf der Legendenebene der Kategorie, Texte auf X_Text, Kopfleisten und Rahmen auf X_Geometrie. Der Allgemeinteil wird als Block «Allgemeinteil» übernommen.
- Dateiname: `edeco ag-<Bezeichnung>-<Kategorie>.dxf` bzw. `…-Legende.dxf`.
- PDF: dieselbe Zeichnung wie die DXF-Datei, als Vektorgrafik auf einer Seite in Originalgrösse (mm 1:1) mit 10 mm Rand. Texte als Umrisse, Farben wie im DXF, mit oder ohne Allgemeinteil. Kein Zusatzprogramm nötig.
- Dateiname PDF: `edeco ag-<Bezeichnung>-<Kategorie>.pdf` bzw. `…-Legende.pdf`.
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
| Doppelt im selben Abschnitt | prüfen | Legende |
| Nicht mehr in den Plänen | prüfen | Legende |
| Legende älter als der letzte Import | prüfen | Legende |

Die Prüfung liest nur, sie ändert nichts. Sie läuft nach jeder Projektänderung und beim Öffnen des Reiters neu.

## Speicherort

Legenden: `projekt.nlproj`, Tabelle `legends` (id, Name, Reihenfolge, Dokument Version 4). Die erste Legende steht zusätzlich in der alten Tabelle `legend`, damit ältere Programmversionen sie lesen. Firmenwerte: `edeco ag-Legenden-firma.sqlite`, Tabelle `options` (Schlüssel `legend_*`), Firmentexte in `descriptions`.

## Links im Editor

- «Im Projekt, nicht in der Legende» und «Aus der Bibliothek» zeigen kleine Symbol-Icons. Anklicken fügt hinzu, Ziehen auf einen Abschnitt legt das Symbol dort ab, mit dem Firmentext, sonst dem Bibliotheksnamen.
- Liegt dasselbe Symbol schon in der Legende, steht «doppelt» an der Zeile. Ziehen geht trotzdem. Auf dem Blatt ist das zweite Vorkommen orange gestrichelt markiert.

## So testest du

1. Einstellungen → Legende der Firma: dich als Admin eintragen, Pfad auf eine DXF-Vorlage setzen.
2. Projekt → «Legende bearbeiten» rechts in der Reiterleiste → «Vorschlag aus dem Projekt erstellen».
3. Allgemeinteil oben, darunter farbige Abschnitte. Raster «★ Standard», Spalten 2 und 3 ausprobieren.
4. Schriftgrösse auf 3 setzen, Strg+Z: ein Schritt zurück.
5. Eine Kopfleiste anklicken, Farben ändern, Umrandung aus.
6. Export «Nur Brandmeldeanlage» mit und ohne Allgemeinteil, die DXF in Nova oder einem DXF-Viewer öffnen. Dasselbe als PDF.
7. «+ Neue Legende» → «Brandmelder», nur die Kategorie Brandmeldeanlage wählen. Etwas ändern, zur ersten Legende wechseln und zurück: Die Änderung ist noch da.
8. «Für neue Projekte merken», neues Projekt anlegen: hat die Werte. Ein anderes bestehendes Projekt: unverändert.

## Bekannte Grenzen

- Textbreiten rechnet das Programm mit einer Arial-Näherung. In Nova kann ein Text minimal breiter oder schmaler sein.
- DWG-Export und DWG-Allgemeinteil sind ohne Windows mit ODA nicht getestet.
- Das PDF-Layout entspricht der DXF-Datei. Schriften kommen aus den Windows-Schriften (arial.ttf), fehlt eine, nimmt ezdxf eine Ersatzschrift.
