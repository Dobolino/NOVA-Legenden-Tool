# Phase 1: Bibliothek

Stand: 30.09.2026

## Umfang

- Bibliothek aus beiden Datensätzen (V2 2025, V1 2022), zusammen 4664 Symbole.
- Familien: eine Kachel pro Funktion, der UP-Vertreter steht vorne. Der Schalter «Alle Varianten anzeigen» zeigt jede Variante einzeln.
- Suche nach Name und Katalogcode, Filter nach Kategorie, Datensatz und Montageart, Kachelgrösse einstellbar.
- Detailansicht: grosses Bild mit Anschlusspunkten, alle Varianten, Angaben (Code, Nummernkreis, Ordner, Schablonen, 3D-Datei, Kennbuchstabe), Hinweise zu unklaren Familien.
- Kategorien zuordnen: Häkchen in der Detailansicht. Die Zuordnung gilt für die ganze Familie und für alle im Firmenordner. «Automatisch zuordnen» stellt die Regel wieder her.
- Kategorien verwalten: anlegen, umbenennen, unterordnen, per Ziehen oder Pfeilen umsortieren, ausblenden, löschen, auf Standard zurücksetzen. Pro Kategorie: Ebene, Spalten, Abstand, Nummernkreise.
- Regeln der Firma: Beschriftungsvarianten zusammenfassen (Standard an), Ausrichtungen zusammenfassen (Standard aus), leere Kategorien anzeigen, Legende nach Kategorien gliedern.
- Einstellungen: Datensätze (automatische Suche oder Pfad einfügen), Firmenordner, Nova-Version, Status des ODA File Converters.
- Installation: Setup-exe ohne Adminrechte, eigenes Programmfenster (Edge WebView2), Symbol auf dem Desktop.
- Update-Knopf: Das Programm prüft beim Start, ob auf GitHub eine neuere Version liegt, und zeigt oben rechts «Update verfügbar». Unter Einstellungen → Programm-Update lädt «Jetzt aktualisieren» das Setup, prüft die Prüfsumme, installiert still und startet das Programm neu. Braucht Internetzugang zu github.com.
- Automatische Suche nur in `C:\Users\Public\Documents\Trimble\Warehouse`: nur Elektro-Datensätze mit Symbolen, jede Datei-Kopie eines Datensatzes nur einmal. Doppelte Einträge sind kein Fehler mehr. Knopf «Alle entfernen».
- Parametrische Symbole (Leuchten, Verteiler, Heizungen) zeigen eine vereinfachte Vorschau aus Länge, Breite und Typ, markiert mit «vereinfacht».

## Speicherorte

| Was | Wo |
|---|---|
| Einstellungen, Bibliotheks-Cache, Protokoll | `%LOCALAPPDATA%\NOVA-Legenden` |
| Kategorien, Zuordnungen, Regeln (gemeinsam) | `<Firmenordner>\edeco ag-Legenden-firma.sqlite` |
| Programm | `%LOCALAPPDATA%\Programs\NOVA-Legenden` |

Jede Änderung an den Firmendaten speichert Benutzer und Zeit (Tabelle `log` in edeco ag-Legenden-firma.sqlite). Eine ältere Datei `firma.sqlite` wird beim Öffnen einmal umbenannt.

## So testest du Phase 1

1. Setup herunterladen: https://github.com/Dobolino/NOVA-Legenden-Tool/releases/latest → «Assets» → `NOVA-Legenden-Setup-0.1.0.exe`. Dann installieren.
2. NOVA-Legenden starten. Oben rechts muss «2 Datensätze · 4664 Symbole» stehen. Steht dort 0: Einstellungen → Pfad zur .nzp eintragen.
3. Einstellungen → Firmenordner: einen Testordner eintragen, etwa `T:\_CAD\NOVA-Legenden-Test`.
4. Bibliothek: «Steckdose T23» suchen. Erwartet: 3 Kacheln. Kachel anklicken: 8 Varianten (UP, NUP, AP, NAP, je mit und ohne Text), UP mit Stern.
5. Kategorie ändern: in der Detailansicht ein zweites Häkchen setzen. Auf einem zweiten PC mit demselben Firmenordner prüfen, ob die Zuordnung dort erscheint.
6. Kategorien: eine neue Kategorie anlegen, verschieben, wieder löschen.
7. Links «Brandmeldeanlage» wählen: nur BMA-Symbole.

Melde mir bitte: falsch gezeichnete Symbole (Code nennen), falsche Familien, falsche Kategorien und ob der Start auf den Firmen-PCs klappt.

## Korrekturen nach der Code-Prüfung

- Datensatzfilter: «Alle Datensätze» bleibt stehen. Der Standard V2 gilt nur beim ersten Laden.
- Kategorien: «Unter» auf «–» macht eine Unterkategorie wieder zur Hauptkategorie.
- Nummernkreise: Das Feld hält den Text während der Eingabe und speichert beim Verlassen. «230, 240» ergibt zwei Kreise, leere und doppelte Einträge fallen weg.
- Zähler in der Seitenleiste zählen nur den gewählten Datensatz.
- Die Suche in der Familienansicht findet Name und Katalogcode aller Varianten (z. B. den AP-Code).

## Farben, Füllung, Ellipsen

- Farben aus Nova: Teile mit eigener Farbe (meist schwarze Linien) und Teile in der Ebenenfarbe werden unterschieden. Bei den «Füllung»-Symbolen erscheint die Fläche hell (Ebenenfarbe), die Linien darüber bleiben sichtbar.
- Schalter «Füllung und Schraffur anzeigen» in der Detailansicht, pro Familie, gespeichert für die ganze Firma. Nur bei Symbolen mit Flächen oder Schraffuren sichtbar.
- Ellipsenbögen korrigiert: Nova speichert Start- und Endwinkel und die Matrix zeilenweise. Betroffen waren 43 Bögen (z. B. 101-040 ZUKO Leser Biometrisch, 130-420 Anbau Strassenleuchte).
- Nach einem Update baut das Programm den Bibliotheks-Cache selbst neu auf, auch wenn sich dessen Aufbau geändert hat.

## Weitere Nova-Datensätze

- Die automatische Suche nimmt alle Elektro-Datensätze (DataFormat «…_elo»). HLKS- und Sanitär-Datensätze im Warehouse-Ordner bleiben draussen.
- Geprüft: Niederspannung CH (983 Symbole), Niederspannung VT (1619, Verteiler-Schema), Schwachstrom CH (438), Elektro-Trassen (keine Symbole, nur Trassen-Bauteile).
- 6 Symbole in den Niederspannung-Datensätzen haben abgeschnittene Grafiken (Fehler in den Trimble-Daten). Das Tool liest den vollständigen Teil und lädt den Rest des Datensatzes normal.
- Alle Nummernkreise der neuen Datensätze haben eine Kategorie. Niederspannung VT kommt in die neue Kategorie «Schema Verteiler (Niederspannung)». Bestehende Firmendateien werden einmal ergänzt. Eigene Zuordnungen bleiben unverändert.

## Bekannte Grenzen

- Parametrische Symbole: vereinfachte Vorschau, eingebettete Nova-Symbole darin fehlen. 22 Bibliothekssymbole (.nsb, z. B. Leerdosen, Beschriftungen) zeigen weiter einen Platzhalter. Lösung über den DXF-Import (Phase 2) oder das Lesen der .nsb (Phase 6).
- Das Setup ist nicht signiert (Windows-Warnung beim ersten Start).
- SQLite im Netzwerkordner ist für seltene Änderungen ausgelegt. Viele gleichzeitige Schreibzugriffe können kurz warten (bis 10 Sekunden).
- Firmeneigene Symbole (Makro\Symbole) sind noch nicht enthalten.
- Der Update-Knopf erscheint erst ab Build 4. Wer Build 1 bis 3 installiert hat, installiert Build 4 einmal von Hand.
- Blockiert die Firmen-Firewall github.com, meldet der Knopf «Keine Verbindung zu GitHub». Dann das Setup von Hand verteilen.
