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
        st.markdown(f'<p class="klartext">{klartext}</p>', unsafe_allow_html=True)
        with st.expander("Herleitung"):
            st.markdown(herleitung)
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
            r"f_h(d)=2^{-d/h},\quad f_h(d)=0 \text{ für } d>d_{max}",
            f"Jede Zelle gibt ihre Nachfrage mit diesem Gewicht an Standorte in der Umgebung ab. Die Wegstrecke ist Luftlinie mal {f1(umweg)}, über {f0(dmax)} m hinaus zählt nichts. Wer nur Mittagspausen nutzt, läuft kürzer als ein Anwohner.",
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
            r"t_i=\sum_{c\in \text{Frequenz}} w_c\cdot POI_{c,i}",
            "Weil es keine offenen Personenzahlen gibt, zählt ein gewichteter Index: Ein Büro bringt mehr Mittagskundschaft als eine Bushaltestelle.",
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
            r"A_i=v_1^{\top}z_i,\quad q_i=q_{min}+(q_{max}-q_{min})\cdot PR(A_i)",
            f"Cafés, Bars, Buchläden, Kultur und ähnliche Orte zeigen, wo sich die Zielgruppe bewegt. Eine Hauptkomponente fasst {len(analyse.AFFINITAET)} Kategorien zusammen, der Faktor q liegt zwischen {f1(P['q_min'])} und {f1(P['q_max'])}.",
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
            r"m_c=\max\!\left(m_{min},\,2^{-s_c/s_{1/2}}\right),\quad s_c=\sum_j M_j f_{h_M}(d_{cj})",
            f"M_j zählt {', '.join(analyse.MILIEU[:3])} und weitere Orte im Umfeld. Bei s = {f1(P['milieu_halbwert'])} halbiert sich die Anziehung, der Malus fällt nie unter {f1(P['m_min'])}.",
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
            "Das Huff-Modell verteilt die Nachfrage jeder Quellzelle auf alle Läden in Reichweite. U ist der Anteil, den der neue Laden gewinnt. P ist derselbe Wert ohne Wettbewerb, W der Anteil, den die Konkurrenz übrig lässt.",
            "K_i ist der Wettbewerbsdruck an der Quelle: die mit α gewichtete Zahl bestehender Läden in der Umgebung. Markthalle 3, Bio-Markt 2, Feinkost 1, Supermarkt 0,5, Bäcker 0,2. Gastronomie zählt nicht als Wettbewerb, sondern als Affinität. Weil K ≥ 0, gilt immer U ≤ P.",
            beleg6)

    # Vom Score zum Rang
    st.markdown("<div class='vkopf' style='font-size:1.05rem'>Vom Score zum Rang</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        kasten("Geschäftslagen-Filter", f"Mindestens {P['n_min_geschaeftslage']} POIs in Zelle und Ring 1",
               f"<ul><li>{' · '.join(f'{n}: {v['anteil_lagen'] * 100:.0f} %' for n, v in daten.items())} der Stadtzellen sind Geschäftslagen.</li>"
               "<li>Parks, Gleise und Wohnstraßen fallen heraus. Nur Geschäftslagen bekommen einen Rang.</li></ul>")
    with c2:
        kasten("Prozentrang und Score-Index", "Referenz sind die Geschäftslagen der Stadt",
               f"<ul><li>Score-Index = U geteilt durch den Median der Geschäftslagen.</li><li>Top 10 in {escape(stadt)}: {f1(d['index_top10'][0])} bis {f1(d['index_top10'][1])}-mal so stark wie eine typische Geschäftslage.</li>"
               "<li>Nur innerhalb einer Stadt vergleichbar.</li></ul>")
    with c3:
        kasten("Profil", f"Quantile von P_T/P: oberste {int((1 - P['profil_quantil_hoch']) * 100)} % Mittag, unterste {int(P['profil_quantil_tief'] * 100)} % Feierabend",
               f"<ul><li>{escape(stadt)}: Mittag {d['mittag'] * 100:.0f} %, Ganztag {d['ganztag'] * 100:.0f} %, Feierabend {d['abend'] * 100:.0f} % der Geschäftslagen.</li>"
               "<li>Mittag spricht eher für Deli, Feierabend eher für Markt.</li></ul>")
    H.quelle(f"{H.QUELLE} Parameter: analyse.PARAMETER. Methodik: Specs/analyse_erklaerung.md.")

    # 2 Sicht B
    abschnitt(H, "a2", "2 · Sicht B: Die Angebotslücke", "Wo gibt es weniger Läden, als das Umfeld erwarten lässt?")
    aktionstitel(f"Das Umfeld erklärt rund {dev_out * 100:.0f} % der Ladenverteilung, der Rest ist die Lücke." if dev_out is not None else "Das Umfeld erklärt einen Teil der Ladenverteilung, der Rest ist die Lücke.")
    st.latex(r"\log\mu_c=\beta_0+\delta_{\text{Stadt}(c)}+\beta^{\top}x_c+S_c,\qquad y_c\sim NB(\mu_c)")
    st.markdown("<p class='klartext'>Zielgröße y ist die Zahl direkter Wettbewerber je Zelle. Fünf Merkmale (Einwohner, Kaufkraft, Alter, Affinität, Tag) erklären, wie viele Läden dort zu erwarten sind. S ist ein räumlicher Effekt für Nachbarschaften, die kein Merkmal fängt.</p>", unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        H.exhibit_titel("Modellvergleich", f"Test-Devianz, kleiner ist besser. Gewählt: {str(lm.get('variante', '–')).replace('_', ' ')}")
        td = lm.get("test_devianz", {})
        if td:
            md = pd.DataFrame({"Modell": [m.replace("_", " ") for m in td], "Devianz": list(td.values()), "Gewählt": [m == lm.get("variante") for m in td]})
            st.altair_chart(H.theme_chart(alt.Chart(md).mark_bar().encode(
                y=alt.Y("Modell:N", sort=None, title=None), x=alt.X("Devianz:Q", title="Test-Devianz −2 log L", scale=alt.Scale(zero=False, domain=[float(min(td.values())) * 0.97, float(max(td.values())) * 1.01])),
                color=alt.condition("datum.Gewählt", alt.value("#2C6EF2"), alt.value("#B9BDC6")), tooltip=["Modell", alt.Tooltip("Devianz:Q", format=".0f")]).properties(height=150)), width="stretch")
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
    st.latex(r"g_c=\sum_j(\hat y_j-y_j)\,f(d_{cj})")
    st.markdown("<p class='klartext'>Die Lücke ist erwartete minus vorhandene Läden, über die Laufweite geglättet. Positiv heißt: Im Umfeld stehen weniger Läden, als die Merkmale erwarten lassen.</p>", unsafe_allow_html=True)
    with st.expander("Warum Negative Binomial und ein räumlicher Effekt?"):
        st.markdown("**Overdispersion und räumliche Abhängigkeit sind zwei verschiedene Probleme.** Bei Poisson gilt Var = μ. Bei Wettbewerberzahlen streuen manche Gebiete deutlich stärker, die Negative Binomial erlaubt Var = μ + φμ². "
                    "Der räumliche Effekt S fängt davon unabhängig Nachbarschaftsähnlichkeit auf, etwa eine nicht gemessene Einkaufsstraße.")
        st.latex(r"\operatorname{Var}(y_c)=\mu_c+\phi\mu_c^2")
        st.markdown("**Warum kein OLS?** Die Zielgröße ist eine Zählvariable mit vielen Nullen. log(0) ist nicht definiert, und ein lineares Modell für log(y) wäre ein anderes statistisches Modell.")
    H.quelle("Quelle: luecke_modell.json, Modell über alle Städte gemeinsam. Methodik: Specs/analyse_erklaerung.md.")

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
    H.quelle(f"Quelle: {key}_scored.csv, Geschäftslagen der gewählten Stadt.")

    # 4 Absicherung
    abschnitt(H, "a4", "4 · Absicherung: Wie belastbar ist das?")
    aktionstitel("Drei unabhängige Tests prüfen das Modell gegen reale Läden, gegen unsere Setzungen und gegen unbekannte Gebiete.")
    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        kasten("Plausibilität", "Trifft das Potenzial reale Ladenstandorte?",
               "<ul>" + "".join(f"<li><b>{escape(n)}:</b> {v['plaus'] * 100:.0f} % der Feinkostläden in den oberen 20 % nach Potenzial (Zufall: 20 %).</li>" for n, v in daten.items() if v["plaus"] is not None)
               + "<li>Nicht zirkulär: Wettbewerber gehen weder in Nachfrage noch Affinität ein.</li></ul>")
    with c2:
        kasten("Robustheit", f"{f0(P['n_laeufe'])} Läufe mit zufällig variierten Setzungen",
               f"<ul><li>Variiert werden {len(analyse.SPANNEN)} Parameter in plausiblen Spannen, darunter Reichweiten, θ und die Wettbewerbsgewichte.</li>"
               "<li>Sicherer Kandidat: mindestens 70 % der Läufe in den Top 10. Wackelig: unter 30 %.</li></ul>")
        t10 = lagen.nsmallest(10, "rang")
        if "top10_anteil" in t10:
            tb = pd.DataFrame({"Rang": [f"#{int(r)}" for r in t10["rang"]], "Anteil": t10["top10_anteil"] * 100})
            st.altair_chart(H.theme_chart(alt.Chart(tb).mark_bar(color="#2C6EF2").encode(
                x=alt.X("Rang:N", sort=None, title=f"Top 10 in {stadt}"), y=alt.Y("Anteil:Q", title="Läufe in den Top 10 (%)", scale=alt.Scale(domain=[0, 100]))).properties(height=140)), width="stretch")
    with c3:
        kasten("Räumliche Kreuzvalidierung", f"{P['cv_teile']} Teile, H3-Zellen der Auflösung {P['cv_h3_eltern']} bleiben zusammen",
               f"<ul><li>Erklärte Devianz in der Stichprobe: {lm.get('erklaerte_devianz_in_stichprobe', 0) * 100:.0f} %, außerhalb: {lm.get('erklaerte_devianz_ausserhalb', 0) * 100:.0f} %.</li>"
               "<li>Benachbarte Zellen liegen nie gleichzeitig in Training und Test. So misst der Test, ob das Modell auch für unbekannte Viertel trägt.</li></ul>")
    H.quelle("Quelle: <stadt>_plausibilitaet.json, <stadt>_scored.csv (top10_anteil), luecke_modell.json.")

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
        st.markdown(f"<p class='klartext'>F ist die gemeinsam gewonnene Nachfrage. Ein gieriges Verfahren nimmt in jedem Schritt den Standort mit dem größten Zugewinn. Weil F submodular ist, erreicht es mindestens 1 − 1/e ≈ 63 % des Optimums. Der Zugewinn sinkt von Schritt zu Schritt, weil sich die Standorte Kunden teilen.</p>", unsafe_allow_html=True)
    H.quelle(f"Quelle: {key}_portfolio.csv; Faktor aus analyse.portfolio() live berechnet.")

    # 6 Grenzen
    abschnitt(H, "a6", "6 · Grenzen")
    kasten("Was das Modell nicht kann", "Ehrlich bleiben ist Teil der Methode",
           "<ul><li><b>Modell statt Messung:</b> Es kennt keine Umsätze und ist nicht kalibriert. Alle Parameter sind Setzungen, der Robustheitstest zeigt ihren Einfluss.</li>"
           "<li><b>Miete statt Kaufkraft:</b> Bestandsmieten vom Mai 2022 sind nur ein Ersatz für das fehlende Einkommen.</li>"
           "<li><b>Index statt Personenzahl:</b> Die Tagesbevölkerung ist ein gewichteter Index. Distanzen sind Luftlinie mal 1,3 ohne Hindernisse.</li></ul>")
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
