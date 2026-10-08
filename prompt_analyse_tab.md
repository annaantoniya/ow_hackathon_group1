# Prompt: Analyse-Tab neu aufbauen

Überarbeite in `app.py` (Streamlit, Branch `dev-max`) die Ansicht **„Analyse“**. Heute hat sie drei Unter-Tabs (Pipeline, Modell, Absicherung) mit fest eingetipptem Text. Neu soll sie die Methodik Schritt für Schritt erklären. Die mathematischen Schritte sollen sichtbar bleiben, die Darstellung soll aber wie ein Beratungs-Deck wirken: Jede Folie beginnt mit der Kernaussage, dann folgen Beleg und Formel.

## Quellen

- **Inhalt:** `Specs/analyse_erklaerung.md`. Daraus stammen die Abschnitte, die Formeln und die Erklärungen.
- **Maßgeblich bei Widersprüchen:** `analyse.py`, vor allem das Dict `PARAMETER`. Lies Parameterwerte zur Laufzeit aus `analyse.PARAMETER`, statt sie abzutippen. Bekannter Widerspruch: Die Tabelle der Frequenzgewichte in `analyse_erklaerung.md` (Abschnitt 5, Bahnhof 5,0) ist veraltet. Im Code gilt Büro 4 > Hochschule 3 > Bahnhof 2 = Tram/U-Bahn 2 > Bus 1.
- **Ergebnisse:** Zuerst `python analyse.py` ausführen. Alle Zahlen im Tab kommen live aus `data/`:
  - `<stadt>_scored.csv`
  - `<stadt>_pca.json` (Variante, erklärte Varianz, Ladungen)
  - `<stadt>_plausibilitaet.json`
  - `<stadt>_portfolio.csv`
  - `luecke_modell.json` (gewähltes Modell, Test-Devianzen, Koeffizienten, Standardfehler, erklärte Devianz)
- Nichts hart codieren, was sich aus diesen Dateien lesen lässt. Heute nimmt der Tab für die Plausibilität fest München. Neu zeigt er alle drei Städte oder folgt der Stadtwahl.

## Stilregeln (Consulting)

1. **Action Titles:** Jede Überschrift ist ein ganzer Satz mit der Aussage, kein Thema. Also nicht „Wettbewerb“, sondern „Bestehende Läden schöpfen an den Top-Standorten 70 bis 85 % des Potenzials ab“, mit der Zahl live gerechnet.
2. **Pyramide:** Oben steht die Aussage, darunter höchstens drei Belege, darunter die Formel.
3. **Formel immer mit Übersetzung:** `st.latex(...)` für die Formel, daneben oder darunter ein Satz in Klartext, was sie bedeutet und warum sie für die Standortwahl zählt.
4. **Zahlen mit Einheit und Bezug,** zum Beispiel „68 % der Feinkostläden liegen in den oberen 20 % nach Potenzial (Zufall: 20 %)“.
5. **Kurz:** Höchstens drei Bullets pro Kasten, keine Fließtextblöcke. Die Herleitung bekommt je Schritt einen `st.expander("Herleitung")`.
6. Nutze die vorhandenen Helfer und Klassen in `app.py`: `kopf`, `exhibit_titel`, `bumper`, `quelle`, `panel`, `.kasten`, `.zahlen`, `.pipe`. Farben aus `T` und den Konstanten. Keine neue Optik erfinden.

## Aufbau

### 0. Executive Summary (oben, immer sichtbar)
Drei Kernaussagen als Zahlenkacheln:
- Zwei unabhängige Sichten, nämlich Score (Huff-Modell) und Angebotslücke (Regression). Konsens heißt, dass beide im obersten Zehntel liegen. Anzahl der Konsens-Standorte je Stadt.
- Das Potenzial trifft reale Muster: Plausibilitätswert je Stadt gegenüber 20 % bei Zufall.
- Die Lücke ist datenbasiert: erklärte Devianz außerhalb der Stichprobe aus `luecke_modell.json`.

Darunter das Gesamtschaubild aus Abschnitt 30 als horizontale Pipeline (`.pipe`). Ein Klick oder Anker auf einen Schritt springt zum passenden Abschnitt.

### 1. Sicht A: Der Score, in sechs Schritten
Je Schritt gibt es einen Action Title, die Formel, einen Satz Klartext und eine Zahl oder Grafik aus den Daten.

| Schritt | Formel (aus `analyse_erklaerung.md`) | Beleg aus den Daten |
|---|---|---|
| Raster und Distanz | $f_h(d)=2^{-d/h}$, Umweg 1,3, max. 1.500 m | Liniendiagramm $f_h(d)$ für h = 400 m (Anwohner) und 250 m (Tag) |
| Anwohnernachfrage | $N_i = E_i \cdot a_i \cdot h_i \cdot k_i$, $k_i=\operatorname{clip}(m_i/\tilde m,\,k_{min},k_{max})^\gamma$ | Median-Miete und Kappungsgrenzen je Stadt |
| Tagesfrequenz | $t_i=\sum_c w_c\,POI_{c,i}$ | Gewichte aus `PARAMETER`, Hinweis „Index, keine Personenzahl“ |
| Affinität | $A_i=v_1'z_i$, $q_i=q_{min}+(q_{max}-q_{min})PR(A_i)$ | erklärte Varianz PC1 und Ladungen aus `<stadt>_pca.json` als Balken. Variante `pca` oder Rückfall `anteil_affinitaet` erwähnen |
| Milieu-Malus | $m_c=\max(m_{min},2^{-s_c/s_{1/2}})$ | Anteil der Stadtzellen mit `m_milieu < 0,9`, Beispiel Frankfurter Bahnhofsviertel |
| Potenzial, Wettbewerb, Score | $U_c=\sum_i O_i\frac{a_{neu}m_cf(d_{ic})}{a_{neu}m_cf(d_{ic})+K_i+a_0}$, $W=U/P$ | Rechenbeispiel: ohne Wettbewerb gewinnt der Laden vor der Tür ≈ 60 % (Kommentar zu `a_0` in `analyse.py`). Dazu der Median von `w` der Top 10 |

Danach ein Kasten **„Vom Score zum Rang“**:
- Geschäftslagen-Filter: mindestens 5 POIs in Zelle plus Ring 1. Zeigen, wie viel Prozent der Stadtzellen das sind.
- Prozentränge, Referenz sind die Geschäftslagen der Stadt.
- `score_index` = $U/\text{Median}(U_{Lagen})$ mit Werten der Top 10.
- Profil Mittag, Ganztag oder Feierabend über die Quantile von $P_T/P$.

### 2. Sicht B: Die Angebotslücke
- Action Title, zum Beispiel: „Das Umfeld erklärt rund die Hälfte der Ladenverteilung, der Rest ist die Lücke“ (Zahl live).
- Zielgröße $y_c$ (direkte Wettbewerber) und das Modell $\log\mu_c=\beta_0+\delta_{Stadt}+\beta^\top x_c+S_c$.
- **Modellvergleich als Grafik:** Test-Devianz von Poisson, NB und räumlichem NB aus `luecke_modell.json`, das gewählte Modell hervorgehoben. Ein Satz zur Auswahlregel: Das komplexere Modell nur bei mindestens 1 % Verbesserung. Nicht behaupten, dass das räumliche Modell gewählt wurde. Die Variante kommt aus `variante`.
- **Treiber:** Koeffizienten mit ±1,96 Standardfehler als Punkt-Fehlerbalken-Diagramm. Negative Vorzeichen aus `negative_vorzeichen` markieren und erklären, dass sie berichtet und nicht korrigiert werden.
- Lücke $g_c=\sum_j(\hat y_j-y_j)f(d_{cj})$ mit Klartext: positiv heißt, es stehen weniger Läden da, als das Umfeld erwarten lässt.
- Expander „Warum NB und räumlicher Effekt?“ mit dem Inhalt aus Abschnitt 19 (Overdispersion gegenüber räumlicher Abhängigkeit, warum kein OLS).

### 3. Konsens: Wo beide Sichten übereinstimmen
- Formel $PR(U)\ge 90 \wedge PR(g)\ge 90$.
- Streudiagramm `pr_score` gegen `pr_luecke` der Geschäftslagen der gewählten Stadt. Das Konsens-Quadrat oben rechts ist schattiert, die Top 10 sind hervorgehoben.
- Zahl: Konsens-Standorte je Stadt.

### 4. Absicherung: Wie belastbar ist das?
Drei Kacheln nebeneinander, jeweils mit Aussage, Zahl und Formel oder Methode:
- **Plausibilität:** Anteil der Feinkostläden in den oberen 20 % nach Potenzial, je Stadt, gegenüber 20 %. Ausdrücklich: Der Test ist nicht zirkulär.
- **Robustheit:** Anzahl der Läufe (`n_laeufe`), Spannen aus `SPANNEN`. Verteilung von `top10_anteil` der Top 10 als Balken mit den Schwellen sicher ≥ 70 % und wackelig < 30 %.
- **Räumliche Kreuzvalidierung:** H3-Elternzellen der Auflösung 6 bleiben zusammen, 5 Teile, erklärte Devianz in und außerhalb der Stichprobe.

### 5. Portfolio: Fünf Standorte, die sich ergänzen
- Gierige Auswahl. Die Zielfunktion $F(S)$ ist submodular, daher erreicht die Auswahl mindestens $1-1/e≈63\,\%$ des Optimums.
- Tabelle aus `<stadt>_portfolio.csv` (Schritt, Rang einzeln, Zugewinn). Dazu der Satz, um welchen Faktor das Portfolio besser ist als die 5 besten Einzelstandorte. Dafür F des Portfolios gegen F der Ränge 1 bis 5 rechnen oder aus der Konsolenausgabe übernehmen.

### 6. Grenzen (Abschnitt 31)
Ein Kasten mit drei Bullets: Modell statt Messung, Miete als Ersatz für Kaufkraft, Tagesindex statt Personenzahl. Dazu `bumper("Der Score ordnet Standorte, er sagt keinen Umsatz voraus.")`.

## Akzeptanzkriterien
- Jede Überschrift ist ein Satz mit Aussage. Mindestens die Hälfte enthält eine live berechnete Zahl.
- Jeder Methodikschritt zeigt eine Formel per `st.latex` und einen Satz Klartext.
- Keine Zahl ist hart codiert, wenn sie in `data/` oder `analyse.PARAMETER` steht. Nach einem erneuten Lauf von `analyse.py` stimmt der Tab ohne Codeänderung.
- Die Stadtwahl wirkt auf alle stadtbezogenen Zahlen. Stadtübergreifende Werte (Modell, Koeffizienten) sind als solche gekennzeichnet.
- Hell- und Dunkelmodus funktionieren (Farben über `T`).
- Unter jedem Abschnitt steht eine Quellenzeile über `quelle(...)`.
