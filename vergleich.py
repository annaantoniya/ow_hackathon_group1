"""Die Ansicht "Vergleich": die Ergebnisseite für alle, in einfacher Sprache.

Aufbau nach prompt_vergleich_tab_umbau.md, mit zwei Änderungen: Je Stadt gibt es einen Steckbrief für den besten Standort
(Platz 1) und danach Steckbriefe für die stärksten Viertel, nach derselben Vorgehensweise.
Keine Formeln, keine Spaltennamen, keine Fachbegriffe. Alle Zahlen kommen live aus data/, nach einem neuen Lauf von
analyse.py stimmt alles ohne Codeänderung. Viertelnamen stammen aus assets/viertel_cache.json, nachfüllen mit
python vergleich.py --viertel
Hilfsfunktionen bekommt das Modul von app.py über das Objekt H, wie methodik.py.
"""
import json
import sys
from html import escape
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import streamlit as st

import methodik as M
from methodik import f0, kasten, zahlen

VIERTEL_DATEI = Path(__file__).parent / "assets" / "viertel_cache.json"
DIREKT = ["deli", "feinkost_kaese", "wein", "bio_markt", "reformhaus", "markthalle", "pasta"]
MILIEU = ["spielhalle", "wettbuero", "erotik", "drogenhilfe", "pfandleiher"]
STARK_AB = 90  # ein Feld gehört zu den stärksten Lagen der Stadt, wenn es stärker ist als 90 von 100 Einkaufslagen
N_VIERTEL = 3
FORMAT = {
    "Mittagsstandort": "Mittagsstandort: Deli mit Mittagstisch und To-go.",
    "Feierabendstandort": "Feierabendstandort: Markt mit Einkauf für zu Hause.",
    "Ganztagsstandort": "Ganztagsstandort: Mittagsgeschäft und Einkauf nach Feierabend.",
}
QUELLEN = "Quellen: Statistisches Bundesamt, Volkszählung 2022; OpenStreetMap-Mitwirkende (frei zugängliche Online-Karte)."


# ------------------------------------------------------------------------------------------------ Zahlen in Worten
def rund(x) -> str:
    """Auf zwei geltende Ziffern runden: 28.042 wird 28.000, 8,6 wird 9."""
    if x is None or not np.isfinite(x) or x == 0:
        return "0"
    stellen = max(0, int(np.floor(np.log10(abs(x)))) - 1)
    return f0(round(x, -stellen))


def von100(p) -> str:
    return f"{min(99, max(1, round(p)))} von 100"


def mal(f) -> str:
    return (f"{f:.1f}".replace(".", ",") if f < 3 else f"{f:.0f}") + "-mal"


def gegenueber(f, wort="so viele") -> str:
    """Faktor gegenüber einer typischen Einkaufslage der Stadt in Worten."""
    if not np.isfinite(f):
        return ""
    if f >= 1.95:
        return f"{mal(f)} {wort} wie in einer typischen Einkaufslage der Stadt"
    if f >= 1.15:
        return f"rund {rund((f - 1) * 100)} % mehr als in einer typischen Einkaufslage der Stadt"
    if f > 0.87:
        return "etwa so viele wie in einer typischen Einkaufslage der Stadt"
    return f"rund {rund((1 - f) * 100)} % weniger als in einer typischen Einkaufslage der Stadt"


def sicherheit(a) -> str:
    if a >= 0.9:
        return "sehr sicher"
    if a >= 0.7:
        return "sicher"
    if a >= 0.5:
        return "eher sicher"
    return "unsicher"


def anzahl(n, eins, viele) -> str:
    return f"{f0(n)} {eins if round(n) == 1 else viele}"


def aufzaehlung(teile) -> str:
    return teile[0] if len(teile) == 1 else ", ".join(teile[:-1]) + " und " + teile[-1]


def tag(text, plus=True) -> str:
    return f'<span class="sb-tag {"plus" if plus else "minus"}">{escape(text)}</span>'


# ------------------------------------------------------------------------------------------------ Daten
def viertel_cache() -> dict:
    try:
        return json.loads(VIERTEL_DATEI.read_text(encoding="utf-8"))
    except Exception:
        return {}


def viertel_name(cache, lat, lon):
    v = cache.get(f"{lat:.4f},{lon:.4f}")
    return (v[0], v[1]) if v else (None, None)


@st.cache_data
def _stadt(key, stand):
    """Alles, was die Steckbriefe einer Stadt brauchen: alle Felder, die Einkaufslagen und die Vergleichswerte."""
    v = M.scored(key).set_index("h3", drop=False)
    v["laeden"] = v[[f"poi_{c}" for c in DIREKT]].fillna(0).sum(axis=1)
    v["gastro"] = v[["poi_cafe", "poi_restaurant"]].fillna(0).sum(axis=1)
    v["halt"] = v[["poi_tram_ubahn", "poi_bahnhof"]].fillna(0).sum(axis=1)
    v["milieu_n"] = v[[f"poi_{c}" for c in MILIEU if f"poi_{c}" in v.columns]].fillna(0).sum(axis=1)
    stadt = v[v["in_stadt"]]
    lagen = stadt[stadt["rang"].notna()]
    bewohnt = stadt[stadt["einwohner"] > 0]
    ref = {  # typische Einkaufslage: Mittelwert je Feld über alle Einkaufslagen der Stadt
        "einwohner": float(lagen["einwohner"].mean()), "gastro": float(lagen["gastro"].mean()),
        "buero": float(lagen["poi_buero"].mean()), "halt": float(lagen["halt"].mean()),
        "jung": float(np.average(bewohnt["anteil_20_49"].fillna(0), weights=bewohnt["einwohner"])),
        "miete": float(stadt.loc[stadt["miete_qm"].notna() & ~stadt["miete_geschaetzt"].astype(bool), "miete_qm"].median()),
    }
    return v, lagen, ref


def stadt_daten(key):
    return _stadt(key, M._stand(f"{key}_scored.csv"))


def umfeld(v, zellen) -> dict:
    """Summen und Anteile über eine Menge von Feldern."""
    t = v.loc[v.index.intersection(list(zellen))]
    ew = t["einwohner"].fillna(0)
    mw = t[t["miete_qm"].notna()]
    gew = mw["mietwohnungen"].fillna(0)
    miete = float(np.average(mw["miete_qm"], weights=gew)) if gew.sum() > 0 else float(mw["miete_qm"].mean()) if len(mw) else float("nan")
    return {
        "felder": len(t), "einwohner": float(ew.sum()), "miete": miete,
        "jung": float((t["anteil_20_49"].fillna(0) * ew).sum() / ew.sum()) if ew.sum() else float("nan"),
        "gastro": float(t["gastro"].sum()), "buero": float(t["poi_buero"].sum()), "halt": float(t["halt"].sum()),
        "hochschule": float(t["poi_hochschule"].sum()), "laeden": float(t["laeden"].sum()), "erwartet": float(t["y_erwartet"].sum()),
        "milieu_n": float(t["milieu_n"].sum()),
    }


def warum_hier(u, ref, anteil_tag, ort_text, z=None) -> str:
    """Die Steckbrief-Punkte: Menschen, Kaufkraft, Tagesbetrieb, Umfeld, Konkurrenz. Für alle Steckbriefe gleich."""
    n = max(u["felder"], 1)

    def faktor(k):
        return (u[k] / n) / ref[k] if ref[k] else float("nan")

    f_ew, f_gastro, f_buero = faktor("einwohner"), faktor("gastro"), faktor("buero")
    punkte = []
    jung_plus = np.isfinite(u["jung"]) and u["jung"] - ref["jung"] >= 0.08
    jung = (f", davon {u['jung'] * 100:.0f} % zwischen 20 und 49 Jahren (Stadtschnitt {ref['jung'] * 100:.0f} %)"
            if np.isfinite(u["jung"]) else "")
    punkte.append((f"<b>Menschen:</b> rund {rund(u['einwohner'])} Einwohner {ort_text}{jung}. "
                   f"Das sind {gegenueber(f_ew)}.", f_ew >= 1.15 or (f_ew > 0.87 and jung_plus), f_ew < 0.87 and not jung_plus))
    r = u["miete"] / ref["miete"] if ref["miete"] else float("nan")
    if np.isfinite(r):
        if r >= 1.1:
            k_txt = f"Mieten rund {rund((r - 1) * 100)} % über dem Stadtschnitt, also eher zahlungskräftige Kundschaft."
        elif r <= 0.9:
            k_txt = f"Mieten rund {rund((1 - r) * 100)} % unter dem Stadtschnitt, also eher preisbewusste Kundschaft."
        else:
            k_txt = "Mieten etwa auf dem Niveau der Stadt."
        punkte.append((f"<b>Kaufkraft:</b> {k_txt}", r >= 1.1, r <= 0.9))
    extra = f", {anzahl(u['hochschule'], 'Hochschule', 'Hochschulen')}" if u["hochschule"] else ""
    punkte.append((f"<b>Tagesbetrieb:</b> rund {rund(u['buero'])} Büros{extra} und {anzahl(u['halt'], 'Bahnhof oder Haltestelle', 'Bahnhöfe und Haltestellen')} in der Nähe, "
                   f"{gegenueber(f_buero, 'so viele Büros')}. Etwa {anteil_tag * 100:.0f} % der möglichen Kundschaft kommt tagsüber "
                   f"zum Arbeiten oder Lernen, der Rest wohnt hier.", f_buero >= 1.5, f_buero < 0.87))
    punkte.append((f"<b>Umfeld:</b> rund {rund(u['gastro'])} Cafés und Restaurants in der Nähe, {gegenueber(f_gastro)}.",
                   f_gastro >= 1.5, f_gastro < 0.87))
    erw = u["erwartet"]
    k = (f"<b>Konkurrenz:</b> {anzahl(u['laeden'], 'Feinkostladen, Deli, Bio-Markt oder Weinhandlung', 'Feinkostläden, Delis, Bio-Märkte oder Weinhandlungen')} in der Nähe. "
         f"Für so ein Umfeld wären etwa {rund(erw)} zu erwarten.")
    if z is not None:
        k += f" Die bestehenden Läden, auch Supermärkte und Bäcker, binden rund {rund((1 - z['w']) * 100)} % der Kundschaft."
    stark_besetzt = z is not None and z["pr_wettbewerbsfreiheit"] < 40
    punkte.append((k, u["laeden"] < 0.8 * erw and erw >= 2 and not stark_besetzt, u["laeden"] > 1.2 * erw or stark_besetzt))
    if (z is not None and z["m_milieu"] < 0.9) or (z is None and u["milieu_n"] >= 3):
        punkte.append((f"<b>Ungünstiges Umfeld:</b> {anzahl(u['milieu_n'], 'Spielhalle, Wettbüro oder Ähnliches', 'Spielhallen, Wettbüros oder Ähnliches')} in der Nähe. "
                       "Dafür ziehen wir etwas ab.", False, True))
    li = "".join(f"<li>{txt} {tag('Stärke') if plus else (tag('Bremse', False) if minus else '')}</li>" for txt, plus, minus in punkte)
    return f"<ul>{li}</ul>"


def urteil(z) -> str:
    """Ein Satz Urteil aus denselben Schwellen wie staerken_satz(): ab 80 Stärke, unter 40 Bremse."""
    stark, bremse = [], []
    for spalte, gut, schlecht in (("pr_potenzial", "viel passende Kundschaft", "wenig passende Kundschaft"),
                                  ("pr_affinitaet", "ein passendes Umfeld", "wenig passendes Umfeld"),
                                  ("pr_wettbewerbsfreiheit", "wenig Konkurrenz", "viel Konkurrenz durch bestehende Läden"),
                                  ("pr_luecke", "weniger Feinkostläden als erwartet", "kaum fehlende Läden")):
        if z[spalte] >= 80:
            stark.append(gut)
        elif z[spalte] < 40:
            bremse.append(schlecht)
    satz = aufzaehlung(stark) if stark else "solide Werte ohne große Ausreißer"
    satz = satz[0].upper() + satz[1:]
    if bremse:
        satz += ", aber " + aufzaehlung(bremse)
    zusatz = "doppelt bestätigt" if z["konsens"] else "nicht doppelt bestätigt"
    return f"{satz}. {zusatz[0].upper() + zusatz[1:]} und {sicherheit(z['top10_anteil'])}."


def lage_text(H, key, z):
    teil, _ = viertel_name(viertel_cache(), z["lat"], z["lon"])
    if teil is None:
        v = H.viertel(z["lat"], z["lon"])
        teil = v[0] if v else None
    naehe = H.lagebezeichnung(z, H.lade_pois(key))
    return teil, naehe


# ------------------------------------------------------------------------------------------------ Steckbriefe
def steckbrief_standort(H, name, key) -> str:
    v, lagen, ref = stadt_daten(key)
    z = lagen.nsmallest(1, "rang").iloc[0]
    teil, naehe = lage_text(H, key, z)
    u = umfeld(v, h3.grid_disk(z["h3"], 2))
    badge = '<span class="badge ja">doppelt bestätigt</span>' if z["konsens"] else '<span class="badge">nicht doppelt bestätigt</span>'
    titel = f"Platz 1 · {escape(teil)}" if teil else "Platz 1"
    return (f'<div class="sb"><div class="sb-kopf"><span class="sb-stadt">{escape(name)}</span>{badge}</div>'
            f'<h4>{titel}</h4><div class="sb-ort">{escape(naehe)}</div>'
            f'<p class="sb-urteil">{escape(urteil(z))}</p>'
            f'<div class="sb-kz"><b>{mal(z["score_index"])}</b> so viel Kundenpotenzial wie eine typische Einkaufslage, '
            f'die stärkste von {f0(len(lagen))} Einkaufslagen der Stadt.</div>'
            f'<div class="sb-titel">Warum hier?</div>{warum_hier(u, ref, z["anteil_tag"], "im Umkreis von etwa 600 Metern", z)}'
            f'<div class="sb-fuss"><p><b>Wie sicher?</b> In {von100(z["top10_anteil"] * 100)} Testrechnungen unter den besten zehn der Stadt.</p>'
            f'<p><b>Welches Format passt?</b> {escape(FORMAT.get(z["profil"], str(z["profil"])))}</p></div></div>')


@st.cache_data
def _viertel(key, stand, cache_stand):
    """Die stärksten Viertel: wo liegen die meisten Felder, die stärker sind als 90 von 100 Einkaufslagen der Stadt?"""
    v, lagen, _ = stadt_daten(key)
    cache = viertel_cache()
    stark = lagen[lagen["pr_score"] >= STARK_AB].copy()
    namen = [viertel_name(cache, a, b) for a, b in zip(stark["lat"], stark["lon"])]
    stark["teil"] = [n[0] for n in namen]
    stark["bezirk"] = [n[1] for n in namen]
    ohne = int(stark["teil"].isna().sum())
    gruppen = []
    for teil, g in stark.dropna(subset=["teil"]).groupby("teil"):
        beste = g.nsmallest(1, "rang").iloc[0]
        gruppen.append({"teil": teil, "bezirk": g["bezirk"].dropna().iloc[0] if g["bezirk"].notna().any() else None,
                        "n": len(g), "konsens": int(g["konsens"].sum()), "beste": beste, "rang": int(beste["rang"]),
                        "zellen": sorted({c for h in g["h3"] for c in h3.grid_disk(h, 1)}),
                        "anteil_tag": float(g["anteil_tag"].mean()), "profil": g["profil"].mode().iloc[0]})
    gruppen.sort(key=lambda x: (-x["n"], x["rang"]))
    return gruppen, len(stark), ohne


def staerkste_viertel(key):
    return _viertel(key, M._stand(f"{key}_scored.csv"), VIERTEL_DATEI.stat().st_mtime if VIERTEL_DATEI.exists() else 0.0)


def steckbrief_viertel(name, key, nr, g, n_stark) -> str:
    v, _, ref = stadt_daten(key)
    u = umfeld(v, g["zellen"])
    b = g["beste"]
    bezirk = f"Bezirk {escape(g['bezirk'])}" if g["bezirk"] else escape(name)
    kons = (f", {g['konsens']} davon doppelt bestätigt" if g["konsens"] else ", keine davon doppelt bestätigt")
    badge = '<span class="badge ja">doppelt bestätigt</span>' if g["konsens"] else ""
    flaeche = u["felder"] * 0.105  # ein Feld ist rund 0,1 km² groß
    return (f'<div class="sb"><div class="sb-kopf"><span class="sb-stadt">{escape(name)} · Viertel {nr}</span>{badge}</div>'
            f'<h4>{escape(g["teil"])}</h4><div class="sb-ort">{bezirk}</div>'
            f'<p class="sb-urteil">{g["n"]} der {n_stark} stärksten Lagen der Stadt liegen hier{kons}. '
            f'Die beste davon steht auf Platz {g["rang"]}.</p>'
            f'<div class="sb-kz">Gebiet rund um diese Lagen: {u["felder"]} Felder, etwa {f"{flaeche:.1f}".replace(".", ",")} km².</div>'
            f'<div class="sb-titel">Warum hier?</div>{warum_hier(u, ref, g["anteil_tag"], "in diesem Gebiet")}'
            f'<div class="sb-fuss"><p><b>Wie sicher?</b> Die beste Lage bleibt in {von100(b["top10_anteil"] * 100)} Testrechnungen unter den besten zehn der Stadt.</p>'
            f'<p><b>Welches Format passt?</b> Meistens {escape(FORMAT.get(g["profil"], str(g["profil"])))}</p></div></div>')


# ------------------------------------------------------------------------------------------------ Städte
def stadt_fazit(lagen):
    """Ein Satz Fazit je Stadt, aus den besten fünf Standorten abgeleitet."""
    t5, t10 = lagen.nsmallest(5, "rang"), lagen.nsmallest(10, "rang")
    k5, s5 = int(t5["konsens"].sum()), float(t5["top10_anteil"].median())
    if k5 == 0:
        return "Viel Kundschaft, aber kaum fehlende Läden.", "Hier zählt die Lage mit dem besten Kundenpotenzial. Fehlende Läden sind kein Argument.", k5, s5, t10
    if k5 >= 3 and s5 >= 0.75:
        return "Die Spitze ist klar und stabil.", f"{k5} der besten 5 sind doppelt bestätigt und bleiben meist unter den besten zehn.", k5, s5, t10
    if k5 >= 3:
        return ("Starke Spitze, aber viele ähnlich gute Orte.",
                f"{k5} der besten 5 sind doppelt bestätigt. Viele ähnlich starke Orte teilen sich die vorderen Plätze.", k5, s5, t10)
    return "Gemischtes Bild.", f"Nur {k5} der besten 5 sind doppelt bestätigt.", k5, s5, t10


# ------------------------------------------------------------------------------------------------ Ansicht
def abschnitt(nr, titel, untertitel=""):
    u = f'<span class="klein">{escape(untertitel)}</span>' if untertitel else ""
    st.markdown(f'<div class="vkopf">{nr} · {escape(titel)}{u}</div>', unsafe_allow_html=True)


def ansicht(H):
    daten = M.kz()
    if not daten:
        st.info("Noch keine Ergebnisse. Bitte zuerst die Analyse rechnen.")
        return
    staedte = {n: d["key"] for n, d in daten.items()}
    n_konsens = sum(d["konsens"] for d in daten.values())
    pl = [d["plaus"] for d in daten.values() if d["plaus"] is not None]
    felder = sum(d["zellen"] for d in daten.values())
    orte = sum(len(M.pois(k)) for k in staedte.values())
    ew = sum(d["einwohner"] for d in daten.values())
    fazit = {n: stadt_fazit(stadt_daten(k)[1]) for n, k in staedte.items()}
    klar = [n for n, f in fazit.items() if f[2] >= 3]
    offen = [n for n, f in fazit.items() if f[2] < 3]

    gesamt_fazit = ""
    if klar:
        gesamt_fazit += f"{aufzaehlung(klar)} {'hat' if len(klar) == 1 else 'haben'} klare, doppelt bestätigte Favoriten."
    if offen:
        gesamt_fazit += f" In {aufzaehlung(offen)} ist das Bild weniger eindeutig."

    H.kopf("Vergleich", f"Wir haben {len(staedte)} Städte Feld für Feld durchgerechnet und {n_konsens} doppelt bestätigte Standorte gefunden")

    # 1 Auf einen Blick
    lo, hi = round(min(pl) * 10), round(max(pl) * 10)
    zahlen([
        (f0(n_konsens), f"Standorte in {len(staedte)} Städten sind doppelt bestätigt: Beide Rechenwege sehen sie ganz vorn."),
        (f"{lo} bis {hi} von 10" if lo != hi else f"{lo} von 10",
         "heutigen Feinkostläden liegen dort, wo unsere Rechnung das meiste Kundenpotenzial sieht. Bei Zufall wären es 2 von 10."),
        (f"rund {rund(felder)}", f"Felder von etwa 300 × 300 Metern ausgewertet, mit rund {rund(orte)} Orten wie Cafés, Läden und Haltestellen."),
        (f"{ew / 1e6:.1f}".replace(".", ",") + " Mio.", "Menschen leben in den drei Städten. Jedes Feld ist ein paar Häuserblöcke groß."),
    ], spalten=4)
    H.bumper(gesamt_fazit.strip())

    # 2 Datengrundlage
    abschnitt(2, "Wir haben nur offene, amtliche und für alle drei Städte gleiche Daten genutzt",
              "damit die Ergebnisse vergleichbar und nachprüfbar sind")
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        kasten("Wer dort lebt", "Amtliche Volkszählung 2022",
               "<ul><li>Wie viele Menschen wohnen in jedem Feld, wie viele davon sind 20 bis 49 Jahre alt, wie viele leben in kleinen Haushalten?</li>"
               "<li>Die Miete pro Quadratmeter steht für die Kaufkraft.</li></ul>")
    with c2:
        kasten("Was es dort gibt", "Frei zugängliche Online-Karte, von Freiwilligen gepflegt",
               "<ul><li><b>Konkurrenz:</b> Feinkost, Delis, Bio-Märkte, Weinhandlungen, Supermärkte, Bäcker.</li>"
               "<li><b>Passendes Umfeld:</b> Cafés, Restaurants, Buchläden, Kultur, Yoga-Studios.</li>"
               "<li><b>Tagesbetrieb:</b> Büros, Hochschulen, Bahnhöfe, Haltestellen.</li>"
               "<li><b>Ungünstiges Umfeld:</b> Spielhallen, Wettbüros, Rotlicht.</li></ul>")
    c1, c2 = st.columns([1.7, 1], gap="medium")
    with c1:
        kasten("Warum gerade diese Daten?", "Ein Satz pro Punkt",
               "<ul><li><b>Kleinräumig:</b> Wir wollten Straßenzüge unterscheiden, nicht ganze Stadtteile. Deshalb teilen wir jede Stadt in Felder von etwa 300 × 300 Metern.</li>"
               "<li><b>Gleich für alle drei Städte:</b> Nur so lassen sich München, Frankfurt und Berlin nach denselben Regeln bewerten.</li>"
               "<li><b>Offen und kostenlos:</b> Jeder kann die Ergebnisse nachrechnen.</li>"
               "<li><b>Ehrliche Ersatzgrößen:</b> Einkommen gibt es nicht kleinräumig, deshalb nehmen wir die Miete. Passantenzahlen gibt es nicht offen, "
               "deshalb zählen wir Büros, Hochschulen und Haltestellen. Kriminalitätsdaten gibt es nicht straßengenau, deshalb zählen wir Spielhallen und Wettbüros. "
               "Merkmale wie Herkunft oder Nationalität nutzen wir bewusst nicht.</li></ul>")
    with c2:
        kasten("Was die Daten nicht können", "Gut zu wissen",
               "<ul><li>Die Volkszählung zeigt den Stand von 2022.</li>"
               "<li>Die Online-Karte ist nicht überall gleich vollständig.</li>"
               "<li>Ladengröße und Umsatz kennen wir nicht.</li></ul>")

    # 3 Vorgehen
    abschnitt(3, "So sind wir vorgegangen, in drei Schritten", "Details mit allen Rechenwegen im Tab Analyse")
    laeufe = f0(M.P["n_laeufe"])
    schritte = [
        ("Schritt 1", "Kundenpotenzial berechnen", "Wie viele passende Kunden wohnen oder arbeiten in Laufweite, und wie viele davon würde ein neuer Laden der Konkurrenz abnehmen?"),
        ("Schritt 2", "Fehlende Läden finden", "Aus den heutigen Feinkostläden haben wir gelernt, welche Viertel solche Läden anziehen. Wo weniger stehen, als das Viertel erwarten lässt, gibt es eine Lücke."),
        ("Schritt 3", "Doppelt prüfen", f"Ein Standort ist besonders stark, wenn beide Wege ihn ganz vorn sehen. Zusätzlich haben wir alle Annahmen {laeufe}-mal leicht verändert und geprüft, ob der Ort vorn bleibt."),
    ]
    html = "".join(f'<div class="pstep"><div class="n">{escape(n)}</div><b>{escape(t)}</b><span>{escape(x)}</span></div>' for n, t, x in schritte)
    st.markdown(f'<div class="pipe" style="grid-template-columns: repeat(3, 1fr)">{html}</div>', unsafe_allow_html=True)

    # 4 Ergebnis je Stadt
    rho = np.mean([stadt_daten(k)[1][["pr_score", "einwohner"]].corr(method="spearman").iloc[0, 1] for k in staedte.values()])
    titel4 = ("Die stärksten Standorte liegen nicht einfach dort, wo die meisten Menschen wohnen, sondern wo Kundschaft, Umfeld und wenig Konkurrenz zusammenkommen"
              if rho < 0.5 else "Die stärksten Standorte liegen dort, wo viele Menschen wohnen und wenig Konkurrenz ist")
    abschnitt(4, titel4)
    kh = "".join(f"<th>{escape(n)}</th>" for n in staedte)

    def zeile(titel, hinweis, werte):
        h = f"<small>{escape(hinweis)}</small>" if hinweis else ""
        return f"<tr><th class='z'>{escape(titel)}{h}</th>" + "".join(f"<td>{w}</td>" for w in werte) + "</tr>"

    def charakter(t10):
        p = t10["profil"].value_counts()
        return f"{escape(p.index[0])}<small> {p.iloc[0]} der besten 10</small>"

    tab = (f"<table class='vgl'><thead><tr><th></th>{kh}</tr></thead><tbody>"
           + zeile("Doppelt bestätigte Standorte", "beide Rechenwege sehen sie ganz vorn", [f0(daten[n]["konsens"]) for n in staedte])
           + zeile("Davon unter den besten 10", "", [f"{fazit[n][4]['konsens'].sum()} von 10" for n in staedte])
           + zeile("Typischer Charakter der besten Lagen", "Mittags-, Feierabend- oder Ganztagsstandort", [charakter(fazit[n][4]) for n in staedte])
           + zeile("Wie sicher sind die besten 5?", "Testrechnungen, in denen sie unter den besten zehn bleiben, typischer Wert",
                   [f"{von100(fazit[n][3] * 100)}" for n in staedte])
           + zeile("Fazit", "", [f"{escape(fazit[n][0])}<small>{escape(fazit[n][1])}</small>" for n in staedte])
           + "</tbody></table>")
    st.markdown(f"<div class='tab vgltab'>{tab}</div>", unsafe_allow_html=True)

    # 5 Platz 1 je Stadt
    namen = []
    for n, k in staedte.items():
        z = stadt_daten(k)[1].nsmallest(1, "rang").iloc[0]
        namen.append(lage_text(H, k, z)[0] or n)
    abschnitt(5, f"Die besten Einzelstandorte liegen in {aufzaehlung([f'{t} ({n})' for t, n in zip(namen, staedte)])}",
              "Platz 1 je Stadt mit Steckbrief")
    for spalte, (n, k) in zip(st.columns(len(staedte), gap="medium"), staedte.items()):
        spalte.markdown(steckbrief_standort(H, n, k), unsafe_allow_html=True)

    # 6 Die stärksten Viertel je Stadt
    abschnitt(6, "Die stärksten Viertel: Hier liegen viele starke Lagen dicht beieinander",
              f"je Stadt die {N_VIERTEL} Viertel mit den meisten Lagen, die stärker sind als {STARK_AB} von 100 Einkaufslagen")
    fehlend = 0
    for n, k in staedte.items():
        gruppen, n_stark, ohne = staerkste_viertel(k)
        fehlend += ohne
        if not gruppen:
            st.caption(f"{n}: Für die stärksten Lagen fehlen noch die Viertelnamen.")
            continue
        top = gruppen[:N_VIERTEL]
        st.markdown(f'<div class="atitel">{escape(n)}: Die meisten starken Lagen liegen in {escape(aufzaehlung([g["teil"] for g in top]))}</div>',
                    unsafe_allow_html=True)
        for nr, (spalte, g) in enumerate(zip(st.columns(N_VIERTEL, gap="medium"), top), start=1):
            spalte.markdown(steckbrief_viertel(n, k, nr, g, n_stark), unsafe_allow_html=True)
    if fehlend:
        st.caption(f"Für {fehlend} starke Lagen fehlt noch der Viertelname. Nachladen mit: python vergleich.py --viertel")

    # 7 Selbst vergleichen
    abschnitt(7, "Selbst vergleichen", "zwei bis fünf Standorte, auch aus verschiedenen Städten")
    selbst_vergleichen(H, staedte)

    # 8 Abschluss
    H.bumper("Unsere Rechnung zeigt, wo sich ein Besuch vor Ort lohnt. Sie ersetzt ihn nicht.")
    st.markdown(f'<div class="quelle">{escape(QUELLEN)}</div>', unsafe_allow_html=True)


def selbst_vergleichen(H, staedte):
    """Die frühere Gegenüberstellung, in einfacher Sprache. Die Karte legt Standorte über vgl_extra und vgl_wahl dazu."""
    optionen = {}
    for n, k in staedte.items():
        lagen, po = stadt_daten(k)[1], H.lade_pois(k)
        for _, r in lagen.nsmallest(10, "rang").iterrows():
            optionen[f"{n} · #{int(r['rang'])} {H.lagebezeichnung(r, po)}"] = (k, r["h3"])
    optionen.update(st.session_state.get("vgl_extra", {}))
    standard = [lb for lb in optionen if lb.split(" · ")[1].startswith("#1 ")][:3]
    wahl = st.multiselect("Standorte vergleichen", list(optionen), default=None if "vgl_wahl" in st.session_state else standard,
                          max_selections=5, key="vgl_wahl", label_visibility="collapsed",
                          placeholder="Standorte wählen, auch aus der Karte mit „Zum Vergleich“")
    if len(wahl) < 2:
        st.info("Wähle mindestens zwei Standorte aus.")
        return
    st.markdown("<div class='hinweisbox'>Jede Stadt wird für sich bewertet. Deshalb zeigen wir hier nur Werte im Vergleich zur eigenen Stadt, "
                "zum Beispiel „stärker als 97 von 100 Einkaufslagen der Stadt“.</div>", unsafe_allow_html=True)
    sp = []
    for lb in wahl:
        k, h_ = optionen[lb]
        v, lagen, ref = stadt_daten(k)
        z = v.loc[h_]
        sp.append({"stadt": lb.split(" · ")[0], "ort": lb.split(" · ", 1)[1], "z": z, "u": umfeld(v, h3.grid_disk(h_, 2)), "ref": ref,
                   "lage": pd.notna(z["rang"])})

    def balken(p, i):
        return f'<div class="vb"><i style="width:{max(0, min(100, p)):.0f}%; background:{H.FARBEN[i % len(H.FARBEN)]}"></i></div>'

    def f(x, k):
        n = max(x["u"]["felder"], 1)
        return (x["u"][k] / n) / x["ref"][k] if x["ref"][k] else float("nan")

    zeilen = [
        ("Kundenpotenzial", "stärker als … Einkaufslagen der eigenen Stadt",
         [(f"<b>stärker als {von100(x['z']['pr_score'])}</b>{balken(x['z']['pr_score'], i)}" if x["lage"] else "keine belebte Lage")
          for i, x in enumerate(sp)]),
        ("Fehlende Läden", "stärker als … Einkaufslagen der eigenen Stadt",
         [f"<b>stärker als {von100(x['z']['pr_luecke'])}</b>{balken(x['z']['pr_luecke'], i)}" for i, x in enumerate(sp)]),
        ("Doppelt bestätigt", "", ["<span class='badge ja'>ja</span>" if x["z"]["konsens"] else "<span class='badge'>nein</span>" for x in sp]),
        ("Wie sicher?", "Testrechnungen unter den besten zehn der Stadt",
         [f"{von100(x['z']['top10_anteil'] * 100)}<small> {sicherheit(x['z']['top10_anteil'])}</small>" for x in sp]),
        ("Format", "", [escape(str(x["z"]["profil"])) for x in sp]),
        ("Menschen", "Einwohner im Umkreis von etwa 600 Metern",
         [f"rund {rund(x['u']['einwohner'])}<small> {mal(f(x, 'einwohner'))} typisch</small>" for x in sp]),
        ("Kaufkraft", "Miete im Vergleich zum Stadtschnitt",
         [(f"{(x['u']['miete'] / x['ref']['miete'] - 1) * 100:+.0f} %" if np.isfinite(x["u"]["miete"]) else "–") for x in sp]),
        ("Tagesbetrieb", "Büros in der Nähe; Anteil der Kundschaft, die tagsüber kommt",
         [f"rund {rund(x['u']['buero'])} Büros<small> {x['z']['anteil_tag'] * 100:.0f} % tagsüber</small>" for x in sp]),
        ("Umfeld", "Cafés und Restaurants in der Nähe", [f"rund {rund(x['u']['gastro'])}<small> {mal(f(x, 'gastro'))} typisch</small>" for x in sp]),
        ("Konkurrenz", "Feinkostläden in der Nähe, vorhanden gegenüber erwartet",
         [f"{f0(x['u']['laeden'])} statt etwa {rund(x['u']['erwartet'])}" for x in sp]),
    ]
    kopf_ = "".join(f"<th class='sp{' konsens' if x['z']['konsens'] else ''}'><span class='pkt' style='background:{H.FARBEN[i % len(H.FARBEN)]}'></span>"
                    f"<b>{escape(x['stadt'])}</b><small>{escape(x['ort'])}</small></th>" for i, x in enumerate(sp))
    koerper = "".join(f"<tr><th class='z'>{escape(t)}{f'<small>{escape(h)}</small>' if h else ''}</th>" + "".join(f"<td>{c}</td>" for c in zellen) + "</tr>"
                      for t, h, zellen in zeilen)
    st.markdown(f"<div class='tab vgltab'><table class='vgl'><thead><tr><th></th>{kopf_}</tr></thead><tbody>{koerper}</tbody></table></div>",
                unsafe_allow_html=True)


# ------------------------------------------------------------------------------------------------ Viertelnamen nachladen
def viertel_nachladen():
    """Holt die Viertelnamen aller Lagen, die stärker sind als 90 von 100 Einkaufslagen, über Nominatim (höchstens eine Anfrage pro Sekunde)."""
    import ssl
    import time
    import urllib.request
    try:
        import certifi
        kontext = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        kontext = None
    cache = viertel_cache()
    offen = []
    for k in M.STAEDTE.values():
        p = M.DATA / f"{k}_scored.csv"
        if not p.exists():
            continue
        s = pd.read_csv(p)
        s = s[s["in_stadt"] & s["rang"].notna() & (s["pr_score"] >= STARK_AB)]
        offen += [f"{a:.4f},{b:.4f}" for a, b in zip(s["lat"], s["lon"])]
    offen = [o for o in dict.fromkeys(offen) if o not in cache]
    print(f"{len(offen)} Viertelnamen fehlen, Dauer etwa {len(offen) * 1.2 / 60:.0f} Minuten")
    for i, sch in enumerate(offen, start=1):
        lat, lon = map(float, sch.split(","))
        url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=14&addressdetails=1&accept-language=de&lat={lat:.5f}&lon={lon:.5f}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "olive-whitespot-hackathon/1.0"})
            a = json.load(urllib.request.urlopen(req, timeout=10, context=kontext)).get("address", {})
            teil = a.get("suburb") or a.get("neighbourhood") or a.get("quarter") or a.get("city_district") or a.get("town") or a.get("village")
            bezirk = a.get("city_district") if a.get("city_district") != teil else a.get("borough")
            cache[sch] = [teil, bezirk] if teil else None
        except Exception as e:
            print("Fehler bei", sch, e)
        if i % 25 == 0 or i == len(offen):
            VIERTEL_DATEI.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
            print(f"{i} von {len(offen)}")
        time.sleep(1.1)


if __name__ == "__main__" and "--viertel" in sys.argv:
    viertel_nachladen()
