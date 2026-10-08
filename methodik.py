"""Die Ansichten "Analyse" und "Datengrundlage": Methodik als Beratungs-Deck.

Jede Überschrift ist ein Satz mit Aussage und einer live gerechneten Zahl. Alle Zahlen stammen aus data/ und aus
analyse.PARAMETER beziehungsweise datengrundlage.py. Nach einem neuen Lauf von analyse.py stimmt alles ohne Codeänderung.
Hilfsfunktionen und Farben bekommt das Modul von app.py über das Objekt H, damit es keinen Import im Kreis gibt.
"""
import json
from html import escape
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import analyse
import datengrundlage as dg

DATA = Path(__file__).parent / "data"
STAEDTE = {"München": "muenchen", "Frankfurt": "frankfurt", "Berlin": "berlin"}
FARBE_STADT = {"München": "#0B1B4D", "Frankfurt": "#2C6EF2", "Berlin": "#009DE0"}
P = analyse.PARAMETER


# ------------------------------------------------------------------------------------------------ Daten laden
def _json(name):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


@st.cache_data
def _scored(key, stand):
    return pd.read_csv(DATA / f"{key}_scored.csv")


@st.cache_data
def _grid(key, stand):
    return pd.read_csv(DATA / f"{key}_grid.csv")


@st.cache_data
def _pois(key, stand):
    return pd.read_csv(DATA / f"{key}_pois.csv")


def _stand(name):
    """Änderungszeitpunkt der Datei, damit neue Ergebnisse den Cache ungültig machen."""
    p = DATA / name
    return p.stat().st_mtime if p.exists() else 0.0


def scored(key):
    return _scored(key, _stand(f"{key}_scored.csv"))


def grid(key):
    return _grid(key, _stand(f"{key}_grid.csv"))


def pois(key):
    return _pois(key, _stand(f"{key}_pois.csv"))


def verfuegbar():
    return {n: k for n, k in STAEDTE.items() if (DATA / f"{k}_scored.csv").exists() and (DATA / f"{k}_grid.csv").exists()}


@st.cache_data
def kennzahlen(stand):
    """Alle Kennzahlen je Stadt, einmal gerechnet. stand ändert sich, wenn eine Datei neu geschrieben wird."""
    out = {}
    for name, k in verfuegbar().items():
        s = scored(k)
        stadt = s[s["in_stadt"]]
        lagen = stadt[stadt["rang"].notna()]
        gemessen = stadt[stadt["miete_qm"].notna() & ~stadt["miete_geschaetzt"].astype(bool)]
        median = float(gemessen["miete_qm"].median())
        verh = gemessen["miete_qm"] / median
        pl = _json(f"{k}_plausibilitaet.json") or {}
        pca = _json(f"{k}_pca.json") or {}
        bewohnt = stadt[stadt["einwohner"] > 0]
        mit_miete = bewohnt[bewohnt["miete_qm"].notna()]
        top10 = lagen.nsmallest(10, "rang")
        out[name] = {
            "key": k, "zellen_gesamt": len(s), "zellen": len(stadt), "lagen": len(lagen),
            "anteil_lagen": len(lagen) / len(stadt), "einwohner": float(stadt["einwohner"].sum()),
            "unbewohnt": float((stadt["einwohner"] == 0).mean()), "median_miete": median,
            "k_min": float(np.quantile(verh, P["k_quantil_unten"])), "k_max": float(np.quantile(verh, P["k_quantil_oben"])),
            "miete_geschaetzt": float(mit_miete["miete_geschaetzt"].astype(bool).mean()) if len(mit_miete) else float("nan"),
            "alter_geschaetzt": float(bewohnt["alter_geschaetzt"].astype(bool).mean()) if len(bewohnt) else float("nan"),
            "milieu_anteil": float((stadt["m_milieu"] < 0.9).mean()), "milieu_min": float(stadt["m_milieu"].min()),
            "konsens": int(lagen["konsens"].sum()), "konsens_top10": int(top10["konsens"].sum()),
            "plaus": pl.get("anteil_pois_in_top_zellen"), "pca_var": pca.get("erklaerte_varianz_pc1"),
            "pca_variante": pca.get("variante"), "pca_korr": pca.get("korrelation_mit_gesamtdichte"),
            "mittag": float((lagen["profil"] == "Mittagsstandort").mean()), "ganztag": float((lagen["profil"] == "Ganztagsstandort").mean()),
            "abend": float((lagen["profil"] == "Feierabendstandort").mean()),
            "w_top10": float(top10["w"].median()), "index_top10": (float(top10["score_index"].min()), float(top10["score_index"].max()))
            if "score_index" in top10 else (float("nan"), float("nan")),
        }
    return out


def kz():
    stand = sum(_stand(f"{k}_scored.csv") for k in STAEDTE.values()) + _stand("luecke_modell.json")
    return kennzahlen(stand)


def f0(x): return f"{x:,.0f}".replace(",", ".")
def f1(x): return f"{x:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
def f2(x): return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
def pct(x, nk=0): return (f"{x * 100:.{nk}f}").replace(".", ",") + " %"


# ------------------------------------------------------------------------------------------------ Bausteine
def kasten(titel, frage, html):
    st.markdown(f'<div class="kasten"><h4>{escape(titel)}</h4><div class="frage-k">{escape(frage)}</div>{html}</div>', unsafe_allow_html=True)


def zahlen(kacheln, spalten=3):
    html = "".join(f'<div class="zahl"><b>{escape(z)}</b><span>{escape(t)}</span></div>' for z, t in kacheln)
    st.markdown(f'<div class="zahlen" style="grid-template-columns: repeat({spalten}, 1fr)">{html}</div>', unsafe_allow_html=True)


def abschnitt(H, anker, titel, untertitel=""):
    u = f'<span class="klein">{escape(untertitel)}</span>' if untertitel else ""
    st.markdown(f'<div id="{anker}"></div><div class="vkopf">{escape(titel)}{u}</div>', unsafe_allow_html=True)


def aktionstitel(text):
    st.markdown(f'<div class="atitel">{escape(text)}</div>', unsafe_allow_html=True)


def pipeline(schritte):
    """Horizontale Pipeline. schritte: (Nummer, Titel, Text, Anker oder None)."""
    html = ""
    for nr, titel, text, anker in schritte:
        a0, a1 = (f'<a href="#{anker}" style="text-decoration:none;color:inherit">', "</a>") if anker else ("", "")
        html += f'<div class="pstep">{a0}<div class="n">{escape(nr)}</div><b>{escape(titel)}</b><span>{text}</span>{a1}</div>'
    st.markdown(f'<div class="pipe">{html}</div>', unsafe_allow_html=True)


def schritt(nr, titel, formel, klartext, herleitung, beleg):
    """Ein Methodikschritt: links Aussage, Formel und Klartext, rechts der Beleg aus den Daten."""
    links, rechts = st.columns([1.05, 1], gap="medium")
    with links:
        aktionstitel(f"{nr}  {titel}")
        st.latex(formel)
        erster = klartext.split(". ")[0].rstrip(".") + "."
        st.markdown(f'<p class="klartext">{erster}</p>', unsafe_allow_html=True)
    with rechts:
        beleg()


# ------------------------------------------------------------------------------------------------ Analyse
def analyse_ansicht(H, stadt, key):
    daten = kz()
    if not daten:
        st.info("Noch keine Ergebnisse. Bitte `python analyse.py` ausführen.")
        return
    lm = _json("luecke_modell.json") or {}
    koef, se = lm.get("koeffizienten", {}), lm.get("standardfehler", {})
    n_k = sum(d["konsens"] for d in daten.values())
    pl_werte = [d["plaus"] for d in daten.values() if d["plaus"] is not None]
    dev_out = lm.get("erklaerte_devianz_ausserhalb")
    s = scored(key)
    s_stadt = s[s["in_stadt"]]
    lagen = s_stadt[s_stadt["rang"].notna()]
    d = daten.get(stadt) or next(iter(daten.values()))

    H.kopf("Analyse", f"Zwei unabhängige Sichten finden {n_k} Konsens-Standorte in {len(daten)} Städten, und beide halten Tests gegen reale Läden stand")

    # 0 Executive Summary
    zahlen([
        (f"{n_k} Konsens-Standorte", " · ".join(f"{n} {v['konsens']}" for n, v in daten.items()) + ". Konsens heißt: Score (Huff-Modell) und Angebotslücke (Regression) liegen beide im obersten Zehntel."),
        (f"{min(pl_werte) * 100:.0f} bis {max(pl_werte) * 100:.0f} %", "der Feinkostläden liegen in den 20 % Zellen mit dem höchsten Potenzial. Bei Zufall wären es 20 %."),
        (f"{dev_out * 100:.0f} %" if dev_out is not None else "–", "der Ladenverteilung erklärt das Umfeld außerhalb der Stichprobe (räumliche Kreuzvalidierung)."),
    ])
    pipeline([
        ("1 Raster", "Distanz", "Nähe zählt, 1.500 m Reichweite", "a1"),
        ("2 Nachfrage", "Anwohner und Tag", "Einwohner, Miete, Alter, Frequenz", "a1"),
        ("3 Umfeld", "Affinität und Milieu", "Passung des Umfelds, Malus für Problemlagen", "a1"),
        ("4 Score", "Huff-Modell", "Potenzial mal Wettbewerbsfreiheit", "a1"),
        ("5 Lücke", "Regression", "Erwartete minus vorhandene Läden", "a2"),
        ("6 Absicherung", "Tests und Portfolio", "Plausibilität, Robustheit, Portfolio", "a4"),
    ])

    # 1 Sicht A
    abschnitt(H, "a1", "1 · Sicht A: Der Score, in sechs Schritten", "Wie viel passende Nachfrage würde ein neuer Laden gewinnen?")
    umweg, dmax, dself = P["umwegfaktor"], P["d_max_m"], P["d_selbst_m"]
    hA, hT = P["h_anwohner_m"], P["h_tag_m"]

    def beleg1():
        dd = np.arange(0, dmax + 1, 25)
        df_ = pd.DataFrame({"Entfernung (m)": np.tile(dd, 2), "Gewicht": np.concatenate([2.0 ** (-dd / hA), 2.0 ** (-dd / hT)]),
                            "Gruppe": ["Anwohner"] * len(dd) + ["Tagesbevölkerung"] * len(dd)})
        st.altair_chart(H.theme_chart(alt.Chart(df_).mark_line(strokeWidth=3).encode(
            x=alt.X("Entfernung (m):Q", title="Wegstrecke in m"), y=alt.Y("Gewicht:Q", title="Gewicht f(d)", scale=alt.Scale(domain=[0, 1])),
            color=alt.Color("Gruppe:N", scale=alt.Scale(range=["#2C6EF2", "#0B1B4D"]), legend=alt.Legend(orient="bottom", title=None))).properties(height=210)), width="stretch")

    schritt("1", f"Nähe zählt: Nach {hA} m ist nur noch die Hälfte der Nachfrage erreichbar, bei der Tagesbevölkerung schon nach {hT} m.",
            r"f_h:\mathbb{R}_{\ge 0}\to[0,1],\qquad f_h(d)=2^{-d/h}\cdot\mathbf{1}_{\{d\le 1500\}}",
            f"Benachbarte Zellen werden exponentiell weniger in Betracht gezogen. Jede Zelle gibt ihre Nachfrage mit diesem Gewicht an Standorte in der Umgebung ab. Die Wegstrecke ist Luftlinie mal {f1(umweg)}, über {f0(dmax)} m hinaus zählt nichts (Indikatorfunktion).",
            "h ist die Halbwertsdistanz: Bei d = h halbiert sich das Gewicht. Anwohner laufen rund fünf Minuten, die Tagesbevölkerung weniger, weil Mittagspausen kurz sind. Die Wegstrecke wird mit einem Umwegfaktor aus der Luftlinie geschätzt, weil kein Wegenetz verwendet wird.",
            beleg1)

    def beleg2():
        zeilen = "".join(f"<tr><td>{escape(n)}</td><td>{f2(v['median_miete'])} €/m²</td><td>{f2(v['k_min'])}</td><td>{f2(v['k_max'])}</td></tr>" for n, v in daten.items())
        st.markdown(f"<div class='tab'><table><thead><tr><th>Stadt</th><th>Median-Miete</th><th>k min</th><th>k max</th></tr></thead><tbody>{zeilen}</tbody></table></div>"
                    f"<p class='klein'>k ist der Kaufkraftfaktor: Miete der Zelle durch den Stadtmedian, gekappt bei den {int(P['k_quantil_unten'] * 100)}- und {int(P['k_quantil_oben'] * 100)}-Prozent-Quantilen der eigenen Stadt.</p>", unsafe_allow_html=True)

    schritt("2", f"Kaufkraft kommt aus der Miete, aber nur relativ zur eigenen Stadt: Der Median liegt zwischen {f1(min(v['median_miete'] for v in daten.values()))} und {f1(max(v['median_miete'] for v in daten.values()))} €/m².",
            r"N_i=E_i\cdot a_i\cdot h_i\cdot k_i,\quad k_i=\operatorname{clip}\!\left(\tfrac{m_i}{\tilde m},k_{min},k_{max}\right)^{\gamma}",
            "Anwohnernachfrage ist die Zahl der Einwohner (E) mal Anteil der 20- bis 49-Jährigen (a) mal Anteil kleiner Haushalte (h) mal Kaufkraftfaktor (k). Die Miete ist nur ein Ersatz für das fehlende Einkommen.",
            "Der Zensus kennt kein Einkommen. Die Miete ersetzt es, weil teure Viertel meist kaufkräftiger sind. Mieten sind zwischen Städten nicht vergleichbar, deshalb teilt jede Stadt durch ihren eigenen Median. Die Kappung verhindert, dass einzelne Ausreißer das Ergebnis bestimmen. γ steuert, wie stark Kaufkraft zählt.",
            beleg2)

    def beleg3():
        gew = pd.DataFrame({"Kategorie": [c.replace("_", "/") for c in analyse.FREQUENZ], "Gewicht": [P[f"w_{c}"] for c in analyse.FREQUENZ]})
        st.altair_chart(H.theme_chart(alt.Chart(gew).mark_bar(color="#2C6EF2").encode(
            y=alt.Y("Kategorie:N", sort=None, title=None, axis=alt.Axis(labelOverlap=False)), x=alt.X("Gewicht:Q", title="Gewicht je POI"), tooltip=["Kategorie", "Gewicht"]).properties(height=170)), width="stretch")
        st.markdown(f"<p class='klein'>Anteil der Tagesbevölkerung an der Nachfrage: θ = {f1(P['theta'] * 100)} %. Der Index misst keine Personen, nur ein relatives Mehr oder Weniger.</p>", unsafe_allow_html=True)

    schritt("3", f"Die Tagesbevölkerung trägt {int(P['theta'] * 100)} % der Nachfrage und kommt aus Büros, Hochschulen und Haltestellen.",
            r"t_i=\sum_{c\in \text{Frequenz}} w_c\,POI_{c,i},\qquad O^A_i=q_i(1-\theta)\frac{N_i}{\sum_j N_j},\quad O^T_i=q_i\,\theta\,\frac{t_i}{\sum_j t_j}",
            f"Die Quellnachfrage wird in Anwohner (A) und Tagesfrequenz (T) aufgeteilt, gewichtet mit θ = {f1(P['theta'])}. Weil es keine offenen Personenzahlen gibt, zählt für T ein gewichteter Index: Ein Büro bringt mehr Mittagskundschaft als eine Bushaltestelle.",
            "Die Gewichte sind Setzungen mit der Rangfolge Büro, Hochschule, Bahnhof gleich Tram und U-Bahn, dann Bus. Der Robustheitstest variiert sie, hält aber die Rangfolge ein.",
            beleg3)

    def beleg4():
        pca = _json(f"{key}_pca.json") or {}
        lad = pca.get("ladungen", {})
        if lad:
            ld = pd.DataFrame({"Kategorie": list(lad), "Ladung": list(lad.values())})
            st.altair_chart(H.theme_chart(alt.Chart(ld).mark_bar(color="#009DE0").encode(
                y=alt.Y("Kategorie:N", sort="-x", title=None, axis=alt.Axis(labelOverlap=False)), x=alt.X("Ladung:Q", title=f"Ladung auf der ersten Komponente, {stadt}"), tooltip=["Kategorie", "Ladung"]).properties(height=230)), width="stretch")
        st.markdown(f"<p class='klein'>Variante: {escape(str(pca.get('variante', '–')))} (Rückfall auf den Affinitätsanteil, wenn die Komponente nur Zentralität misst: Korrelation mit der Gesamtdichte über 0,9; hier {f2(pca.get('korrelation_mit_gesamtdichte', 0))}).</p>", unsafe_allow_html=True)

    pv = [v["pca_var"] for v in daten.values() if v["pca_var"] is not None]
    schritt("4", f"Eine einzige Achse erklärt {min(pv) * 100:.0f} bis {max(pv) * 100:.0f} % der Unterschiede im Umfeld, deshalb reicht ein Affinitätsfaktor.",
            r"s_{c,i}=\sum_j POI_{c,j}\,f(d_{ij})\ \ (c\in\text{AFFINITÄT}),\qquad A_i=\langle v_1,z_i\rangle,\quad q_i=q_{min}+(q_{max}-q_{min})\,PR(A_i)",
            f"Die Standortaffinität zieht latente Faktoren aus geglätteten Kategoriendichten. Der Affinitätsindex A ist die orthogonale Projektion der standardisierten Dichten z auf die erste Hauptkomponente v₁. Sie fasst {len(analyse.AFFINITAET)} Kategorien zusammen, der Faktor q liegt zwischen {f1(P['q_min'])} und {f1(P['q_max'])}.",
            "Je Kategorie wird die geglättete Dichte gebildet, logarithmiert und je Stadt standardisiert. Die erste Hauptkomponente v1 ist die Richtung mit der größten gemeinsamen Streuung. Der Prozentrang übersetzt den Index in den Faktor q.",
            beleg4)

    def beleg5():
        zeilen = "".join(f"<tr><td>{escape(n)}</td><td>{pct(v['milieu_anteil'])}</td><td>{f2(v['milieu_min'])}</td></tr>" for n, v in daten.items())
        st.markdown(f"<div class='tab'><table><thead><tr><th>Stadt</th><th>Zellen mit Abzug (m &lt; 0,9)</th><th>stärkster Abzug</th></tr></thead><tbody>{zeilen}</tbody></table></div>", unsafe_allow_html=True)
        if "Frankfurt" in daten:
            fr = scored(daten["Frankfurt"]["key"])
            fr = fr[fr["in_stadt"] & fr["rang"].notna()]
            z = fr.nsmallest(1, "m_milieu").iloc[0]
            med = daten["Frankfurt"]["median_miete"]
            st.markdown(f"<p class='klein'>Beispiel Frankfurter Bahnhofsviertel: Eine Geschäftslage mit m = {f2(z['m_milieu'])} hat eine Miete von {f2(z['miete_qm'] / med)}-mal dem Stadtmedian. Der Malus trifft also auch teure Lagen.</p>", unsafe_allow_html=True)

    mi = [v["milieu_anteil"] for v in daten.values()]
    schritt("5", f"Spielhallen und Rotlicht dämpfen die Anziehung eines Standorts, das betrifft {min(mi) * 100:.0f} bis {max(mi) * 100:.0f} % der Stadtzellen.",
            r"m_k=\max\!\left(0{,}2,\ 2^{-\frac{1}{2}\sum_j M_j\,f_{250}(d_{kj})}\right)",
            f"Der standortspezifische Milieu-Malus m_k dämpft die Anziehung eines Standorts k. M_j zählt {', '.join(analyse.MILIEU[:3])} und weitere Orte im 250-m-Umfeld. Je zwei gewichtete Orte halbiert sich die Anziehung, der Malus fällt nie unter {f1(P['m_min'])}.",
            "Es gibt keine offenen kleinräumigen Kriminalitätsdaten. Das Milieu wird deshalb über konkrete Orte erfasst, nicht über Bevölkerungsgruppen. Das ist methodisch sauberer und vermeidet Diskriminierung.",
            beleg5)

    a_neu, a_0 = P["a_neu"], P["a_0"]
    vor_tuer = a_neu * 2.0 ** (-dself / hA) / (a_neu * 2.0 ** (-dself / hA) + a_0)

    def beleg6():
        zahlen([(f"{vor_tuer * 100:.0f} %", f"gewinnt ein Laden vor der Tür ohne Wettbewerb (a_neu = {f1(a_neu)}, a₀ = {f2(a_0)}, Abstand {dself} m)"),
                (f"{d['w_top10'] * 100:.0f} %", f"des Potenzials bleiben an den Top-10-Standorten in {stadt} nach dem Wettbewerb übrig (Median von W)")], spalten=2)
        st.markdown("<p class='klein'>Der Rest kauft online, woanders oder gar nicht (Außenoption a₀). Sie darf nie null sein, sonst gewänne jeder Laden alles.</p>", unsafe_allow_html=True)

    schritt("6", f"Bestehende Läden schöpfen an den Top-10-Standorten in {stadt} einen großen Teil des Potenzials ab: Es bleiben {d['w_top10'] * 100:.0f} %.",
            r"U_c=\sum_i O_i\,\frac{a_{neu}\,m_c\,f(d_{ic})}{a_{neu}\,m_c\,f(d_{ic})+K_i+a_0},\qquad W_c=\frac{U_c}{P_c}",
            "Das Huff-Modell verteilt die Nachfrage jeder Quellzelle auf alle Läden in Reichweite. U ist der relative Marktanteil des neuen Ladens (Huff-Score), P das Monopolpotenzial, also derselbe Wert ohne Wettbewerb. Die Wettbewerbsfreiheit W = U/P ist der Anteil, den die Konkurrenz übrig lässt.",
            "K_i ist der Wettbewerbsdruck an der Quelle: die mit α gewichtete Zahl bestehender Läden in der Umgebung. Markthalle 3, Bio-Markt 2, Feinkost 1, Supermarkt 0,5, Bäcker 0,2. Gastronomie zählt nicht als Wettbewerb, sondern als Affinität. Weil K ≥ 0, gilt immer U ≤ P.",
            beleg6)


    # 2 Sicht B
    abschnitt(H, "a2", "2 · Sicht B: Die Angebotslücke", "Wo gibt es weniger Läden, als das Umfeld erwarten lässt?")
    aktionstitel(f"Das Umfeld erklärt rund {dev_out * 100:.0f} % der Ladenverteilung, der Rest ist die Lücke." if dev_out is not None else "Das Umfeld erklärt einen Teil der Ladenverteilung, der Rest ist die Lücke.")
    st.latex(r"y_c\sim \mathrm{NB}(\mu_c,\phi),\quad \operatorname{Var}(y_c)=\mu_c+\phi\,\mu_c^2")
    st.latex(r"\log\mu_c=\beta_0+\delta_{\text{Stadt}(c)}+X_c^{\top}\beta+S_c,\qquad S_c=\sum_k b_k\exp\!\left(-\frac{d_{ck}^2}{2s^2}\right)")
    st.markdown("<p class='klartext'>Zielgröße y: direkte Wettbewerber je Zelle. Fünf distanzgeglättete Merkmale X erklären sie, räumliche Gauß-Kerne S fangen den Rest der Nachbarschaft auf.</p>", unsafe_allow_html=True)
    st.latex(r"(\hat\beta,\hat b)=\arg\max\left(\log L-\tfrac{\lambda}{2}\|b\|_2^2\right)")
    st.markdown(f"<p class='klartext'>Ridge-Strafe auf die Kern-Gewichte b. λ minimiert die Devianz außerhalb der Stichprobe (gewählt: λ = {f0(lm.get('s_lambda', 0))}).</p>", unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        H.exhibit_titel("Modellvergleich", f"Test-Devianz, kleiner ist besser. Gewählt: {str(lm.get('variante', '–')).replace('_', ' ')}")
        td = lm.get("test_devianz", {})
        if td:
            md = pd.DataFrame({"Modell": [m.replace("_", " ") for m in td], "Devianz": list(td.values()), "Gewählt": [m == lm.get("variante") for m in td]})
            st.altair_chart(H.theme_chart(alt.Chart(md).mark_bar().encode(
                y=alt.Y("Modell:N", sort=None, title=None, axis=alt.Axis(labelLimit=200)), x=alt.X("Devianz:Q", title="Test-Devianz −2 log L", scale=alt.Scale(zero=False)),
                color=alt.condition("datum.Gewählt", alt.value("#2C6EF2"), alt.value("#B9BDC6")), tooltip=["Modell", alt.Tooltip("Devianz:Q", format=".0f")]).properties(height=170)), width="stretch")
        st.markdown(f"<p class='klein'>Auswahlregel: Ein komplexeres Modell nur, wenn es die Test-Devianz um mindestens {int(P['min_verbesserung_modell'] * 100)} % senkt. Welche Variante gilt, steht in luecke_modell.json.</p>", unsafe_allow_html=True)
    with c2:
        H.exhibit_titel("Treiber", "Koeffizient mit ±1,96 Standardfehler, standardisierte Merkmale")
        if koef:
            kd = pd.DataFrame([{"Merkmal": m, "Koeffizient": koef[m], "lo": koef[m] - 1.96 * se.get(m, 0), "hi": koef[m] + 1.96 * se.get(m, 0)} for m in analyse.MERKMALE if m in koef])
            basis = alt.Chart(kd).encode(y=alt.Y("Merkmal:N", sort=None, title=None))
            st.altair_chart(H.theme_chart((basis.mark_rule(strokeWidth=3, color="#8DB4FF").encode(x=alt.X("lo:Q", title="Koeffizient"), x2="hi:Q")
                                            + basis.mark_point(filled=True, size=110, color="#0B1B4D").encode(x="Koeffizient:Q", tooltip=["Merkmal", alt.Tooltip("Koeffizient:Q", format="+.2f")])
                                            + alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color="#98A0B3").encode(x="x:Q")).properties(height=190)), width="stretch")
        neg = lm.get("negative_vorzeichen", [])
        if neg:
            st.markdown(f"<p class='klein'><b>Unerwartetes Vorzeichen:</b> {escape(', '.join(neg))}. Es wird berichtet und nicht korrigiert. Die Standardfehler sind zu klein, weil Nachbarzellen nicht unabhängig sind, sie dienen nur zur Orientierung.</p>", unsafe_allow_html=True)
    st.latex(r"g_c=\sum_{j\in I}(\hat\mu_j-y_j)\,f(d_{cj})")
    st.markdown("<p class='klartext'>Erwartete minus vorhandene Läden, über die Laufweite geglättet. Positiv heißt: Es stehen weniger Läden da, als das Umfeld erwarten lässt.</p>", unsafe_allow_html=True)

    # 3 Konsens
    abschnitt(H, "a3", "3 · Konsens: Wo beide Sichten übereinstimmen")
    aktionstitel(f"In {stadt} liegen {d['konsens']} von {d['lagen']} Geschäftslagen in beiden Sichten im obersten Zehntel, in den Top 10 sind es {d['konsens_top10']}.")
    c1, c2 = st.columns([1.5, 1], gap="medium")
    with c1:
        pts = lagen[["pr_score", "pr_luecke", "rang", "konsens"]].copy()
        pts["Top 10"] = pts["rang"] <= 10
        sw = P["konsens_schwelle"]
        quad = alt.Chart(pd.DataFrame({"x0": [sw], "x1": [100], "y0": [sw], "y1": [100]})).mark_rect(color="#2C6EF2", opacity=0.14).encode(
            x=alt.X("x0:Q", scale=alt.Scale(domain=[0, 100])), x2="x1:Q", y=alt.Y("y0:Q", scale=alt.Scale(domain=[0, 100])), y2="y1:Q")
        punkte = alt.Chart(pts).mark_circle(size=22, opacity=0.45, color="#8DB4FF").encode(
            x=alt.X("pr_luecke:Q", title="Lücken-Perzentil (Sicht B)", scale=alt.Scale(domain=[0, 100])), y=alt.Y("pr_score:Q", title="Score-Perzentil (Sicht A)", scale=alt.Scale(domain=[0, 100])))
        top = alt.Chart(pts[pts["Top 10"]]).mark_circle(size=90, color="#0B1B4D").encode(x="pr_luecke:Q", y="pr_score:Q", tooltip=["rang", "pr_score", "pr_luecke"])
        st.altair_chart(H.theme_chart((quad + punkte + top).properties(height=330)), width="stretch")
    with c2:
        st.latex(r"PR(U)\ge 90\ \wedge\ PR(g)\ge 90")
        st.markdown(f"<p class='klartext'>Sicht A fragt, wie viel Nachfrage ein Laden gewinnt. Sicht B fragt, wo Läden fehlen. Wo beide dasselbe sagen, ist das Urteil am stärksten. Schattiert ist das Konsens-Quadrat, dunkel die Top 10 von {escape(stadt)}.</p>", unsafe_allow_html=True)
        zahlen([(str(v["konsens"]), n) for n, v in daten.items()], spalten=len(daten))

    # 4 Absicherung
    abschnitt(H, "a4", "4 · Absicherung: Wie belastbar ist das?")
    aktionstitel("Drei unabhängige Tests prüfen das Modell gegen reale Läden, gegen unsere Setzungen und gegen unbekannte Gebiete.")
    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        kasten("Plausibilität", "Trifft das Potenzial reale Ladenstandorte?",
               "<ul>" + "".join(f"<li><b>{escape(n)}:</b> {v['plaus'] * 100:.0f} % der Feinkostläden in den oberen 20 % nach Potenzial (Zufall: 20 %).</li>" for n, v in daten.items() if v["plaus"] is not None)
               + "</ul>")
    with c2:
        kasten("Robustheit", f"{f0(P['n_laeufe'])} Läufe mit zufällig variierten Setzungen",
               f"<ul><li>{len(analyse.SPANNEN)} Parameter variiert. Sicher: mindestens 70 % der Läufe in den Top 10.</li></ul>")
    with c3:
        kasten("Räumliche Kreuzvalidierung", f"{P['cv_teile']} Teile, H3-Zellen der Auflösung {P['cv_h3_eltern']} bleiben zusammen",
               f"<ul><li>Erklärte Devianz in der Stichprobe: {lm.get('erklaerte_devianz_in_stichprobe', 0) * 100:.0f} %, außerhalb: {lm.get('erklaerte_devianz_ausserhalb', 0) * 100:.0f} %.</li>"
               "</ul>")

    # 5 Portfolio
    abschnitt(H, "a5", "5 · Portfolio: Fünf Standorte, die sich ergänzen")
    verh = portfolio_faktor(key)
    aktionstitel(f"Das Portfolio aus {P['k_portfolio']} Standorten in {stadt} gewinnt {f2(verh)}-mal so viel Nachfrage wie die {P['k_portfolio']} besten Einzelstandorte." if verh else f"Fünf Standorte, die sich möglichst wenig Kunden wegnehmen.")
    c1, c2 = st.columns([1.2, 1], gap="medium")
    with c1:
        pf = DATA / f"{key}_portfolio.csv"
        if pf.exists():
            ptab = pd.read_csv(pf)
            ptab = pd.DataFrame({"Schritt": ptab["schritt"], "Rang einzeln": ptab["rang_einzeln"].astype(int), "Zugewinn": ptab["zugewinn"].map(lambda x: f"{x:.5f}"), "F nach Schritt": ptab["f_nach_schritt"].map(lambda x: f"{x:.5f}")})
            st.markdown(H.tabelle(ptab), unsafe_allow_html=True)
    with c2:
        st.latex(r"F(S)=\sum_i O_i^{A}\frac{X_i^{A}(S)}{X_i^{A}(S)+K_i^{A}+a_0}+\sum_i O_i^{T}\frac{X_i^{T}(S)}{X_i^{T}(S)+K_i^{T}+a_0}")
        st.markdown(f"<p class='klartext'>Gieriges Verfahren: Jeder Schritt nimmt den Standort mit dem größten Zugewinn. F ist submodular, daher mindestens 1 − 1/e ≈ 63 % des Optimums.</p>", unsafe_allow_html=True)

    # 6 Grenzen
    abschnitt(H, "a6", "6 · Grenzen")
    kasten("Grenzen", "Ehrlich bleiben ist Teil der Methode",
           "<ul><li><b>Modell statt Messung:</b> keine Umsätze, alle Parameter sind Setzungen.</li>"
           "<li><b>Ersatzgrößen:</b> Miete für Kaufkraft, Index für Tagesbevölkerung.</li></ul>")
    H.bumper("Der Score ordnet Standorte, er sagt keinen Umsatz voraus.")
    H.quelle(H.QUELLE)


@st.cache_data
def _portfolio_faktor(key, stand):
    g = grid(key)
    p = dict(P)
    gs, ctx = analyse.bewerte_stadt(g, p)
    _, verh = analyse.portfolio(gs, ctx, p)
    return float(verh)


def portfolio_faktor(key):
    try:
        return _portfolio_faktor(key, _stand(f"{key}_grid.csv") + _stand("../analyse.py"))
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------ Datengrundlage
def daten_ansicht(H):
    daten = kz()
    if not daten:
        st.info("Noch keine Ergebnisse. Bitte `python datengrundlage.py` und `python analyse.py` ausführen.")
        return
    n_poi = {n: len(pois(v["key"])) for n, v in daten.items()}
    gesamt_poi, gesamt_ew = sum(n_poi.values()), sum(v["einwohner"] for v in daten.values())
    gesamt_z = sum(v["zellen"] for v in daten.values())
    gemessen = float(np.mean([1 - v["miete_geschaetzt"] for v in daten.values()]))
    H.kopf("Datengrundlage", f"Zwei offene Quellen, {f0(gesamt_z)} Hexagone in {len(daten)} Städten und {f0(gesamt_poi)} POIs: genug Auflösung, um Straßenzüge zu unterscheiden")
    zahlen([(f"{gesamt_ew / 1e6:.1f} Mio.".replace(".", ","), "Einwohner im Raster der drei Städte"), (f0(gesamt_z), "Hexagone in den Stadtgrenzen, je rund 0,1 km²"),
            (f0(gesamt_poi), "POIs aus OpenStreetMap in 34 Kategorien".replace("34", str(len(analyse.ALLE_KATEGORIEN + analyse.MILIEU)))),
            (pct(gemessen), "der Mietwerte bewohnter Zellen sind gemessen, der Rest aus Nachbarzellen geschätzt")], spalten=4)

    # 1 Pipeline
    abschnitt(H, "d1", "1 · So haben wir mit den Daten gearbeitet")
    aktionstitel("Aus Zensus, OpenStreetMap und Stadtgrenzen wird in sechs Schritten eine Tabelle mit einer Zeile je Hexagon.")
    pipeline([
        ("1 Quellen", "Zwei offene Quellen", "Zensus 2022 (100-m-Gitter, Stand Mai 2022), OpenStreetMap über die Overpass API, amtliche Stadtgrenzen", None),
        ("2 Gebiet", "Stadt plus Puffer", f"Puffer {f0(dg.PUFFER_M)} m: {' · '.join(f'{n} {f0(v['zellen_gesamt'])} gegenüber {f0(v['zellen'])}' for n, v in daten.items())} Zellen", None),
        ("3 Raster", "H3, Auflösung 9", "Zellen von etwa 0,1 km² und 200 m Kantenlänge", None),
        ("4 Zuordnung", "Mittelpunkt entscheidet", "Zensuszellen über den Mittelpunkt, POIs über die Koordinate, Miete nach Wohnungen gewichtet", None),
        ("5 Bereinigung", "Dubletten und Lücken", f"Dubletten unter {dg.DUBLETTEN_RADIUS_M} m entfernt, Miete aus bis zu 2 Ringen Nachbarn, Alter aus dem Stadtwert, jeweils markiert", None),
        ("6 Ergebnis", "Eine Zeile je Hexagon", f"{len(grid(next(iter(daten.values()))['key']).columns)} Spalten in <code>&lt;stadt&gt;_grid.csv</code>", None),
    ])
    fluss = ("<div class='fluss'><div class='fk'>Zensus 2022</div><div class='fk'>OpenStreetMap</div><div class='fk'>Stadtgrenzen</div><i>›</i>"
             "<div class='fk dk'>datengrundlage.py</div><i>›</i><div class='fk'>&lt;stadt&gt;_grid.csv<br><small>&lt;stadt&gt;_pois.csv</small></div><i>›</i>"
             "<div class='fk dk'>analyse.py</div><i>›</i><div class='fk'>&lt;stadt&gt;_scored.csv<br><small>Portfolio · Modell</small></div><i>›</i><div class='fk dk'>App</div></div>")
    st.markdown(fluss, unsafe_allow_html=True)
    H.quelle("Quelle: datengrundlage.py, Specs/datengrundlage_erklaerung.md. Parameter live aus dem Skript.")

    # 2 Was eingeflossen ist
    abschnitt(H, "d2", "2 · Was in die Analyse eingeflossen ist")
    aktionstitel("Jedes Merkmal hat genau eine Aufgabe im Modell.")
    zeilen = [
        ("Soziodemografie", "einwohner, anteil_20_49, anteil_hh_1_3", "Anwohnernachfrage N, Regressionsmerkmale Einwohner und Alter"),
        ("Kaufkraft (Ersatz)", "miete_qm relativ zum Stadtmedian", "Kaufkraftfaktor k in N, Regressionsmerkmal Kaufkraft"),
        (f"Direkter Wettbewerb ({len(analyse.WETTBEWERB_DIREKT)} Kategorien)", ", ".join(analyse.WETTBEWERB_DIREKT), "Wettbewerbsdruck K und Zielgröße y der Regression"),
        (f"Breiter Wettbewerb ({len(analyse.WETTBEWERB_BREIT)})", ", ".join(analyse.WETTBEWERB_BREIT), "Wettbewerbsdruck K mit kleinerem Gewicht α"),
        (f"Affinität ({len(analyse.AFFINITAET)})", ", ".join(analyse.AFFINITAET), "Hauptkomponente, Faktor q, Regressionsmerkmal Affinität"),
        (f"Frequenz ({len(analyse.FREQUENZ)})", ", ".join(analyse.FREQUENZ), "Tagesindex t, Regressionsmerkmal Tag"),
        (f"Milieu ({len(analyse.MILIEU)})", ", ".join(analyse.MILIEU), "Milieu-Malus m"),
        ("Qualitätsflags", "miete_geschaetzt, alter_geschaetzt", "Median der Miete nur aus gemessenen Werten"),
    ]
    c1, c2 = st.columns([1.6, 1], gap="medium")
    with c1:
        st.markdown(H.tabelle(pd.DataFrame(zeilen, columns=["Gruppe", "Merkmale", "Geht ein in"])), unsafe_allow_html=True)
    with c2:
        kasten("Bewusst nicht verwendet", "Was fehlt, und warum",
               "<ul><li><b>Einkommen:</b> Im Zensus nicht vorhanden. Die Miete dient als Ersatz.</li>"
               "<li><b>Herkunft oder Ausländeranteil:</b> Methodisch schwach und diskriminierend. Das Milieu wird über konkrete Orte erfasst.</li>"
               "<li><b>Gastronomie als Wettbewerb:</b> Sie zählt als Affinität, weil sie die Zielgruppe anzieht.</li>"
               "<li><b>Personenzahlen am Tag:</b> Keine offene Quelle, deshalb ein Index.</li></ul>")
    gruppen = []
    for n, v in daten.items():
        pt = pois(v["key"])
        for gname, anz in pt["gruppe"].value_counts().items():
            gruppen.append({"Stadt": n, "Gruppe": gname.replace("_", " "), "POIs": int(anz)})
    if gruppen:
        H.exhibit_titel("POIs je Gruppe und Stadt", "Anzahl, OpenStreetMap")
        st.altair_chart(H.theme_chart(alt.Chart(pd.DataFrame(gruppen)).mark_bar().encode(
            y=alt.Y("Stadt:N", title=None), x=alt.X("POIs:Q", title=None),
            color=alt.Color("Gruppe:N", scale=alt.Scale(range=["#0B1B4D", "#2C6EF2", "#009DE0", "#8DB4FF", "#CEECFF"]), legend=alt.Legend(orient="bottom", title=None)),
            tooltip=["Stadt", "Gruppe", "POIs"]).properties(height=150)), width="stretch")
    H.quelle("Quelle: <stadt>_pois.csv und analyse.py (Kategorienlisten live importiert).")

    # 3 Erkenntnisse
    abschnitt(H, "d3", "3 · Die wichtigsten Erkenntnisse aus der Datengrundlage")
    mieten = {n: v["median_miete"] for n, v in daten.items()}

    def erkenntnis(nr, titel, zahl, heisst, extra=None):
        c1, c2 = st.columns([1.2, 1], gap="medium")
        with c1:
            aktionstitel(f"{nr}. {titel}")
            st.markdown(f"<p class='klartext'>{zahl}</p><p class='klartext'><b>Was heißt das für uns?</b> {heisst}</p>", unsafe_allow_html=True)
        with c2:
            if extra:
                extra()

    def e1():
        df_ = pd.DataFrame({"Stadt": list(mieten), "Median-Miete (€/m²)": list(mieten.values())})
        st.altair_chart(H.theme_chart(alt.Chart(df_).mark_bar().encode(
            y=alt.Y("Stadt:N", title=None), x=alt.X("Median-Miete (€/m²):Q"), color=alt.Color("Stadt:N", scale=alt.Scale(domain=list(FARBE_STADT), range=list(FARBE_STADT.values())), legend=None),
            tooltip=["Stadt", alt.Tooltip("Median-Miete (€/m²):Q", format=".2f")]).properties(height=120)), width="stretch")

    erkenntnis(1, "Die Mieten sind zwischen den Städten nicht vergleichbar, deshalb bewerten wir jede Stadt für sich.",
               "Median-Miete: " + ", ".join(f"{n} {f2(m)} €/m²" for n, m in mieten.items()) + ".",
               "Ein gemeinsamer Maßstab sähe die teuerste Stadt überall vorn. Wir teilen die Miete durch den Median der eigenen Stadt.", e1)

    def e2():
        d2 = pd.DataFrame([{"Stadt": n, "Anteil": a, "Art": t} for n, v in daten.items() for t, a in (("unbewohnt", v["unbewohnt"]), ("Geschäftslage", v["anteil_lagen"]))])
        st.altair_chart(H.theme_chart(alt.Chart(d2).mark_bar().encode(
            x=alt.X("Stadt:N", title=None, axis=alt.Axis(labelAngle=0)), xOffset="Art:N", y=alt.Y("Anteil:Q", axis=alt.Axis(format="%"), title="Anteil der Stadtzellen"),
            color=alt.Color("Art:N", scale=alt.Scale(range=["#B9BDC6", "#2C6EF2"]), legend=alt.Legend(orient="bottom", title=None))).properties(height=170)), width="stretch")

    erkenntnis(2, "Ein großer Teil jeder Stadt ist unbewohnt, die Analyse konzentriert sich auf echte Geschäftslagen.",
               "Unbewohnte Stadtzellen: " + ", ".join(f"{n} {v['unbewohnt'] * 100:.0f} %" for n, v in daten.items()) + ". Geschäftslagen: " + ", ".join(f"{n} {v['anteil_lagen'] * 100:.0f} %" for n, v in daten.items()) + " der Stadtzellen.",
               "Parks, Gleise und Wohnstraßen sind keine Ladenstandorte. Nur Geschäftslagen bekommen einen Rang.", e2)

    wb = {}
    for n, v in daten.items():
        pt = pois(v["key"])
        gz = scored(v["key"])
        gz = gz[gz["in_stadt"]]
        wb[n] = (int((pt["gruppe"] == "wettbewerb_direkt").sum()), float((gz[[f"poi_{c}" for c in analyse.WETTBEWERB_DIREKT]].sum(axis=1) == 0).mean()))
    erkenntnis(3, "Direkte Wettbewerber sind selten: Jede Zelle zählt.",
               "Direkte Wettbewerber: " + ", ".join(f"{n} {f0(a)}" for n, (a, _) in wb.items()) + ". Zellen ohne einen einzigen: " + ", ".join(f"{n} {z * 100:.0f} %" for n, (_, z) in wb.items()) + ".",
               "Bei so vielen Nullen taugt ein lineares Modell nicht. Wir nutzen ein Zählmodell (Negative Binomial) und glätten das Umfeld.")

    pv = {n: v["pca_var"] for n, v in daten.items() if v["pca_var"] is not None}
    erkenntnis(4, "Das Umfeld ist eindimensional: Eine Achse beschreibt drei Viertel der Unterschiede.",
               "Erklärte Varianz der ersten Komponente: " + ", ".join(f"{n} {a * 100:.0f} %" for n, a in pv.items()) + ".",
               f"Die Ladungen sind fast gleich. Deshalb prüfen wir gegen reine Zentralität: Liegt die Korrelation mit der Gesamtdichte über 0,9, gilt der Rückfall auf den Affinitätsanteil. Aktuell: {', '.join(f'{n} {f2(v['pca_korr'])}' for n, v in daten.items() if v['pca_korr'] is not None)}.")

    erkenntnis(5, "Das Milieu betrifft nur wenige, aber zentrale Lagen.",
               "Stadtzellen mit Milieu-Malus (m < 0,9): " + ", ".join(f"{n} {v['milieu_anteil'] * 100:.0f} %" for n, v in daten.items()) + ".",
               "Ein Premium-Konzept hat in Spielhallen- und Rotlicht-Umfeld weniger Anziehung. Der Malus senkt den Score dort, auch bei hoher Miete.")

    dev = (_json("luecke_modell.json") or {}).get("erklaerte_devianz_ausserhalb")
    erkenntnis(6, "Die Daten tragen: Das Potenzial trifft reale Ladenstandorte.",
               "Anteil der Feinkostläden in den oberen 20 % nach Potenzial: " + ", ".join(f"{n} {v['plaus'] * 100:.0f} %" for n, v in daten.items() if v["plaus"] is not None) + " (Zufall: 20 %)."
               + (f" Das Umfeld erklärt außerhalb der Stichprobe {dev * 100:.0f} % der Ladenverteilung." if dev is not None else ""),
               "Das Modell hat Vorhersagekraft, ohne dass Läden in die Nachfrage eingehen. Es ist aber kein Umsatzmodell.")

    def e7():
        pr = pd.DataFrame([{"Stadt": n, "Profil": p_, "Anteil": v[k_]} for n, v in daten.items() for p_, k_ in (("Mittag", "mittag"), ("Ganztag", "ganztag"), ("Feierabend", "abend"))])
        st.altair_chart(H.theme_chart(alt.Chart(pr).mark_bar().encode(
            y=alt.Y("Stadt:N", title=None), x=alt.X("Anteil:Q", stack="normalize", axis=alt.Axis(format="%"), title=None),
            color=alt.Color("Profil:N", scale=alt.Scale(domain=["Mittag", "Ganztag", "Feierabend"], range=["#0B1B4D", "#2C6EF2", "#9DC1FF"]), legend=alt.Legend(orient="bottom", title=None))).properties(height=150)), width="stretch")

    erkenntnis(7, "Die Profile unterscheiden sich je Stadt.",
               "Mittagsstandorte unter den Geschäftslagen: " + ", ".join(f"{n} {v['mittag'] * 100:.0f} %" for n, v in daten.items()) + ".",
               "Mittagsstandorte sprechen eher für Deli und Mitnahme, Feierabendstandorte eher für den Markt. Das Profil entscheidet über das Format.", e7)
    H.quelle("Quelle: <stadt>_scored.csv, <stadt>_pca.json, <stadt>_plausibilitaet.json, luecke_modell.json.")

    # 4 Qualität
    abschnitt(H, "d4", "4 · Datenqualität und Grenzen")
    aktionstitel(f"Die Daten sind flächendeckend und offen, aber {pct(min(v['miete_geschaetzt'] for v in daten.values()))} bis {pct(max(v['miete_geschaetzt'] for v in daten.values()))} der Mietwerte bewohnter Zellen sind geschätzt.")
    ampel = [
        ("Zensus 2022", "<span class='ampel g'></span>", "Amtlich und flächendeckend",
         "Stand Mai 2022, kein Einkommen. Geschätzt (Anteil bewohnter Zellen): " + ", ".join(f"{n} Miete {pct(v['miete_geschaetzt'])}, Alter {pct(v['alter_geschaetzt'])}" for n, v in daten.items()),
         "Geschätzte Werte sind markiert, der Median nutzt nur gemessene Mieten"),
        ("OpenStreetMap", "<span class='ampel y'></span>", "Aktuell und detailliert", "Nicht überall gleich vollständig, ohne Ladengröße und Umsatz", "Dubletten unter 20 m entfernt, Kategorien nach Priorität"),
        ("Distanzen", "<span class='ampel y'></span>", "Einfach und nachvollziehbar", f"Luftlinie mal {f1(P['umwegfaktor'])}, Flüsse und Bahntrassen zählen nicht als Hindernis", "Umwegfaktor als Faustregel, Reichweiten variieren im Robustheitstest"),
    ]
    zeilen_a = "".join(f"<tr><td>{a} <b>{escape(q)}</b></td><td>{escape(s)}</td><td>{escape(w)}</td><td>{escape(u)}</td></tr>" for q, a, s, w, u in ampel)
    st.markdown(f"<div class='tab'><table><thead><tr><th>Quelle</th><th>Stärke</th><th>Schwäche</th><th>Umgang</th></tr></thead><tbody>{zeilen_a}</tbody></table></div>", unsafe_allow_html=True)
    H.quelle("Hinweis: Anteile beziehen sich auf bewohnte Stadtzellen mit Mietwert und sind live aus den grid-Dateien gerechnet.")

    # 5 Lizenzen
    abschnitt(H, "d5", "5 · Quellen und Lizenzen")
    st.markdown("<div class='klartext'><b>Zensus 2022:</b> © Statistisches Bundesamt (Destatis), Zensus 2022, Gitterdaten im 100-m-Raster. Lizenz: Datenlizenz Deutschland, Namensnennung, Version 2.0 (dl-de/by-2-0). "
                "<b>OpenStreetMap:</b> © OpenStreetMap-Mitwirkende, abgefragt über die Overpass API. Lizenz: Open Database License (ODbL) 1.0. Die POI-Daten stehen als abgeleitete Datenbank ebenfalls unter ODbL 1.0.</div>", unsafe_allow_html=True)
    H.quelle("Quelle: data/README.md. Lizenztexte stehen auf den Seiten der Anbieter.")


# ------------------------------------------------------------------------------------------------ Vergleich (Ergebnisseite)
def runde(x, einheit=""):
    """Rundet für den Fließtext: 28.000, 1.200, 90."""
    x = float(x)
    r = round(x, -3) if x >= 10000 else round(x, -2) if x >= 1000 else round(x, -1) if x >= 100 else round(x)
    return f"{r:,.0f}".replace(",", ".") + einheit


def von_zehn(x):
    return f"{round(x * 10):.0f}"


PROFIL_SATZ = {"Mittagsstandort": "Mittagsstandort: Deli mit Mittagstisch und zum Mitnehmen",
               "Feierabendstandort": "Feierabendstandort: Markt mit Einkauf für zu Hause",
               "Ganztagsstandort": "Ganztagsstandort: Mittagsgeschäft und Einkauf nach Feierabend"}


@st.cache_data
def steckbriefe(key, stand, n=5):
    """Die besten n Standorte einer Stadt mit allen Zahlen für den Steckbrief (Umkreis: Feld plus zwei Ringe, etwa 500 m)."""
    import h3
    s = scored(key)
    s_i = s.set_index("h3", drop=False)
    stadt = s[s["in_stadt"]]
    lagen = stadt[stadt["rang"].notna()]
    med_alter = float(stadt.loc[stadt["einwohner"] > 0, "anteil_20_49"].median())
    med_miete = float(stadt.loc[stadt["miete_qm"].notna() & ~stadt["miete_geschaetzt"].astype(bool), "miete_qm"].median())
    direkt = [f"poi_{c}" for c in analyse.WETTBEWERB_DIREKT]
    out = []
    for _, r in lagen.nsmallest(n, "rang").iterrows():
        ring = s_i.loc[s_i.index.intersection(h3.grid_disk(r["h3"], 2))]
        ew = float(ring["einwohner"].sum())
        alter = float((ring["einwohner"] * ring["anteil_20_49"].fillna(0)).sum() / ew) if ew > 0 else float("nan")
        out.append({
            "h3": r["h3"], "lat": float(r["lat"]), "lon": float(r["lon"]), "rang": int(r["rang"]), "konsens": bool(r["konsens"]),
            "sicher": float(r["top10_anteil"]), "profil": r["profil"], "pr_score": float(r["pr_score"]), "index": float(r["score_index"]),
            "pr_pot": float(r["pr_potenzial"]), "pr_wf": float(r["pr_wettbewerbsfreiheit"]), "pr_aff": float(r["pr_affinitaet"]),
            "konkurrenz_anteil": float(1 - r["w"]), "milieu": float(r["m_milieu"]),
            "einwohner": ew, "alter_rel": alter / med_alter if med_alter and not np.isnan(alter) else float("nan"),
            "miete_rel": float(r["miete_qm"]) / med_miete if pd.notna(r["miete_qm"]) else float("nan"),
            "umfeld": int(ring[["poi_cafe", "poi_restaurant"]].fillna(0).sum().sum()),
            "buero": int(ring["poi_buero"].fillna(0).sum()), "halt": int(ring[["poi_tram_ubahn", "poi_bahnhof"]].fillna(0).sum().sum()),
            "vorhanden": float(ring[direkt].fillna(0).sum().sum()), "erwartet": float(ring["y_erwartet"].fillna(0).sum()),
        })
    return out


def punkte(sb):
    """Was den Ort auszeichnet oder bremst: (Symbol, Text). Stärken ab 80, Bremsen unter 40, wie bei staerken_satz()."""
    p = []
    if sb["pr_pot"] >= 80:
        p.append(("+", f"<b>Menschen:</b> rund {runde(sb['einwohner'])} Einwohner im Umkreis von etwa 500 m" + (", überdurchschnittlich viele zwischen 20 und 49" if sb["alter_rel"] > 1.05 else "")))
    if not np.isnan(sb["miete_rel"]) and (sb["miete_rel"] >= 1.2 or sb["miete_rel"] <= 0.85):
        p.append(("+" if sb["miete_rel"] >= 1.2 else "–", f"<b>Kaufkraft:</b> Mieten {abs(sb['miete_rel'] - 1) * 100:.0f} % {'über' if sb['miete_rel'] >= 1 else 'unter'} dem Stadtschnitt"))
    if sb["pr_aff"] >= 80 or sb["umfeld"] >= 60:
        p.append(("+", f"<b>Umfeld:</b> rund {runde(sb['umfeld'])} Cafés und Restaurants in der Nähe"))
    if sb["buero"] >= 30:
        p.append(("+", f"<b>Tagesbetrieb:</b> rund {runde(sb['buero'])} Büros und {sb['halt']} Haltestellen in der Nähe"))
    if sb["erwartet"] > 0:
        if sb["vorhanden"] <= 0.7 * sb["erwartet"]:
            p.append(("+", f"<b>Konkurrenz:</b> {sb['vorhanden']:.0f} Feinkostläden in der Nähe, zu erwarten wären etwa {sb['erwartet']:.0f}"))
        elif sb["vorhanden"] >= 0.9 * sb["erwartet"]:
            p.append(("–", f"<b>Konkurrenz:</b> {sb['vorhanden']:.0f} Feinkostläden stehen schon da, etwa so viele wie zu erwarten"))
    if sb["pr_wf"] < 40:
        p.append(("–", f"<b>Konkurrenz:</b> bestehende Läden binden rund {sb['konkurrenz_anteil'] * 100:.0f} % der Kundschaft"))
    if sb["milieu"] < 0.9:
        p.append(("–", "<b>Umfeld:</b> Abzug wegen Spielhallen oder Wettbüros in der Nähe"))
    return p[:4]


def steckbrief_html(sb, name, nah):
    urteil = ("Doppelt bestätigt" if sb["konsens"] else "Nicht doppelt bestätigt")
    fehlt = sb["erwartet"] > 0 and sb["vorhanden"] <= 0.7 * sb["erwartet"]
    kern = ("Viel passende Kundschaft" if sb["pr_pot"] >= 80 else "Solide Kundschaft") + (", und es fehlen Läden" if fehlt else (", wenig Konkurrenz" if sb["pr_wf"] >= 60 else ", aber schon Konkurrenz vor Ort"))
    pk = "".join(f"<li class='{'plus' if s == '+' else 'minus'}'>{t}</li>" for s, t in punkte(sb))
    sicher = f"bleibt in {sb['sicher'] * 100:.0f} von 100 Testrechnungen unter den besten zehn"
    badge = f"<span class='badge ja'>doppelt bestätigt</span>" if sb["konsens"] else "<span class='badge'>nicht doppelt bestätigt</span>"
    return (f"<div class='sb'><div class='sbkopf'><span class='pin'>{sb['rang']}</span><div><b>{escape(name)}</b><small>{escape(nah)}</small></div></div>"
            f"{badge}<p class='kern'>{kern}. Stärker als {sb['pr_score']:.0f} von 100 Einkaufslagen der Stadt, {sb['index']:.1f}-mal so stark wie eine typische.</p>"
            f"<ul>{pk}</ul><p class='fuss2'><b>Wie sicher?</b> {sicher}.<br><b>Welches Format?</b> {escape(PROFIL_SATZ.get(sb['profil'], ''))}.</p></div>")


def stadt_satz(sbs, key):
    """Aussage-Überschrift je Stadt, aus den Daten abgeleitet."""
    k = sum(x["konsens"] for x in sbs)
    sicher = np.median([x["sicher"] for x in sbs])
    lat, lon = np.array([x["lat"] for x in sbs]), np.array([x["lon"] for x in sbs])
    spanne = np.hypot((lat.max() - lat.min()) * 111, (lon.max() - lon.min()) * 111 * np.cos(np.radians(lat.mean())))
    mittag = sum(x["profil"] == "Mittagsstandort" for x in sbs) >= 3
    if k == 0:
        return "Viel Kundschaft, aber kaum fehlende Läden: Hier zählt die Lage mit dem größten Kundenpotenzial."
    if k >= 4 and sicher >= 0.7:
        return "Die Spitze ist klar und stabil: Alle besten Standorte sind doppelt bestätigt und bleiben auch bei veränderten Annahmen vorn."
    if k >= 4 and spanne < 3:
        return "Die stärksten Standorte bilden ein " + ("Mittags-" if mittag else "") + "Cluster auf engem Raum, etwas weniger sicher, weil sich viele ähnlich starke Orte die Plätze teilen."
    return "Das Bild ist gemischt: Ein Teil der besten Standorte ist doppelt bestätigt."


def _ansicht(pts):
    """Ausschnitt, in dem alle fünf Standorte sichtbar sind. Die Karte ist flach, deshalb wird der Zoom nach der Höhe der Streuung gewählt."""
    import pydeck as pdk
    dlat = (pts["lat"].max() - pts["lat"].min()) * 111.0
    dlon = (pts["lon"].max() - pts["lon"].min()) * 111.0 * float(np.cos(np.radians(pts["lat"].mean())))
    spanne_km = max(dlat * 2.6, dlon * 0.9, 1.2)
    # Zoom 12 zeigt auf 300 px Höhe etwa 4 km; je größer die Streuung, desto kleiner der Zoom
    zoom = float(np.clip(12.0 - np.log2(max(spanne_km, 4.0) / 4.0), 10.5, 14.0))
    return pdk.ViewState(latitude=float(pts["lat"].mean()), longitude=float(pts["lon"].mean()), zoom=zoom, min_zoom=8, max_zoom=17)


def vergleich_ansicht(H):
    import pydeck as pdk
    daten = kz()
    if not daten:
        st.info("Noch keine Ergebnisse. Bitte `python analyse.py` ausführen.")
        return
    stand = sum(_stand(f"{v['key']}_scored.csv") for v in daten.values())
    sb_alle = {n: steckbriefe(v["key"], stand) for n, v in daten.items()}
    n_k = sum(v["konsens"] for v in daten.values())
    pl = [v["plaus"] for v in daten.values() if v["plaus"] is not None]
    gesamt_z = sum(v["zellen"] for v in daten.values())
    gesamt_o = sum(len(pois(v["key"])) for v in daten.values())
    klar = [n for n in daten if sum(x["konsens"] for x in sb_alle[n]) >= 4]
    offen = [n for n in daten if sum(x["konsens"] for x in sb_alle[n]) == 0]
    fazit = (f"{' und '.join(klar)} haben klare, doppelt bestätigte Favoriten." if klar else "Die Favoriten sind nicht überall doppelt bestätigt.") + (f" In {' und '.join(offen)} ist das Bild weniger eindeutig." if offen else "")

    H.kopf("Vergleich", "Wir haben in drei Städten die stärksten Standorte für OLIVE gefunden und doppelt geprüft")

    # 1 Auf einen Blick
    zahlen([(f0(n_k), "Einkaufslagen sind doppelt bestätigt: Beide Rechenwege sehen sie ganz vorn."),
            (f"{von_zehn(min(pl))} bis {von_zehn(max(pl))} von 10", "heutigen Feinkostläden liegen dort, wo wir das meiste Kundenpotenzial sehen. Bei Zufall wären es 2 von 10."),
            (f"{runde(gesamt_z)} Felder", f"und {runde(gesamt_o)} Orte (Läden, Cafés, Büros, Haltestellen) ausgewertet.")], spalten=3)
    aktionstitel(fazit)

    # 2 Datengrundlage
    abschnitt(H, "v2", "Wir haben nur offene, amtliche und für alle Städte gleiche Daten genutzt, damit alles vergleichbar und nachprüfbar ist")
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        kasten("Wer dort lebt", "Amtliche Volkszählung 2022",
               "<ul><li>Wie viele Menschen wohnen in einem Feld, wie viele sind 20 bis 49 Jahre alt, wie viele leben in kleinen Haushalten?</li><li>Die Miete pro Quadratmeter steht für die Kaufkraft.</li></ul>")
    with c2:
        kasten("Was es dort gibt", "Frei zugängliche Online-Karte",
               "<ul><li><b>Konkurrenz:</b> Feinkost, Delis, Bio-Märkte, Weinhandlungen, Supermärkte, Bäcker.</li><li><b>Passendes Umfeld:</b> Cafés, Restaurants, Buchläden, Kultur.</li>"
               "<li><b>Tagesbetrieb:</b> Büros, Hochschulen, Bahnhöfe, Haltestellen. <b>Ungünstiges Umfeld:</b> Spielhallen, Wettbüros.</li></ul>")
    st.markdown("<div class='kasten' style='margin-top:0.6rem'><h4>Warum gerade diese Daten?</h4><ul>"
                "<li><b>Kleinräumig:</b> Felder von etwa 300 × 300 Metern zeigen Straßenzüge, nicht nur Stadtteile.</li>"
                "<li><b>Gleich für alle drei Städte und frei nachrechenbar.</b></li>"
                "<li><b>Ehrliche Ersatzgrößen:</b> Miete statt Einkommen, Büros und Haltestellen statt Passantenzahlen. Herkunft nutzen wir bewusst nicht.</li></ul>"
                "<div class='schwach'>Grenzen: Stand der Volkszählung ist 2022, die Online-Karte ist nicht überall gleich vollständig, Ladengröße und Umsatz kennen wir nicht.</div></div>", unsafe_allow_html=True)

    # 3 Vorgehen
    abschnitt(H, "v3", "So sind wir vorgegangen: berechnen, Lücken suchen, doppelt prüfen")
    pipeline([("1 Kundenpotenzial", "Wie viele Kunden gewinnt ein Laden?", "Wie viele passende Kunden wohnen oder arbeiten in Laufweite, und wie viele nähme ein neuer Laden der Konkurrenz ab?", None),
              ("2 Fehlende Läden", "Wo fehlt etwas?", "Wir haben aus den heutigen Feinkostläden gelernt, welche Viertel sie anziehen. Wo weniger stehen als erwartet, gibt es eine Lücke.", None),
              ("3 Doppelt prüfen", "Beide Wege müssen zustimmen", "Besonders stark ist ein Ort, wenn beide Wege ihn ganz vorn sehen. Alle Annahmen haben wir 1.000-mal leicht verändert.", None)])

    # 4 Ergebnisse
    abschnitt(H, "v4", "Die stärksten Standorte liegen dort, wo Kundschaft, Umfeld und wenig Konkurrenz zusammenkommen, nicht dort, wo am meisten Menschen wohnen")
    cols = st.columns(len(daten), gap="medium")
    for col, (n, v) in zip(cols, daten.items()):
        with col:
            sbs = sb_alle[n]
            mod = pd.Series([x["profil"] for x in sbs]).mode().iloc[0]
            kasten(n, stadt_satz(sbs, v["key"]).split(":")[0].rstrip("."),
                   f"<ul><li><b>{v['konsens']}</b> doppelt bestätigte Einkaufslagen, {sum(x['konsens'] for x in sbs)} von 5 in den Top 5.</li>"
                   f"<li>Typischer Charakter: {escape(mod)}.</li></ul>")

    # 5 White Spots je Stadt
    abschnitt(H, "v5", "Die White Spots je Stadt: fünf Standorte mit klarem Profil")
    gew_stadt = st.segmented_control("Stadt", list(daten), default=list(daten)[0], key="vgl_stadt", label_visibility="collapsed") or list(daten)[0]
    for n, v in [(gew_stadt, daten[gew_stadt])]:  # nur die gewählte Stadt wird gezeichnet, damit die Karte richtig zentriert
        if True:
            sbs = sb_alle[n]
            aktionstitel(f"{n}: {stadt_satz(sbs, v['key'])}")
            po = pois(v["key"])
            namen, nahs = [], []
            for x in sbs:
                vt = H.viertel(round(x["lat"], 4), round(x["lon"], 4))
                namen.append(vt[0] if vt else H.lagebezeichnung({"lat": x["lat"], "lon": x["lon"]}, H.lade_pois(v["key"])))
                nah = H.in_der_naehe(v["key"], round(x["lat"], 4), round(x["lon"], 4), 1)
                nahs.append(("nahe " + nah[0][0]) if nah else n)
            pts = pd.DataFrame({"lat": [x["lat"] for x in sbs], "lon": [x["lon"] for x in sbs], "t": [str(x["rang"]) for x in sbs]})
            with st.container(key="vglkarte"):
              st.pydeck_chart(pdk.Deck(layers=[
                  pdk.Layer("ScatterplotLayer", pts, get_position=["lon", "lat"], get_radius=250, radius_min_pixels=11, radius_max_pixels=11, get_fill_color=[11, 27, 77, 255], stroked=True, get_line_color=[255, 255, 255, 255], line_width_min_pixels=2),
                  pdk.Layer("TextLayer", pts, get_position=["lon", "lat"], get_text="t", get_size=13, get_color=[255, 255, 255, 255])],
                  initial_view_state=_ansicht(pts), map_style=H.karte_style),
                  width="stretch", height=300, key=f"vgl_karte_{v['key']}")
            st.markdown("<div class='sbraster'>" + "".join(steckbrief_html(x, namen[i], nahs[i]) for i, x in enumerate(sbs)) + "</div>", unsafe_allow_html=True)

    # 6 Selbst vergleichen
    with st.expander("Selbst vergleichen: zwei bis fünf Standorte nebeneinander"):
        opts = {f"{n} · Platz {x['rang']}": (n, i) for n, sbs in sb_alle.items() for i, x in enumerate(sbs)}
        wahl = st.multiselect("Standorte wählen", list(opts), default=[f"{n} · Platz 1" for n in daten], max_selections=5, key="vgl_neu")
        if len(wahl) >= 2:
            sel = [sb_alle[opts[w][0]][opts[w][1]] for w in wahl]
            kopf_ = "".join(f"<th>{escape(w)}</th>" for w in wahl)
            def zl(t, fn): return f"<tr><th class='z'>{escape(t)}</th>" + "".join(f"<td>{fn(x)}</td>" for x in sel) + "</tr>"
            tab = (f"<table class='vgl'><thead><tr><th></th>{kopf_}</tr></thead><tbody>"
                   + zl("Stärker als … von 100 Einkaufslagen", lambda x: f"<b>{x['pr_score']:.0f}</b>")
                   + zl("Doppelt bestätigt", lambda x: "<span class='badge ja'>ja</span>" if x["konsens"] else "<span class='badge'>nein</span>")
                   + zl("Wie sicher (von 100 Testrechnungen)", lambda x: f"<b>{x['sicher'] * 100:.0f}</b>")
                   + zl("Anteil Kundschaft bei der Konkurrenz", lambda x: f"{x['konkurrenz_anteil'] * 100:.0f} %")
                   + zl("Einwohner im Umkreis", lambda x: runde(x["einwohner"]))
                   + zl("Cafés und Restaurants", lambda x: runde(x["umfeld"]))
                   + zl("Büros", lambda x: runde(x["buero"]))
                   + zl("Feinkostläden: vorhanden / erwartet", lambda x: f"{x['vorhanden']:.0f} / {x['erwartet']:.0f}")
                   + zl("Format", lambda x: escape(x["profil"].replace("standort", "")))
                   + "</tbody></table>")
            st.markdown(f"<div class='tab vgltab'>{tab}</div><p class='klein'>Alle Werte gelten nur im Vergleich zur eigenen Stadt. Rohwerte sind zwischen Städten nicht vergleichbar.</p>", unsafe_allow_html=True)

    H.bumper("Unsere Rechnung zeigt, wo sich ein Besuch vor Ort lohnt. Sie ersetzt ihn nicht.")
    H.quelle(H.QUELLE)
