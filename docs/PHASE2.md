# Phase 2: Projekte und Import

Stand: 30.09.2026

## Ablauf

1. Reiter **Projekte** → **Legende erstellen**.
2. Vorhandenes Projekt aus der Liste wählen, oder **Neues Projekt**: Name, Nova-Version (19.2 oder 20), optional **Vorlage** aus einem anderen Projekt (übernimmt Einstellungen und Ebenen, keine Pläne).
3. In der Projektansicht pro Geschoss einen Plan importieren: Name (z. B. EG), Datei wählen (DXF, N4D, DWG), **Plan importieren**.
4. **Gesamtliste**: alle Apparate aller Geschosse, eine Spalte pro Geschoss, Total, Montagearten (UP, AP …), gegliedert nach Kategorien mit Ebenenfarbe.
5. **Unbekannt**: Elemente, die das Tool nicht sicher erkennt. Pro Element eine Rangliste passender Bibliothekssymbole mit Trefferwert. Klick übernimmt. **Kein Apparat (ignorieren)** blendet es aus. Die Entscheidung gilt für die ganze Firma und bei jedem weiteren Import automatisch.
6. **Ebenen und Farben**: alle Ebenen der Pläne mit Farbe und Linienart.
7. **Nicht berücksichtigt**: Leitungen, Masse, Beschriftungen und von Hand ignorierte Elemente, mit Anzahl.

## Speicherort

Standard: `T:\_CAD\NovaDat\NovaFirma12\Makro\Legenden` (änderbar unter Einstellungen → Projektordner).

```
Legenden\
  <Projektname>\
    projekt.nlproj        Projektdatei (SQLite): Pläne, Versionen, Elemente, Ebenen, Einstellungen
    Plaene\               Kopie jeder importierten Datei mit Datum
  _Geloescht\             gelöschte Projekte (verschoben, nicht zerstört)
```

Projektfunktionen: umbenennen, kopieren, als ZIP exportieren, löschen (verschiebt nach `_Geloescht`), Nova-Version ändern, anderes Projekt direkt öffnen.

Jeder Import eines Plans ist eine Version. **Neu importieren** legt eine neue Version an. Der Vergleich zwischen Versionen folgt in Phase 3.

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
8. Exportieren (ZIP), Kopieren, Umbenennen, Löschen ausprobieren. Gelöschtes Projekt liegt in `_Geloescht`.

## Bekannte Grenzen

- Gesamtliste zeigt die Symbole aus der Bibliothek. Parametrische Leuchten erscheinen vereinfacht.
- Die Farbe einer Kategorie kommt aus der Ebene, die in der Kategorie eingetragen ist. Passt die Ebene nicht zu den Plänen (z. B. E_Licht gegenüber E_232.5_Licht), fehlt die Farbe. Ebene unter Kategorien anpassen.
- SQLite-Projektdateien auf T: sind für gleichzeitiges Lesen gut, gleichzeitiges Schreiben am selben Projekt wartet kurz.
- Änderungsvergleich zwischen Versionen: Phase 3.
