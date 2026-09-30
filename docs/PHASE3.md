# Phase 3: Änderungen zwischen zwei Importen

Stand: 30.09.2026

## Ablauf

1. Einen Plan importieren (siehe [Phase 2](PHASE2.md)).
2. Dieselbe Geschosszeile später mit **Neu importieren** und der geänderten Datei noch einmal einlesen.
3. Reiter **Änderungen**. Pro Geschoss stehen «Von» und «Nach». Voreingestellt ist der vorige Import gegen den aktuellen.
4. Die Tabelle zeigt Apparate: **Neu**, **Weg**, **Anzahl geändert**, mit Vorher, Nachher und Differenz.
5. Darunter, getrennt: Leitungen, Masse und Beschriftungen, wenn sich deren Anzahl geändert hat.
6. In der Pläne-Tabelle steht unter dem Geschoss die Kurzform, zum Beispiel «zum vorigen Import: 1 neu, 1 weg».

Ein Geschoss mit nur einem Import hat noch keinen Vergleich.

## Was verglichen wird

Jeder Import bleibt als Version in `projekt.nlproj`. Auf der Festplatte liegt weiterhin nur eine Plandatei pro Geschoss.

Die Zuordnung ist der gespeicherte Schlüssel des Elements (Katalogcode, Bezeichnung oder Name), derselbe Schlüssel wie bei der Gesamtliste. Ein Schalter, der schon im vorigen Import war, bleibt dieselbe Zeile, auch wenn die Anzahl sich ändert. Anzahl 0 gilt als «weg».

| Anzeige | Bedeutung |
|---|---|
| Neu | im gewählten «Nach»-Import vorhanden, im «Von»-Import nicht |
| Weg | im «Von»-Import vorhanden, im «Nach»-Import Anzahl 0 oder fehlend |
| Anzahl geändert | in beiden Importen vorhanden, Anzahl verschieden |

«Von» und «Nach» lassen sich tauschen. Dann drehen sich Neu und Weg um.

## So testest du Phase 3

1. Update installieren (Build mit diesem Stand).
2. Projekt öffnen, einen Plan importieren. Reiter Änderungen: «Erst ein Import».
3. Dieselbe Datei noch einmal mit **Neu importieren** laden. Erwartet: «keine Änderung zum vorigen Import».
4. Eine geänderte Datei desselben Geschosses importieren (Apparat dazu, Apparat gelöscht, Anzahl geändert).
5. Reiter Änderungen: die drei Fälle mit der richtigen Differenz. Leitungen nur im unteren Block.

## Bekannte Grenzen

- Verglichen werden Anzahlen pro Apparat, nicht die Position im Plan.
- Zwei Importe, die das Programm nicht als denselben Apparat erkennt, erscheinen als «weg» und «neu» statt als eine geänderte Zeile.
- Der Legenden-Editor folgt in Phase 4.
