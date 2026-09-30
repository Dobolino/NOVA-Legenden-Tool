# Phase 0: Analyse und Validierung

Stand: 30.09.2026. Geprüfte Dateien:

| Datei | Inhalt |
|---|---|
| Elektroinstallationen.V2.CH.nzp | Datensatz V2, Version 1.3.2, Stand 2025-09 |
| Elektroinstallationen.CH.nzp | Datensatz V1 (Vorgänger), Version 2.8.7, Stand 2022-03 |
| Legende_edeco20.n4d | bestehende Legende (Makro) |
| 3_1.OG.n4d | Plan 1. OG |
| Benutzerschablonen.n5q | Layout-Vorlagen edeco |

Nicht vorhanden: DWG- oder DXF-Beispielpläne, ODA File Converter, Angabe zur Nova-Version der N4D-Dateien.

## 1. Ergebnis in Kürze

- Die Zuordnung Name zu Geometrie ist **gelöst und geprüft**. Alle 16 Dateien beider Datensätze lassen sich lesen und Byte für Byte identisch zurückschreiben.
- Beide Datensätze ergeben zusammen 4664 2D-Symbole (V2: 2346, V1: 2318). Davon haben 4275 eine vollständige Vektorgeometrie. Beim Lesen treten 0 Warnungen auf.
- Der Nummernkreis ist die Nova-«Sheet»-Nummer und entspricht genau einem Ordner der Schablone. Er taugt als Kategorieschlüssel.
- Die UP/AP-Familienregel trifft bei V2 auf 625 Familien mit mehreren Varianten zu. 31 Familien haben einen Hinweis zur Prüfung.
- N4D: Lesen **teilweise**. Objekte mit Katalogcode, Grafikvariante und Ebene sowie Legendentexte mit Position lese ich sicher. Die Einfügepunkte der Nova-Bauteile sind noch nicht dekodiert. Schreiben ist noch nicht begonnen.
- Alle 94 Codes der Legende und alle 43 Codes des OG-Plans finden sich im Datensatz. Erkennung über den Katalogcode funktioniert damit zu 100 % für diese Beispiele.

## 2. Aufbau der .nzp-Dateien (gelöst)

Die .nzp ist ein ZIP-Archiv. Jede Datei darin (Graphic, Data, Folder, Package, Translation, Set, UserInterface, Macro) hat dasselbe Format. Es ist eine binär gespeicherte XML-Struktur:

```
uint32   Anzahl Pool-Einträge N
N mal:   uint16 Pool-Index, danach CString (FF FE FF, Länge, UTF-16LE)
danach:  uint16-Strom = Knotenbaum
         Knoten = Name, Anzahl Attribute, (Schlüssel, Wert)*, Anzahl Kinder, Kinder
```

Alle Werte im Baum sind Verweise in den Pool. Die «Tabelle aus uint16-Werten» aus der Vorarbeit ist also der Knotenbaum. Der Pool ist nicht nach Index sortiert gespeichert. Für einen exakten Rundlauf merkt sich der Parser die Reihenfolge.

Ausschnitt aus Graphic, in XML-Schreibweise:

```
<GraphicItem ID="2D-10" Description="Schalter, Schema 0, UP" Type="Geometry"
             Usage="I" PlaceMode="W,Y" Sheet="10" Item="10-10" Geometry="((1)((…">
<GraphicItem ID="3D-10" Description="Schalter_Taster" Type="3DGeo" Usage="3D"
             GraphicFile="CH_UP_Schalter_Taster.ng3d" Sheet="10" Item="10-10">
```

Name, Katalogcode (Item), Nummernkreis (Sheet) und Geometrie stehen im selben Knoten. Mehrere 2D-Varianten eines Codes haben eigene IDs (2D-10, 2D-20, zum Beispiel «Var. 1» und «Var. 2»). Ein Symbol ist deshalb eindeutig über Datensatz + Katalogcode + Grafik-ID.

Weitere Dateien:

| Datei | Inhalt |
|---|---|
| Data | Sheets (Nummernkreise) mit Beschreibung, Standardwerten und Bauteil-Einträgen (Name, Masse, IFC-Typ, Kennbuchstabe) |
| Folder | Ordnerbaum wie in Nova, Ordner-ID = Nummernkreis |
| Package | Schablonen (Stencils) mit Reihenfolge der Symbole |
| Translation | Übersetzungen DE nach EN, FR, IT |
| Set | Datensatz-ID, Version, Vorgänger-ID |

### Symboltypen

| Typ | V2 | V1 | Bedeutung |
|---|---|---|---|
| Geometry | 2182 | 2093 | Vektorgeometrie im Text. Vollständig gelesen. |
| Engine | 141 | 185 | Parametrische Leuchten, etwa `2DNeutral;Typ=0;A=*L;B=*;Fill=1\|4\|5\|8`. Nova erzeugt die Grafik zur Laufzeit. |
| Symbol | 22 | 40 | Verweis in eine .nsb-Bibliothek im Ordner Lib (Leerdosen, Beschriftungen). Die .nsb sind OLE-Container wie N4D. |

### Geometrie-Grammatik

```
((Anzahl Gruppen)(Gruppe)…)            Gruppen, zum Beispiel X_Geometrie, X_Text, X_Schraffur
Gruppe = (Name)()(Flag)(Kurven)(Füllflächen)(Schraffuren)(Texte)
((Anzahl)(("NP0")(x;y;z))…)            Anschlusspunkte NP0, NP1, NP2, WP
((Anzahl)(("CP1")(x;y;z)(Wert))…)      Konstruktionspunkte
(xmin;ymin;xmax;ymax;1)                Umriss
```

| Element | Format |
|---|---|
| Line | (Start)(Ende) |
| Arc | (Mittelpunkt)(Start)(Ende)(Richtung). Start = Ende heisst Vollkreis. |
| EllipticArc | ((Matrix 2x2)(Mittelpunkt))(Winkelbereich)(Startwinkel) |
| FlexPolygon, FlexPolyline | (n\|x;y\|x;y…)(Segmente). Leeres Segment = Gerade, sonst Arc. |
| Spline | (Grad)(Kontrollpunkte)(Knotenvektor)(Gewichte) |
| Text | ((Matrix)(Position))(("Arial")(0)(0))("Inhalt"). Höhe aus der Matrix, meist 2.5 mm. |

Häufigkeit in V2: 15 128 Linien, 2400 Bögen, 1591 Füllflächen, 877 Texte, 74 Schraffuren, 47 Ellipsenbögen, 44 Splines, 36 Polylinien.

### Massstab

Koordinaten sind Meter im Papiermassstab 1:1. Ein Schaltersymbol hat 5 mm Durchmesser (Radius 0.0025). Texte sind 2.5 mm hoch. Nova skaliert beim Platzieren mit dem Planmassstab. Die Legende ist in einer anderen Einheit gespeichert (siehe Abschnitt 5). Das Verhältnis prüfe ich in Phase 5 mit einem echten DXF-Export aus Nova.

## 3. Kategorien

Der Nummernkreis ist das Nova-Sheet. Beispiel: Sheet 230 heisst «Brandmeldeanlagen UP», Sheet 240 «Brandmeldeanlagen AP». Ordner und Sheet haben dieselbe ID. Damit ist die automatische Zuordnung eindeutig. Namensmuster nutze ich nur, wenn ein Sheet unbekannt ist.

Vorschlag Zuordnung (Datei `backend/nova_legend/categories/defaults.py`):

| Kategorie | Nummernkreise | Ebene (aus Legende_edeco20) | Symbole V2 |
|---|---|---|---|
| Allgemein | 9999, Label_10, Label_20 | E_Starkstrom | 117 |
| Leitungen | 410, Label_30, Label_40 | E_Leitung_Licht | 8 |
| Verteiler und Stromquellen | 405, 420 | E_Starkstrom | 42 |
| Licht und Leuchten | 130, 135, 140, 145, Dialux, Relux | E_Licht | 136 |
| Fluchtwegleuchten | 165 | E_Fluchtwegleuchten | 31 |
| Schalter und Taster | 10 bis 80 | E_Licht | 202 |
| Steckdosen und Dosen | 90, 100, 390, 400 | E_Licht | 146 |
| Kraft und Elektrogeräte | 170 | E_Starkstrom | 70 |
| Schwachstrom | 330 | E_Schwachstrom | 125 |
| . Telefon | 250, 260 | E_Telefon | 116 |
| . EDV und UKV | 310, 320 | E_EDV | 248 |
| . TV und Video | 290 | E_RadioTV | 82 |
| . Gegensprechanlage | 345 (V1), 346, 347 | E_GSA | 32 |
| . Uhren | 270 | E_Uhren | 22 |
| . PANS und Krankenruf | 370, 380 | E_Schwachstrom_allgemein | 144 |
| BUS-KNX | 210, 220, 225 | E_BUS-KNX | 194 |
| Brandmeldeanlage | 230, 240 | E_Brandmeldeanlagen | 178 |
| Sicherheit | 350, 360 | E_Sicherheit | 129 |
| Melder, Fühler, Sensoren (HLKS) | 110, 120 | E_HLKS | 72 |
| Blitzschutz und Erdung | 190, 200 | E_Starkstrom | 84 |
| Diverse | 101 | E_Starkstrom | 168 |

Befunde:
- Die Kategorie «Melder, Fühler, Sensoren (HLKS)» fehlt in deinem Startvorschlag. Die Legende nutzt dafür die Ebene E_HLKS. Ich habe sie ergänzt.
- V1 nutzt für die Gegensprechanlage Sheet 345, V2 die Sheets 346 und 347.
- Der OG-Plan nutzt andere Ebenen als die Legende, etwa E_232.5_Licht und E_233_Leuchten (BKP-Nummern). Die Ebene pro Kategorie muss pro Projekt einstellbar sein.
- 72 Symbole in V2 (143 in V1) liegen in keinem Ordner. Sie erscheinen in Nova nicht in der Schablone, haben aber ein Sheet und bekommen so trotzdem eine Kategorie.

## 4. UP/AP-Familien

Regel (Datei `backend/nova_legend/library/families.py`):

1. Familienschlüssel = Name ohne Montageart (UP, AP, NUP, NAP, EB) und ohne Beschriftungsvariante («(Ohne Text)», «(Text horizontal)», «(Text stehend)», «(Text vertikal)», «(Mit Text)»).
2. Vertreter = UP mit Standardbeschriftung. Fehlt UP: NUP, dann EB, dann ohne Montageart, dann AP, dann NAP.
3. Gegenprüfung über die Code-Paare: Sheet 10 zu 20, 30 zu 40 usw., gleiche Nummer hinter dem Bindestrich. Weicht der Name ab, erscheint ein Hinweis.
4. Die Montageart kommt zuerst aus dem Symbolnamen, sonst aus dem Bauteilnamen, dem Sheet oder dem Ordner. Beispiel: «Rauchmelder, Var. 1» in Sheet 230 wird UP, in Sheet 240 AP.

Zahlen V2:

| Montagearten in der Familie | Familien |
|---|---|
| UP + AP | 484 |
| UP + AP + NUP + NAP | 33 |
| AP + EB | 32 |
| UP + AP + ohne Angabe | 29 |
| nur ohne Angabe (mehrere Varianten) | 41 |

Beispiele:
- «Schalter, Schema 0»: 10-10 UP (Vertreter), 10-230 NUP, 20-10 AP, 20-230 NAP. Die AP-Variante ist halbausgefüllt. Das bestätigt die Regel «Unterscheidung UP / AP (halbausgefüllt)».
- «Steckdose T23, 2-fach»: 8 Varianten (UP, NUP, AP, NAP je mit und ohne Text).

Fälle mit Hinweis (Auswahl, alle in `familien_…html` mit Filter «nur mit Hinweis»):
- Bus-Taster: 210-10 heisst «liegend, UP», 220-10 heisst «stehend, AP». Die Grafik-IDs sind vertauscht. Die Namensregel ordnet trotzdem richtig zu.
- Fühler: «Raumthermostat, Var. 1, UP» gegenüber «Raumthermostat-2, AP». Unterschiedliche Schreibweise der Varianten.
- 230-660 «Feuerwehrschlüsseldepot» gegenüber 240-660 «Manuelle Aktivierung BFS». Verschiedene Funktionen mit gleicher Nummer. Hier ist die Code-Paar-Regel falsch, die Namensregel richtig.
- Dosen 390/400: die Nummern passen nur in 2 von 12 Fällen. Hier gilt nur die Namensregel.

Ergebnis: Die Namensregel ist zuverlässiger als die Code-Paare. Die Code-Paare dienen nur als Prüfung.

## 5. N4D-Dateien

Container: OLE (olefile). Ströme `Elements`, `Bitmap` (Vorschau 160 x 120, BMP 24 Bit), `Header`, `Version`, `OLEClients`.

**Korrektur zur Vorarbeit:** `Elements` nutzt NICHT die Pool-Serialisierung der .nzp. Es ist ein eigenes Binärformat. Es enthält CStrings im selben Format, dazwischen Doubles, Zähler, Objektverweise (Muster `33 xx 00 00 00`), GUIDs und eingebettete 3D-Körper im ACIS-Format («Plancal nova 27.0.2 NT»).

Was ich sicher lese:

| Inhalt | Legende_edeco20 | 3_1.OG |
|---|---|---|
| Nova-Objekte mit Datensatz, Code, Grafik-ID | 102 Objekte, 94 Codes | 421 Objekte, 43 Codes |
| Ebene pro Objekt | 99 von 102 | 359 von 421 |
| Freie Texte mit Position und Drehung | 91 | 0 (Format weicht ab oder keine freien Texte) |
| Ebenen im Plan | 26 | 50 |
| Schriften | Arial, arial.ttf, Iso.shx | Arial, calibri.ttf |
| Datensätze | nur V1 (CH) | V2 (631 Verweise) und V1 (26) |

Aufbau eines Nova-Objekts: Elementname (mit angehängter 16-Byte-GUID im String), Symbolbild (`elektro\ico_…`), Benutzer, Datensatz, Sheet, Code, Bauteildaten, Ebene, dann ein zweiter Block mit Datensatz, Sheet, Code, Grafik-ID und Grafikname.

Aufbau eines Textes: CString, Kennung `33 04 00 00 00 66 3e 00`, GUID, 3x3-Matrix (Drehung, Spiegelung), Werte, x bei +98 Byte, y bei +106 Byte ab Matrixbeginn.

Raster der Legende: Symbolspalten bei x = 13.35 und 117.025, Textspalten bei x = 23.1 und 126.775. Zeilenabstand 4.55. Die Legende ist rund 220 x 220 Einheiten gross. Das spricht für Millimeter auf dem Papier. Die Seite `legende_Legende_edeco20.html` zeigt die Texte an ihrer Position.

Offen:
- Einfügepunkt, Drehung und Massstab der Nova-Bauteile (Symbole). Sie liegen nicht im selben Rahmenformat wie die Texte.
- Bedeutung der Zähler und Längenfelder. Ohne sie ist Schreiben (Phase 6, Stufe 2 und höher) nicht möglich.
- Das Feld nach der Kennung `2d 66 ff 00` hat die Werte 8271 (Legende) und 8729 (OG). Es kann eine Formatversion oder ein Objektzähler sein.
- Prüfsummen habe ich keine gefunden. Das ist gut für Phase 6, aber nicht bewiesen.

## 6. Nova 19.2 und Nova 20

Aus den Dateien lässt sich die Nova-Version nicht sicher ablesen:
- Beide Datensätze tragen `DataFormat = nova10.2_elo`. Das ist das Datensatzformat, nicht die Programmversion.
- Beide N4D-Dateien tragen ACIS 27.0.2 und dasselbe Containerformat.
- Der Name «Legende_edeco20» deutet auf Nova 20. Die Schablone verweist noch auf «Legende edeco19.n4d».

Ich brauche von dir je eine Datei, die sicher mit Nova 19.2 und sicher mit Nova 20 gespeichert ist (siehe Fragen).

## 7. Benutzerschablonen.n5q

Eigenes Binärformat (kein ZIP, kein OLE), CStrings wie oben. Es enthält Vorlagen «Standard V3.2» und «V3.4» und verweist auf Makros unter `T:\_CAD\NovaDat\NovaFirma12\Makro`, darunter `Legende edeco19.n4d`, `Plankopf edeco18.n4d`, Planrahmen A0 bis A4 und eigene Symbole unter `Makro\Symbole\` (etwa «T23 NUP.n4d», «Hohldeckenmelder mit Indikator.n4d», «IR-Empfänger.n4d»). Diese Firmensymbole sind nicht im Trimble-Datensatz. Für die Bibliothek brauche ich den Ordner `Makro\Symbole`.

## 8. Kompatibilitätsmatrix (Stand Phase 0)

| Format | Richtung | Nova 19.2 | Nova 20 | Bemerkung |
|---|---|---|---|---|
| NZP (Datensatz) | Lesen | [Geprüft] | [Geprüft] | Datensatzformat nova10.2_elo, unabhängig von der Programmversion. Rundlauf byte-gleich. |
| N4D | Lesen | [Eingeschränkt] | [Eingeschränkt] | Codes, Ebenen, Texte ja. Symbol-Einfügepunkte nein. Version der Beispieldateien unbekannt. |
| N4D | Schreiben | [Ungeprüft] | [Ungeprüft] | Phase 6 |
| DXF | Lesen | [Ungeprüft] | [Ungeprüft] | Keine Beispieldatei |
| DXF | Schreiben | [Ungeprüft] | [Ungeprüft] | Phase 5 |
| DWG | Lesen | [Ungeprüft] | [Ungeprüft] | Keine Beispieldatei, ODA-Converter fehlt in der Testumgebung |
| DWG | Schreiben | [Ungeprüft] | [Ungeprüft] | Phase 5 |

DWG/DXF-Ausgabeversion: Herstellerangaben zu Nova 19.2 und 20 liegen mir nicht geprüft vor. Ich lege sie erst nach einem Import-Test in beiden Versionen fest. Vorschlag bis dahin: DXF/DWG R2013 (AC1027). Diese Version lesen praktisch alle aktuellen CAD-Programme.

## 9. Risiken

1. **N4D schreiben.** Ohne Kenntnis der Zähler und Verweise kann Nova eine geänderte Datei ablehnen oder falsch anzeigen. Das Risiko ist ab Stufe 3 (Symbol verschieben) hoch. Rückfall: DXF/DWG-Export und Einfügen in Nova.
2. **Engine-Leuchten** (141 in V2). Ihre Grafik entsteht erst in Nova. Das Tool zeigt dafür vorerst einen Platzhalter. Rückfall: Du exportierst diese Leuchten einmal als DXF aus Nova.
3. **Lib-Symbole** (.nsb, 22 in V2). Gleiches Format wie N4D, noch nicht gelesen.
4. **Versionen.** Ohne sichere Beispieldateien beider Nova-Versionen bleibt jede Aussage zu Unterschieden eine Vermutung.
5. **Rechte an Daten.** Trimble-Datensatz und edeco-Vorlagen liegen nur lokal im Ordner `samples` und sind von Git ausgeschlossen.

## 10. Rückfall, falls N4D-Symbole nicht dekodierbar sind

Die Bibliothek braucht diesen Rückfall nicht, weil die .nzp vollständig gelesen ist. Für Pläne gilt: Exportiere den Plan in Nova als DWG oder DXF (Datei > Exportieren > DWG/DXF, Blöcke nicht auflösen). Das Tool liest die Blöcke mit ezdxf und erkennt die Symbole über Blocknamen und Geometrie. Die genauen Menüpunkte prüfe ich mit dir, sobald du einen Export gemacht hast.

## 11. Nächste Schritte

- Phase 1 (Bibliothek) ist nicht blockiert. Die Daten aus Phase 0 reichen.
- Phase 2 (Import N4D) ist für die Symbolliste nicht blockiert: Codes und Anzahl pro Plan liegen vor. Positionen fehlen noch, werden für die Legende aber nicht gebraucht.
- Phase 2 (Import DWG/DXF) wartet auf Beispieldateien.
