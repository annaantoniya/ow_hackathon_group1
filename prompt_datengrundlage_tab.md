# Prompt: Tab „Datengrundlage“

Baue in `app.py` (Streamlit, Branch `dev-max`) eine neue Ansicht **„Datengrundlage“** und nimm sie in `ANSICHTEN` auf, zwischen „Vergleich“ und „Analyse“. Der Tab soll zeigen:
1. wie wir mit den Daten gearbeitet haben,
2. was davon in die Analyse eingeflossen ist und was bewusst nicht,
3. was die wichtigsten Erkenntnisse aus unserer Datengrundlage sind.

Stil wie im Analyse-Tab: Consulting-Deck. Jede Überschrift ist ein Satz mit Aussage, darunter höchstens drei Belege mit Zahl und Einheit. Nutze die vorhandenen Helfer `kopf`, `exhibit_titel`, `bumper`, `quelle`, `panel` und die Klassen `.kasten`, `.zahlen`, `.pipe`.

## Quellen

- **Inhalt:** `Specs/datengrundlage_erklaerung.md`, ergänzt um `Specs/Kurzfassung.md` (Abschnitte 2 und 3) und `data/README.md` (Lizenzen).
- **Maßgeblich bei Widersprüchen:** `datengrundlage.py` und `analyse.py`. Konstanten wie `PUFFER_M`, `DUBLETTEN_RADIUS_M`, die Kategorienlisten `WETTBEWERB_DIREKT`, `WETTBEWERB_BREIT`, `AFFINITAET`, `FREQUENZ`, `MILIEU` und `PARAMETER` zur Laufzeit importieren, nicht abtippen. Die Zahl der POI-Kategorien wird in Doku und App unterschiedlich angegeben (33 oder 34). Sie wird aus den Listen gezählt.
- **Daten:**
  - `data/<stadt>_grid.csv`: Eingabe der Analyse, eine Zeile je Hexagon.
  - `data/<stadt>_pois.csv`: eine Zeile je POI mit `gruppe` und `kategorie`.
  - `data/<stadt>_scored.csv`, `<stadt>_plausibilitaet.json`, `<stadt>_pca.json`, `luecke_modell.json`: daraus die Kennzahlen, wie gut die Daten tragen.
- Alle Zahlen live aus den Dateien rechnen. Die Kontrollwerte unten dienen nur zum Prüfen, nicht zum Abtippen.

## Aufbau

### 0. Kopf und Executive Summary
`kopf("Datengrundlage", "<Action Title>")`, zum Beispiel: „Zwei offene Quellen, 15.000 Hexagone in drei Städten, 53.000 POIs: genug Auflösung, um Straßenzüge zu unterscheiden“ (Werte live).

Zahlenkacheln über alle drei Städte:
- Einwohner im Raster
- Hexagone in der Stadt
- POIs gesamt
- Anteil gemessener statt geschätzter Mietwerte

### 1. So haben wir mit den Daten gearbeitet (Pipeline)
Horizontale `.pipe` mit sechs Schritten. Jeder Schritt bekommt einen Satz und eine Kennzahl:

| Schritt | Inhalt | Kennzahl |
|---|---|---|
| Quellen | Zensus 2022 (100-m-Gitter), OpenStreetMap über die Overpass API, amtliche Stadtgrenzen | 2 Quellen, Stand Mai 2022 bzw. Abrufdatum |
| Gebiet | Stadtgrenze plus Puffer von `PUFFER_M` = 1.500 m, damit Randlagen ihr Umland sehen | Hexagone gesamt gegenüber Hexagonen in der Stadt |
| Raster | H3-Auflösung 9, ungefähr 0,1 km² je Zelle | Anzahl je Stadt |
| Zuordnung | Zensuszellen über ihren Mittelpunkt ins Hexagon, POIs über die Koordinate. Miete nach Wohnungen gewichtet | – |
| Bereinigung | Kategorien nach Priorität (Bio-Markt vor Supermarkt), Dubletten derselben Kategorie innerhalb von 20 m entfernt, Lücken gefüllt (Miete aus bis zu 2 Ringen Nachbarn, Alter aus dem Stadtwert) und markiert | Anteil `miete_geschaetzt`, `alter_geschaetzt` |
| Ergebnis | `<stadt>_grid.csv`: 1 Zeile = 1 Hexagon, Spalten = Merkmale | Anzahl Spalten |

Darunter das Datenfluss-Schaubild aus Abschnitt 15 von `datengrundlage_erklaerung.md`, als Grafik nachgebaut und nicht als ASCII.

### 2. Was in die Analyse eingeflossen ist
**Action Title:** „Jedes Merkmal hat genau eine Aufgabe im Modell.“

Tabelle Merkmal → Rolle im Modell (Rolle laut `analyse.py`):

| Gruppe | Merkmale | Geht ein in |
|---|---|---|
| Soziodemografie | `einwohner`, `anteil_20_49`, `anteil_hh_1_3` | Anwohnernachfrage $N$, Regressionsmerkmale Einwohner und Alter |
| Kaufkraft (Ersatz) | `miete_qm` relativ zum Median der Stadt | Kaufkraftfaktor $k$ in $N$, Regressionsmerkmal Kaufkraft |
| Direkter Wettbewerb | 7 Kategorien (`WETTBEWERB_DIREKT`) | Wettbewerbsdruck $K$ und Zielgröße $y$ der Regression |
| Breiter Wettbewerb | 5 Kategorien (`WETTBEWERB_BREIT`) | Wettbewerbsdruck $K$ mit kleinerem Gewicht $\alpha$ |
| Affinität | 12 Kategorien (`AFFINITAET`) | PCA → Affinitätsfaktor $q$, Regressionsmerkmal Affinität |
| Frequenz | 5 Kategorien (`FREQUENZ`) | Tagesindex $t$, Regressionsmerkmal Tag |
| Milieu | 5 Kategorien (`MILIEU`) | Milieu-Malus $m$ |
| Qualitätsflags | `miete_geschaetzt`, `alter_geschaetzt` | Median der Miete nur aus gemessenen Werten |

Darunter ein Kasten **„Bewusst nicht verwendet“**:
- Kein Einkommen, weil es im Zensus fehlt. Stattdessen dient die Miete als Ersatz.
- Kein Ausländeranteil o. Ä.: methodisch schwach und diskriminierend. Das Milieu wird über konkrete Orte erfasst (Spielhallen, Wettbüros …).
- Gastronomie zählt nicht als Wettbewerb, sondern als Affinität.
- Keine Personenzahlen für die Tagesbevölkerung, weil keine offene Quelle existiert. Stattdessen ein Index.

Optional als Grafik: gestapelter Balken POIs je Gruppe und Stadt aus `<stadt>_pois.csv` (Spalte `gruppe`).

### 3. Die wichtigsten Erkenntnisse aus der Datengrundlage
Jede Erkenntnis ist ein eigener Kasten mit Action Title, Zahl und „Was heißt das für uns?“. Werte live rechnen. Die Kontrollwerte stammen aus dem Lauf vom 8. Oktober 2026:

1. **„Die Mieten sind zwischen den Städten nicht vergleichbar, deshalb bewerten wir jede Stadt für sich.“**
   - Median-Miete München 13,15 €/m², Frankfurt 9,90 €/m², Berlin 7,73 €/m².
   - Darstellung: Balken plus Box- oder Violinplot von `miete_qm` je Stadt.
2. **„Ein großer Teil jeder Stadt ist unbewohnt, die Analyse konzentriert sich auf echte Geschäftslagen.“**
   - Unbewohnte Stadtzellen: München 25 %, Frankfurt 49 %, Berlin 33 %.
   - Geschäftslagen: München 52 %, Frankfurt 34 %, Berlin 37 % der Stadtzellen.
3. **„Direkte Wettbewerber sind selten: Jede Zelle zählt.“**
   - Direkte Wettbewerber: München 335, Frankfurt 145, Berlin 594.
   - Bei 2.600 bis 9.500 Stadtzellen haben die meisten Zellen 0 Wettbewerber. Deshalb wird ein Zählmodell (NB) verwendet und das Umfeld geglättet.
4. **„Das Umfeld ist eindimensional: Eine Achse beschreibt drei Viertel der Unterschiede.“**
   - Erklärte Varianz von PC1 der Affinitäts-POIs: München 80 %, Frankfurt 75 %, Berlin 81 % (`<stadt>_pca.json`).
   - Die Ladungen sind nahezu gleich. Deshalb gibt es den Test gegen reine Zentralität: Korrelation mit der Gesamtdichte unter 0,9, sonst Rückfall.
5. **„Das Milieu betrifft nur wenige, aber zentrale Lagen.“**
   - Stadtzellen mit `m_milieu < 0,9`: München 22 %, Frankfurt 11 %, Berlin 16 %.
   - Beispiel Frankfurter Bahnhofsviertel: $m$ = 0,2 trotz überdurchschnittlicher Miete.
6. **„Die Daten tragen: Das Potenzial trifft reale Ladenstandorte.“**
   - Anteil der Feinkostläden in den oberen 20 % nach Potenzial: München 68 %, Frankfurt 82 %, Berlin 84 % (Zufall: 20 %).
   - Das Umfeld erklärt außerhalb der Stichprobe rund 51 % der Ladenverteilung (`luecke_modell.json`).
7. **„Die Profile unterscheiden sich je Stadt.“**
   - Verteilung Mittag, Ganztag, Feierabend der Geschäftslagen je Stadt als gestapelter Balken.

### 4. Datenqualität und Grenzen
Ampel-Tabelle je Quelle mit Stärke, Schwäche und Umgang:
- **Zensus:** amtlich und flächendeckend, aber Stand Mai 2022 und ohne Einkommen. Geschätzte Werte sind markiert. Anteil `miete_geschaetzt` der bewohnten Stadtzellen je Stadt zeigen (Kontrollwert 8 bis 12 %).
  - Achtung: In `Kurzfassung.md` und in den `GRENZEN` in `app.py` steht „29 bis 45 %“. Diese Zahl bezieht sich auf eine andere Grundgesamtheit. Nur live gerechnete Werte mit klarer Definition zeigen und den Text in `GRENZEN` angleichen.
- **OpenStreetMap:** aktuell und detailliert, aber nicht überall gleich vollständig, ohne Ladengröße und ohne Umsatz. Dubletten werden entfernt, und es gilt eine Priorität der Kategorien.
- **Distanzen:** Luftlinie mal 1,3. Flüsse und Bahntrassen gelten nicht als Hindernis.

Optional: Karte der gewählten Stadt, auf der Hexagone mit geschätzter Miete schraffiert oder hervorgehoben sind.

### 5. Quellen und Lizenzen
Aus `data/README.md`: Zensus 2022 © Destatis, dl-de/by-2-0. OpenStreetMap © OSM-Mitwirkende, ODbL 1.0. Am Ende als `quelle(...)`.

## Akzeptanzkriterien
- Neuer Eintrag „Datengrundlage“ in `ANSICHTEN`. Die bestehenden Ansichten funktionieren unverändert.
- Jede Überschrift ist ein Satz mit Aussage. Jede Erkenntnis in Abschnitt 3 hat eine live berechnete Zahl und einen Satz „Was heißt das für uns?“.
- Keine Kennzahl ist hart codiert. Nach `python datengrundlage.py` und `python analyse.py` stimmen alle Werte ohne Codeänderung.
- Kategorienlisten und Parameter werden aus `analyse.py` und `datengrundlage.py` importiert.
- Der Stadtvergleich ist auf einen Blick lesbar, alle drei Städte nebeneinander, ohne Stadtwahl.
- Hell- und Dunkelmodus funktionieren (Farben über `T`).
