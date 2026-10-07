# Umsetzungsspezifikation

Diese Fassung ist so geschrieben, dass Claude oder Claude Code sie ohne Rückfragen umsetzen kann. Sie beschreibt eine Pipeline und eine Kartenanwendung, die für München, Frankfurt und Berlin White Spots für einen Premium-Food-Markt berechnet und erklärt.

## 1. Auftrag

Baue zwei Dinge: eine Datenpipeline, die je Stadt eine Tabelle mit Score und Treibern pro Hexagon erzeugt, und eine Kartenanwendung, die diese Tabellen erkundbar macht.

**Die Geschäftsfrage:** Wo in München, Frankfurt und Berlin würde ein neuer mediterraner Food Market mit Deli-Theke die meiste passende Nachfrage gewinnen, die der bestehende Handel nicht bedient?

**Fertig ist die Arbeit, wenn:**

- `python run_all.py` aus den Rohdaten ohne Fehler `data/<stadt>_scored.csv` für alle drei Städte erzeugt.
- `streamlit run app.py` Karte, Rangliste, Standortvergleich und Treiber-Erklärung für alle drei Städte zeigt.
- Alle Prüfungen aus Abschnitt 9 bestanden sind.
- Jeder Zahlenwert des Modells in `config.yaml` steht und keiner im Code.

**Bereits vorhanden:**

| Datei | Leistet | Stand |
| --- | --- | --- |
| `fetch_osm.py` | Holt alle POIs je Stadt in einer Overpass-Anfrage, speichert die Antwort im Ordner `cache/` | Logik mit Testdaten geprüft, gegen die echte API ungetestet |
| `build_grid.py` | Bringt Zensus und POIs je Stadt auf das Hexagon-Raster | Zensus-Teil mit echten Daten für alle drei Städte gelaufen, POI-Teil nur mit Testpunkten |

**Nicht Teil des Auftrags:** Umsatzprognosen in Euro, Routing über Wegenetze, Daten aus kostenpflichtigen Quellen.

## 2. Rahmen

Alles läuft in Python, ohne Datenbank und ohne Dienste, die einen Schlüssel brauchen.

**Pakete:** pandas, numpy, h3 (Version 4), pyproj, pyshp, shapely, scikit-learn, pyyaml, streamlit, pydeck. Die vorhandenen Skripte liefen mit pandas 3.0, numpy 2.4, h3 4.5 und scikit-learn 1.8.

**Ordnerstruktur:**

```text
whitespot/
  config.yaml        alle Parameter (Abschnitt 7)
  fetch_osm.py       vorhanden
  build_grid.py      vorhanden
  model.py           Schritte 3 bis 8 aus Abschnitt 5
  robustness.py      Schritt 9
  portfolio.py       Schritt 10
  run_all.py         ruft alles in Reihenfolge auf
  app.py             Kartenanwendung
  tests/             Prüfungen aus Abschnitt 9
  zensus/            Rohdaten, nicht ins Repo (rund 800 MB entpackt)
  cache/             Overpass-Antworten, ins Repo
  data/              Zwischen- und Endergebnisse, ins Repo
```

**Konventionen:**

- Spaltennamen deutsch, klein, mit Unterstrich. Die vorhandenen Namen aus `build_grid.py` bleiben unverändert.
- Distanzen in Metern, Koordinaten als Breiten- und Längengrad in WGS84.
- H3 in der Schreibweise von Version 4: `latlng_to_cell`, `cell_to_latlng`, `grid_disk`, `geo_to_cells`. Die Namen aus Version 3 funktionieren nicht.
- Jede Größe wird am Mittelpunkt ihres Hexagons verortet, auch POIs.
- Zufallszahlen mit festem Startwert 42.
- Jedes Skript lässt sich mehrfach starten und liefert dasselbe Ergebnis. Am Ende gibt es eine kurze Zusammenfassung mit Zeilenzahlen aus.
- Kommentare im Code erklären das Warum, auf Deutsch.

## 3. Städte und Untersuchungsgebiet

Das Untersuchungsgebiet je Stadt ist die amtliche Stadtgrenze plus 1.500 m Puffer. Gerechnet wird auf dem Gebiet mit Puffer, bewertet und gereiht werden nur Zellen mit `in_stadt == True`.

Der Puffer verhindert Randeffekte: Ohne ihn sähen Zellen am Stadtrand nur die halbe Nachbarschaft.

| Schlüssel | Amtlicher Schlüssel (AGS) | Rechteck: Süd, West, Nord, Ost | Hexagone mit Puffer | Hexagone in der Stadt | Einwohner in der Stadt | Median-Miete je Hexagon |
| --- | --- | --- | --- | --- | --- | --- |
| `muenchen` | 09162 | 48.048, 11.341, 48.262, 11.743 | 4.540 | 3.055 | 1.475.469 | 13,19 Euro je m² |
| `frankfurt` | 06412 | 50.002, 8.452, 50.240, 8.822 | 4.119 | 2.590 | 744.205 | 9,94 Euro je m² |
| `berlin` | 11000 | 52.325, 13.066, 52.689, 13.782 | 12.574 | 9.472 | 3.594.123 | 7,71 Euro je m² |

Alle Zahlen stammen aus dem Testlauf von `build_grid.py` am 7. Oktober 2026. Sie dienen in Abschnitt 9 als Sollwerte.

**Raster:** H3, Auflösung 9. Eine Zelle hat im Mittel 0,105 km² Fläche und rund 200 m Kantenlänge.

## 4. Daten

Die Pipeline nutzt fünf Dateien des Zensus 2022 und einen POI-Abruf aus OpenStreetMap je Stadt.

### 4.1 Zensus 2022

**Quelle:** [Statistisches Bundesamt, Zensus 2022](https://www.destatis.de/DE/Themen/Gesellschaft-Umwelt/Bevoelkerung/Zensus2022/_inhalt.html), Abschnitt Publikationen. Alle Archive liegen unter `https://www.destatis.de/static/DE/zensus/gitterdaten/<Archivname>`. Sie werden in den Ordner `zensus/` entpackt.

| Archiv | Genutzte Datei | Genutzte Spalten |
| --- | --- | --- |
| `Zensus2022_Bevoelkerungszahl.zip` | `*Bevoelkerungszahl_100m-Gitter.csv` | `Einwohner` |
| `Durchschnittliche_Nettokaltmiete_und_Anzahl_der_Wohnungen.zip` | `*Nettokaltmiete_Anzahl_der_Wohnungen_100m-Gitter.csv` | `durchschnMieteQM`, `AnzahlWohnungen`, `werterlaeuternde_Zeichen` |
| `Alter_in_10er-Jahresgruppen.zip` | `*Alter_in_10er-Jahresgruppen_100m-Gitter.csv` | `Insgesamt_Bevoelkerung`, `Unter10`, `a10bis19`, `a20bis29`, `a30bis39`, `a40bis49`, `a50bis59`, `a60bis69`, `a70bis79`, `a80undaelter` |
| `Zensus2022_Groesse_des_privaten_Haushalts_in_Gitterzellen.zip` | `*Groesse_des_privaten_Haushalts_100m-Gitter.csv` | `Insgesamt_Haushalte`, `1_Person`, `2_Personen`, `3_Personen`, `4_Personen`, `5_Personen`, `6_Personen_und_mehr` |
| `Shapefile_Zensus2022.zip` | `EPSG_25832/VG250_KRS.*` | `AGS`, `GF`, `GEN` |

**Leseregeln, alle an den echten Dateien geprüft:**

- Trennzeichen ist das Semikolon.
- Die ersten drei Spalten jeder Gitterdatei sind `GITTER_ID_100m`, `x_mp_100m`, `y_mp_100m`. Die Koordinaten sind Zellmittelpunkte in EPSG:3035.
- Die Mietdatei nutzt das Komma als Dezimalzeichen.
- Unterdrückte Werte stehen als Halbgeviertstrich in der Zelle. Sie werden zu fehlenden Werten.
- Die Dateien enthalten nur bewohnte Zellen. Unbewohnte Hexagone erhalten null Einwohner.
- Im Shapefile steht die Landfläche einer Stadt in den Zeilen mit `GF == 4`. Das Koordinatensystem ist EPSG:25832.
- Die Dateien sind groß: Die Altersdatei hat entpackt 244 MB. Sie werden in Stücken von 500.000 Zeilen gelesen und sofort auf die Stadtrechtecke zugeschnitten.

**Wie `build_grid.py` mit Lücken umgeht:**

- **Miete:** Mittelwert je Hexagon, gewichtet mit `AnzahlWohnungen`. Fehlt er, wird der gewichtete Mittelwert der Nachbarn in zwei Ringen eingesetzt und `miete_geschaetzt` auf wahr gesetzt. Das betrifft je nach Stadt 29 bis 45 Prozent der Hexagone mit Mietwert.
- **Altersanteil:** Summe der Klassen 20 bis 49 geteilt durch die Summe aller veröffentlichten Klassen. Decken die veröffentlichten Klassen weniger als die Hälfte der Einwohner ab, wird der Stadtwert eingesetzt und `alter_geschaetzt` auf wahr gesetzt.
- **Haushalte:** Gleiche Logik wie beim Alter. Der Anteil kleiner Haushalte liegt in allen drei Städten bei 75 bis 80 Prozent und trennt deshalb kaum. Er steht in der Tabelle, geht aber nicht in den Score ein.

**Ungeklärt:** Die Spalte `werterlaeuternde_Zeichen` enthält bei manchen Zeilen `KLAMMERN`. Die Bedeutung steht in der Datensatzbeschreibung im Archiv. Bis zur Klärung werden diese Zeilen wie alle anderen behandelt.

### 4.2 OpenStreetMap

**Abruf:** `python fetch_osm.py` holt die drei Städte nacheinander, mit 20 Sekunden Pause dazwischen. Die Rechtecke aus Abschnitt 3 sind im Skript hinterlegt. Ergebnis ist `data/<stadt>_pois.csv` mit den Spalten `osm_id`, `lat`, `lon`, `gruppe`, `kategorie`, `name`, `brand`, `cuisine`, `organic`.

| Gruppe | Kategorien | Rolle im Modell |
| --- | --- | --- |
| `wettbewerb_direkt` | `deli`, `feinkost_kaese`, `wein`, `bio_markt`, `reformhaus`, `markthalle`, `pasta` | Wettbewerb im Huff-Modell, Grundlage des Plausibilitätstests |
| `wettbewerb_breit` | `supermarkt`, `obst_gemuese`, `metzger`, `baecker`, `fisch` | Wettbewerb im Huff-Modell mit geringem Gewicht |
| `affinitaet` | `cafe`, `restaurant`, `bar`, `buchhandlung`, `interior`, `boutique`, `blumen`, `fitness_yoga`, `kultur`, `galerie_museum`, `coworking`, `fahrradladen` | Affinitätsfaktor |
| `frequenz` | `bahnhof`, `tram_ubahn`, `bus`, `buero`, `hochschule` | Index der Tagesbevölkerung |

Jede Kategorie gehört zu genau einem Baustein. Gastronomie ist Affinität und nie Wettbewerb.

**Regeln:**

- Eine Anfrage je Stadt. Die Antwort liegt danach in `cache/` und wird nie erneut abgerufen.
- Dubletten entfernen: POIs derselben Kategorie, die weniger als 20 m auseinanderliegen, zählen einmal. Das ist noch nicht eingebaut und gehört in `build_grid.py` vor die Zählung.
- Die Antwort für Berlin ist groß. Läuft die Anfrage in ein Zeitlimit, wird sie nach Gruppen in vier Anfragen geteilt und zusammengeführt.
- Antwortet Overpass gar nicht, dient der Länderauszug von Geofabrik als Ersatz.

### 4.3 Ergebnis der Aufbereitung

`data/<stadt>_grid.csv` enthält eine Zeile pro Hexagon mit diesen Spalten:

| Spalte | Inhalt |
| --- | --- |
| `h3` | Kennung des Hexagons |
| `lat`, `lon` | Mittelpunkt |
| `stadt` | Schlüssel der Stadt |
| `in_stadt` | Wahr, wenn der Mittelpunkt innerhalb der Stadtgrenze liegt |
| `einwohner` | Einwohner, null bei unbewohnten Zellen |
| `miete_qm` | Nettokaltmiete in Euro je m² |
| `mietwohnungen` | Zahl der Wohnungen hinter dem Mietwert |
| `miete_geschaetzt` | Wahr, wenn der Mietwert aus Nachbarzellen stammt |
| `anteil_20_49` | Anteil der 20- bis 49-Jährigen |
| `alter_geschaetzt` | Wahr, wenn der Stadtwert eingesetzt wurde |
| `haushalte` | Zahl der Haushalte |
| `anteil_hh_1_2` | Anteil der Haushalte mit einer oder zwei Personen |
| `poi_<kategorie>` | Anzahl je Kategorie, eine Spalte pro Kategorie |

## 5. Pipeline

Die Pipeline hat elf Schritte. Die ersten zwei sind vorhanden, neun sind zu bauen. `run_all.py` ruft die Schritte 2 bis 10 für alle drei Städte in dieser Reihenfolge auf.

| Nr. | Schritt | Datei | Eingabe | Ausgabe |
| --- | --- | --- | --- | --- |
| 1 | POIs abrufen | `fetch_osm.py` | Overpass | `data/<stadt>_pois.csv` |
| 2 | Raster bauen | `build_grid.py` | `zensus/`, POIs | `data/<stadt>_grid.csv` |
| 3 | Nachbarschaften berechnen | `model.py` | Raster | Paarliste im Arbeitsspeicher |
| 4 | Nachfrage und Tagesbevölkerung | `model.py` | Raster | Spalten `n_anwohner`, `t_index` |
| 5 | Affinität | `model.py` | Raster, Paarliste | Spalten `aff_index`, `q`, dazu `data/<stadt>_pca.json` |
| 6 | Potenzial und Wettbewerb | `model.py` | alles Vorige | Spalten `p_anw`, `p_tag`, `p`, `u_anw`, `u_tag`, `u`, `w` |
| 7 | Filter, Ränge, Profil | `model.py` | alles Vorige | Spalten `geschaeftslage`, `rang`, `pr_*`, `anteil_tag`, `profil` |
| 8 | Plausibilitätstest | `model.py` | Score, POIs | `data/<stadt>_plausibilitaet.json` |
| 9 | Robustheit | `robustness.py` | Raster, Paarliste | Spalten `top10_anteil`, `rang_median`, `rang_p10`, `rang_p90` |
| 10 | Portfolio | `portfolio.py` | Score-Bausteine | `data/<stadt>_portfolio.csv` |
| 11 | Anwendung | `app.py` | `data/<stadt>_scored.csv` und Begleitdateien | Karte |

Die Schritte 4 bis 9 schreiben ihre Spalten in eine gemeinsame Datei `data/<stadt>_scored.csv`.

### Schritt 3 im Detail: Nachbarschaften

Alle Distanzsummen des Modells nutzen dieselbe Paarliste. Sie wird einmal je Stadt berechnet.

1. Mittelpunkte aller Hexagone des Gebiets mit Puffer in Bogenmaß umrechnen.
2. Mit `sklearn.neighbors.BallTree` und der Metrik `haversine` alle Paare suchen, deren Luftlinie höchstens `d_max_m / umwegfaktor` beträgt.
3. Die Luftlinie mit dem Erdradius 6.371.000 m in Meter umrechnen und mit `umwegfaktor` multiplizieren.
4. Für das Paar einer Zelle mit sich selbst die Distanz `d_selbst_m` einsetzen statt null.
5. Als drei Felder speichern: Index i, Index j, Distanz d. Die Liste ist symmetrisch.

Bei 1.500 m Maximaldistanz hat jede Zelle rund 40 Nachbarn. Berlin kommt damit auf etwa 500.000 Paare. Das ist eine Schätzung aus Zellfläche und Radius, keine Messung.

Eine Summe über Nachbarn ist dann eine gewichtete Zählung über die Paarliste, zum Beispiel mit `numpy.bincount(i, weights=wert[j] * f(d))`.

## 6. Modell

Der Score U eines Standorts ist die Nachfrage, die ein neuer Laden dort gewinnen würde. Die folgenden Formeln stehen in Rechenreihenfolge. Alle Summen laufen über die Paarliste aus Schritt 3, alle Parameter kommen aus Abschnitt 7.

### 6.1 Distanzgewicht

```latex
f_h(d) = 2^{-d/h} \quad \text{für } d \le d_{\max}, \qquad f_h(d) = 0 \text{ sonst}
```

h ist die Halbwertsdistanz. Es gibt drei Werte: für Anwohner, für Tagesbevölkerung und für die Affinität.

### 6.2 Nachfrage der Anwohner

```latex
N_i = E_i \cdot a_i \cdot k_i, \qquad k_i = \left( \min\!\left( \max\!\left( \frac{m_i}{\tilde{m}},\, k_{\min} \right),\, k_{\max} \right) \right)^{\gamma}
```

- E ist `einwohner`, a ist `anteil_20_49`, m ist `miete_qm`.
- Der Median der Miete wird je Stadt gebildet, über Zellen mit `in_stadt` und ohne `miete_geschaetzt`.
- Fehlt die Miete einer Zelle ganz, ist k gleich 1.

### 6.3 Index der Tagesbevölkerung

```latex
t_i = \sum_{c \in \text{Frequenz}} w_c \cdot \text{poi}_{c,i}
```

Die Gewichte w je Kategorie stehen in Abschnitt 7. Der Index misst keine Personen, nur ein relatives Mehr oder Weniger.

### 6.4 Affinität

1. Je Affinitätskategorie c die geglättete Dichte berechnen.
2. Logarithmieren mit log(1 + s) und je Stadt standardisieren.
3. Hauptkomponentenanalyse über die zwölf standardisierten Spalten rechnen.
4. Das Vorzeichen der ersten Komponente so drehen, dass sie positiv mit dem Mittelwert der zwölf Spalten korreliert.
5. Den Index in einen Faktor q übersetzen.

```latex
s_{c,i} = \sum_j \text{poi}_{c,j}\, f_{h_{\text{Aff}}}(d_{ij}), \qquad q_i = q_{\min} + (q_{\max} - q_{\min}) \cdot \text{Prozentrang}(\text{Index}_i)
```

Der Prozentrang liegt zwischen 0 und 1 und wird über die Zellen mit `in_stadt` gebildet. Zellen im Puffer erhalten den Prozentrang, den ihr Indexwert innerhalb der Verteilung der Stadtzellen hätte.

**Kontrolle und Rückfall:** Speichere Ladungen und erklärte Varianz in `data/<stadt>_pca.json`. Korreliert die erste Komponente mit mehr als 0,9 mit der geglätteten Dichte aller POIs, misst sie Zentralität. Nutze dann als Index den Anteil der geglätteten Affinitäts-POIs an allen geglätteten POIs. Vermerke in der JSON-Datei, welche Variante gilt.

### 6.5 Quellnachfrage

Die Nachfrage wird in zwei Teilen geführt, weil beide Gruppen unterschiedliche Reichweiten haben.

```latex
O^{A}_i = q_i \cdot (1-\theta) \cdot \frac{N_i}{\sum_j N_j}, \qquad O^{T}_i = q_i \cdot \theta \cdot \frac{t_i}{\sum_j t_j}
```

Die Summen im Nenner laufen über alle Zellen des Gebiets mit Puffer.

### 6.6 Potenzial

Das Potenzial ist die Nachfrage, die der neue Laden ohne jeden Wettbewerber gewinnen würde. Es ist das Huff-Modell aus 6.7 mit Wettbewerbsdruck null.

```latex
P^{A}_c = \sum_i O^{A}_i \cdot \frac{A_{\text{neu}}\, f_{h_A}(d_{ic})}{A_{\text{neu}}\, f_{h_A}(d_{ic}) + A_0}, \qquad P_c = P^{A}_c + P^{T}_c
```

Der Tagesteil wird genauso mit dem Tagesgewicht gerechnet. Nur mit dieser Definition gilt, dass U nie größer ist als P. Die einfache Summe der distanzgewichteten Nachfrage erfüllt das nicht.

### 6.7 Wettbewerb und Score

Jede Zelle j hat eine Wettbewerbsstärke aus ihren POIs. Jede Quellzelle i sieht daraus einen Wettbewerbsdruck K.

```latex
A_j = \sum_{c \in \text{Wettbewerb}} \alpha_c \cdot \text{poi}_{c,j}, \qquad K^{A}_i = \sum_j A_j\, f_{h_A}(d_{ij}), \qquad K^{T}_i = \sum_j A_j\, f_{h_T}(d_{ij})
```

Das Huff-Modell gibt dem neuen Laden am Standort c seinen Anteil an der Nachfrage jeder Quellzelle.

```latex
U^{A}_c = \sum_i O^{A}_i \cdot \frac{A_{\text{neu}}\, f_{h_A}(d_{ic})}{A_{\text{neu}}\, f_{h_A}(d_{ic}) + K^{A}_i + A_0}
```

Der Tagesteil wird genauso mit dem Tagesgewicht gerechnet. Score und Zerlegung sind dann:

```latex
U_c = U^{A}_c + U^{T}_c, \qquad W_c = \frac{U_c}{P_c} \in (0, 1]
```

- A0 ist die Außenoption: alle, die online, woanders oder gar nicht kaufen. Sie darf nie null sein.
- W ist der Anteil des Potenzials, den der Wettbewerb übrig lässt. Hat eine Zelle kein Potenzial, ist W nicht definiert und bleibt leer.

### 6.8 Geschäftslage

Eine Zelle ist eine Geschäftslage, wenn in ihr und ihren sechs direkten Nachbarn zusammen mindestens `n_min_geschaeftslage` POIs der Gruppen Wettbewerb und Affinität liegen. Die Nachbarn liefert `h3.grid_disk(zelle, 1)`.

### 6.9 Ränge, Treiber und Profil

| Spalte | Berechnung |
| --- | --- |
| `rang` | Rang nach U, absteigend, je Stadt, nur Zellen mit `in_stadt` und `geschaeftslage` |
| `pr_score`, `pr_potenzial`, `pr_wettbewerbsfreiheit`, `pr_affinitaet` | Prozentränge von U, P, W und q je Stadt über alle Zellen mit `in_stadt`, Werte von 0 bis 100 |
| `anteil_tag` | Tagesteil des Potenzials geteilt durch das gesamte Potenzial |
| `profil` | `Mittagsstandort`, wenn `anteil_tag` über 1,5 mal theta liegt. `Feierabendstandort`, wenn er unter 0,5 mal theta liegt. Sonst `Ganztagsstandort`. |

Die Schwellen 1,5 und 0,5 sind Setzungen und stehen in der Konfiguration.

### 6.10 Plausibilitätstest

Bestimme je Stadt die 20 Prozent der Stadtzellen mit dem höchsten Potenzial P. Zähle, welcher Anteil der POIs der Gruppe `wettbewerb_direkt` in diesen Zellen liegt. Schreibe Anteil, Zahl der POIs und Zahl der Zellen in `data/<stadt>_plausibilitaet.json`.

Ein Anteil nahe 20 Prozent bedeutet, dass das Potenzial nichts vorhersagt. Der Test ist nicht zirkulär, weil Wettbewerber weder in N noch in t noch in q eingehen.

### 6.11 Städtevergleich

Der Standardlauf bewertet jede Stadt für sich. Ein zweiter Lauf nutzt für den Kaufkraftfaktor den gemeinsamen Miet-Median aller drei Städte und für die Affinität eine gemeinsame Standardisierung. Er schreibt die Spalten `u_gemeinsam` und `rang_gemeinsam`.

Die Mieten unterscheiden sich stark: 13,19, 9,94 und 7,71 Euro je m². Im gemeinsamen Lauf liegt München deshalb fast überall vorn. Die Anwendung zeigt diese Ansicht nur auf ausdrückliche Auswahl und mit Hinweis.

### 6.12 Robustheit

1. Ziehe je Lauf alle Parameter gleichverteilt aus den Spannen in Abschnitt 7. Gewichte und Attraktivitäten werden einzeln mit einem Faktor aus ihrer Spanne multipliziert.
2. Rechne die Schritte 4, 6 und 7 neu. Die Paarliste und der Affinitätsfaktor q bleiben fest.
3. Speichere je Lauf den Rang jeder Geschäftslage.
4. Wiederhole das `n_laeufe`-mal.

Ausgabe je Zelle: `top10_anteil` als Anteil der Läufe mit Rang 1 bis 10, dazu `rang_median`, `rang_p10` und `rang_p90`.

Der Umwegfaktor wird nicht gezogen. Er skaliert alle Distanzen gleich und wirkt deshalb wie eine Änderung der Halbwertsdistanzen, die bereits variieren.

### 6.13 Portfolio

Gesucht ist die Menge S aus k Standorten mit der höchsten gemeinsam gewonnenen Nachfrage.

```latex
F(S) = \sum_i O^{A}_i \cdot \frac{X^{A}_i(S)}{X^{A}_i(S) + K^{A}_i + A_0} \;+\; \sum_i O^{T}_i \cdot \frac{X^{T}_i(S)}{X^{T}_i(S) + K^{T}_i + A_0}, \qquad X^{A}_i(S) = \sum_{c \in S} A_{\text{neu}}\, f_{h_A}(d_{ic})
```

**Verfahren:** Beginne mit der leeren Menge. Füge in jedem Schritt den Kandidaten hinzu, der F am stärksten erhöht. Kandidaten sind die 300 Geschäftslagen mit dem höchsten U je Stadt.

**Ausgabe** in `data/<stadt>_portfolio.csv`: Reihenfolge, Zelle, Zugewinn je Schritt, F nach jedem Schritt. Dazu eine Vergleichszahl: F des Portfolios geteilt durch F der k besten Einzelstandorte.

F ist monoton und submodular. Das einfache Verfahren erreicht deshalb mindestens 63 Prozent des Optimums (Nemhauser, Wolsey und Fisher, 1978).

## 7. Parameter

Alle Werte stehen in `config.yaml` unter den Schlüsseln der ersten Spalte. Jeder Wert ist eine Setzung ohne Messung. Die Spanne gilt für den Robustheitstest. Ein Strich bedeutet: Der Wert bleibt dort fest.

### Raster und Distanz

| Schlüssel | Startwert | Spanne | Bedeutung |
| --- | --- | --- | --- |
| `h3_aufloesung` | 9 | – | Größe der Hexagone |
| `puffer_m` | 1500 | – | Rand um die Stadtgrenze |
| `d_max_m` | 1500 | – | Größte berücksichtigte Wegstrecke |
| `umwegfaktor` | 1,3 | – | Wegstrecke je Meter Luftlinie |
| `d_selbst_m` | 100 | – | Distanz einer Zelle zu sich selbst |
| `h_anwohner_m` | 400 | 300 bis 500 | Halbwertsdistanz der Anwohner |
| `h_tag_m` | 250 | 150 bis 350 | Halbwertsdistanz der Tagesbevölkerung |
| `h_affinitaet_m` | 400 | – | Halbwertsdistanz für das Umfeld |

### Nachfrage

| Schlüssel | Startwert | Spanne | Bedeutung |
| --- | --- | --- | --- |
| `gamma` | 1,0 | 0,5 bis 1,5 | Wie stark Kaufkraft zählt |
| `k_min`, `k_max` | 0,5 und 2,0 | – | Grenzen des Kaufkraftfaktors |
| `theta` | 0,3 | 0,1 bis 0,5 | Anteil der Tagesbevölkerung an der Nachfrage |
| `w_buero` | 1 | Faktor 0,5 bis 1,5 | Gewicht je Büro |
| `w_hochschule` | 5 | Faktor 0,5 bis 1,5 | Gewicht je Hochschule |
| `w_bahnhof` | 5 | Faktor 0,5 bis 1,5 | Gewicht je Bahnhof |
| `w_tram_ubahn` | 2 | Faktor 0,5 bis 1,5 | Gewicht je Tram- oder U-Bahn-Halt |
| `w_bus` | 0,5 | Faktor 0,5 bis 1,5 | Gewicht je Bushaltestelle |
| `q_min`, `q_max` | 0,5 und 1,5 | – | Grenzen des Affinitätsfaktors |

### Wettbewerb

| Schlüssel | Startwert | Spanne | Bedeutung |
| --- | --- | --- | --- |
| `a_neu` | 2,0 | – | Attraktivität des neuen Ladens, Bezugsgröße |
| `a_0` | 1,33 | Faktor 0,5 bis 1,5 | Außenoption. Der Startwert bedeutet 60 Prozent Gewinn direkt vor der Tür ohne Wettbewerb. |
| `alpha_markthalle` | 3,0 | Faktor 0,5 bis 1,5 | Großes, direkt vergleichbares Angebot |
| `alpha_bio_markt` | 2,0 | Faktor 0,5 bis 1,5 | Ähnliche Kundschaft, volles Sortiment |
| `alpha_deli`, `alpha_feinkost_kaese`, `alpha_wein`, `alpha_pasta`, `alpha_reformhaus` | je 1,0 | Faktor 0,5 bis 1,5 | Direkter, aber kleiner Wettbewerber |
| `alpha_supermarkt` | 0,5 | Faktor 0,5 bis 1,5 | Bedient nur einen Teil des Bedarfs |
| `alpha_baecker`, `alpha_metzger`, `alpha_obst_gemuese`, `alpha_fisch` | je 0,2 | Faktor 0,5 bis 1,5 | Geringe Überschneidung |

### Auswertung

| Schlüssel | Startwert | Bedeutung |
| --- | --- | --- |
| `n_min_geschaeftslage` | 5 | Mindestzahl POIs in Zelle und Nachbarn |
| `profil_schwelle_hoch`, `profil_schwelle_tief` | 1,5 und 0,5 | Vielfache von theta für die Profilgrenzen |
| `plausibilitaet_anteil` | 0,2 | Anteil der besten Zellen im Plausibilitätstest |
| `top_n` | 10 | Länge der Rangliste |
| `n_laeufe` | 1000 | Läufe im Robustheitstest, bei Zeitnot 200 |
| `k_portfolio` | 5 | Standorte je Portfolio |
| `n_kandidaten_portfolio` | 300 | Kandidaten je Stadt |
| `zufall_startwert` | 42 | Startwert für Zufallszahlen |

## 8. Plattform

Die Anwendung liest nur fertige Dateien aus `data/` und rechnet selbst nichts Schweres. Sie muss drei Dinge leisten, die die Aufgabe ausdrücklich verlangt: White Spots zeigen, Standorte vergleichen, Treiber erklären.

**Technik:** Streamlit mit pydeck und der Ebene `H3HexagonLayer`. Die Hintergrundkarte muss ohne Zugangsschlüssel laufen. Meines Wissens geht das mit dem Kartenanbieter `carto` in pydeck, das ist beim Bau zu prüfen.

### Seitenleiste

| Bedienelement | Auswahl |
| --- | --- |
| Stadt | München, Frankfurt, Berlin |
| Ebene | Score, Potenzial, Wettbewerbsfreiheit, Affinität, Tagesanteil, Stabilität, Einwohner, Miete |
| Nur Geschäftslagen | An oder aus, Standard an |
| Portfolio zeigen | An oder aus, Standard aus |
| Maßstab | Innerhalb der Stadt oder gemeinsam über alle drei, Standard innerhalb |

### Ansichten

1. **Karte.** Hexagone, eingefärbt nach dem Prozentrang der gewählten Ebene. Die zehn besten Standorte sind hervorgehoben und nummeriert. Ein Tooltip zeigt Rang, Score-Prozentrang, die drei Treiber und das Profil.
2. **Rangliste.** Tabelle der zehn besten Standorte mit Rang, Lagebezeichnung, Score-Prozentrang, den drei Treibern, Profil und Stabilität. Ein Klick auf eine Zeile zentriert die Karte.
3. **Vergleich.** Auswahl von zwei oder drei Standorten aus der Rangliste. Nebeneinander stehen Balken der drei Treiber und die Rohwerte: Einwohner im Umkreis von 400 m, Miete, Zahl der Wettbewerber im Umkreis von 400 m, Profil.
4. **Treiber-Erklärung.** Für den gewählten Standort ein bis zwei Sätze aus Regeln, dazu ein Balkendiagramm der Zerlegung von U in Potenzial der Anwohner, Potenzial der Tagesbevölkerung und Wettbewerbsfreiheit.
5. **Annahmen.** Eigene Seite mit der Parametertabelle aus `config.yaml`, den Grenzen aus Abschnitt 11, den Ergebnissen des Plausibilitätstests je Stadt und den Quellenangaben.

### Regeln für die Texte

- **Lagebezeichnung:** Name des nächstgelegenen POI der Kategorien `bahnhof` oder `tram_ubahn` aus der POI-Datei, in der Form „nahe Name“. Fehlt ein Name im Umkreis von 800 m, stehen die Koordinaten.
- **Treiber-Sätze:** Ein Treiber mit Prozentrang ab 80 gilt als Stärke, einer unter 40 als Bremse. Beispiel: „Stark durch hohes Potenzial der Anwohner und wenig Wettbewerb. Gebremst durch ein Umfeld mit geringer Affinität.“
- **Stabilität:** `top10_anteil` ab 70 Prozent heißt „sicherer Kandidat“, unter 30 Prozent „wackeliger Kandidat“, dazwischen „mittel“.
- **Keine Scheingenauigkeit:** Die Oberfläche zeigt Ränge und Prozentränge, keine Rohwerte von U und keine Euro-Beträge.

### Fußzeile

Jede Seite nennt die Quellen: OpenStreetMap-Mitwirkende und Statistisches Bundesamt, Zensus 2022. Die genauen Lizenztexte stehen auf den Seiten der Anbieter und sind vor dem Pitch zu prüfen.

## 9. Prüfungen

Jeder Schritt gilt erst als fertig, wenn seine Prüfung besteht. Die Prüfungen liegen als Tests im Ordner `tests/` oder laufen am Ende des jeweiligen Skripts.

| Schritt | Prüfung | Sollwert |
| --- | --- | --- |
| 1 POIs | Keine Kategorie hat null Treffer | Je Stadt mindestens ein POI je Kategorie, sonst Warnung |
| 1 POIs | Stichprobe von Hand | Zehn dem Team bekannte Läden sind enthalten und richtig eingeordnet |
| 2 Raster | Zahl der Hexagone in der Stadt | München 3.055, Frankfurt 2.590, Berlin 9.472 |
| 2 Raster | Einwohner in der Stadt | München 1.475.469, Frankfurt 744.205, Berlin 3.594.123, Abweichung unter 1 Prozent |
| 3 Paarliste | Symmetrie und Grenze | Jedes Paar kommt in beiden Richtungen vor, keine Distanz über `d_max_m` |
| 4 Nachfrage | Normierung | Mit q gleich 1 summieren sich beide Teile der Quellnachfrage zusammen zu 1 |
| 5 Affinität | Wertebereich | q liegt in jeder Zelle zwischen `q_min` und `q_max` |
| 6 Score | Schranken | U ist nie größer als P, W liegt zwischen 0 und 1 |
| 6 Score | Grenzfall | Ohne Wettbewerber ist W in jeder Zelle mit Potenzial genau 1 |
| 6 Score | Handrechnung | Ein Beispiel mit drei Zellen und einem Wettbewerber liefert den von Hand gerechneten Wert |
| 7 Ränge | Eindeutigkeit | Jeder Rang von 1 bis zur Zahl der Geschäftslagen kommt je Stadt genau einmal vor |
| 9 Robustheit | Wiederholbarkeit | Zwei Läufe mit demselben Startwert liefern identische Spalten |
| 10 Portfolio | Abnehmender Zugewinn | Der Zugewinn je Schritt steigt nie. Liegt F des Portfolios unter F der k besten Einzelstandorte, gibt das Skript eine Warnung aus |
| 11 Anwendung | Bedienung | Wechsel von Stadt und Ebene dauert unter zwei Sekunden, alle fünf Ansichten zeigen Inhalt |

**Sichtprüfung der Karten, von einem Menschen:**

- Die Einwohnerkarte zeigt Flüsse, Parks und Gewerbegebiete als leere Flächen.
- Die Mietkarte zeigt die teuren Viertel dort, wo das Team sie erwartet.
- Die Affinitätskarte ist nicht bloß eine Karte der Innenstadt.
- Unter den zehn besten Standorten ist keiner, der mitten in einem Park oder auf einem Bahngelände liegt.

## 10. Reihenfolge und Rückfallpläne

Baue in dieser Reihenfolge. Nach jeder Stufe gibt es eine lauffähige, vorzeigbare Version. Eine spätere Stufe beginnt erst, wenn die Prüfungen der vorigen bestehen.

| Stufe | Inhalt | Ergebnis | Rückfall, wenn es hakt |
| --- | --- | --- | --- |
| 1 | Schritte 1 und 2 für alle drei Städte | Raster mit POIs | Overpass antwortet nicht: Länderauszug von Geofabrik nutzen. Berlin läuft ins Zeitlimit: Anfrage nach Gruppen teilen. |
| 2 | Durchstich: Schritt 3 und eine vereinfachte Fassung von Schritt 6, dazu Karte mit einer Ebene | Karte mit echtem, grobem Score | Keiner. Diese Stufe muss stehen. |
| 3 | Schritte 4 bis 7 vollständig | Score, Treiber, Profil, Rangliste | Affinität nicht deutbar: Mittelwert der standardisierten Kategorien statt Hauptkomponente. |
| 4 | Anwendung mit Rangliste, Vergleich und Treiber-Erklärung | Alle Pflichtfunktionen der Aufgabe | Vergleich als einfache Tabelle statt Balken. |
| 5 | Schritt 8 und Seite Annahmen | Plausibilitätszahl je Stadt | Zahl nur im Pitch nennen. |
| 6 | Schritt 9 | Stabilität je Standort | 200 statt 1.000 Läufe, oder nur für die 50 besten Standorte ausweisen. |
| 7 | Schritt 10 | Portfolio je Stadt | Entfällt. Der Spike ist dann das Tag-Nacht-Profil aus Stufe 3. |
| 8 | Gemeinsamer Maßstab aus 6.11 | Städtevergleich | Entfällt. |

**Vereinfachte Fassung für den Durchstich:** Einwohner je Zelle distanzgewichtet summieren und durch eins plus die distanzgewichtete Zahl der direkten Wettbewerber teilen. Das ersetzt für Stufe 2 die Schritte 4 bis 6.

**Zeitmarken für den Hackathon-Tag:** Stufe 2 bis 12:30, Stufe 3 bis 14:00, Stufe 4 und alle weiteren Funktionen bis 15:30, danach nur noch Fehlerbehebung.

**Bei Zeitnot wird in dieser Reihenfolge gestrichen:** Stufe 8, Stufe 6, Stufe 7, Stufe 5. Die Stufen 1 bis 4 bleiben, weil die Aufgabe sie verlangt.

## 11. Grenzen des Modells

Diese Punkte stehen wörtlich auf der Seite Annahmen der Anwendung. Die Jury bewertet Transparenz über Limitationen ausdrücklich.

- Das Modell kennt keine Umsätze und ist nicht kalibriert. Der Score ordnet Standorte, er sagt keinen Umsatz voraus.
- Alle Parameter sind Setzungen. Der Robustheitstest zeigt, wie stark die Rangfolge von ihnen abhängt.
- Die Miete ist ein Ersatz für Kaufkraft. Sie stammt aus Bestandsmieten vom Mai 2022. Je nach Stadt sind 29 bis 45 Prozent der Werte aus Nachbarzellen geschätzt.
- Mieten sind zwischen Städten nicht vergleichbar. Die Standardansicht bewertet deshalb jede Stadt für sich.
- Die Tagesbevölkerung ist ein Index aus Büros, Hochschulen und Haltestellen, keine Personenzahl.
- OpenStreetMap ist nicht überall gleich vollständig. Gut kartierte Viertel können zu günstig erscheinen.
- Alle Wettbewerber einer Kategorie zählen gleich. Ladengröße und Qualität sind unbekannt.
- Distanzen sind Luftlinie mal 1,3. Flüsse, Bahntrassen und Autobahnen als Hindernisse sind nicht berücksichtigt.
- Das Modell kennt keine freien Ladenflächen und keine Gewerbemieten.
- Kleine Zahlen im Zensus sind aus Gründen der Geheimhaltung leicht verändert oder unterdrückt.
