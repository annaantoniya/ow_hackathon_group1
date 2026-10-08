# Prompt: Vergleichs-Tab für White Spots

**Ziel:** Baue in unsere Oberfläche einen Tab „Vergleich“. Dort wählt man 2 bis 5 White Spots aus, auch aus verschiedenen Städten, und sieht sie nebeneinander. Die Leitfrage lautet: *Warum ist Standort A besser oder schlechter als B, und wie sicher ist das?*

**Datengrundlage:** Zuerst `python analyse.py` ausführen, schneller geht es mit `--laeufe 200`. Danach liegen in `data/` diese Dateien:

- `<stadt>_scored.csv`: eine Zeile pro H3-Hexagon. Hier stehen alle Merkmale unten.
- `<stadt>_portfolio.csv`: die 5 gierig gewählten Standorte je Stadt.
- `<stadt>_plausibilitaet.json` und `luecke_modell.json`: Kennzahlen auf Ebene der Stadt und des Modells.

Kandidaten sind nur Zeilen mit `in_stadt == True` und `geschaeftslage == True`, also solche, bei denen `rang` nicht leer ist.

## Wichtigste Regel: Was über Städte hinweg vergleichbar ist

`analyse.py` normiert die Nachfrage für jede Stadt einzeln, denn die Quellnachfrage summiert sich je Stadt zu 1. Deshalb sind absolute Werte zwischen Städten **nicht** vergleichbar. Ein Standort in Berlin hat automatisch kleinere Rohwerte als einer in Frankfurt.

- ❌ **Nicht nebeneinanderstellen, wenn die Städte verschieden sind:** `u`, `p`, `p_anw`, `p_tag`, `n_anwohner`, `t_index`, `aff_index`, `rang`. Berlin hat ungefähr 9.500 Zellen, Frankfurt ungefähr 2.600, Rang 10 bedeutet also nicht dasselbe. Auch `x_*` gehört dazu, weil diese Werte je Stadt standardisiert sind.
- ✅ **Vergleichbar:** Prozentränge `pr_*` (0 bis 100, jeweils gegen die Geschäftslagen der eigenen Stadt), `konsens`, `profil`, `w` (Anteil 0 bis 1), `m_milieu` (0,2 bis 1), `beitrag_*` (gemeinsame Koeffizienten über alle Städte), `luecke`, `y_erwartet` und `y_direkt` (in der Einheit „Läden“, aus dem gemeinsamen Modell mit Stadteffekt).
- ⚠️ **Rohwerte nur als Kontext:** Miete in Euro immer relativ zum Median der eigenen Stadt zeigen, also `miete_qm / Median(miete_qm der Stadtzellen)`. Die Mieten der drei Städte liegen zu weit auseinander.

## Merkmale für den Vergleich, in dieser Reihenfolge

### 1. Gesamturteil (oberste Zeile, als Badges oder Kacheln)

| Merkmal | Spalte | Lesart |
|---|---|---|
| Score-Perzentil | `pr_score` | Sicht A: gewinnbare Nachfrage |
| Score-Index | `score_index` | U geteilt durch den Median der Geschäftslagen der Stadt, „2,5-mal so stark wie eine typische Geschäftslage“. Unterscheidet die Top-Standorte, die beim Perzentil alle bei 99 bis 100 liegen. Nur innerhalb einer Stadt vergleichbar |
| Lücken-Perzentil | `pr_luecke` | Sicht B: weniger Läden als erwartet |
| Konsens | `konsens` | beide ≥ 90, das sind die stärksten Kandidaten |
| Rang in der Stadt | `rang` | nur mit dem Zusatz „von N Geschäftslagen“ zeigen |
| Im Portfolio | h3 steht in `<stadt>_portfolio.csv` | Teil der besten 5er-Kombination |

### 2. Stabilität (wie sicher ist das Urteil?)

| Merkmal | Spalte |
|---|---|
| Anteil der Läufe in den Top 10 | `top10_anteil` |
| Rangspanne | `rang_median`, `rang_p10` bis `rang_p90` (als Fehlerbalken) |

Hinweis im Tab: Top 10 ist in Berlin strenger als in Frankfurt, weil Berlin mehr Zellen hat.

### 3. Warum der Score so ist (Zerlegung von Sicht A)

| Merkmal | Spalte | Lesart |
|---|---|---|
| Potenzial | `pr_potenzial` | Nachfrage ohne Wettbewerb |
| Wettbewerbsfreiheit | `pr_wettbewerbsfreiheit`, roh `w` | Anteil, den die Konkurrenz übrig lässt |
| Affinität | `pr_affinitaet` | passendes Umfeld (Cafés, Kultur …) |
| Milieu-Malus | `m_milieu` | 1 = kein Abzug, 0,2 = maximaler Abzug |
| Profil | `profil`, `anteil_tag` | Mittags-, Ganztags- oder Feierabendstandort, daraus folgt eher Deli oder eher Markt |

Darstellung: Radar- oder Balkendiagramm mit den vier `pr_*`-Achsen, ein Standort pro Farbe.

### 4. Warum die Lücke so ist (Treiber von Sicht B)

| Merkmal | Spalte |
|---|---|
| Läden vorhanden gegenüber erwartet | `y_direkt` gegenüber `y_erwartet` |
| Lücke im Umfeld | `luecke` (> 0 heißt unterversorgt) |
| Treiberbeiträge | `beitrag_einwohner`, `beitrag_kaufkraft`, `beitrag_alter`, `beitrag_affinitaet`, `beitrag_tag` |

Darstellung: Divergierende Balken je Treiber. Die Beiträge liegen auf der log-Skala und addieren sich. Koeffizienten und Standardfehler aus `luecke_modell.json` kommen in einen Info-Tooltip. Achtung: `alter` hat ein negatives Vorzeichen.

### 5. Umfeld-Steckbrief (Kontext, keine Bewertung)

- Einwohner (`einwohner`), Anteil der 20- bis 49-Jährigen (`anteil_20_49`), Anteil kleiner Haushalte (`anteil_hh_1_3`), Miete relativ zum Median der Stadt.
- Direkte Wettbewerber (`poi_deli`, `poi_feinkost_kaese`, `poi_wein`, `poi_bio_markt`, `poi_reformhaus`, `poi_markthalle`, `poi_pasta`) und breite Wettbewerber (`poi_supermarkt`, `poi_obst_gemuese`, `poi_metzger`, `poi_baecker`, `poi_fisch`).
- Die POI-Spalten zählen nur die eigene Zelle (ungefähr 0,1 km²). Sinnvoller ist die Summe aus Zelle und Ring 1: `h3.grid_disk(h3, 1)`, so wie es `geschaeftslage()` in `analyse.py` macht.

### 6. Datenqualität (als kleines Warnsymbol)

- `miete_geschaetzt` und `alter_geschaetzt`: Wert stammt aus Nachbarzellen.
- Stadtebene aus `<stadt>_plausibilitaet.json`: `anteil_pois_in_top_zellen` gegenüber 0,2 zeigt, wie gut das Potenzial in dieser Stadt trägt.

## Zusätzlich: Städtevergleich (eigene Ansicht im selben Tab)

Je Stadt: Anzahl der Konsens-Standorte, Anzahl der Geschäftslagen, Median-Miete, Plausibilitätswert, Stadteffekt aus `luecke_modell.json` (`stadt_frankfurt`, `stadt_berlin` gegenüber München als Referenz) und die Profilverteilung (Mittag, Ganztag, Feierabend).

## Akzeptanzkriterien

- Standorte lassen sich aus der Karte oder Top-Liste auswählen, gemischt über Städte, mit 2 bis 5 Spalten.
- Werden Standorte aus verschiedenen Städten verglichen, erscheinen nur die ✅-Merkmale als Hauptwerte. Absolute Scores sind ausgeblendet oder als „nur innerhalb der Stadt“ markiert.
- Jeder Wert hat einen Tooltip mit Lesart in einem Satz, die Texte stehen in den Tabellen oben.
- Konsens- und Portfolio-Standorte sind optisch hervorgehoben.
