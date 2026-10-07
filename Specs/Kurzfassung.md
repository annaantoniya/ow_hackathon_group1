# White-Spot-Konzept: München, Frankfurt, Berlin (Kurzfassung)

Stand: 7. Oktober 2026

Kurzfassung zum schnellen Lesen und Korrigieren. Wir bewerten mit einem einheitlichen Modell, wo in München, Frankfurt und Berlin ein neuer Premium-Food-Markt die meiste unbediente Nachfrage fände. Die ausführliche Fassung steht in `umsetzungsspezifikation.md`.

## 1. Konzept und Zielgruppe

**Konzept:** Ein mediterraner Food Market mit Deli-Theke in urbaner Lauflage. Hochwertige Lebensmittel zum Mitnehmen, dazu Sofortverzehr mittags und am frühen Abend.

**Zielgruppe:** Zwei Gruppen, die zu unterschiedlichen Zeiten kaufen.

- **Anwohner:** 20 bis 49 Jahre, kleine Haushalte, überdurchschnittliche Kaufkraft. Sie kaufen abends und am Wochenende zu Fuß ein.
- **Tagesbevölkerung:** Berufstätige und Studierende. Sie kaufen mittags und nach Feierabend auf dem Weg zur Bahn.

## 2. Die drei Städte

München, Frankfurt und Berlin sind Bürostandorte des Veranstalters. Die Jury kennt die Viertel und kann unsere Ergebnisse sofort einordnen. Zugleich fordert jede Stadt das Modell an einer anderen Stelle.

| Stadt | Einwohner im Raster | Hexagone in der Stadt | Median-Miete je Hexagon | Was die Stadt prüft |
|---|---|---|---|---|
| München | 1.475.469 | 3.055 | 13,19 Euro je m² | Hohe Kaufkraft fast überall: Findet das Modell trotzdem Unterschiede? |
| Frankfurt | 744.205 | 2.590 | 9,94 Euro je m² | Viele Pendler: Trägt die Tagesbevölkerung einen Standort? |
| Berlin | 3.594.123 | 9.472 | 7,71 Euro je m² | Viele Zentren, niedrige Bestandsmieten: Hält das Kaufkraft-Signal? |

Die Zahlen stammen aus einem Testlauf mit den Zensus-Gitterdaten 2022 und der amtlichen Stadtgrenze. Dass Frankfurt viele Pendler hat, ist allgemein bekannt, aber hier nicht mit Zahlen belegt.

**Wichtige Folge der Mietunterschiede:** Die Mieten liegen so weit auseinander, dass ein gemeinsamer Maßstab München überall vorn sähe. Wir bewerten deshalb zuerst jede Stadt für sich und vergleichen die Städte erst in einer zweiten Ansicht.

## 3. Daten

Zwei offene Quellen tragen das Modell. Alles landet in einer Tabelle pro Stadt mit einer Zeile pro Hexagon von rund 0,1 km².

| Quelle | Liefert | Stand |
|---|---|---|
| Zensus 2022, 100-m-Gitter | Einwohner, Nettokaltmiete, Altersgruppen, Haushaltsgrößen | Geladen und für alle drei Städte aufbereitet |
| OpenStreetMap | Wettbewerber, Umfeld der Zielgruppe, Haltestellen, Büros, Hochschulen | Abrufskript fertig, Abruf steht noch aus |

**Bekannte Schwächen:** Der Zensus zeigt Mai 2022 und enthält kein Einkommen, die Miete ist nur ein Ersatzsignal. Je nach Stadt sind 29 bis 45 Prozent der Mietwerte aus Nachbarzellen geschätzt. OpenStreetMap kennt weder Ladengrößen noch Umsätze.

## 4. Methodik

Wir betrachten jeden Standort aus zwei Sichten. Standorte, die in beiden vorn liegen, sind die stärksten Kandidaten.

### Sicht A: Der Score

Er beantwortet: Wie viel passende Nachfrage würde ein neuer Laden an diesem Ort gewinnen?

1. **Nachfrage der Anwohner.** Einwohner je Zelle, gewichtet mit dem Anteil der 20- bis 49-Jährigen und einem Kaufkraftfaktor aus der Miete.
2. **Tagesbevölkerung.** Ein Index aus Büros, Hochschulen und Haltestellen, weil es dafür keine Personenzahlen gibt.
3. **Affinität.** Ein Faktor für das Umfeld: Wo viele Cafés, Restaurants, Buchläden und Kulturorte sind, lebt und bewegt sich die Zielgruppe.
4. **Potenzial.** Die Nachfrage, die ein neuer Laden dort ohne jeden Wettbewerb gewinnen würde. Wer 400 m entfernt wohnt, zählt halb, wer 800 m entfernt wohnt, ein Viertel.
5. **Wettbewerb.** Das Huff-Modell verteilt die Nachfrage auf alle Läden in Reichweite. Übrig bleibt der Anteil für den neuen Laden.
6. **Score.** Potenzial mal Anteil, den der Wettbewerb übrig lässt. Diese Zerlegung liefert zugleich die Erklärung, warum ein Standort gut ist.

### Sicht B: Die Angebotslücke

Sie beantwortet: Wo gibt es weniger Läden, als das Umfeld erwarten lässt?

- Eine Regression lernt aus den Standorten heutiger Feinkostläden und Bio-Märkte, welche Merkmale eines Umfelds Läden anziehen.
- Der White Spot ist die Lücke: erwartete minus vorhandene Läden.
- Die Gewichte kommen damit aus den Daten statt aus unseren Setzungen, und die Koeffizienten erklären zugleich die Treiber.
- Die Schwäche: Das Modell lernt, wo Läden stehen, und nicht, wo sie sich lohnen.

### Drei Absicherungen

- Nur echte Geschäftslagen zählen. Parks und reine Wohnstraßen fallen heraus.
- Ein Plausibilitätstest prüft, ob das Potenzial vorhersagt, wo heute schon Feinkostläden stehen.
- Ein Robustheitstest variiert alle Annahmen 1.000-mal und zeigt, welche Standorte stabil vorn liegen.

## 5. Spike

| Kandidat | Idee | Aufwand |
|---|---|---|
| **Angebotslücke als Residuum** (Favorit) | Sicht B aus Abschnitt 4: datenbasierte Gewichte, White Spot als Lücke | Mittel |
| **Tag-Nacht-Profil** (sichere Wahl) | Jeder Standort wird als Feierabend-, Mittags- oder Ganztagsstandort eingeordnet. Daraus folgt, ob eher ein Markt oder eher ein Deli passt. | Gering |
| **Portfolio** (ehrgeizige Wahl) | Die beste Kombination aus fünf Standorten je Stadt, die sich nicht gegenseitig Kunden wegnehmen | Hoch |

**Rückfallplan:** Steht der gewählte Spike morgen um 15:30 nicht, bleibt das Tag-Nacht-Profil. Es fällt aus dem Grundmodell fast ohne Zusatzaufwand ab.

## 6. Annahmen zum Korrigieren

Jede Zeile ist eine Setzung ohne Messung. Wer widerspricht, trägt einen anderen Wert ein.

| Annahme | Startwert | Warum |
|---|---|---|
| Kernaltersgruppe | 20 bis 49 Jahre | Der Zensus liefert nur Zehnjahresgruppen |
| Kaufkraft | Miete der Zelle geteilt durch den Median der eigenen Stadt | Mieten zwischen Städten sind nicht vergleichbar |
| Reichweite Anwohner | Halbwert bei 400 m | Rund fünf Gehminuten |
| Reichweite Tagesbevölkerung | Halbwert bei 250 m | Mittagspausen sind kurz |
| Wegstrecke | Luftlinie mal 1,3 | Faustregel statt Wegenetz |
| Anteil der Tagesbevölkerung an der Nachfrage | 30 Prozent | Hängt am Konzept: mehr Deli heißt höherer Anteil |
| Gewicht der Wettbewerber | Markthalle 3, Bio-Supermarkt 2, Feinkost 1, Supermarkt 0,5, Bäcker und Metzger 0,2 | Je ähnlicher das Sortiment, desto höher |
| Gewinn ohne Wettbewerb direkt vor der Tür | 60 Prozent | Der Rest kauft online, woanders oder gar nicht |
| Geschäftslage | Mindestens fünf Läden oder Lokale in der Zelle und ihren Nachbarn | Ein Laden braucht ein Umfeld mit Laufkundschaft |
| Gastronomie | Zählt als Affinität, nicht als Wettbewerb | Restaurants ziehen die Zielgruppe an |

## 7. Offene Entscheidungen

- [ ] Konzept und Zielgruppe bestätigt oder geändert
- [ ] Spike gewählt
- [ ] Städtevergleich: nur innerhalb jeder Stadt oder zusätzlich über alle drei
- [ ] Rollen im Team verteilt

## 8. Was das Modell nicht kann

- Es kennt keine Umsätze. Der Score ordnet Standorte, er sagt keinen Umsatz voraus.
- Es kennt die Tagesbevölkerung nur als groben Index.
- Es rechnet mit Luftlinie und sieht keine Flüsse oder Bahntrassen als Hindernisse.
- Es kennt keine freien Ladenflächen und keine Gewerbemieten.
