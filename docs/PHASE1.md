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

## Speicherorte

| Was | Wo |
|---|---|
| Einstellungen, Bibliotheks-Cache, Protokoll | `%LOCALAPPDATA%\NOVA-Legenden` |
| Kategorien, Zuordnungen, Regeln (gemeinsam) | `<Firmenordner>\firma.sqlite` |
| Programm | `%LOCALAPPDATA%\Programs\NOVA-Legenden` |

Jede Änderung an den Firmendaten speichert Benutzer und Zeit (Tabelle `log` in firma.sqlite).

## So testest du Phase 1

1. Setup herunterladen: https://github.com/Dobolino/NOVA-Legenden-Tool/releases/latest → «Assets» → `NOVA-Legenden-Setup-0.1.0.exe`. Dann installieren.
2. NOVA-Legenden starten. Oben rechts muss «2 Datensätze · 4664 Symbole» stehen. Steht dort 0: Einstellungen → Pfad zur .nzp eintragen.
3. Einstellungen → Firmenordner: einen Testordner eintragen, etwa `T:\_CAD\NOVA-Legenden-Test`.
4. Bibliothek: «Steckdose T23» suchen. Erwartet: 3 Kacheln. Kachel anklicken: 8 Varianten (UP, NUP, AP, NAP, je mit und ohne Text), UP mit Stern.
5. Kategorie ändern: in der Detailansicht ein zweites Häkchen setzen. Auf einem zweiten PC mit demselben Firmenordner prüfen, ob die Zuordnung dort erscheint.
6. Kategorien: eine neue Kategorie anlegen, verschieben, wieder löschen.
7. Links «Brandmeldeanlage» wählen: nur BMA-Symbole.

Melde mir bitte: falsch gezeichnete Symbole (Code nennen), falsche Familien, falsche Kategorien und ob der Start auf den Firmen-PCs klappt.

## Bekannte Grenzen

- 141 parametrische Leuchten (Engine) und 22 Bibliothekssymbole (.nsb) zeigen einen Platzhalter. Lösung in Phase 2 über den DXF-Import.
- Das Setup ist nicht signiert (Windows-Warnung beim ersten Start).
- SQLite im Netzwerkordner ist für seltene Änderungen ausgelegt. Viele gleichzeitige Schreibzugriffe können kurz warten (bis 10 Sekunden).
- Firmeneigene Symbole (Makro\Symbole) sind noch nicht enthalten.
