# Prompt: Vergleichs-Tab umbauen – verständlich erklärt

## Worum es geht

Der Tab „Vergleich“ soll zur **Ergebnisseite für alle** werden, nicht nur für Fachleute. Wer ihn liest, soll nach zwei Minuten wissen:

1. Mit welchen Daten wir gearbeitet haben und warum genau mit diesen.
2. Was dabei herausgekommen ist.
3. Welche White Spots wir in München, Frankfurt und Berlin gefunden haben und was jeden dieser Orte stark macht, belegt mit den Daten, die wir verwendet haben.

Der Stil ist wie im Analyse-Tab: aufgebaut wie eine Beraterpräsentation. Jede Überschrift ist schon die Aussage. Darunter stehen wenige, klare Belege. Anders als im Analyse-Tab gibt es hier **keine Formeln, keinen Code und keine Fachbegriffe**.

## Sprachregeln

- Schreibe so, dass es jemand ohne Statistik-Kenntnisse beim ersten Lesen versteht.
- Kurze Sätze, aktive Sprache. Höchstens drei Punkte pro Kasten.
- Jede Überschrift ist ein ganzer Satz mit Aussage, zum Beispiel „In Berlin liegen die stärksten Standorte rund um die Friedrichstraße“ statt „Ergebnisse Berlin“.
- Zahlen immer mit Vergleich, damit man sie einordnen kann: „doppelt so viele“, „8 von 10“, „mehr als in 9 von 10 Lagen der Stadt“.
- Keine Spaltennamen, keine Abkürzungen, keine englischen Begriffe in der Oberfläche.

Diese Übersetzungen gelten im ganzen Tab:

| Statt … | … schreiben wir |
|---|---|
| H3-Hexagon, Zelle | Feld, etwa 300 × 300 Meter groß, also ein paar Häuserblöcke |
| POI | Orte wie Cafés, Läden, Büros oder Haltestellen |
| Score, Huff-Modell | Kundenpotenzial: wie viele passende Kunden ein neuer Laden hier gewinnen könnte |
| Score-Index | „2,5-mal so stark wie eine typische Einkaufslage der Stadt“ |
| Prozentrang | „stärker als 97 von 100 Einkaufslagen der Stadt“ |
| Angebotslücke, Residuum | fehlende Läden: hier gibt es weniger Feinkostläden, als das Viertel erwarten lässt |
| Konsens | doppelt bestätigt: beide Rechenwege sehen den Ort ganz vorn |
| Robustheit, Top-10-Anteil | „bleibt in 9 von 10 Testrechnungen unter den besten zehn“ |
| Wettbewerbsfreiheit | Anteil der Kundschaft, den die bestehende Konkurrenz übrig lässt |
| Affinität | passendes Umfeld: Cafés, Restaurants, Buchläden, Kultur |
| Tagesindex, Frequenz | Tagesbetrieb: Büros, Hochschulen, Bahnhöfe und Haltestellen |
| Milieu-Malus | Abzug für ein ungünstiges Umfeld, etwa Spielhallen oder Wettbüros |
| Geschäftslage | belebte Lage, in der schon Läden und Cafés sind |
| Zensus | amtliche Volkszählung 2022 |
| OpenStreetMap | frei zugängliche Online-Karte, von Freiwilligen gepflegt |
| Regression, Modell | „wir haben aus den heutigen Läden gelernt, welche Viertel Feinkost anziehen“ |

## Aufbau des Tabs

### 1. Auf einen Blick
Oben stehen drei bis vier große Zahlen mit je einer Zeile Erklärung, zum Beispiel:
- „185 Standorte in drei Städten sind doppelt bestätigt.“
- „7 bis 8 von 10 heutigen Feinkostläden liegen dort, wo unsere Rechnung das meiste Kundenpotenzial sieht. Bei Zufall wären es 2 von 10.“
- „Rund 15.000 Felder und 53.000 Orte ausgewertet.“

Darunter steht ein Satz als Fazit, etwa: „München und Berlin haben klare, doppelt bestätigte Favoriten. In Frankfurt ist das Bild weniger eindeutig.“

### 2. Unsere Datengrundlage – und warum sie so aussieht
**Überschrift:** „Wir haben nur offene, amtliche und für alle drei Städte gleiche Daten genutzt, damit die Ergebnisse vergleichbar und nachprüfbar sind.“

Zwei Kästen nebeneinander:

**Wer dort lebt** (amtliche Volkszählung 2022)
- Wie viele Menschen wohnen in jedem Feld, wie viele davon sind 20 bis 49 Jahre alt, wie viele leben in kleinen Haushalten?
- Die Miete pro Quadratmeter steht für die Kaufkraft.

**Was es dort gibt** (frei zugängliche Online-Karte)
- Konkurrenz: Feinkost, Delis, Bio-Märkte, Weinhandlungen, Supermärkte, Bäcker.
- Passendes Umfeld: Cafés, Restaurants, Buchläden, Kultur, Yoga-Studios.
- Tagesbetrieb: Büros, Hochschulen, Bahnhöfe, Haltestellen.
- Ungünstiges Umfeld: Spielhallen, Wettbüros, Rotlicht.

Darunter ein Kasten **„Warum gerade diese Daten?“**, ein Satz pro Punkt:
- **Kleinräumig:** Wir wollten Straßenzüge unterscheiden, nicht ganze Stadtteile. Deshalb teilen wir jede Stadt in Felder von etwa 300 × 300 Metern.
- **Gleich für alle drei Städte:** Nur so lassen sich München, Frankfurt und Berlin nach denselben Regeln bewerten.
- **Offen und kostenlos:** Jeder kann die Ergebnisse nachrechnen.
- **Ehrliche Ersatzgrößen:** Einkommen gibt es nicht kleinräumig, deshalb nehmen wir die Miete. Passantenzahlen gibt es nicht offen, deshalb zählen wir Büros, Hochschulen und Haltestellen. Kriminalitätsdaten gibt es nicht straßengenau, deshalb zählen wir Spielhallen und Wettbüros. Merkmale wie Herkunft oder Nationalität nutzen wir bewusst nicht.

Zum Schluss ein kleiner Kasten mit den Grenzen der Daten, ohne Drama:
- Die Volkszählung zeigt den Stand von 2022.
- Die Online-Karte ist nicht überall gleich vollständig.
- Ladengröße und Umsatz kennen wir nicht.

### 3. So sind wir vorgegangen – in drei Sätzen
Eine einfache Bildleiste mit drei Schritten, ohne Formeln:
1. **Kundenpotenzial berechnen:** Wie viele passende Kunden wohnen oder arbeiten in Laufweite, und wie viele davon würde ein neuer Laden der Konkurrenz abnehmen?
2. **Fehlende Läden finden:** Aus den heutigen Feinkostläden haben wir gelernt, welche Viertel solche Läden anziehen. Wo weniger stehen, als das Viertel erwarten lässt, gibt es eine Lücke.
3. **Doppelt prüfen:** Ein White Spot ist besonders stark, wenn beide Wege ihn ganz vorn sehen. Zusätzlich haben wir alle Annahmen 1.000-mal leicht verändert und geprüft, ob der Ort vorn bleibt.

Für Details folgt ein Hinweis auf den Analyse-Tab.

### 4. Was dabei herausgekommen ist
**Überschrift mit Aussage**, zum Beispiel: „Die stärksten Standorte liegen nicht dort, wo am meisten Menschen wohnen, sondern dort, wo Kundschaft, Umfeld und wenig Konkurrenz zusammenkommen.“

Ein Städtevergleich nebeneinander, als einfache Tabelle oder Kacheln je Stadt:
- Anzahl der doppelt bestätigten Standorte
- typischer Charakter der besten Lagen: Mittags-, Feierabend- oder Ganztagsstandort
- ein Satz Fazit je Stadt

Die Kontrollwerte vom 8. Oktober 2026 stehen unten bei den Städten.

### 5. Die White Spots je Stadt
Für jede Stadt ein eigener Abschnitt mit einer Überschrift als Aussage, einer kleinen Übersichtskarte und darunter Steckbriefe der **fünf besten Standorte**.

**Jeder Steckbrief hat dieselbe Form:**

> **Platz 1 · [Viertel, nächste Haltestelle]**
> *Ein Satz Urteil*, zum Beispiel: „Viel passende Kundschaft, kaum Konkurrenz – doppelt bestätigt und sehr sicher.“
>
> **Warum hier?**
> - **Menschen:** rund 28.000 Einwohner im Umkreis von etwa 500 Metern, davon überdurchschnittlich viele zwischen 20 und 49.
> - **Kaufkraft:** Mieten etwa auf dem Niveau der Stadt (bzw. „ein Drittel über dem Stadtschnitt“).
> - **Umfeld:** rund 100 Cafés und Restaurants in der Nähe.
> - **Tagesbetrieb:** rund 90 Büros und mehrere Haltestellen in der Nähe.
> - **Konkurrenz:** 4 Feinkostläden in der Nähe, für so ein Viertel wären etwa 9 zu erwarten.
>
> **Wie sicher?** In 98 von 100 Testrechnungen unter den besten zehn.
> **Welches Format passt?** Ganztagsstandort: Mittagsgeschäft und Einkauf nach Feierabend.

Regeln für die Steckbriefe:
- Nur die drei bis fünf Punkte zeigen, die diesen Ort **wirklich auszeichnen** oder **bremsen**. Bei Bremsen wird ehrlich gesagt, was gegen den Ort spricht, zum Beispiel „viel Konkurrenz: Die bestehenden Läden binden rund 70 % der Kundschaft“.
- „Doppelt bestätigt“ wird als deutliches Abzeichen gezeigt.
- Formatempfehlung je Profil:
  - Mittagsstandort: Deli mit Mittagstisch und To-go.
  - Feierabendstandort: Markt mit Einkauf für zu Hause.
  - Ganztagsstandort: beides.
- Zahlen runden („rund 28.000“, „etwa 9“) und immer einordnen.

**Was die Daten heute zeigen (Kontrollwerte, live neu berechnen):**

- **München: „Die Spitze ist klar und stabil.“**
  - Die besten drei liegen westlich der Innenstadt.
  - Alle drei sind doppelt bestätigt.
  - Sie bleiben in 91 bis 98 von 100 Testrechnungen unter den besten zehn.
  - Muster: viele junge Erwachsene, viele Büros, deutlich weniger Feinkostläden als erwartet (zum Beispiel 2 statt etwa 10).
- **Frankfurt: „Viel Kundschaft, aber kaum fehlende Läden.“**
  - Die besten Lagen im Westen haben Mieten rund 30 bis 40 % über dem Stadtschnitt und viel passende Kundschaft.
  - Dort gibt es aber schon etwa so viele Feinkostläden, wie man erwarten würde.
  - Deshalb ist keiner der Top 6 doppelt bestätigt.
  - Empfehlung im Text: Hier zählt die Lage mit dem besten Kundenpotenzial. Die Lücke ist kein Argument.
- **Berlin: „Die stärksten Standorte bilden ein Mittags-Cluster in Mitte.“**
  - Die besten Lagen liegen dicht beieinander, mit sehr vielen Büros (150 bis 180 in der Nähe) und über 120 Cafés und Restaurants.
  - Sie sind doppelt bestätigt.
  - Sie sind etwas weniger sicher: in 6 von 10 Testrechnungen unter den besten zehn. Das liegt daran, dass sich viele ähnlich starke Orte die Plätze teilen.
  - Format: Deli mit Mittagsgeschäft.

### 6. Selbst vergleichen (optional, am Ende)
Die bisherige Gegenüberstellung von zwei bis fünf Standorten kann als letzter Abschnitt bleiben, aber ebenfalls in einfacher Sprache:
- Balken „stärker als X von 100 Einkaufslagen“
- „doppelt bestätigt ja/nein“
- „wie sicher“
- die Steckbrief-Punkte

Ein Hinweis erklärt, dass Rohwerte zwischen Städten nicht vergleichbar sind und deshalb nur „im Vergleich zur eigenen Stadt“ gezeigt werden.

### 7. Abschluss
Ein Satz am Ende: „Unsere Rechnung zeigt, wo sich ein Besuch vor Ort lohnt. Sie ersetzt ihn nicht.“ Darunter die Quellen in einer Zeile.

---

## Technische Hinweise für die Umsetzung

Dieser Teil ist nur für die Umsetzung gedacht. Nichts davon erscheint im Tab.

- Die Ansicht „Vergleich“ in `app.py` (Branch `dev-max`) wird umgebaut. Vorhandene Helfer und Optik weiterverwenden: `kopf`, `exhibit_titel`, `bumper`, `quelle`, `panel`, `.kasten`, `.zahlen`, `.pipe`, Farben über `T`.
- Alle Zahlen live aus `data/` rechnen, nichts abtippen. Zuerst `python analyse.py` ausführen.
- Zuordnung der Steckbrief-Punkte zu den Daten:
  - Top 5 je Stadt: `rang` 1 bis 5 aus `<stadt>_scored.csv`
  - Name: `viertel()` bzw. `lagebezeichnung()`
  - „Umkreis von etwa 500 Metern“: Summe über `h3.grid_disk(h3, 2)`
  - Menschen: `einwohner`, Anteil `anteil_20_49` gegenüber dem Stadtmedian
  - Kaufkraft: `miete_qm` geteilt durch den Median der Stadtzellen
  - Umfeld: `poi_cafe` + `poi_restaurant`
  - Tagesbetrieb: `poi_buero`, `poi_tram_ubahn` + `poi_bahnhof`
  - Konkurrenz: Summe der direkten Wettbewerber gegenüber Summe `y_erwartet`
  - Abzug für ungünstiges Umfeld nur erwähnen, wenn `m_milieu` < 0,9
  - „Stärker als X von 100“: `pr_score`
  - „X-mal so stark“: `score_index`
  - Doppelt bestätigt: `konsens`
  - Wie sicher: `top10_anteil`
  - Format: `profil`
  - Konkurrenz-Anteil: 1 − `w`
- Was einen Ort auszeichnet oder bremst, ergibt sich aus `pr_potenzial`, `pr_wettbewerbsfreiheit`, `pr_affinitaet` und dem Verhältnis vorhanden zu erwartet: ab 80 eine Stärke, unter 40 eine Bremse. Das ist dieselbe Regel wie `staerken_satz()`.
- Zahlen für „Auf einen Blick“ und den Städtevergleich:
  - Konsens-Zählung aus `<stadt>_scored.csv`
  - Treffer der Plausibilitätsprüfung aus `<stadt>_plausibilitaet.json`
  - Felder- und Ortszahlen aus `<stadt>_grid.csv` und `<stadt>_pois.csv`
- Fertig ist der Tab, wenn:
  - kein Fachbegriff aus der linken Spalte der Übersetzungstabelle im Tab vorkommt,
  - jede Überschrift eine Aussage ist,
  - jeder Steckbrief dieselbe Form hat,
  - nach einem neuen Lauf von `analyse.py` alle Zahlen ohne Codeänderung stimmen,
  - Hell- und Dunkelmodus funktionieren.
