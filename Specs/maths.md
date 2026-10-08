# Mathematische Vorgehensweise der Datenanalyse

Die Datenanalysearbeit folgt mathematisch im Kern einer **räumlichen Standortanalyse auf einem Hexagon-Raster**, bei der Nachfrage, Standortaffinität und Wettbewerb zunächst modelliert und anschließend zu einem Standortscore kombiniert werden. Ergänzend wird mit einer Regression geprüft, wo das vorhandene Angebot geringer ist, als es aufgrund der Standortmerkmale zu erwarten wäre.

Die Fragestellung ist damit:

> **Welche räumlichen Zellen weisen gleichzeitig hohe potenzielle Nachfrage und eine vergleichsweise geringe Angebotsabdeckung auf?**

## 1. Räumliche Diskretisierung

Das gesamte Untersuchungsgebiet wird zunächst in H3-Hexagone der Auflösung 9 zerlegt. Jedes Hexagon $i$ wird durch seinen Mittelpunkt repräsentiert. Zusätzlich wird die eigentliche Stadtgrenze um 1.500 m erweitert, damit Standorte am Stadtrand nicht künstlich zu wenig Nachbarschaft erhalten.

Die grundlegende Beobachtungseinheit der Analyse ist somit nicht eine Adresse oder ein Stadtteil, sondern eine räumliche Zelle

$i = 1,\ldots,n.$

Für jede Zelle liegen anschließend Merkmale wie

$E_i = \text{Einwohner},$

$m_i = \text{Miete},$

$a_i = \text{Anteil der 20- bis 49-Jährigen}$

sowie die Anzahl verschiedener POI-Kategorien vor.

## 2. Räumliche Nachbarschaft

Da Nachfrage und Wettbewerb nicht ausschließlich innerhalb einer Zelle wirken, wird für jedes relevante Zellpaar $(i,j)$ die Distanz

$d_{ij}$

berechnet.

Berücksichtigt werden nur Zellen innerhalb einer maximalen Entfernung

$d_{ij}\leq d_{\max}.$

Aus der Luftliniendistanz wird mittels eines Umwegfaktors von 1,3 eine approximierte tatsächliche Wegstrecke gebildet.

Für jede Stadt entsteht dadurch eine Liste aller relevanten Zellpaare. Damit kann jede räumliche Größe später als gewichtete Nachbarschaftssumme geschrieben werden.

## 3. Distanzgewichtung

Für sämtliche räumlichen Effekte wird eine exponentiell fallende Gewichtungsfunktion verwendet:

$f_h(d)=2^{-d/h}.$

Dabei bezeichnet $h$ die sogenannte Halbwertsdistanz.

Es gilt beispielsweise:

$f_h(0)=1$

und

$f_h(h)=\frac12.$

Ein Objekt in Entfernung $h$ besitzt somit nur noch halb so viel Einfluss wie ein unmittelbar benachbartes Objekt.

Für

$d>d_{\max}$

wird der Einfluss vollständig auf null gesetzt.

Es werden unterschiedliche Halbwertsdistanzen verwendet, beispielsweise für

- Einwohner,
- Tagesbevölkerung,
- Affinität.

Dadurch lässt sich modellieren, dass unterschiedliche Nachfragekomponenten verschiedene räumliche Reichweiten besitzen.

## 4. Berechnung der Einwohnernachfrage

Für jede Zelle wird zunächst eine gewichtete Nachfrage der dort wohnenden Bevölkerung berechnet:

$N_i = E_i\cdot a_i\cdot k_i.$

Dabei ist

$E_i$

die Einwohnerzahl,

$a_i$

der Anteil der 20- bis 49-Jährigen und

$k_i$

ein Kaufkraftfaktor.

Die Kaufkraft wird über das Verhältnis der lokalen Miete zum Median der jeweiligen Stadt approximiert:

$k_i = \left[\min\left(\max\left(\frac{m_i}{\tilde m},k_{\min}\right),k_{\max}\right)\right]^\gamma.$

Dabei ist

$\tilde m$

die Medianmiete der Stadt.

Ein Gebiet erhält also eine höhere Nachfrage, wenn dort

1. viele Menschen leben,
2. ein hoher Anteil zur relevanten Altersgruppe gehört und
3. die Miete als Proxy für Kaufkraft relativ hoch ist.

## 5. Tagesbevölkerung

Neben der Wohnbevölkerung soll auch Nachfrage durch Menschen berücksichtigt werden, die sich tagsüber in einem Gebiet aufhalten.

Dafür wird ein Index

$t_i = \sum_{c\in C_{\text{Frequenz}}} w_c\,POI_{c,i}$

gebildet.

Beispielsweise können Bahnhöfe, Büros, Hochschulen oder ÖPNV-Haltestellen unterschiedlich gewichtet werden.

Wichtig ist, dass

$t_i$

**keine geschätzte Personenzahl** ist, sondern lediglich einen relativen Frequenzindikator darstellt.

## 6. Berechnung der Standortaffinität

Danach wird untersucht, ob die Umgebung grundsätzlich zu einem Premium-Food-Konzept passt.

Dazu werden beispielsweise Cafés, Restaurants, Boutiquen, Buchhandlungen, Kulturangebote oder Fitnessstudios verwendet.

Zunächst wird für jede Kategorie $c$ die räumlich geglättete Dichte berechnet:

$s_{c,i} = \sum_j POI_{c,j} f_{h_{\text{Aff}}}(d_{ij}).$

Ein POI in einer Nachbarzelle zählt somit ebenfalls, allerdings mit geringerem Gewicht.

Anschließend werden die Werte logarithmiert:

$x_{c,i} = \log(1+s_{c,i})$

und innerhalb jeder Stadt standardisiert:

$z_{c,i} = \frac{x_{c,i}-\mu_c}{\sigma_c}.$

Auf diese standardisierten Variablen wird eine **Hauptkomponentenanalyse, PCA**, angewendet. Die erste Hauptkomponente dient als gemeinsamer Affinitätsindex.

Mathematisch entspricht der Index ungefähr

$A_i = v_1^\top z_i,$

wobei $v_1$ der Eigenvektor der Kovarianzmatrix mit dem größten Eigenwert ist.

Der kontinuierliche Index wird anschließend anhand seines Prozentrangs in einen Faktor

$q_i = q_{\min} + (q_{\max}-q_{\min})PR(A_i)$

überführt.

Damit liegt der Affinitätsfaktor beispielsweise zwischen

$0{,}5$

und

$1{,}5.$

Ein Standort mit besonders hoher Affinität kann die lokale Nachfrage somit verstärken.

## 7. Bildung der Quellnachfrage

Anschließend wird die Nachfrage in zwei getrennte Komponenten zerlegt.

### Wohnbevölkerung

$O_i^A = q_i(1-\theta)\frac{N_i}{\sum_jN_j}$

und Tagesbevölkerung

$O_i^T = q_i\theta\frac{t_i}{\sum_jt_j}.$

Der Parameter

$\theta$

legt fest, wie stark die Tagesbevölkerung gegenüber der Wohnbevölkerung gewichtet wird.

Im Basismodell gilt

$\theta=0{,}3.$

Somit stammen ungefähr 70 % der modellierten Ausgangsnachfrage aus der Wohnbevölkerung und 30 % aus dem Tagesfrequenzindikator, bevor die Affinität berücksichtigt wird.

## 8. Berechnung des theoretischen Standortpotenzials

Für jeden potenziellen Ladenstandort $c$ wird nun gefragt:

> Wie viel Nachfrage könnte dieser Standort erhalten, wenn kein Wettbewerber vorhanden wäre?

Dafür wird

$P_c^A = \sum_i O_i^A \frac{A_{\text{neu}}f_{h_A}(d_{ic})}{A_{\text{neu}}f_{h_A}(d_{ic})+A_0}$

berechnet.

Entsprechend wird

$P_c^T$

für die Tagesbevölkerung berechnet.

Das Gesamtpotenzial lautet

$P_c = P_c^A+P_c^T.$

Der Ausdruck im Bruch stellt die Wahrscheinlichkeit beziehungsweise den Nachfrageanteil dar, den der neue Laden gegenüber einer Außenoption erhalten würde.

## 9. Modellierung des Wettbewerbs

Als Nächstes werden bestehende Wettbewerber einbezogen.

Jede Zelle $j$ erhält zunächst eine Wettbewerbsstärke

$A_j = \sum_c \alpha_c POI_{c,j}.$

Dabei sind

$\alpha_c$

kategoriespezifische Konkurrenzgewichte.

Eine Markthalle kann beispielsweise stärker gewichtet werden als ein Bäcker.

Für jede Quellzelle $i$ wird daraus ein räumlicher Wettbewerbsdruck berechnet:

$K_i^A = \sum_j A_j f_{h_A}(d_{ij})$

und analog

$K_i^T = \sum_j A_j f_{h_T}(d_{ij}).$

Damit wirkt ein Wettbewerber umso stärker, je näher er an der jeweiligen Nachfragequelle liegt.

## 10. Huff-Modell und zentraler Standortscore

Der zentrale Score ist anschließend die Nachfrage, die der neue Laden tatsächlich gewinnen könnte.

Für die Wohnbevölkerung:

$U_c^A = \sum_i O_i^A \frac{A_{\text{neu}}f_{h_A}(d_{ic})}{A_{\text{neu}}f_{h_A}(d_{ic})+K_i^A+A_0}.$

Analog wird

$U_c^T$

für die Tagesbevölkerung berechnet.

Der Gesamtwert lautet

$U_c = U_c^A+U_c^T.$

und bildet den eigentlichen Standortscore.

Je größer

$U_c,$

desto mehr passende Nachfrage kann der neue Standort unter Berücksichtigung bestehender Konkurrenz voraussichtlich auf sich ziehen.

Zusätzlich wird

$W_c = \frac{U_c}{P_c}$

berechnet.

Dabei ist

$P_c$

das Potenzial ohne Konkurrenz und

$U_c$

das Potenzial mit Konkurrenz.

Somit ist

$W_c$

ein Maß für die **Wettbewerbsfreiheit**.

$W_c\approx1$

bedeutet wenig Wettbewerbsdruck, während

$W_c\ll1$

auf starken Wettbewerb hinweist.

## 11. Rangbildung

Die relevanten Standorte werden anschließend anhand von

$U_c$

absteigend sortiert.

Zusätzlich werden Prozentränge für verschiedene Komponenten berechnet:

$PR(U_c),$

$PR(P_c),$

$PR(W_c),$

$PR(q_c).$

Referenz der Prozentränge sind die Geschäftslagen der Stadt, nicht alle Stadtzellen. Sonst drücken Parks und Wohnstraßen mit $U_c \approx 0$ jeden brauchbaren Standort an den oberen Rand. Für $PR(g_c)$ gilt dieselbe Referenz. Zusätzlich wird

$U_c / \operatorname{Median}(U \text{ der Geschäftslagen})$

ausgegeben, weil der Prozentrang an der Spitze kaum noch unterscheidet.

Dadurch lässt sich für einen Standort getrennt erkennen, ob sein guter Rang beispielsweise durch

- besonders viel Nachfrage,
- hohe Affinität oder
- wenig Wettbewerb

entsteht.

## 12. Zweites Modell: datengetriebene Angebotslücke

Neben dem strukturellen Score $U_c$ enthält die Analyse noch einen zweiten, methodisch wichtigen Ansatz.

Hier wird nicht gefragt

> „Wie attraktiv wäre ein neuer Laden?“

sondern

> „Wie viele vergleichbare Läden müsste es aufgrund der Standortmerkmale eigentlich geben?“

Als Zielvariable wird die Zahl direkter Wettbewerber

$y_c$

verwendet.

Als erklärende Variablen werden fünf Merkmale verwendet:

$x_{\text{Einwohner}}, \quad x_{\text{Kaufkraft}}, \quad x_{\text{Alter}}, \quad x_{\text{Affinität}}, \quad x_{\text{Tag}}.$

Diese werden jeweils innerhalb der Stadt standardisiert.

## 13. Poisson-Regression

Da die abhängige Variable eine Anzahl

$y_c=0,1,2,\ldots$

ist, wird zunächst eine Poisson-Regression verwendet:

$\mathbb{E}[y_c] = \exp\left(\beta_0+\delta_{\text{Stadt}(c)}+\sum_{k=1}^{5}\beta_kx_{k,c}\right).$

Dabei sind

$\beta_k$

die aus den Daten geschätzten Effekte der Standortmerkmale und

$\delta_{\text{Stadt}}$

feste Stadteffekte.

Aus dem Modell erhält man für jede Zelle eine erwartete Anzahl von Wettbewerbern:

$\hat y_c.$

## 14. Berechnung des White Spots als Residuum

Die eigentliche Angebotslücke entsteht aus der Differenz

$\hat y_j-y_j.$

Ist beispielsweise

$\hat y_j=3$

aber tatsächlich nur

$y_j=1,$

fehlen gegenüber dem statistischen Erwartungswert zwei Anbieter.

Da ein Laden in der Nachbarzelle ebenfalls relevant ist, werden diese Residuen wiederum räumlich geglättet:

$g_c = \sum_j(\hat y_j-y_j)f_{h_A}(d_{cj}).$

Ein hoher positiver Wert

$g_c>0$

bedeutet damit:

> Aufgrund von Einwohnern, Kaufkraft, Alter, Affinität und Tagesfrequenz würde das Modell mehr Anbieter erwarten, als tatsächlich vorhanden sind.

Das ist die datengetriebene Definition eines **White Spots**.

## 15. Zwei unabhängige Sichtweisen

Die Analyse erzeugt damit bewusst zwei unterschiedliche Rankings.

### Strukturelles Nachfragemodell

$U_c$

fragt:

> Wie viel Nachfrage könnte ein neuer Laden gewinnen?

Dabei werden ökonomisch gesetzte Parameter für Distanz, Wettbewerb und Nachfrage verwendet.

### Statistische Angebotslücke

$g_c$

fragt:

> Gibt es aufgrund der beobachteten Standortmerkmale ungewöhnlich wenig bestehendes Angebot?

Hier werden die Zusammenhänge aus den tatsächlichen Standortdaten gelernt.

Besonders interessant sind deshalb Standorte, für die gleichzeitig gilt:

$PR(U_c)\geq90$

und

$PR(g_c)\geq90.$

Diese werden als **Konsens-Standorte** definiert.

## 16. Prüfung der statistischen Aussagekraft

Damit das Regressionsmodell nicht nur die vorhandenen Daten auswendig lernt, wird eine räumliche Kreuzvalidierung durchgeführt.

Die Zellen werden dabei über größere H3-Gebiete in fünf Gruppen eingeteilt.

Dann wird wiederholt:

$80\% \text{ Training} \rightarrow 20\% \text{ Test}.$

Anschließend wird geprüft, wie viel der Abweichung der Wettbewerberzahl das Modell auf bisher ungesehenen Regionen erklärt.

Verwendet wird die erklärte Devianz.

Ist

$D_{\text{out-of-sample}}<0{,}05,$

gilt die Vorhersagekraft als sehr gering und es wird eine Warnung ausgegeben.

Zusätzlich wird Überdispersion kontrolliert. Falls

$\frac{\chi^2_{\text{Pearson}}}{df}>1{,}5,$

wird anstelle der Poisson-Regression eine Negative-Binomial-Regression verwendet.

## 17. Robustheitsanalyse

Da viele Parameter des strukturellen Modells nicht empirisch geschätzt, sondern gesetzt werden, wird geprüft, wie stabil die Rangliste gegenüber diesen Annahmen ist.

Dazu werden die Parameter in jeder Simulation aus vorgegebenen Intervallen gezogen.

Für Simulation

$r=1,\ldots,R$

entsteht somit ein neuer Score

$U_c^{(r)}$

und ein neuer Rang

$R_c^{(r)}.$

In der Spezifikation sind bis zu

$R=1000$

Simulationen vorgesehen.

Für jeden Standort werden anschließend beispielsweise

$\operatorname{Median}(R_c)$

sowie das 10-%- und 90-%-Quantil berechnet.

Besonders aussagekräftig ist

$Top10Anteil_c = \frac{\#\{r:R_c^{(r)}\leq10\}}{R}.$

Ein Standort, der in fast allen Simulationen unter den Top 10 bleibt, ist deutlich robuster als ein Standort, dessen Rang stark von den Parametern abhängt.

## 18. Portfoliooptimierung mehrerer Standorte

Abschließend wird nicht nur ein einzelner Standort betrachtet, sondern eine Kombination

$S=\{c_1,\ldots,c_k\}.$

Die gemeinsam gewonnene Nachfrage lautet

$F(S) = \sum_i O_i^A \frac{X_i^A(S)}{X_i^A(S)+K_i^A+A_0} + \sum_i O_i^T \frac{X_i^T(S)}{X_i^T(S)+K_i^T+A_0},$

wobei

$X_i^A(S)=\sum_{c\in S}A_{\text{neu}}f_{h_A}(d_{ic}).$

Man kann also nicht einfach die fünf besten Einzelstandorte auswählen, weil sich deren Einzugsgebiete möglicherweise stark überschneiden.

Stattdessen wird iterativ der Standort hinzugefügt, der den größten zusätzlichen Nutzen

$\Delta F(c\mid S)=F(S\cup\{c\})-F(S)$

erzeugt.

Damit wird berücksichtigt, dass zwei nahe beieinanderliegende Filialen teilweise dieselben Kunden ansprechen.

## 19. Gesamte mathematische Logik

Die Datenanalyse lässt sich kompakt als folgende Prozesskette darstellen:

```text
Rohdaten
   ↓
räumliches H3-Raster
   ↓
Distanzgewichtung
   ↓
Nachfrage + Tagesfrequenz + Affinität
   ↓
Potenzial P_c
   ↓
Wettbewerbsdruck K_i
   ↓
Standortscore U_c
```

Parallel dazu läuft die empirische Analyse:

```text
Standortmerkmale
   ↓
Poisson-/Negativ-Binomial-Regression
   ↓
erwartete Anbieterzahl ŷ_c
   ↓
Angebotslücke g_c
```

Die finale Standortentscheidung basiert damit nicht auf **einer einzigen künstlichen Kennzahl**, sondern auf drei Ebenen:

**Attraktivität + statistische Angebotslücke + Robustheit**

Damit verbindet die Analyse ein strukturelles Nachfragemodell mit einer empirischen Prüfung des vorhandenen Angebots und einer Robustheitsanalyse der Modellannahmen.
