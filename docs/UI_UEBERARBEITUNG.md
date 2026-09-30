# UI-Überarbeitung

Stand: 30.09.2026

## Begriffe

| Begriff | Bedeutung |
|---|---|
| Programmversion | Version und Build von NOVA-Legenden (Einstellungen → Info) |
| Nova-Version | Version von Trimble Nova, zum Beispiel 19.2 oder 20. Eine Angabe zum Projekt, keine Zusage zur Kompatibilität. |
| Symbol-Datensatz | Nova-Symbolbibliothek, zum Beispiel V1 (2022) oder V2 (2025) |
| Importversion | Ein gespeicherter Import eines Geschossplans |

## Was sich geändert hat

- Projektansicht: Titel aus Projektnummer und Bezeichnung, beschriftete Felder, «Projekt wechseln» für das zweite Dropdown, Aktionen «Projekt duplizieren», «Projekt als ZIP exportieren», «Vorlage ausblenden», «Nach ‚Gelöscht‘ verschieben».
- Pläne: einklappbar («Pläne · 3 Geschosse»), Zustand pro Projekt für die Sitzung gemerkt. Ohne Pläne immer offen. Import zeigt «Läuft», «Fertig» oder «Fehler» im Bereich. Pro Geschoss «Neue Planversion importieren», ↑ ↓ und «Weitere Aktionen» (Geschoss umbenennen, Datei entfernen).
- Gesamtliste: volle Fensterbreite, Kopfzeile und Spalten Symbol und Bezeichnung bleiben beim Scrollen sichtbar.
- Ebenen und Farben: standardmässig nur Kategorien mit Apparaten in den aktuellen Importen, «Alle Kategorien anzeigen». Zustand als Text: «Automatisch → E_232.5_Licht», «Manuell → E_Licht», «Ebene wählen», «Im Projekt nicht verwendet». Fehlende Ebene und Ebene ohne Farbangabe sind getrennt beschriftet.
- Änderungen: «Vergleich von Importversionen», Geschoss, Von, Tauschen, Nach. Status «Neu», «Entfallen», «Anzahl geändert», Anzahl als «3 → 5 · +2».
- Bibliothek: «Symbolgrösse», beschriftete Filter, «Keine Symbolvorschau verfügbar» mit Grund im Tooltip und in der Detailansicht.
- Kategorien: Übersicht links, Bearbeitung rechts (unter 1100 px darunter). Speichern und Verwerfen, Anzeige «Nicht gespeichert» und «Gespeichert». Beim Wechsel mit offenen Änderungen fragt das Programm nach.
- Einstellungen: «Datei wählen …» für Datensätze, «Ordner wählen …» für Projekt- und Firmenordner (nur im Programmfenster). Abbrechen lässt den Wert unverändert. Info zeigt «Programmversion» und die Begriffe.

## Technik

- Dateidialoge: `backend/nova_legend/dialogs.py`, Route `POST /api/dialog/{dataset|folder}`. Das Programmfenster meldet sich beim Start an (`dialogs.attach`). Im Browser-Modus sind die Knöpfe gesperrt.
- Status der Kategorien: `category_usage` und `category_state` in `backend/nova_legend/projects/colors.py`. Die Zuordnungslogik (`pick_category_layer`) ist unverändert.
