# Phase 4: Legenden-Editor

Stand: 30.09.2026

## Ablauf

1. Projekt öffnen, Reiter **Legende**.
2. **Vorschlag aus dem Projekt erstellen**: alle Apparate der aktuellen Importe, ein Abschnitt pro Kategorie (Einstellung «Legende nach Kategorien gliedern»). Kategorien, die ausgeblendet sind, fehlen. Gibt es AP- oder NAP-Varianten, kommt der Hinweis «Unterscheidung UP / AP (halbausgefüllt)» dazu.
3. Auf der Zeichenfläche verschieben: Symbole, Abschnitte (an der Überschrift), freie Texte und den Titel. **Einrasten** mit wählbarem Raster (0,25 bis 5 mm, auch 4,55 mm Zeilenabstand).
4. Anklicken öffnet rechts die Eigenschaften: Beschreibung, Schriftgrösse, Massstab, Position, Abschnitt. Parametrische Leuchten zusätzlich Länge und Breite in Millimetern wie im Plan.
5. Links die Gliederung: Abschnitte ein- und ausklappen, mit ↑ ↓ umsortieren, Einträge anwählen. Darunter **Im Projekt, nicht in der Legende** (per Klick oder «Alle hinzufügen») und **Aus der Bibliothek hinzufügen**.
6. **+ Linie** für Leitungen und Trassen (durchgezogen, gestrichelt, punktiert, Strich-Punkt, Länge wählbar), **+ Hinweis** mit halb gefülltem Kreis, **+ Freier Text**.
7. **Automatisch anordnen** ordnet Abschnitte in Legendenspalten und Einträge in Zeilen. Danach frei nachbearbeiten.
8. **Rückgängig** und **Wiederholen** (Strg+Z, Strg+Y). Ein Zug mit der Maus und ein bearbeitetes Textfeld sind je ein Schritt.

Die Legende speichert sich selbst, etwa eine Sekunde nach der letzten Änderung. Oben rechts steht «Gespeichert … von …».

## Texte

| Quelle | Wirkung |
|---|---|
| Firmentext | «Als Firmentext speichern» merkt die Beschreibung einer Symbolfamilie für die ganze Firma (Tabelle `descriptions` in `edeco ag-Legenden-firma.sqlite`). Neue Vorschläge in allen Projekten nutzen ihn. |
| Legende edeco | Die 65 Texte der bestehenden Legende (Legende_edeco20.n4d) stehen als Vorschläge bereit, sortiert nach Ähnlichkeit zum aktuellen Text. |
| Bibliothek | Ohne Firmentext steht der Name der Familie aus der Bibliothek. |

Die Zuordnung «dieser Text gehört zu diesem Symbol» steht im N4D nicht sicher: Texte und Symbole liegen getrennt, die Einfügepunkte der Symbole sind noch nicht entschlüsselt. Darum schlägt das Programm die Texte vor und du bestätigst sie.

## Vorlage und Masse

Aus der bestehenden edeco-Legende übernommen: Zeilenabstand 4,55 mm, Text 9,75 mm rechts der Symbolmitte, Spaltenbreite 103,7 mm, zwei Legendenspalten, Schrift Arial. Textgrössen: Titel 5 mm, Überschrift 3,5 mm, Text 2,5 mm. Alles unter «Legende» (nichts angewählt) änderbar. Spalten und Zeilenabstand pro Abschnitt kommen aus der Kategorie und lassen sich pro Legende ändern.

Grosse Symbole (zum Beispiel Leitungspfeile) verkleinert der Vorschlag auf die Zeilenhöhe. Der Massstab steht im Feld «Massstab Symbol» und bleibt frei änderbar. Parametrische Leuchten zeichnet das Programm im Massstab 1:50 (einstellbar) mal diesem Massstab.

## Speicherort

Die Legende liegt in `projekt.nlproj` (Tabelle `legend`). Kopieren und ZIP-Export nehmen sie mit. Ältere Projektdateien bekommen die Tabelle beim ersten Öffnen der Legende.

## Darstellung hell und dunkel

Oben rechts wechselt der Knopf zwischen hell und dunkel. Unter Einstellungen → Darstellung gibt es zusätzlich «Wie Windows». Die Wahl gilt pro Computer (lokale Einstellungen). Die Legende bleibt immer weiss wie auf dem Plan.

## So testest du Phase 4

1. Update installieren (Build mit diesem Stand).
2. Projekt mit importierten Plänen öffnen, Reiter Legende, «Vorschlag aus dem Projekt erstellen».
3. Ein Symbol ziehen, Strg+Z, Strg+Y.
4. Ein Symbol anklicken, Beschreibung ändern, einen Vorschlag aus der edeco-Legende anklicken, «Als Firmentext speichern».
5. Eine Leuchte aus der Bibliothek hinzufügen (z. B. «Rechteckleuchte»), Länge 1500 eingeben.
6. «+ Linie» für eine Leitung, Linienart gestrichelt.
7. Einen Abschnitt mit ↑ verschieben, «Automatisch anordnen».
8. Programm schliessen und neu öffnen: die Legende ist unverändert da.
9. Oben rechts auf hell umschalten, Programm neu starten: bleibt hell.

## Bekannte Grenzen

- Kein Export. DXF und DWG folgen in Phase 5, N4D in Phase 6.
- Eine Legende pro Projekt. Die Auswahl «je Kategorie eine eigene Legende» kommt mit dem Export.
- Symbole aus .nsb-Bibliotheken erscheinen als Rahmen «keine Vorschau».
- Mehrfachauswahl gibt es nicht. Ein Abschnitt verschiebt alle seine Einträge.
- Lange Texte laufen über die Spaltenbreite hinaus. Die Breite prüft das Programm nicht.
