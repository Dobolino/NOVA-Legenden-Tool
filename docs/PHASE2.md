# Phase 2: Projekte und Import

Stand: 30.09.2026

## Ablauf

1. Reiter **Projekte** → **Legende erstellen**.
2. Vorhandenes Projekt aus der Liste wählen, oder **Neues Projekt**: Projektnummer, Bezeichnung, Nova-Version (19.2 oder 20), optional **Vorlage** aus einem anderen Projekt (übernimmt Einstellungen und Ebenen, keine Pläne). **Vorlage ausblenden** nimmt ein Projekt aus dieser Liste, ohne es zu löschen. **Nach ‚Gelöscht‘ verschieben** steht in der Liste und in der Projektansicht.
3. In der Projektansicht **Pläne importieren …**: eine oder mehrere Dateien wählen oder hierher ziehen (DXF, N4D, DWG). Ein Fenster zeigt pro Datei den Geschossnamen zum Prüfen; heisst er wie ein vorhandenes Geschoss, wird die Datei dessen neue Planversion. Der Geschossname kommt aus dem Dateinamen, wenn er EG, 1. OG, UG, DG oder Stock enthält (`3_1.OG.dxf` → `1. OG`). Geschosse lassen sich ziehen, um die Spalten zu sortieren.
4. **Gesamtliste**: alle Apparate aller Geschosse, eine Spalte pro Geschoss, Total, gegliedert nach Kategorien mit Ebenenfarbe. Die Montageart bleibt nur in der Bibliothek als Filter.
5. **Unbekannt**: Elemente, die das Tool nicht sicher erkennt. Pro Element eine Rangliste passender Bibliothekssymbole mit Trefferwert. Klick übernimmt. **Kein Apparat (ignorieren)** blendet es aus. Die Entscheidung gilt für die ganze Firma und bei jedem weiteren Import automatisch.
6. **Ebenen und Farben**: Farbe pro Kategorie (automatisch oder selbst gewählt) und darunter alle Ebenen der Pläne mit Farbe und Linienart.
7. **Nicht berücksichtigt**: Leitungen, Masse, Beschriftungen und von Hand ignorierte Elemente, mit Anzahl.

## Speicherort

Standard: `T:\_CAD\NovaDat\NovaFirma12\Makro\Legenden` (änderbar unter Einstellungen → Projektordner).

```
Legenden\
  <Projektname>\
    projekt.nlproj        Projektdatei (SQLite): Pläne, Versionen, Elemente, Ebenen, Einstellungen
    Plaene\               eine Plandatei pro Geschoss (wird beim Neuimport ersetzt)
  _Geloescht\             gelöschte Projekte (verschoben, nicht zerstört)
```

Die gemeinsamen Kategorien liegen in `edeco ag-Legenden-firma.sqlite` (ältere Datei `firma.sqlite` wird einmal umbenannt).

**Projekt als ZIP exportieren** lädt eine ZIP-Datei `edeco ag-<Bezeichnung>-projekt.zip`. Darin liegt der Projektordner mit `projekt.nlproj` (die Projektdatenbank) und einer Plandatei pro Geschoss. `projekt.nlproj` ist der interne Dateiname, nicht der Name des Downloads.

Projektfunktionen: Projektnummer und Bezeichnung speichern, **Projekt duplizieren**, **Projekt als ZIP exportieren**, **Nach ‚Gelöscht‘ verschieben** (verschiebt nach `_Geloescht`), Nova-Version ändern, anderes Projekt direkt öffnen, als Vorlage ausblenden.

**Neue Planversion importieren** ersetzt die Plandatei dieses Geschosses und legt eine neue Importversion an. Apparate, die in der neuen Datei fehlen, bleiben in der Liste mit Anzahl 0. Zuordnung über Katalogcode, Bezeichnung (Bez) oder Name, damit eine bestehende Zeile und eine gespeicherte Entscheidung erhalten bleiben. **Weitere Aktionen → Datei entfernen** entfernt nur die gespeicherte Plandatei. Importierte Anzahlen und Versionen bleiben erhalten. Eine Zeile mit Total 0 lässt sich mit **Zeile löschen** entfernen. Was sich zwischen zwei Importen geändert hat, zeigt Phase 3.

## Erkennung

| Quelle | Regel |
|---|---|
| DXF, DWG | Attribut `TypID` = Katalogcode, `Bez` = Grafikname, `Herkunft` = Datensatz. Ohne Attribute: Blockname = Symbolname. Leitungen, Masse, Beschriftungen, Plankopf und Planrahmen zählen nicht. |
| N4D | Datensatz, Katalogcode und Grafik direkt aus dem Objekt. Beschriftungen (Label_*) zählen nicht. |
| Alle | Vorrang hat eine gespeicherte Entscheidung (Firmenordner, Tabelle `mappings`). |

Ergebnis am Plan 1. OG: N4D 238 Apparate erkannt. DXF 236 erkannt, 5 Arten unbekannt (Gruppenzuleitung, Deckendurchbruch, LED-Langfeldleuchte 8W, Gateway, umbenannter Verteiler).

Dasselbe Symbol aus V1 und V2 erscheint in der Gesamtliste als eine Zeile.

### Vorschläge für unbekannte Elemente

Trefferwert 0 bis 100 %:

| Teil | Gewicht |
|---|---|
| Namensähnlichkeit (rapidfuzz) | 60 % |
| Geometrie (Anzahl Linien, Bögen, Flächen, Texte, Seitenverhältnis) | 20 % |
| gleicher Nummernkreis | 10 % |
| Ebene passt zur Kategorie | 10 % |

### Ebenenfarben

- DXF/DWG: Farbe aus der Ebenentabelle.
- N4D: nach dem Ebenennamen steht die Farbe als R, G, B, 0 (zweimal). Geprüft: 17 von 17 Ebenen stimmen mit dem DXF desselben Plans überein.
- Jede importierte Farbe wird auch im Firmenordner gespeichert (Tabelle `layer_colors`).

### DWG

Braucht den ODA File Converter (Einstellungen zeigen, ob er gefunden wurde). Ohne Converter meldet der Import: «Plan in Nova als DXF exportieren und diese Datei importieren.» Die Umwandlung selbst ist hier nicht getestet (kein Windows mit ODA in der Testumgebung).

## So testest du Phase 2

1. Update installieren (Build ab 9).
2. Einstellungen → Projektordner prüfen: `T:\_CAD\NovaDat\NovaFirma12\Makro\Legenden`.
3. Projekte → Legende erstellen → Neues Projekt «Test Phase 2», Nova 19.2.
4. Plan importieren: «1. OG», Datei `3_1.OG.n4d`. Erwartet: 238 Apparate, Gesamtliste mit rund 40 Zeilen.
5. Zweiten Plan importieren: «1. OG DXF», Datei `3_1.OG.dxf`. Erwartet: zweite Spalte, Reiter Unbekannt (5).
6. Unbekannt: «Gateway» → Vorschlag «Funk-Gateway» anklicken. Das Element verschwindet aus Unbekannt und erscheint in der Gesamtliste.
7. Neues Projekt mit Vorlage «Test Phase 2» anlegen, denselben DXF importieren: Gateway ist sofort erkannt.
8. Projekt als ZIP exportieren, Projekt duplizieren, Umbenennen, Nach ‚Gelöscht‘ verschieben ausprobieren. Gelöschtes Projekt liegt in `_Geloescht`.

## Bekannte Grenzen

- Gesamtliste zeigt die Symbole aus der Bibliothek. Parametrische Leuchten erscheinen vereinfacht.
- Die Farbe einer Kategorie sucht zuerst die Legendenebene (E_Licht), sonst eine Planeebene mit demselben Namensteil (E_232.5_Licht). E_233_Leuchten passt nicht zu E_Licht. Unter **Ebenen und Farben** und in der Gruppenzeile lässt sich die Ebene pro Projekt wählen. Gibt es keine passende Ebene, steht der Grund daneben.
- SQLite-Projektdateien auf T: sind für gleichzeitiges Lesen gut, gleichzeitiges Schreiben am selben Projekt wartet kurz.
- Änderungsvergleich zwischen zwei Importen: [Phase 3](PHASE3.md).
