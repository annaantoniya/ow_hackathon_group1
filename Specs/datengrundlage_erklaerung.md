Ja. Ich würde die Datei **nicht Zeile für Zeile**, sondern als Datenpipeline lesen. Dann werden die drei Fragen sehr klar:

> **1. Welche Daten kommen hinein? → 2. Welche Merkmale werden daraus erzeugt? → 3. Wie sieht die fertige Analysetabelle aus?**

---

# 1. Gesamtidee der Datenabfrage

Das Skript baut für **München, Frankfurt und Berlin** eine räumliche Datengrundlage auf.

Die Grundidee ist:

**Stadtgebiet → kleine räumliche Zellen → pro Zelle Bevölkerungs-/Wohnungsdaten + Wettbewerber + Umfeld + Frequenz**

Am Ende wird also nicht primär die Stadt als Ganzes betrachtet, sondern sehr viele kleine **H3-Hexagone**.

Das ist wichtig, weil die spätere Analyse offenbar nach sogenannten **White Spots** sucht: Gebiete, in denen beispielsweise eine bestimmte Zielgruppe vorhanden ist, aber das passende Angebot fehlt oder relativ schwach vertreten ist.

---

# 2. Frage 1: Was für Daten werden genutzt?

Das Skript verwendet im Wesentlichen **zwei Datenquellen**:

| Datenquelle                | Was wird daraus genommen?                           | Zweck                                            |
| -------------------------- | --------------------------------------------------- | ------------------------------------------------ |
| **Zensus 2022 / Destatis** | Einwohner, Miete, Alter, Haushalte                  | Beschreibung der Bevölkerung und des Wohnumfelds |
| **OpenStreetMap**          | Geschäfte, Gastronomie, Kultur, Verkehr, Büros etc. | Beschreibung des Angebots und der Frequenz       |

Zusätzlich gibt es noch **Verwaltungsgrenzen**, die bestimmen, wo die untersuchten Städte liegen.

---

## 2.1 Zensusdaten

Der Zensus kommt in diesem Skript aus **100 × 100 m großen Rasterzellen**.

Es werden vier Themenbereiche heruntergeladen:

### A. Bevölkerung

Aus:

```python
ZENSUS_ARCHIVE["bevoelkerung"]
```

wird insbesondere

```text
Einwohner
```

verwendet.

Damit weiß das Modell:

> **Wie viele Menschen leben in diesem räumlichen Bereich?**

Unbewohnte Zellen werden explizit mit **0 Einwohnern** versehen.

---

### B. Miete

Hier werden zwei Größen verwendet:

```text
durchschnMieteQM
AnzahlWohnungen
```

Also:

* durchschnittliche Nettokaltmiete in €/m²
* Anzahl der Wohnungen

Die Wohnungen werden später zur Gewichtung verwendet.

Beispiel:

| 100-m-Zelle |   Miete | Wohnungen |
| ----------- | ------: | --------: |
| A           | 12 €/m² |       100 |
| B           | 20 €/m² |        10 |

Die Zelle A beeinflusst den aggregierten Mietwert also wesentlich stärker als B.

Das Ergebnis ist:

> **durchschnittliche Nettokaltmiete pro m² für das jeweilige Hexagon**

---

### C. Alter

Der Zensus enthält Altersgruppen:

```text
Unter10
10–19
20–29
30–39
40–49
50–59
60–69
70–79
80+
```

Das Skript macht daraus **nicht jede einzelne Altersgruppe**, sondern einen spezifischen Zielgruppenindikator:

```text
anteil_20_49
```

also:

> **Welcher Anteil der Bevölkerung ist zwischen 20 und 49 Jahre alt?**

Dafür wird gerechnet:

$$
\frac{20\text{-}29 + 30\text{-}39 + 40\text{-}49}
{\text{alle veröffentlichten Altersgruppen}}
$$

Das ist bereits ein wichtiges Beispiel für den Unterschied zwischen **Rohdaten** und **Merkmalen**.

Der Zensus liefert Altersklassen – das Skript erzeugt daraus den analytisch interessanten Anteil 20–49.

---

### D. Haushalte

Hier werden unter anderem erfasst:

```text
Insgesamt_Haushalte
1_Person
2_Personen
3_Personen
4_Personen
5_Personen
6_Personen und mehr
```

Daraus entstehen:

```text
haushalte
anteil_hh_1_3
```

Also:

1. **Anzahl der Haushalte**
2. **Anteil der 1-, 2- und 3-Personen-Haushalte**

Der zweite Wert wird berechnet als:

$$
\frac{\text{1-Personen-Haushalte + 2-Personen-Haushalte + 3-Personen-Haushalte}}
{\text{alle Haushalte}}
$$

---

# 3. Die zweite Datenquelle: OpenStreetMap

Jetzt kommt der Angebots-/Umweltteil.

Das Skript fragt über die **Overpass API** OpenStreetMap-Daten ab.

Es sucht dort nach bestimmten sogenannten **POIs – Points of Interest**.

Das sind beispielsweise:

* Supermärkte
* Bio-Märkte
* Bäckereien
* Cafés
* Restaurants
* Boutiquen
* Fitnessstudios
* Museen
* Bahnhöfe
* Bushaltestellen
* Büros
* Hochschulen

Dabei werden die OSM-Tags ausgewertet.

Zum Beispiel:

```python
("affinitaet", "cafe", [{"amenity": {"cafe"}}])
```

bedeutet sinngemäß:

> Wenn ein OSM-Objekt `amenity=cafe` hat, wird es als **Café** klassifiziert.

---

# 4. Besonders wichtig: Die POIs werden in fünf Gruppen eingeteilt

Das ist für das Verständnis des Projekts wahrscheinlich der wichtigste Teil.

Die 34 Kategorien werden fünf übergeordneten Gruppen zugeordnet.

## Gruppe 1: `wettbewerb_direkt`

Das sind Anbieter, die **ähnlich oder direkt konkurrierend** zum untersuchten Angebot sind.

Dazu gehören:

* Markthalle
* Bio-Markt
* Reformhaus
* Deli
* Feinkost/Käse
* Wein
* Pasta

Die Idee:

> **Wo gibt es bereits ein ähnliches Angebot?**

---

## Gruppe 2: `wettbewerb_breit`

Hier geht es um Anbieter, die einen **Teil des gleichen Bedarfs** abdecken.

Zum Beispiel:

* Supermarkt
* Obst & Gemüse
* Metzger
* Bäcker
* Fisch

Das ist also breiterer Wettbewerb.

---

## Gruppe 3: `affinitaet`

Hier geht es weniger um Konkurrenz und mehr darum:

> **Ist das Umfeld für die Zielgruppe bzw. das Konzept attraktiv?**

Dazu zählen:

* Café
* Restaurant
* Bar
* Buchhandlung
* Interior
* Boutique
* Blumen
* Fitness/Yoga
* Kultur
* Galerie/Museum
* Coworking
* Fahrradladen

Das sind sogenannte **Umfeldmerkmale**.

---

## Gruppe 4: `frequenz`

Hier wird versucht, die **potenzielle Tagesfrequenz** abzubilden.

Zum Beispiel:

* Tram/U-Bahn
* Bahnhof
* Bus
* Hochschule
* Büro

Die Überlegung ist:

> Ein Standort kann auch dann attraktiv sein, wenn dort nicht besonders viele Menschen wohnen, aber sehr viele Menschen täglich vorbeikommen.

---

## Gruppe 5: `milieu`

Für Kriminalität gibt es keine kleinräumigen, zwischen den Städten vergleichbaren offenen Daten. Diese Gruppe ist deshalb ein **Ersatzindikator für ein Umfeld, das Feinkost-Laufkundschaft abschreckt**, zum Beispiel ein Bahnhofsviertel.

| Kategorie | OSM-Tags |
| --- | --- |
| Spielhalle | `amenity=gambling`, `amenity=casino`, `leisure=adult_gaming_centre` |
| Wettbüro | `shop=bookmaker` |
| Erotik | `shop=erotic`, `amenity=stripclub`, `amenity=brothel`, `amenity=love_hotel` |
| Drogenhilfe | `amenity=social_facility` mit `social_facility:for=drug_addicted` |
| Pfandleiher | `shop=pawnbroker` |

Die Idee:

> **Gibt es im Umfeld Merkmale, die einen Feinkostladen unattraktiv machen?**

Demografische Merkmale wie der Ausländeranteil werden bewusst **nicht** verwendet. Sie wären methodisch schwach und diskriminierend.

Ist der Overpass-Cache einer Stadt schon vorhanden, lädt `datengrundlage.py` nur diese Gruppe nach.

---

# 5. Was passiert räumlich mit diesen Daten?

Das ist der Kern des Skripts.

Zunächst wird die Stadtgrenze geladen.

Dann wird ein **1.500-Meter-Puffer** um die Stadtgrenze gelegt:

```python
PUFFER_M = 1500
```

Warum?

Damit auch das Umfeld der Stadt berücksichtigt werden kann.

Danach wird das Untersuchungsgebiet in **H3-Hexagone der Auflösung 9** zerlegt.

Jedes Hexagon hat ungefähr **0,1 km²**.

Wichtig:

> Die Analyse arbeitet anschließend auf diesen Hexagonen.

---

# 6. Wie kommen die 100-m-Zensusdaten in die Hexagone?

Das ist methodisch ein sehr wichtiger Schritt.

Der Zensus liegt zunächst in:

> **100-m-Rasterzellen**

Die Analyse möchte aber:

> **H3-Hexagone**

Deshalb wird für jede Zensuszelle deren Mittelpunkt genommen und geschaut:

> In welchem H3-Hexagon liegt dieser Mittelpunkt?

Dann werden die Werte innerhalb eines Hexagons zusammengeführt.

Beispiel:

```text
100-m-Zelle
100-m-Zelle
100-m-Zelle
100-m-Zelle
       ↓
   H3-Hexagon
```

Dadurch entsteht eine einheitliche räumliche Ebene.

---

# 7. Welche Merkmale werden letztlich aus den Zensusdaten gezogen?

Damit können wir Frage 2 bereits sehr konkret beantworten.

### Bevölkerungsmerkmale

```text
einwohner
anteil_20_49
```

### Wohn-/Immobilienmerkmale

```text
miete_qm
mietwohnungen
```

### Haushaltsmerkmale

```text
haushalte
anteil_hh_1_3
```

### Qualitäts-/Schätzindikatoren

```text
miete_geschaetzt
alter_geschaetzt
```

Diese letzten beiden sind besonders wichtig, weil sie anzeigen, **ob ein Wert tatsächlich gemessen oder ersatzweise geschätzt wurde**.

---

# 8. Wie werden fehlende Daten behandelt?

Das Skript macht hier zwei unterschiedliche Dinge.

## Miete

Wenn eine bewohnte Zelle keinen Mietwert hat, sucht das Skript in einem Radius von bis zu zwei H3-Ringen nach Nachbarn.

Dann wird aus den vorhandenen Nachbarwerten ein gewichteter Mittelwert gebildet.

Das Ergebnis wird markiert:

```text
miete_geschaetzt = True
```

Damit weiß die spätere Analyse:

> Dieser Mietwert ist nicht direkt beobachtet, sondern geschätzt.

---

## Alter

Wenn die Altersdaten für eine Zelle zu unvollständig sind, wird nicht der Nachbar genommen.

Stattdessen wird der **Stadtwert** verwendet:

```text
alter_geschaetzt = True
```

Das bedeutet:

> Wenn wir für diese kleine Fläche nicht genügend belastbare Altersdaten haben, nehmen wir den entsprechenden Anteil der gesamten Stadt.

Das ist methodisch etwas anderes als bei der Miete.

---

# 9. Was passiert mit den OSM-Daten?

Die OSM-Objekte werden zunächst heruntergeladen.

Dann wird jedes Objekt anhand seiner Tags einer Kategorie zugeordnet.

Beispielsweise:

```text
OSM-Objekt
    ↓
shop=supermarket
    ↓
Supermarkt
    ↓
wettbewerb_breit
```

Es gibt dabei eine **Prioritätsreihenfolge**.

Das ist wichtig.

Ein Bio-Supermarkt soll beispielsweise nicht gleichzeitig einfach als normaler Supermarkt behandelt werden.

Darum steht:

```text
bio_markt
```

vor:

```text
supermarkt
```

---

# 10. Danach werden Dubletten entfernt

Das Skript versucht zu vermeiden, dass ein Geschäft mehrfach gezählt wird.

Dazu gilt:

```python
DUBLETTEN_RADIUS_M = 20
```

Objekte derselben Kategorie, die innerhalb von 20 Metern liegen, können als Dublette behandelt werden.

Beispielsweise könnte dasselbe Geschäft in OSM einmal als Punkt und einmal als Fläche auftauchen.

Dann soll es nur einmal gezählt werden.

---

# 11. Die POIs werden anschließend den Hexagonen zugeordnet

Auch hier ist die Logik einfach:

```text
POI
 ↓
Koordinaten
 ↓
H3-Zelle bestimmen
 ↓
Kategorie zählen
```

Aus beispielsweise 15 Cafés in einem Gebiet wird:

```text
poi_cafe = 15
```

in dem entsprechenden Hexagon.

---

# 12. Jetzt können wir Frage 2 exakt beantworten

## Welche Merkmale ziehen wir aus den Daten heraus?

Es gibt drei große Merkmalstypen:

### A. Soziodemografie

* Einwohnerzahl
* Anteil 20–49-Jährige
* Anzahl Haushalte
* Anteil 1- bis 3-Personen-Haushalte

### B. Wohn-/Kaufkraft-/Standortumfeld

* Nettokaltmiete €/m²
* Anzahl Mietwohnungen
* geschätzte vs. gemessene Miete
* geschätzte vs. gemessene Altersstruktur

### C. Angebots- und Frequenzmerkmale

Für **33 POI-Kategorien** jeweils die Anzahl:

```text
poi_markthalle
poi_bio_markt
poi_reformhaus
poi_deli
...
poi_bahnhof
poi_bus
poi_hochschule
poi_buero
```

Das sind letztlich **Zählvariablen pro Hexagon**.

---

# 13. Wie sieht das Endergebnis aus?

Das Skript erzeugt pro Stadt zwei CSV-Dateien.

## Datei 1: `<stadt>_pois.csv`

Beispielsweise:

```text
muenchen_pois.csv
```

Dort steht **eine Zeile pro POI**.

Beispielhaft:

| osm_id   |   lat |   lon | gruppe           | kategorie  | name    | brand |
| -------- | ----: | ----: | ---------------- | ---------- | ------- | ----- |
| node/123 | 48.14 | 11.57 | affinitaet       | cafe       | Café X  |       |
| way/456  | 48.15 | 11.58 | wettbewerb_breit | supermarkt | Markt Y |       |
| node/789 | 48.16 | 11.59 | frequenz         | bus        |         |       |

Diese Datei ist also die **Detailtabelle der einzelnen Geschäfte/Orte**.

---

# 14. Die eigentlich wichtige Analysetabelle

Das ist:

```text
muenchen_grid.csv
frankfurt_grid.csv
berlin_grid.csv
```

Hier gibt es:

> **eine Zeile pro H3-Hexagon**

Und genau diese Tabelle dürfte anschließend von `analyse.py` verwendet werden.

Vereinfacht sieht sie so aus:

| H3-Zelle | Einwohner | Miete | Anteil 20–49 | Haushalte | Anteil 1–3 Pers. | Bio | Supermarkt | Café | Bahnhof | Büro |
| -------- | --------: | ----: | -----------: | --------: | ---------------: | --: | ---------: | ---: | ------: | ---: |
| H3-A     |       820 |  16,2 |         0,54 |       510 |             0,86 |   1 |          3 |    8 |       0 |   12 |
| H3-B     |       240 |  13,8 |         0,42 |       160 |             0,80 |   0 |          1 |    2 |       1 |    4 |
| H3-C     |     1.150 |  19,4 |         0,61 |       720 |             0,89 |   0 |          5 |   12 |       1 |   35 |

**Das ist das eigentliche Endprodukt der Datenabfrage.**

---

# 15. Der komplette Datenfluss in einem Bild

Man kann das Skript daher so zusammenfassen:

```text
                 DATENQUELLEN
                     │
          ┌──────────┴──────────┐
          │                     │
      ZENSUS 2022          OPENSTREETMAP
          │                     │
          │                einzelne POIs
          │                     │
   100-m-Raster            Kategorien
          │                     │
          └──────────┬──────────┘
                     │
                     ▼
              RÄUMLICHE ZUORDNUNG
                     │
                H3-Auflösung 9
                     │
                     ▼
              EIN HEXAGON = 1 ZEILE
                     │
          ┌──────────┼───────────┐
          │          │           │
          ▼          ▼           ▼
       Bewohner    Wohnen      POIs
          │          │           │
      Einwohner     Miete     Wettbewerb
      Alter         Miet-     Affinität
      Haushalte     wohnungen Frequenz
          │          │           │
          └──────────┼───────────┘
                     ▼
              GRID-DATENSATZ
                     │
                     ▼
             analyse.py
                     │
                     ▼
               WHITE SPOTS
```

---

# 16. Was bedeutet „White Spot“ in dieser Datengrundlage?

Das Skript selbst **berechnet den White Spot noch nicht**.

Das ist ein wichtiger Punkt.

`datengrundlage.py` macht zunächst nur:

> **Daten sammeln → bereinigen → räumlich vereinheitlichen → Merkmale erzeugen → Analysetabelle schreiben.**

Erst danach kommt:

```text
analyse.py
```

Dort dürfte aus diesen Merkmalen ein Standort-/White-Spot-Score berechnet werden.

Beispielsweise könnte die spätere Logik vereinfacht fragen:

> **Viele potenzielle Kunden + passendes Umfeld + hohe Frequenz + wenig direkter Wettbewerb = interessanter Standort**

Das ist aber **nicht mehr in dieser Datei implementiert**. Dafür müsste man `analyse.py` anschauen.

---

# 17. Die drei Fragen in sehr kompakter Form

### 1) Was für Daten werden genutzt?

**Zwei Hauptquellen:**

* **Zensus 2022:** Bevölkerung, Alter, Haushalte, Mietniveau
* **OpenStreetMap:** Geschäfte, Gastronomie, Kultur, Verkehr, Büros etc.

Zusätzlich:

* Verwaltungsgrenzen zur räumlichen Abgrenzung
* H3 zur Vereinheitlichung der räumlichen Einheiten

---

### 2) Welche Merkmale werden aus den Daten gezogen?

Pro H3-Hexagon:

**Nachfrage / Zielgruppe**

* Einwohner
* Anteil 20–49-Jährige
* Haushalte
* Anteil 1- bis 3-Personen-Haushalte

**Standort-/Wohnumfeld**

* Miete €/m²
* Anzahl Mietwohnungen

**Wettbewerb**

* Anzahl direkter Wettbewerber
* Anzahl breiter Wettbewerber

**Affinität**

* Cafés
* Restaurants
* Kultur
* Fitness
* Boutiquen
* Coworking etc.

**Frequenz**

* ÖPNV
* Bahnhöfe
* Hochschulen
* Büros

---

### 3) Wie sieht das Endergebnis aus?

Das Ergebnis sind **zwei Datentypen pro Stadt**:

```text
data/
├── muenchen_grid.csv
├── muenchen_pois.csv
├── frankfurt_grid.csv
├── frankfurt_pois.csv
├── berlin_grid.csv
└── berlin_pois.csv
```

Die **`*_pois.csv`** enthält die einzelnen POIs.

Die **`*_grid.csv`** ist die entscheidende Analysetabelle:

> **1 Zeile = 1 H3-Hexagon**
> **Spalten = alle Merkmale dieses Hexagons**

Und genau diese Tabelle ist anschließend die Grundlage für die **White-Spot-Analyse**.

Wenn du mir als Nächstes auch die **`analyse.py`** gibst, kann ich dir genauso methodisch den zweiten Teil erklären: **wie aus diesen Merkmalen konkret der White-Spot-Score entsteht, welche Variablen wie gewichtet werden und wie am Ende ein Standort als „White Spot“ klassifiziert wird.**
