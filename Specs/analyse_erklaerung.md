Gerne. Auf Basis von `analyse.py` würde ich die methodische Erklärung analog zu `datengrundlage.py` aufbauen – also **Datenbasis → Berechnungsschritte → Features/Indikatoren → White-Spot-Logik → Ergebnisse**.

### Methodische Erklärung zu `analyse.py`

# Methodische Erklärung zu `analyse.py`

## Die Mathematik hinter der White-Spot-Analyse

`analyse.py` ist der zweite Teil der Datenpipeline. Während `datengrundlage.py` die räumlichen Daten vorbereitet und für jedes H3-Hexagon Merkmale wie Einwohner, Miete und POIs erzeugt, berechnet `analyse.py` daraus die eigentlichen **White-Spot-Kennzahlen**.

Das Skript beantwortet im Kern die Frage:

> **Welche H3-Zellen sind besonders attraktive potenzielle Standorte, weil dort eine hohe Nachfrage bzw. ein hohes Potenzial auf relativ wenig Wettbewerb und/oder eine Angebotslücke trifft?**

Dabei werden zwei Perspektiven kombiniert:

1. **Standortscore:** Wie attraktiv ist ein Standort aufgrund von Nachfrage, Tagesfrequenz, Affinität und Wettbewerb?
2. **Angebotslücke:** Gibt es an einem Standort weniger relevante Geschäfte, als aufgrund seiner Standortmerkmale zu erwarten wäre?

Aus beiden Perspektiven wird anschließend ein **Konsensindikator** gebildet.

---

# 1. Eingabedaten

`analyse.py` verwendet als wichtigste Eingabe die Dateien

```text
data/<stadt>_grid.csv
```

Diese stammen aus `datengrundlage.py`.

Jede Zeile entspricht einem **H3-Hexagon**. Darin befinden sich unter anderem:

* `h3` – eindeutige Kennung des Hexagons
* `lat`, `lon` – geografische Lage
* `stadt` – Stadt
* `in_stadt` – liegt die Zelle innerhalb des Untersuchungsgebiets?
* `einwohner` – Einwohnerzahl
* `miete_qm` – durchschnittliche Miete pro m²
* `miete_geschaetzt` – Kennzeichnung geschätzter Mietwerte
* `anteil_20_49` – Anteil der 20- bis 49-Jährigen
* `anteil_hh_1_3` – Anteil der Haushalte mit 1 bis 3 Personen
* POI-Anzahlen wie:

  * `poi_supermarkt`
  * `poi_bio_markt`
  * `poi_cafe`
  * `poi_restaurant`
  * `poi_bahnhof`
  * `poi_tram_ubahn`
  * `poi_bus`
  * `poi_buero`
  * `poi_hochschule`
  * usw.

Das Analysemodell arbeitet somit nicht direkt mit einzelnen Adressen, sondern mit **aggregierten Merkmalen je H3-Hexagon**.

---

# 2. Räumliche Nachbarschaften und Distanzen

Die Stadt wird als Raster aus H3-Hexagonen betrachtet.

Für jedes Hexagon werden alle anderen Hexagone gesucht, die höchstens

**1.500 m**

entfernt sind.

Die Entfernung wird zunächst über eine Luftlinienentfernung berechnet und anschließend mit einem

**Umwegfaktor von 1,3**

multipliziert.

Damit soll berücksichtigt werden, dass die tatsächliche Geh- oder Wegstrecke normalerweise länger ist als die direkte Luftlinie.

Für die eigene Zelle wird nicht 0 m verwendet, sondern:

**100 m**

als angenommene durchschnittliche Wegstrecke innerhalb des eigenen Hexagons.

---

# 3. Distanzgewichtung

Nicht jede Quelle beeinflusst einen Standort gleich stark.

Dafür verwendet das Modell eine exponentielle Distanzfunktion:

$$
f_h(d)=2^{-d/h}
$$

`h` ist dabei die sogenannte **Halbwertsdistanz**.

Bei einer Entfernung von `h` beträgt der Einfluss noch 50 %.

Beispiel für `h = 400 m`:

| Entfernung |  Gewicht |
| ---------: | -------: |
|        0 m |     1,00 |
|      100 m | ca. 0,84 |
|      200 m | ca. 0,71 |
|      400 m |     0,50 |
|      800 m |     0,25 |
|    1.200 m |    0,125 |

Damit werden nahe gelegene Zellen deutlich stärker berücksichtigt als weit entfernte.

Für das Modell werden unterschiedliche Halbwertsdistanzen verwendet:

* **Anwohner:** 400 m
* **Tagesbevölkerung:** 250 m
* **Affinität:** 400 m

Die Annahme dahinter ist, dass beispielsweise Büro- oder ÖPNV-Frequenz stärker lokal wirkt als die Wohnbevölkerung.

---

# 4. Nachfrage durch Anwohner

Die Anwohnernachfrage wird aus vier Komponenten gebildet:

1. Einwohnerzahl
2. Anteil der 20- bis 49-Jährigen
3. Anteil der Haushalte mit 1 bis 3 Personen
4. Mietniveau als Ersatzindikator für Kaufkraft

Die Formel lautet:

$$
N_i = E_i \cdot a_i \cdot h_i \cdot k_i
$$

Dabei gilt:

* $E_i$ = Einwohnerzahl
* $a_i$ = Anteil der 20- bis 49-Jährigen
* $h_i$ = Anteil der 1- bis 3-Personen-Haushalte (`anteil_hh_1_3` aus dem Zensus)
* $k_i$ = Kaufkraftfaktor

Der Haushaltsanteil berücksichtigt, dass kleine Haushalte (Singles, Paare, kleine Familien) die Zielgruppe stärker prägen als große Haushalte:

$$
h_i =
\frac{\text{1-Pers.-HH}_i + \text{2-Pers.-HH}_i + \text{3-Pers.-HH}_i}
{\text{alle Haushalte}_i}
$$

Der Kaufkraftfaktor wird aus dem Verhältnis der lokalen Miete zum städtischen Median berechnet. Die Grenzen für das Abschneiden sind keine festen Werte, sondern das **5-%- und 95-%-Quantil dieses Verhältnisses in der jeweiligen Stadt**:

$$
r_i = \frac{m_i}{median(m)}
$$

$$
k_{min} = Q_{0,05}(r), \qquad k_{max} = Q_{0,95}(r)
$$

$$
k_i =
\left(
\operatorname{clip}
\left(
r_i,
k_{min},k_{max}
\right)
\right)^\gamma
$$

Median und Quantile werden je Stadt berechnet. Damit passen sich die Grenzen an die Mietverteilung der Stadt an, und nur die extremsten 5 % am unteren und oberen Rand werden gekappt.

Der Parameter `gamma` beträgt zunächst:

**1,0**

Damit wird eine höhere Miete als Hinweis auf eine höhere Kaufkraft interpretiert.

Wichtig:

> Das Modell verwendet **keine tatsächliche Kaufkraft in Euro**, sondern die Miete als Proxy.

---

# 5. Tagesbevölkerung bzw. Tagesfrequenz

Hier ist eine wichtige Unterscheidung notwendig.

`analyse.py` verwendet **keine tatsächliche Tagesbevölkerung als Personenzahl**.

Stattdessen wird ein **Tagesindex** gebildet:

$$
t_i =
w_{Bahnhof} Bahnhof_i +
w_{Büro} Büro_i +
w_{Hochschule} Hochschule_i +
w_{Tram/U-Bahn} Tram/U-Bahn_i +
w_{Bus} Bus_i
$$

Die Gewichte sind absteigend geordnet: Büro > Hochschule > Bahnhof = Tram/U-Bahn > Bus.

| Frequenzquelle | Gewicht |
| -------------- | ------: |
| Büro           |     4,0 |
| Hochschule     |     3,0 |
| Bahnhof        |     2,0 |
| Tram/U-Bahn    |     2,0 |
| Bus            |     1,0 |

Im Robustheitstest werden die Gewichte variiert, die Rangfolge bleibt dabei in jedem Lauf erhalten.

Der resultierende Wert `t_index` ist deshalb **kein Wert wie „2.500 Personen“**.

Er ist ein **relativer Frequenzindikator**.

Beispiel:

> Hexagon A: `t_index = 20`
> Hexagon B: `t_index = 5`

Dann wird A im Modell als deutlich frequenzstärker behandelt als B.

Das bedeutet aber nicht, dass sich dort viermal so viele Menschen aufhalten.

---

# 6. Standortaffinität

Neben der Nachfrage wird untersucht, ob das Umfeld grundsätzlich zu einem bestimmten Geschäftskonzept passt.

Dafür werden sogenannte **Affinitäts-POIs** verwendet:

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

Für jede dieser Kategorien wird zunächst die gewichtete Anzahl im Umfeld berechnet.

Anschließend wird

$$
\log(1+s)
$$

verwendet, damit sehr hohe POI-Zahlen nicht überproportional dominieren.

Danach werden die Merkmale standardisiert.

---

# 7. PCA zur Ermittlung der Affinität

Die verschiedenen Affinitätsmerkmale werden mit einer **Principal Component Analysis (PCA)** zusammengeführt.

Die PCA sucht eine gemeinsame Dimension, welche die Unterschiede zwischen den Hexagonen möglichst gut erklärt.

Der erste Hauptkomponentenvektor wird als Affinitätsindex verwendet:

$$
A_i = v_1' z_i
$$

Dabei ist:

* $z_i$ = standardisierte Affinitätsmerkmale
* $v_1$ = erster PCA-Eigenvektor
* $A_i$ = Affinitätsindex

Das Modell dreht gegebenenfalls das Vorzeichen so, dass ein höherer Wert tatsächlich „mehr Affinität“ bedeutet.

---

# 8. Schutz vor einem Zentralitäts-Bias

Ein Problem wäre, wenn die PCA lediglich messen würde:

> „Wo gibt es insgesamt viele POIs?“

Dann würde die Affinität praktisch nur die **Zentralität** eines Standorts messen.

Deshalb berechnet das Skript die Korrelation zwischen Affinitätsindex und allgemeiner POI-Dichte.

Ist die Korrelation größer als:

**0,9**

wird auf eine alternative Berechnung gewechselt.

Dann wird der Anteil der Affinitäts-POIs an allen POIs verwendet:

$$
A_i =
\frac{\text{Affinitäts-POIs}_i}
{\text{alle POIs}_i}
$$

Damit soll eher gemessen werden:

> „Wie stark entspricht die Umgebung dem gewünschten Lifestyle-/Affinitätsprofil?“

und nicht nur:

> „Wie zentral ist dieser Standort?“

---

# 9. Affinitätsfaktor q

Der Affinitätsindex wird anschließend in einen Faktor `q` zwischen

**0,5 und 1,5**

umgewandelt.

Dafür wird der Prozentrang innerhalb der Stadt verwendet:

$$
q_i = q_{min} + (q_{max}-q_{min}) \cdot PR(A_i)
$$

Damit gilt ungefähr:

* niedrige Affinität → `q` nahe 0,5
* mittlere Affinität → `q` ungefähr 1,0
* sehr hohe Affinität → `q` nahe 1,5

Der Faktor `q` verstärkt oder reduziert damit die Nachfrage eines Hexagons.

---

# 9a. Milieu-Malus m

Ein Standort in einem Umfeld mit Spielhallen, Wettbüros, Rotlicht oder Drogenhilfe-Einrichtungen ist für einen Feinkostladen ungeeignet, auch wenn dort viele Menschen wohnen oder vorbeikommen. Die Miete erfasst das nicht: Rund um den Frankfurter Hauptbahnhof liegen die Mieten sogar über dem Median der Stadt.

Zuerst wird die distanzgewichtete Zahl der Milieu-POIs im Umfeld berechnet (Halbwertsdistanz **250 m**):

$$
s_c = \sum_j M_j \, f_{250}(d_{cj})
$$

Daraus entsteht der Malus:

$$
m_c = \max\left(m_{min},\ 2^{-s_c / s_{1/2}}\right)
$$

* $s_{1/2} = 2$: Bei zwei gewichteten Milieu-POIs im Umfeld halbiert sich die Anziehung des Standorts.
* $m_{min} = 0{,}2$: Ein Standort fällt nie ganz weg, sondern behält mindestens 20 % seiner Anziehung.
* Ohne Milieu-POIs im Umfeld gilt $m_c = 1$, es ändert sich also nichts.

Der Malus wirkt auf die **Anziehung des neuen Ladens am Standort** $c$, nicht auf die Nachfrage der Menschen im Umfeld:

$$
a_{neu} \cdot m_c \cdot f(d_{ic})
$$

Er geht damit in Potenzial $P$, Huff-Score $U$ und Portfolio ein. Im Robustheitstest wird $s_{1/2}$ um ±50 % variiert.

Beispiel Frankfurt: Im Bahnhofsviertel (bis 0,5 km um den Hauptbahnhof) liegt $m$ bei 0,2. Insgesamt sind nur rund 11 % der Stadtzellen betroffen ($m < 0{,}9$).

Output-Spalten: `milieu_umfeld` ($s_c$) und `m_milieu` ($m_c$).

---

# 10. Aufteilung der Nachfrage

Das Modell kombiniert zwei Nachfragequellen:

### Anwohner

$$
O_i^A =
q_i(1-\theta)
\frac{N_i}{\sum N}
$$

### Tagesfrequenz

$$
O_i^T =
q_i\theta
\frac{t_i}{\sum t}
$$

Der Parameter

$$
\theta = 0,4
$$

bedeutet grundsätzlich:

* 60 % Gewicht auf Anwohnernachfrage
* 40 % Gewicht auf Tagesfrequenz (Tagesbevölkerung)

Wichtig ist jedoch:

> Durch `q` werden die einzelnen Zellen zusätzlich nach ihrer Affinität verstärkt oder abgeschwächt.

---

# 11. Potenzial eines Standorts

Nun wird für jedes Hexagon berechnet, wie viel Nachfrage ein **neuer Laden ohne Wettbewerb** theoretisch erreichen könnte.

Dazu wird ein Huff-ähnliches Gravitationsmodell verwendet.

Die Attraktivität eines neuen Geschäfts nimmt mit der Entfernung ab.

Der Parameter

```text
a_neu = 2,0
```

beschreibt die Attraktivität des hypothetischen neuen Ladens.

Das Modell berechnet getrennt:

* `p_anw` – Potenzial aus Anwohnern
* `p_tag` – Potenzial aus Tagesfrequenz

und anschließend:

$$
P = P_A + P_T
$$

`P` ist somit das **theoretische Nachfragepotenzial** eines Standorts vor Berücksichtigung bestehender Konkurrenz.

---

# 12. Wettbewerbsdruck

Bestehende Geschäfte werden nicht einfach gezählt.

Stattdessen erhalten sie unterschiedliche Wettbewerbsgewichte.

### Direkte Wettbewerber

Zum Beispiel:

* Deli
* Feinkost/Käse
* Wein
* Bio-Markt
* Reformhaus
* Markthalle
* Pasta

### Breitere Wettbewerber

* Supermarkt
* Obst/Gemüse
* Metzger
* Bäcker
* Fisch

Einige Wettbewerber haben einen stärkeren Einfluss als andere.

Beispielsweise:

* Markthalle: `3,0`
* Bio-Markt: `2,0`
* Deli: `1,0`
* Supermarkt: `0,5`
* Bäcker: `0,2`

Der Wettbewerbsdruck einer Zelle lautet:

$$
A_j = \sum_c \alpha_c \cdot POI_{c,j}
$$

Danach wird dieser Wettbewerb wiederum über die Entfernung geglättet.

---

# 13. Huff-Score

Jetzt werden Nachfrage und Wettbewerb zusammengeführt.

Der resultierende Standortwert lautet vereinfacht:

$$
U_c =
\sum_i
O_i
\frac{a_{neu}f(d_{ic})}
{a_{neu}f(d_{ic}) + K_i + a_0}
$$

Dabei gilt:

* $O_i$ = Nachfragequelle
* $f(d)$ = Distanzgewicht
* $K_i$ = Wettbewerbsdruck
* $a_{neu}$ = Attraktivität des neuen Geschäfts
* $a_0 = 1,33$ = Grundalternative

Das Modell berechnet dies getrennt für:

* Anwohner
* Tagesfrequenz

und addiert anschließend beide Teile.

Der finale Wert

**`u`**

ist damit der zentrale **White-Spot-Score**.

Je höher `u`, desto attraktiver ist die Zelle im Modell.

---

# 14. Wettbewerbsfreiheit

Zusätzlich wird berechnet:

$$
W = \frac{U}{P}
$$

Dabei ist:

* `P` = Potenzial ohne Wettbewerb
* `U` = Potenzial nach Berücksichtigung des Wettbewerbs

`W` kann zwischen 0 und 1 liegen.

Interpretation:

* `W ≈ 1` → wenig Wettbewerb
* `W ≈ 0,5` → ein erheblicher Teil des Potenzials wird durch Wettbewerb abgeschöpft
* niedriger `W` → starker Wettbewerbsdruck

Ein Standort kann deshalb beispielsweise ein hohes Potenzial, aber gleichzeitig eine geringe Wettbewerbsfreiheit besitzen.

---

# 15. Geschäftslage-Filter

Nicht jede H3-Zelle wird als möglicher Geschäftsstandort betrachtet.

Das Skript prüft, ob die Zelle selbst und ihre sechs direkten H3-Nachbarn zusammen mindestens

**5 relevante POIs**

aufweisen.

Berücksichtigt werden dafür:

* direkte Wettbewerber
* breite Wettbewerber
* Affinitäts-POIs

Damit sollen beispielsweise sehr dünn besiedelte oder rein funktionale Flächen herausgefiltert werden.

Nur diese sogenannten **Geschäftslagen** erhalten einen Rang.

---

# 16. Ranking der Standorte

Die Geschäftslagen werden anhand des `U`-Scores sortiert.

Dabei gilt:

> **Rang 1 = höchster Score**

Zusätzlich werden mehrere Prozentränge berechnet:

* `pr_score`
* `pr_potenzial`
* `pr_wettbewerbsfreiheit`
* `pr_affinitaet`
* später `pr_luecke`

Diese Werte liegen zwischen 0 und 100.

Beispiel:

> `pr_score = 97`

bedeutet:

> Der Standort liegt beim Score ungefähr im oberen 3-%-Bereich der Geschäftslagen seiner Stadt.

Referenz sind bewusst nur die Geschäftslagen, also die Zellen, die einen Rang bekommen. Gegen alle Stadtzellen gerechnet, darunter Parks, Gleisfelder und Wohnstraßen mit einem Score nahe 0, läge schon eine durchschnittliche Geschäftslage bei einem Prozentrang von 72 bis 80 und jeder Top-Standort bei 99 bis 100.

An der Spitze bleibt der Prozentrang trotzdem eng. Deshalb gibt es zusätzlich

$$
score\_index = \frac{U_c}{\operatorname{Median}(U \text{ der Geschäftslagen})}
$$

Ein Wert von 2,5 heißt: 2,5-mal so stark wie eine typische Geschäftslage der Stadt.

---

# 17. Standortprofil: Mittag, Feierabend oder Ganztag

Das Modell berechnet außerdem:

$$
anteil_{tag} = \frac{P_T}{P}
$$

Damit wird bestimmt, welcher Anteil des Standortpotenzials aus dem Tagesfrequenz-Modell stammt.

Daraus entstehen drei Profile:

* **Mittagsstandort**
* **Feierabendstandort**
* **Ganztagsstandort**

Die Grenzen sind **stadtabhängig**, nämlich Quantile von $anteil_{tag}$ über die Zellen der jeweiligen Stadt:

| Profil | Bedingung |
| --- | --- |
| Mittagsstandort | $anteil_{tag} > Q_{0,8}$ (oberste 20 % der Stadt) |
| Feierabendstandort | $anteil_{tag} < Q_{0,2}$ (unterste 20 % der Stadt) |
| Ganztagsstandort | dazwischen |

Feste Grenzen würden davon abhängen, wie stark die Tagesfrequenz gewichtet ist ($\theta = 0,4$) und wie die Stadt strukturiert ist. Mit Quantilen bekommt jede Stadt eine nutzbare Einteilung. Das Profil ist damit **relativ zur eigenen Stadt**: „Mittagsstandort“ heißt, der Standort ist tagesfrequenzlastiger als 80 % der Stadt.

Das ist eine qualitative Klassifizierung und keine direkte Messung von Besucherzahlen.

---

# 18. Angebotslücke

Neben dem Huff-Score gibt es eine zweite, statistische Perspektive.

Hier wird gefragt:

> **Wie viele direkte Wettbewerber wären an diesem Standort aufgrund seiner Umfeldmerkmale statistisch zu erwarten?**

Dazu werden fünf erklärende Merkmale gebildet:

1. `einwohner`
2. `kaufkraft`
3. `alter`
4. `affinitaet`
5. `tag`

Diese Merkmale beziehen sich überwiegend auf das **Umfeld** des Hexagons und werden über die Distanz gewichtet.

---

# 19. Regression

Die Anzahl der tatsächlich vorhandenen direkten Wettbewerber wird als Zielvariable verwendet:

$$
y_c =
\text{Deli}+
\text{Feinkost/Käse}+
\text{Wein}+
\text{Bio-Markt}+
\text{Reformhaus}+
\text{Markthalle}+
\text{Pasta}
$$

Verwendet wird ein **räumliches Negative-Binomial-Modell**:

$$
\boxed{
y_c \sim NB(\mu_c,\phi)
}
$$

mit

$$
\boxed{
\log(\mu_c)
=
\beta_0
+\delta_{\text{Stadt}(c)}
+\beta^\top x_c
+S_c
}
$$

Dabei gilt:

* $x_c$ = die fünf erklärenden Merkmale aus Abschnitt 18
* $\delta_{\text{Stadt}(c)}$ = Stadt-Effekt
* $\phi$ = Dispersionsparameter
* $S_c$ = **räumlicher Effekt** der Zelle $c$

### Umsetzung von $S_c$ in `analyse.py`

$S_c$ ist eine glatte räumliche Fläche aus Gauß-Basisfunktionen:

$$
S_c = \sum_k b_k \, \phi_k(c), \qquad
\phi_k(c) = \exp\left(-\frac{d_{ck}^2}{2 s^2}\right)
$$

* Knoten $k$ = Mittelpunkte der H3-Elternzellen (Auflösung 7, rund 5 km²) aller Stadtzellen
* $s$ = Bandbreite, **1.500 m**
* Die Koeffizienten $b_k$ werden mit einer Ridge-Strafe $\tfrac{\lambda}{2}\sum_k b_k^2$ geschätzt (penalisiertes IRLS). Dadurch bekommen benachbarte Zellen ähnliche Werte, und ohne Daten fällt $S_c$ auf 0 zurück.
* $\lambda$ wird aus $\{1, 10, 100\}$ per räumlicher Kreuzvalidierung gewählt.

Das entspricht einem räumlichen Zufallseffekt mit niedrigem Rang. Die geschätzten Werte stehen im Output in der Spalte `s_raeumlich`.

### Warum ein räumlicher Effekt?

Ein Modell ohne $S_c$ nimmt an, dass die Abweichungen $y_c-\mu_c$ benachbarter Zellen unabhängig sind. In der Praxis gibt es aber oft **unbeobachtete räumliche Faktoren**, zum Beispiel:

* eine nicht gemessene Attraktivität eines Viertels,
* eine Einkaufsstraße,
* einen bestimmten Mikrolageeffekt,
* regionale Kundenströme,
* nicht erfasste Infrastruktur.

Dann haben benachbarte Zellen $c$ und $d$ systematisch ähnliche Abweichungen. Das ist **räumliche Autokorrelation**.

$S_c$ fängt diese räumliche Variation auf, die die beobachteten Merkmale nicht erklären. Für benachbarte Zellen mit ähnlichen unbeobachteten Standortbedingungen gilt

$$
S_c \approx S_d,
$$

und damit

$$
\mu_c = \exp(\beta^\top x_c + S_c), \qquad
\mu_d = \exp(\beta^\top x_d + S_d).
$$

Die räumliche Struktur wird so **explizit im Modell berücksichtigt**, statt sie vollständig im Fehlerterm zu lassen.

Die räumliche Kreuzvalidierung (Abschnitt 25) verhindert zwar, dass benachbarte Zellen gleichzeitig in Training und Test landen. Sie **modelliert die räumliche Abhängigkeit aber nicht**. Das leistet erst $S_c$.

### Warum Negative Binomial statt Poisson?

Das ist eine **separate Frage** von der räumlichen Korrelation.

Bei Poisson gilt:

$$
\operatorname{Var}(y_c\mid x_c)=\mu_c
$$

Bei der Negative-Binomial-Verteilung darf die Varianz größer sein:

$$
\operatorname{Var}(y_c\mid x_c)=\mu_c+\phi\mu_c^2
$$

Das ist bei Wettbewerberzahlen plausibel, weil einige Gebiete deutlich mehr Wettbewerber haben als andere.

Das Modell behandelt damit zwei unterschiedliche Probleme:

$$
\text{Negative Binomial} \rightarrow \text{Overdispersion},
\qquad
S_c \rightarrow \text{räumliche Abhängigkeit}
$$

### Warum nicht linearisieren und OLS verwenden?

Die Zielgröße ist eine **Zählvariable** ($y_c = 0, 1, 2, \ldots$). Die sinnvolle Linearisierung steckt bereits im Modell: Der Prädiktor $\log E[y_c \mid x_c]$ ist linear in den Parametern.

Ein OLS-Modell $\log(y_c)=x_c\beta+\varepsilon_c$ wäre ein anderes statistisches Modell und scheitert insbesondere an $y_c=0$, weil $\log(0)$ nicht definiert ist.

### Modellvergleich

Das räumliche Modell ist nicht automatisch besser. Deshalb werden drei Modelle gegeneinander getestet:

$$
M_1:\ y_c\sim\text{Poisson}
\qquad
M_2:\ y_c\sim NB
\qquad
M_3:\ y_c\sim NB,\ \log\mu_c=\beta^\top x_c+S_c
$$

Alle drei werden mit **derselben räumlich geblockten Kreuzvalidierung** verglichen. Entscheidend ist die Devianz außerhalb der Stichprobe $D_{\text{test}} = -2 \log L_{\text{test}}$. Anders als die Familien-Devianz ist sie zwischen Poisson und NB vergleichbar. Ein komplexeres Modell wird nur gewählt, wenn es $D_{\text{test}}$ um mindestens 1 % senkt:

* Gilt $D_{\text{test}}(M_3) < D_{\text{test}}(M_2)$, liefert das räumliche Modell bessere Vorhersagen auf räumlich unabhängigen Gebieten und wird verwendet.
* Ist der Unterschied praktisch nicht vorhanden, wird das einfachere NB-Modell vorgezogen.

| | Poisson / NB ($M_1$, $M_2$) | Räumliches NB ($M_3$) |
| --- | --- | --- |
| Zielgröße | Wettbewerberzahl $y_c$ | Wettbewerberzahl $y_c$ |
| Verteilung | Poisson bzw. NB | NB |
| Link | $\log(\mu_c)$ | $\log(\mu_c)$ |
| Stadt-Effekt | ✓ | ✓ |
| räumlicher Effekt | implizit im Fehler | **explizit $S_c$** |
| Overdispersion | nur $M_2$ | ✓ |
| räumliche Kreuzvalidierung | ✓ | ✓ |
| räumliche Abhängigkeit modelliert | ✗ | **✓** |

---

# 20. Erwartete Anzahl von Geschäften

Für jedes Hexagon entsteht dadurch:

`y_erwartet`

Das ist die statistisch erwartete Anzahl direkter Wettbewerber.

Daneben gibt es:

`y_direkt`

= tatsächlich beobachtete Anzahl.

Beispiel:

> Erwartet: 3,2 Geschäfte
> Vorhanden: 1 Geschäft

Dann besteht möglicherweise eine Angebotslücke.

---

# 21. Angebotslücke

Die lokale Angebotslücke wird als räumlich geglättete Differenz berechnet:

$$
g_c =
\sum_j
(\hat y_j-y_j)
f(d_{cj})
$$

Dabei gilt:

* $\hat y_j$ = erwartete Zahl von Geschäften
* $y_j$ = tatsächlich vorhandene Zahl
* $f(d)$ = Distanzgewicht

Im räumlichen Modell enthält die erwartete Zahl den geschätzten räumlichen Effekt:

$$
\hat y_j = \exp(\hat\beta^\top x_j + \hat S_j)
$$

Beispiel: Ein Gebiet hat aufgrund seiner Merkmale $\hat\beta^\top x_j = 1{,}0$. Ohne räumlichen Effekt wäre $\hat y_j = e^{1} \approx 2{,}72$. Mit einem positiven räumlichen Effekt $\hat S_j = 0{,}5$ ergibt sich $\hat y_j = e^{1,5} \approx 4{,}48$. Für diese Lage sind also mehr Wettbewerber zu erwarten, als die gemessenen Merkmale allein erklären.

Ein positiver Wert bedeutet:

> In der Umgebung gibt es weniger Geschäfte, als das statistische Modell aufgrund der Standortmerkmale erwarten würde.

Diese Größe heißt im Output:

**`luecke`**

---

# 22. Konsens zwischen zwei Methoden

Ein besonders wichtiger Schritt ist die Kombination der beiden Perspektiven.

Ein Standort gilt als **Konsens-White-Spot**, wenn gleichzeitig:

$$
PR(U) \geq 90
$$

und

$$
PR(g) \geq 90
$$

erfüllt sind.

Im Code:

```python
g["konsens"] = (
    (g["pr_score"] >= 90) &
    (g["pr_luecke"] >= 90)
)
```

Das bedeutet:

### Perspektive 1

Der Standort hat einen sehr hohen White-Spot-Score.

### Perspektive 2

Gleichzeitig gibt es dort statistisch weniger direkt relevante Geschäfte als erwartet.

Damit soll verhindert werden, dass ein Standort allein aufgrund einer einzigen Modelllogik als White Spot bezeichnet wird.

---

# 23. Plausibilitätsprüfung

Das Modell überprüft außerdem, ob sein theoretisches Potenzial grundsätzlich plausibel erscheint.

Dazu wird geprüft:

> Wie viele der heute vorhandenen direkten Wettbewerber liegen in den oberen 20 % der Zellen nach Potenzial?

Wenn beispielsweise 45 % der bestehenden relevanten Geschäfte in den Top-20-%-Potenzialzellen liegen, wäre das ein Hinweis darauf, dass das Potenzialmodell reale Standortmuster zumindest teilweise reproduziert.

Als Vergleichswert gilt:

**20 %**

Wenn nur etwa 20 % der Geschäfte dort liegen, wäre das Potenzialmodell kaum besser als eine zufällige Einteilung.

Wichtig:

> Diese Prüfung beweist nicht, dass das Modell korrekt ist. Sie ist lediglich ein Plausibilitätstest.

---

# 24. Robustheitsanalyse

Die Modellparameter sind teilweise Annahmen.

Beispiele:

* Halbwertsdistanz der Anwohner
* Halbwertsdistanz der Tagesfrequenz
* Gewicht der Tagesbevölkerung
* Gewicht von Bahnhöfen
* Gewicht von Hochschulen
* Wettbewerbsstärke einzelner Geschäftstypen
* Grundalternative `a_0`

Deshalb werden diese Parameter zufällig innerhalb definierter Bereiche variiert.

Standardmäßig werden:

**1.000 Läufe**

durchgeführt.

Bei jedem Lauf wird der Standort neu gerankt.

Dadurch kann beispielsweise ermittelt werden:

### `top10_anteil`

Wie häufig landet der Standort in den Top 10?

### `rang_median`

Medianischer Rang über alle Läufe.

### `rang_p10`

10-%-Quantil des Rangs.

### `rang_p90`

90-%-Quantil des Rangs.

Beispiel:

> `top10_anteil = 0,94`

bedeutet:

> Der Standort war in 94 % der Robustheitsläufe unter den Top 10.

Das ist ein Hinweis darauf, dass der Standort nicht nur aufgrund einer sehr spezifischen Parametereinstellung gut abschneidet.

---

# 25. Räumliche Kreuzvalidierung der Angebotslücke

Für die Regression wird zusätzlich eine räumliche Kreuzvalidierung durchgeführt.

Das ist wichtig, weil benachbarte H3-Zellen nicht unabhängig voneinander sind.

Daher werden ganze H3-Elternzellen gemeinsam in Trainings- oder Testgruppen gelegt.

Das Modell wird anschließend auf räumlich getrennten Bereichen getestet.

Dabei wird die erklärte Devianz außerhalb der Stichprobe berechnet:

`erklaerte_devianz_ausserhalb`

Auf dieser Kreuzvalidierung werden auch die drei Modelle $M_1$ (Poisson), $M_2$ (NB) und $M_3$ (räumliches NB) aus Abschnitt 19 verglichen. Verwendet wird das Modell mit der niedrigsten Test-Devianz; bei praktisch gleichem Ergebnis das einfachere.

Wenn dieser Wert sehr niedrig ist, gibt das Skript eine Warnung aus:

> Die verwendeten Merkmale erklären die Ladenstandorte kaum; die Angebotslücke ist mit Vorsicht zu lesen.

Das ist eine wichtige Qualitätskontrolle.

---

# 26. Portfolio mehrerer Standorte

Das Modell sucht nicht nur nach einem einzelnen White Spot.

Es kann auch ein Portfolio aus mehreren Standorten bestimmen.

Standardmäßig werden:

**5 Standorte**

ausgewählt.

Dabei wird nicht einfach Rang 1 bis Rang 5 genommen.

Stattdessen wird iterativ der Standort gewählt, der den größten zusätzlichen Nutzen für die gesamte Nachfrageabdeckung bringt.

Das ist eine **greedy / gierige Optimierung**.

Dadurch werden Standorte bevorzugt, die möglichst unterschiedliche Nachfragegebiete abdecken und sich nicht unnötig gegenseitig kannibalisieren.

---

# 27. Zentrale Output-Datei

Die wichtigste Ergebnisdatei ist:

```text
data/<stadt>_scored.csv
```

Sie enthält weiterhin eine Zeile pro H3-Hexagon, jetzt aber zusätzlich die berechneten Analysegrößen.

Besonders wichtige Spalten sind:

| Spalte                   | Bedeutung                                   |
| ------------------------ | ------------------------------------------- |
| `n_anwohner`             | modellierte Anwohnernachfrage               |
| `t_index`                | Tagesfrequenzindikator                      |
| `aff_index`              | Affinitätsindex                             |
| `q`                      | Affinitätsfaktor                            |
| `p_anw`                  | Potenzial aus Anwohnern                     |
| `p_tag`                  | Potenzial aus Tagesfrequenz                 |
| `p`                      | Gesamtpotenzial                             |
| `u_anw`                  | Huff-Score aus Anwohnern                    |
| `u_tag`                  | Huff-Score aus Tagesfrequenz                |
| `u`                      | gesamter White-Spot-Score                   |
| `w`                      | Wettbewerbsfreiheit                         |
| `geschaeftslage`         | geeignete Geschäftslage ja/nein             |
| `rang`                   | Standort-Rang                               |
| `score_index`            | Score relativ zur typischen Geschäftslage   |
| `pr_score`               | Prozentrang des Scores                      |
| `pr_potenzial`           | Prozentrang des Potenzials                  |
| `pr_wettbewerbsfreiheit` | Prozentrang der Wettbewerbsfreiheit         |
| `pr_affinitaet`          | Prozentrang der Affinität                   |
| `anteil_tag`             | Anteil des Tagespotenzials                  |
| `profil`                 | Mittag / Feierabend / Ganztag               |
| `y_direkt`               | tatsächlich vorhandene direkte Wettbewerber |
| `y_erwartet`             | statistisch erwartete Wettbewerber          |
| `luecke`                 | lokale Angebotslücke                        |
| `pr_luecke`              | Prozentrang der Angebotslücke               |
| `konsens`                | beide White-Spot-Methoden stimmen überein   |
| `top10_anteil`           | Stabilität des Top-10-Rangs                 |

---

# 28. Weitere Ausgabedateien

Zusätzlich entstehen:

### `<stadt>_pca.json`

Enthält Informationen zur Affinitäts-PCA:

* verwendete Variante
* Korrelation mit der Gesamt-POI-Dichte
* erklärte Varianz der ersten Hauptkomponente
* PCA-Ladungen der einzelnen Affinitätskategorien

### `<stadt>_plausibilitaet.json`

Enthält die Ergebnisse des Plausibilitätstests.

### `<stadt>_portfolio.csv`

Enthält die schrittweise Auswahl der besten Kombination mehrerer Standorte.

### `luecke_modell.json`

Enthält Informationen zum Regressionsmodell:

* gewähltes Modell (Poisson, NB oder räumliches NB) und Vergleich der Test-Devianzen
* Dispersion $\phi$ und geschätzte räumliche Effekte $\hat S_c$
* Koeffizienten
* Standardfehler
* erklärte Devianz
* Out-of-Sample-Devianz
* negative Koeffizienten

---

# 29. Was ist am Ende ein White Spot?

Ein White Spot ist in diesem Modell **nicht einfach eine Zelle mit wenigen Geschäften**.

Ein guter White-Spot-Kandidat entsteht aus dem Zusammenspiel mehrerer Faktoren:

**Hohe Nachfrage**
→ viele relevante Einwohner und/oder Tagesfrequenz

**+ hohe Affinität**
→ das Umfeld passt zum Geschäftskonzept

**+ ausreichendes theoretisches Potenzial**
→ genügend Nachfrage kann erreicht werden

**+ begrenzter Wettbewerbsdruck**
→ bestehende Geschäfte schöpfen das Potenzial nicht vollständig ab

**+ Angebotslücke**
→ statistisch gibt es weniger relevante Geschäfte als aufgrund des Umfelds zu erwarten wäre

**+ geeignete Geschäftslage**
→ das Gebiet weist ausreichend relevante POIs auf

**+ Robustheit**
→ der Standort bleibt auch bei veränderten Modellannahmen attraktiv

Der stärkste Kandidat ist damit nicht zwingend der Standort mit den meisten Einwohnern.

---

# 30. Gesamtlogik in einem Schaubild

```text
H3-Raster
   │
   ├── Einwohner + Alter + Miete
   │          │
   │          └── Anwohnernachfrage N
   │
   ├── Bahnhof + ÖPNV + Büro + Hochschule
   │          │
   │          └── Tagesindex t
   │
   └── Affinitäts-POIs
              │
              └── PCA / Affinitätsindex q
                       │
                       ▼
             Nachfrageverteilung O
                       │
                       ▼
             Potenzial P
                       │
          + Wettbewerbsdruck K
                       │
                       ▼
                 Huff-Score U
                       │
                       ├── Wettbewerbsfreiheit W
                       └── Standort-Rang
                                │
                                ▼
                  ┌─────────────────────┐
                  │ zweite Modelllogik  │
                  │                     │
                  │ Merkmale            │
                  │       ↓             │
                  │ räumliches NB-Modell│
                  │       ↓             │
                  │ erwartete Läden     │
                  │       ↓             │
                  │ Angebotslücke g     │
                  └─────────┬───────────┘
                            │
                            ▼
                    Konsens-White-Spot
                    Score ≥ 90
                    UND
                    Lücke ≥ 90
                            │
                            ▼
                   Robustheitstest
                            │
                            ▼
                   Portfolio-Auswahl
```

---

# 31. Wichtigste methodische Einschränkung

Die Ergebnisse sind **Modellergebnisse und keine direkt gemessenen Marktpotenziale**.

Besonders wichtig sind die Annahmen bei:

* Mietniveau → Kaufkraft
* POIs → Tagesfrequenz
* gewählten Distanzfunktionen
* Gewichten der Frequenzquellen
* Wettbewerbsgewichten
* PCA-basierter Affinität
* Regression der erwarteten Geschäftszahl (inkl. räumlichem Effekt)

Die Robustheitsanalyse prüft zwar, ob die Ergebnisse gegenüber vielen dieser Annahmen stabil bleiben. Sie macht aus den Annahmen aber keine gemessenen Größen.

Insbesondere die **Tagesbevölkerung wird weiterhin nicht direkt gemessen**. `t_index` ist ein aus POIs gewichteter Frequenzindikator. Für eine echte Tagesbevölkerung wären beispielsweise Pendler-, Mobilfunk-, Besucher- oder Frequenzdaten notwendig.

---

# 32. Kurzfassung

`datengrundlage.py` beantwortet:

> **Welche räumlichen Daten und Merkmale gibt es in jedem H3-Hexagon?**

`analyse.py` beantwortet:

> **Wie attraktiv ist jedes Hexagon als potenzieller Standort und gibt es dort möglicherweise eine Angebotslücke?**

Die zentrale Logik lautet:

$$
\boxed{
\text{Daten}
\rightarrow
\text{Nachfrage}
\rightarrow
\text{Affinität}
\rightarrow
\text{Potenzial}
\rightarrow
\text{Wettbewerb}
\rightarrow
\text{White-Spot-Score}
}
$$

parallel dazu:

$$
\boxed{
\text{Standortmerkmale}
\rightarrow
\text{Regression}
\rightarrow
\text{erwartete Geschäfte}
\rightarrow
\text{Angebotslücke}
}
$$

und schließlich:

$$
\boxed{
\text{Score}
+
\text{Angebotslücke}
+
\text{Robustheit}
\rightarrow
\text{White-Spot-Kandidaten}
}
$$

Damit hast du jetzt methodisch **beide Skripte getrennt dokumentiert**: `datengrundlage.py` beschreibt, **wie die Daten entstehen**, und `analyse.py`, **wie daraus die White Spots berechnet werden**.
