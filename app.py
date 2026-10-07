"""Decision Platform: White Spots für einen Premium-Food-Market.

Liest nur fertige Dateien aus data/ und rechnet nichts Schweres (Spec, Abschnitt 8).
Fehlen die echten Dateien, nimmt die App die Demo-Daten aus data/demo/ (python analyse.py --demo).
Aufbau: Alles Wichtige passt in eine Bildschirmhöhe. Blau gehört den Daten und aktiven Elementen,
Flächen und Rahmen bleiben neutral. Start: streamlit run app.py
"""
import json
from html import escape
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st
from sklearn.neighbors import BallTree

DATA = Path(__file__).parent / "data"
DEMO = DATA / "demo"
STAEDTE = {"München": "muenchen", "Frankfurt": "frankfurt", "Berlin": "berlin"}
ERDRADIUS_M = 6_371_000
WETTBEWERB_DIREKT = ["deli", "feinkost_kaese", "wein", "bio_markt", "reformhaus", "markthalle", "pasta"]
ANSICHTEN = ["Karte", "Rangliste", "Vergleich", "Erklärung", "Annahmen"]

# Farben: Midnight für Struktur, Bright Blue für Bedienung, Sky und Blau für Daten, Coral nur für die Top 10
MIDNIGHT, BLUE, BRIGHT, SKY, CORAL, GREY = "#0B1B4D", "#002C77", "#2C6EF2", "#009DE0", "#EF4E45", "#6B7079"
RAMPE_HELL = [(206, 236, 255), (0, 157, 224), (0, 44, 119), (11, 27, 77)]  # dunkel = hoch
RAMPE_DUNKEL = [(30, 42, 120), (44, 110, 242), (0, 157, 224), (206, 236, 255)]  # auf dunkler Karte: hell = hoch
NICHT_LAGE_HELL, NICHT_LAGE_DUNKEL = [205, 208, 214], [52, 58, 74]
CORAL_RGB = [239, 78, 69]

# Ebene -> Spalte. Spalten ohne pr_-Präfix werden in der App in Prozentränge umgerechnet.
EBENEN = {
    "Score": "pr_score",
    "Angebotslücke": "pr_luecke",
    "Potenzial": "pr_potenzial",
    "Wettbewerbsfreiheit": "pr_wettbewerbsfreiheit",
    "Affinität": "pr_affinitaet",
    "Tagesanteil": "anteil_tag",
    "Stabilität": "top10_anteil",
    "Einwohner": "einwohner",
    "Miete": "miete_qm",
}
TREIBER = {
    "Potenzial": "pr_potenzial",
    "Wettbewerbsfreiheit": "pr_wettbewerbsfreiheit",
    "Affinität": "pr_affinitaet",
}
GRENZEN = [
    "Das Modell kennt keine Umsätze und ist nicht kalibriert. Der Score ordnet Standorte, er sagt keinen Umsatz voraus.",
    "Alle Parameter sind Setzungen. Der Robustheitstest zeigt, wie stark die Rangfolge von ihnen abhängt.",
    "Die Miete ist ein Ersatz für Kaufkraft. Sie stammt aus Bestandsmieten vom Mai 2022. Je nach Stadt sind 29 bis 45 Prozent der Werte aus Nachbarzellen geschätzt.",
    "Mieten sind zwischen Städten nicht vergleichbar. Die Standardansicht bewertet deshalb jede Stadt für sich.",
    "Die Tagesbevölkerung ist ein Index aus Büros, Hochschulen und Haltestellen, keine Personenzahl.",
    "OpenStreetMap ist nicht überall gleich vollständig. Gut kartierte Viertel können zu günstig erscheinen.",
    "Alle Wettbewerber einer Kategorie zählen gleich. Ladengröße und Qualität sind unbekannt.",
    "Distanzen sind Luftlinie mal 1,3. Flüsse, Bahntrassen und Autobahnen als Hindernisse sind nicht berücksichtigt.",
    "Das Modell kennt keine freien Ladenflächen und keine Gewerbemieten.",
    "Kleine Zahlen im Zensus sind aus Gründen der Geheimhaltung leicht verändert oder unterdrückt.",
]

st.set_page_config(page_title="White Spots", layout="wide", initial_sidebar_state="expanded")

# Hell oder Dunkel aus dem Einstellungs-Popover (Zahnrad). Streamlit selbst kann das Theme nicht zur Laufzeit wechseln,
# deshalb steuern wir Farben, Karte und Diagramme hier selbst.
DUNKEL = st.session_state.get("darstellung", "Hell") == "Dunkel"
T = {
    "bg": "#10131A" if DUNKEL else "#F2F3F5",
    "flaeche": "#181C26" if DUNKEL else "#FFFFFF",
    "sidebar": "#141821" if DUNKEL else "#FFFFFF",
    "feld": "#222735" if DUNKEL else "#F2F3F5",
    "rand": "#2B3140" if DUNKEL else "#D8DBE0",
    "text": "#E6E9F0" if DUNKEL else "#1C1E22",
    "titel": "#FFFFFF" if DUNKEL else MIDNIGHT,
    "grau": "#98A0B3" if DUNKEL else GREY,
    "akzent": "#4C8DFF" if DUNKEL else BRIGHT,
    "balken": "#4C8DFF" if DUNKEL else "#2C6EF2",
    "balken2": "#A9C8FF" if DUNKEL else "#8DB4FF",
    "serie": ["#4C8DFF", "#A9C8FF", "#7C8394"] if DUNKEL else ["#2C6EF2", "#8DB4FF", "#9AA0AB"],
    "gitter": "#2B3140" if DUNKEL else "#E3E5E9",
    "bumper_bg": "#1E2A4A" if DUNKEL else "#FFFFFF",
    "bumper_rand": "#3A4A78" if DUNKEL else "#D8DBE0",
    "hover": "#222B3D" if DUNKEL else "#F2F4F8",
    "schatten": "rgba(0, 0, 0, 0.45)" if DUNKEL else "rgba(11, 27, 77, 0.08)",
    "demo": "#FF8A82" if DUNKEL else "#B8322B",
    "karte": "dark" if DUNKEL else "light",
}
# Höhe des Arbeitsbereichs: ein Bildschirm abzüglich Kopfzeile, Titel, Bumper und Quelle
KOERPER = "max(430px, calc(100vh - 235px))"

CSS_DUNKEL = """
section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color: #E6E9F0; }
section[data-testid="stSidebar"] [data-testid="stSelectbox"] div:not([data-testid="stWidgetLabel"]):not([data-testid="stWidgetLabel"] *), section[data-testid="stSidebar"] [data-testid="stMultiSelect"] > div > div { background-color: #222735 !important; border-color: #2B3140 !important; }
section[data-testid="stSidebar"] [data-testid="stSelectbox"] div, section[data-testid="stSidebar"] [data-testid="stSelectbox"] input, section[data-testid="stSidebar"] [data-testid="stMultiSelect"] input { color: #E6E9F0 !important; }
[data-baseweb="popover"] ul, [data-baseweb="menu"] { background-color: #1E2433 !important; }
[data-baseweb="popover"] li, [data-baseweb="menu"] li { background-color: #1E2433 !important; color: #E6E9F0 !important; }
[data-baseweb="popover"] li:hover { background-color: #2B3550 !important; }
"""
st.markdown(f"""
<style>
html, body, [class*="css"] {{ font-family: Arial, Helvetica, sans-serif; }}
.stApp {{ background: {T['bg']}; color: {T['text']}; }}
.stApp p, .stApp li, .stApp label, .stApp td, .stApp th {{ color: inherit; }}
.block-container {{ padding: 0.8rem 2rem 0.4rem 2rem; max-width: none; }}
[data-testid="stVerticalBlock"] {{ gap: 0.55rem; }}
header[data-testid="stHeader"] {{ background: transparent; height: 0; min-height: 0; }}
#MainMenu, footer {{ visibility: hidden; }}
section[data-testid="stSidebar"] {{ background: {T['sidebar']}; border-right: 1px solid {T['rand']}; box-shadow: 2px 0 14px {T['schatten']}; }}
section[data-testid="stSidebar"] h1 {{ font-family: Georgia, serif; font-weight: 400; font-size: 1.6rem; color: {T['titel']}; letter-spacing: -0.01em; }}
/* Ein- und Ausklappen der Seitenleiste: immer sichtbar */
[data-testid="stSidebarCollapseButton"] button, [data-testid="stExpandSidebarButton"] {{ opacity: 1 !important; visibility: visible !important; }}
[data-testid="stExpandSidebarButton"] {{ position: fixed; top: 0.7rem; left: 0.7rem; z-index: 1000; width: 2.4rem; height: 2.4rem; display: flex; align-items: center; justify-content: center; background: {BRIGHT} !important; border-radius: 6px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3); }}
[data-testid="stExpandSidebarButton"]:hover {{ background: {SKY} !important; }}
[data-testid="stExpandSidebarButton"] *, [data-testid="stSidebarCollapseButton"] * {{ color: #FFFFFF !important; fill: #FFFFFF !important; opacity: 1 !important; }}
[data-testid="stSidebarCollapseButton"] button {{ background: {BRIGHT}; border-radius: 6px; width: 2rem; height: 2rem; }}
[data-testid="stSidebarCollapseButton"] button:hover {{ background: {SKY}; }}

.kopf {{ margin: 0.2rem 0 0.7rem 0; }}
.kicker {{ font-size: 0.76rem; font-weight: 600; letter-spacing: 0.16em; text-transform: uppercase; color: {T['akzent']}; }}
.titel {{ font-family: Georgia, "Times New Roman", serif !important; font-weight: 400 !important; font-size: 1.65rem; line-height: 1.2; letter-spacing: -0.01em; color: {T['titel']}; margin-top: 0.15rem; }}
.exh {{ font-size: 0.9rem; font-weight: 700; color: {T['titel']}; margin-bottom: 0.3rem; }}
.exh span {{ font-weight: 400; color: {T['grau']}; }}

.panel {{ background: {T['flaeche']}; border: 1px solid {T['rand']}; padding: 1rem 1.2rem; height: {KOERPER}; overflow: auto; }}
.panel h4 {{ margin: 0 0 0.5rem 0; font-size: 0.9rem; font-weight: 700; color: {T['titel']}; }}
.panel .abschnitt {{ border-top: 1px solid {T['rand']}; padding-top: 0.8rem; margin-top: 0.8rem; }}
.panel p {{ font-size: 0.88rem; line-height: 1.45; margin: 0 0 0.6rem 0; color: {T['text']}; }}
.panel small, .klein {{ color: {T['grau']}; font-size: 0.78rem; }}
.rang {{ display: flex; align-items: center; gap: 0.7rem; padding: 0.45rem 0; }}
.rang + .rang {{ border-top: 1px solid {T['rand']}; }}
.pin {{ display: inline-flex; flex: none; width: 1.6rem; height: 1.6rem; border-radius: 50%; background: {BRIGHT}; color: #fff; font-size: 0.8rem; font-weight: 700; align-items: center; justify-content: center; }}
.rang-t {{ flex: 1; min-width: 0; line-height: 1.25; }}
.rang-t b {{ display: block; font-size: 0.88rem; color: {T['titel']}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.rang-t span {{ font-size: 0.78rem; color: {T['grau']}; }}
.rang-s {{ font-weight: 700; font-size: 1.15rem; color: {T['titel']}; }}
.chip {{ display: inline-block; border: 1px solid {T['rand']}; padding: 0.15rem 0.6rem; margin: 0 0.35rem 0.35rem 0; font-size: 0.8rem; color: {T['text']}; }}
.chip.konsens {{ border-color: {BRIGHT}; color: {T['akzent']}; font-weight: 700; }}
.gross {{ font-weight: 700; font-size: 3rem; line-height: 1; color: {T['titel']}; }}

.bumper {{ background: {T['bumper_bg']}; border: 1px solid {T['bumper_rand']}; border-left: 4px solid {T['akzent']}; margin-top: 0.35rem; padding: 0.55rem 1rem; font-weight: 700; font-size: 0.92rem; color: {T['titel']}; }}
.quelle {{ font-size: 0.72rem; color: {T['grau']}; margin-top: 0.3rem; }}
.demo {{ font-size: 0.72rem; font-weight: 700; color: {T['demo']}; letter-spacing: 0.03em; }}

.legende {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.8rem 2rem; background: {T['flaeche']}; border: 1px solid {T['rand']}; padding: 0.6rem 1rem; }}
.legende.v {{ display: block; border: 0; padding: 0; background: transparent; }}
.leg-titel {{ font-weight: 700; font-size: 1.05rem; line-height: 1.1; color: {T['titel']}; }}
.leg-titel small {{ display: block; font-family: Arial, sans-serif; font-size: 0.76rem; color: {T['grau']}; margin-top: 0.2rem; }}
.leg-skala {{ flex: 1 1 240px; max-width: 360px; margin: 0.6rem 0 0.5rem 0; }}
.leg-balken {{ height: 11px; border-radius: 2px; box-shadow: inset 0 0 0 1px rgba(128, 128, 128, 0.35); }}
.leg-ticks, .leg-enden {{ display: flex; justify-content: space-between; font-size: 0.7rem; color: {T['grau']}; }}
.leg-ticks {{ margin-top: 0.25rem; font-variant-numeric: tabular-nums; }}
.leg-enden {{ font-style: italic; }}
.leg-key {{ display: flex; align-items: center; gap: 0.4rem; font-size: 0.78rem; color: {T['text']}; flex-wrap: wrap; }}
.leg-pin {{ display: inline-flex; width: 1.1rem; height: 1.1rem; align-items: center; justify-content: center; background: {BRIGHT}; color: #fff; font-size: 0.65rem; font-weight: 700; outline: 2px solid {CORAL}; outline-offset: 1px; margin-right: 0.1rem; }}
.leg-feld {{ display: inline-block; width: 1.1rem; height: 1.1rem; margin-left: 0.8rem; margin-right: 0.1rem; }}

.tab {{ overflow: auto; border: 1px solid {T['rand']}; background: {T['flaeche']}; }}
.tab table {{ border-collapse: collapse; width: 100%; font-size: 0.84rem; }}
.tab th {{ position: sticky; top: 0; background: {T['flaeche']}; text-align: left; color: {T['grau']}; font-weight: 600; padding: 0.5rem 0.8rem; border-bottom: 2px solid {T['rand']}; }}
.tab td {{ padding: 0.45rem 0.8rem; border-bottom: 1px solid {T['rand']}; color: {T['text']}; }}
.tab tbody tr:hover td {{ background: {T['hover']}; }}
.tab tbody tr.aktiv td {{ background: {T['hover']}; }}
.panel .tab table {{ table-layout: fixed; }}
.panel .tab th, .panel .tab td {{ padding: 0.4rem 0.5rem; font-size: 0.78rem; word-break: break-word; }}
.tab td:first-child {{ font-weight: 700; color: {T['titel']}; }}
.spalte {{ height: calc({KOERPER} - 1.7rem); overflow: auto; padding-right: 0.4rem; }}
.spalte ul {{ margin: 0; padding-left: 1.1rem; }}
.spalte li {{ font-size: 0.86rem; line-height: 1.45; margin-bottom: 0.45rem; }}

/* Kopfzeile: Ansichten zum Durchklicken, Linie unter der ganzen Leiste */
[data-testid="stElementContainer"]:has([data-testid="stButtonGroup"]) {{ width: 100% !important; }}
[data-testid="stButtonGroup"] {{ width: 100%; gap: 0; border-bottom: 1px solid {T['rand']}; }}
[data-testid="stButtonGroup"] button {{ border-radius: 0; border: 0; border-bottom: 3px solid transparent; margin-bottom: -1px; background: transparent !important; color: {T['grau']}; font-weight: 600; padding: 0.45rem 1.1rem; }}
[data-testid="stButtonGroup"] button:hover {{ color: {T['titel']}; border-bottom-color: {T['rand']}; }}
[data-testid="stButtonGroup"] button[aria-checked="true"] {{ border-bottom: 3px solid {T['akzent']} !important; }}
[data-testid="stButtonGroup"] button[aria-checked="true"] * {{ color: {T['titel']} !important; font-weight: 700; }}
section[data-testid="stSidebar"] [data-testid^="stBaseButton"]:not([data-testid="stBaseButton-headerNoPadding"]) {{ background: {T['feld']}; color: {T['text']}; border: 1px solid {T['rand']}; }}
[data-testid="stPopover"] button {{ background: {T['flaeche']}; color: {T['text']}; border: 1px solid {T['rand']}; min-height: 2.2rem; }}
[data-testid="stPopoverBody"] {{ background: {T['flaeche']}; border: 1px solid {T['rand']}; }}
[data-testid="stPopoverBody"] * {{ color: {T['text']}; }}
/* Karte füllt den Arbeitsbereich */
[data-testid="stDeckGlJsonChart"], [data-testid="stDeckGlJsonChart"] > div, [data-testid="stDeckGlJsonChart"] iframe {{ height: {KOERPER} !important; min-height: 0 !important; }}
{CSS_DUNKEL if DUNKEL else ""}
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------------ Daten
def pfad(key: str, name: str):
    """Echte Datei bevorzugen, sonst Demo. Gibt (Pfad, ist_demo) zurück, Pfad ist None, wenn nichts vorliegt."""
    for ordner, demo in ((DATA, False), (DEMO, True)):
        if (ordner / name).exists():
            return ordner / name, demo
    return None, False


def umkreis_400m(df: pd.DataFrame) -> pd.DataFrame:
    """Einwohner und direkte Wettbewerber im Umkreis von 400 m (Vergleichsansicht, Spec Abschnitt 8)."""
    rad = np.radians(df[["lat", "lon"]].to_numpy())
    nachbarn = BallTree(rad, metric="haversine").query_radius(rad, r=400 / ERDRADIUS_M)
    ew = df["einwohner"].fillna(0).to_numpy()
    spalten = [f"poi_{c}" for c in WETTBEWERB_DIREKT if f"poi_{c}" in df.columns]
    wb = df[spalten].fillna(0).sum(axis=1).to_numpy() if spalten else np.zeros(len(df))
    df = df.copy()
    df["einwohner_400m"] = [ew[i].sum() for i in nachbarn]
    df["wettbewerber_400m"] = [wb[i].sum() for i in nachbarn]
    return df


@st.cache_data
def lade_stadt(key: str):
    p, demo = pfad(key, f"{key}_scored.csv")
    if p is None:
        return None, False
    df = umkreis_400m(pd.read_csv(p))  # Pufferzellen zählen für den Umkreis mit
    return df[df["in_stadt"]].reset_index(drop=True), demo


@st.cache_data
def lade_pois(key: str):
    """Haltestellen mit Namen für die Lagebezeichnung. Fehlt die Datei, gibt es Koordinaten."""
    p, _ = pfad(key, f"{key}_pois.csv")
    if p is None:
        return None
    t = pd.read_csv(p)
    t = t[t["kategorie"].isin(["bahnhof", "tram_ubahn"]) & t["name"].notna()]
    return t[["lat", "lon", "name"]].reset_index(drop=True)


@st.cache_data
def lade_portfolio(key: str):
    p, _ = pfad(key, f"{key}_portfolio.csv")
    return pd.read_csv(p) if p else None


def lade_json(name: str):
    p, _ = pfad("", name)
    return json.loads(p.read_text(encoding="utf-8")) if p else None


@st.cache_data
def lade_parameter():
    try:
        from analyse import PARAMETER
        return PARAMETER
    except Exception:  # analyse.py fehlt oder bricht beim Import ab
        return None


def lagebezeichnung(zeile, pois) -> str:
    """Name der nächsten Haltestelle im Umkreis von 800 m, sonst Koordinaten (Spec, Abschnitt 8)."""
    if pois is not None and len(pois):
        dy = (pois["lat"] - zeile["lat"]) * 111_000
        dx = (pois["lon"] - zeile["lon"]) * 111_000 * np.cos(np.radians(zeile["lat"]))
        d = np.hypot(dx, dy)
        if d.min() <= 800:
            return f"nahe {pois.loc[d.idxmin(), 'name']}"
    return f"{zeile['lat']:.4f}, {zeile['lon']:.4f}"


def farbe(werte: pd.Series, deckkraft: float = 0.7) -> list:
    """Prozentrang 0 bis 100 auf die Farbrampe abbilden. Niedrige Werte sind durchsichtig, hohe kräftig,
    damit beim Hineinzoomen die Straßen unter schwachen Feldern sichtbar bleiben."""
    rampe = RAMPE_DUNKEL if DUNKEL else RAMPE_HELL
    t = (werte.fillna(0).clip(0, 100) / 100 * (len(rampe) - 1)).to_numpy()
    i = np.minimum(t.astype(int), len(rampe) - 2)
    f = (t - i)[:, None]
    a, b = np.array(rampe)[i], np.array(rampe)[i + 1]
    rgb = (a + (b - a) * f).astype(int)
    alpha = (255 * deckkraft * (0.6 + 0.4 * t / (len(rampe) - 1))).astype(int)[:, None]
    return np.hstack([rgb, alpha]).tolist()


def prozent(s: pd.Series) -> pd.Series:
    return s.rank(pct=True) * 100


def staerken_satz(z: pd.Series) -> str:
    """Treiber-Sätze nach den Schwellen der Spec: ab 80 Stärke, unter 40 Bremse."""
    stark = [k for k, c in TREIBER.items() if z[c] >= 80]
    schwach = [k for k, c in TREIBER.items() if z[c] < 40]
    teile = []
    if stark:
        teile.append("Stark durch " + " und ".join(stark))
    if schwach:
        teile.append("gebremst durch " + " und ".join(schwach))
    if not teile:
        return "Solider Standort ohne ausgeprägte Stärken oder Bremsen."
    return ", ".join(teile) + "."


def stabilitaet(anteil: float) -> str:
    if anteil >= 0.7:
        return "sicherer Kandidat"
    if anteil < 0.3:
        return "wackeliger Kandidat"
    return "mittel"


# ------------------------------------------------------------- Bausteine der Optik
def kopf(kicker: str, titel: str):
    st.markdown(f'<div class="kopf"><div class="kicker">{escape(kicker)}</div><div class="titel">{escape(titel)}</div></div>',
                unsafe_allow_html=True)


def exhibit_titel(was: str, einheit: str = ""):
    st.markdown(f'<div class="exh">{escape(was)} <span>{escape(einheit)}</span></div>', unsafe_allow_html=True)


def bumper(text: str):
    st.markdown(f'<div class="bumper">{escape(text)}</div>', unsafe_allow_html=True)


def quelle(text: str):
    st.markdown(f'<div class="quelle">{escape(text)}</div>', unsafe_allow_html=True)


def panel(html: str):
    st.markdown(f'<div class="panel">{html}</div>', unsafe_allow_html=True)


def tabelle(df: pd.DataFrame, hoehe: int | None = None) -> str:
    """Einfache HTML-Tabelle im Look der App. Gibt den HTML-Text zurück."""
    kopfzeile = "".join(f"<th>{escape(str(c))}</th>" for c in df.columns)
    zeilen = "".join("<tr>" + "".join(f"<td>{escape(str(v))}</td>" for v in r) + "</tr>" for r in df.itertuples(index=False))
    stil = f' style="max-height:{hoehe}px"' if hoehe else ""
    return f'<div class="tab"{stil}><table><thead><tr>{kopfzeile}</tr></thead><tbody>{zeilen}</tbody></table></div>'


def legende_html(ebene: str, stadt: str, nur_lagen: bool, senkrecht: bool) -> str:
    """Legende: Ebene, durchgehender Farbverlauf mit Skalenwerten und Schlüssel der Markierungen."""
    rampe = RAMPE_DUNKEL if DUNKEL else RAMPE_HELL
    verlauf = ", ".join(f"rgb({r}, {g}, {b})" for r, g, b in rampe)
    nl = NICHT_LAGE_DUNKEL if DUNKEL else NICHT_LAGE_HELL
    schluessel = '<span class="leg-pin">1</span>Top 10'
    if nur_lagen:
        schluessel += f'<span class="leg-feld" style="background: rgb({nl[0]}, {nl[1]}, {nl[2]})"></span>keine Geschäftslage'
    ticks = "".join(f"<span>{v}</span>" for v in (0, 25, 50, 75, 100))
    return f"""
<div class="legende{' v' if senkrecht else ''}">
  <div class="leg-titel">{escape(ebene)}<small>Prozentrang in {escape(stadt)}</small></div>
  <div class="leg-skala">
    <div class="leg-balken" style="background: linear-gradient(90deg, {verlauf});"></div>
    <div class="leg-ticks">{ticks}</div>
    <div class="leg-enden"><span>niedrig</span><span>hoch</span></div>
  </div>
  <div class="leg-key">{schluessel}</div>
</div>"""


def balkendiagramm(daten: pd.DataFrame, wert: str, farbe_hex: str, domain, hoehe: int):
    """Balkendiagramm mit waagerechten Achsenbeschriftungen (st.bar_chart dreht sie um 90 Grad)."""
    y = alt.Y(f"{wert}:Q", scale=alt.Scale(domain=domain) if domain else alt.Undefined, title=None)
    return alt.Chart(daten).mark_bar(color=farbe_hex).encode(
        x=alt.X("Treiber:N", sort=None, axis=alt.Axis(labelAngle=0, labelLimit=220, title=None)), y=y,
    ).properties(height=hoehe)


def theme_chart(chart):
    """Achsen, Gitter und Legende in den Farben des gewählten Modus, transparenter Hintergrund."""
    farbe_achse = T["text"]
    return (chart.configure(background="transparent")
            .configure_view(stroke=None)
            .configure_axis(labelColor=farbe_achse, titleColor=farbe_achse, gridColor=T["gitter"], domainColor=T["gitter"], tickColor=T["gitter"])
            .configure_legend(labelColor=farbe_achse, titleColor=farbe_achse)
            .configure_header(labelColor=farbe_achse))


# ---------------------------------------------------------------- Seitenleiste
st.sidebar.title("White Spots")
stadt_name = st.sidebar.selectbox("Stadt", list(STAEDTE))
key = STAEDTE[stadt_name]
df, ist_demo = lade_stadt(key)
if df is None:
    st.error(f"Für {stadt_name} liegen keine Daten vor. Demo erzeugen mit: python analyse.py --demo")
    st.stop()
pois = lade_pois(key)

# Kopfzeile: Ansichten zum Durchklicken links, Zahnrad rechts (Darstellung, Deckkraft der Felder, Kommentarfeld)
nav, zahnrad = st.columns([9.6, 2.0], vertical_alignment="center")
with nav:
    gewaehlte_ansicht = st.segmented_control("Ansicht", ANSICHTEN, default="Karte", key="ansicht",
                                             label_visibility="collapsed")
ansicht = gewaehlte_ansicht or "Karte"  # ein Klick auf die aktive Ansicht würde sie abwählen
with zahnrad.popover("Einstellungen", icon=":material/settings:", use_container_width=True):
    st.radio("Darstellung", ["Hell", "Dunkel"], key="darstellung", horizontal=True)
    st.slider("Deckkraft der Felder", 0.2, 1.0, 0.9, 0.05, key="deckkraft",
              help="Niedriger = Straßen und Gebäude darunter besser sichtbar, vor allem beim Hineinzoomen.")
    st.toggle("Kommentarfeld zeigen", value=True, key="kommentar")
deckkraft = st.session_state.get("deckkraft", 0.9)
zeige_panel = st.session_state.get("kommentar", True)

if "auswahl" not in st.session_state:
    st.session_state["auswahl"] = {}

# Gemeinsame Auswahlbasis
top = df[df["rang"].notna()].nsmallest(10, "rang").copy()
top["lage"] = top.apply(lagebezeichnung, axis=1, pois=pois)
n_konsens = int(top["konsens"].sum())
optionen = {f"#{int(r.rang)} {r.lage}": r.h3 for r in top.itertuples()}

# Seitenleiste: nur die Bedienelemente der gerade offenen Ansicht
ebene, nur_lagen, zeige_portfolio = "Score", True, False
if ansicht == "Karte":
    ebene = st.sidebar.selectbox("Ebene", list(EBENEN))
    nur_lagen = st.sidebar.toggle("Nur Geschäftslagen", value=True)
    zeige_portfolio = st.sidebar.toggle("Portfolio zeigen", value=False)
    if "rang_gemeinsam" in df.columns:
        st.sidebar.radio("Maßstab", ["Innerhalb der Stadt", "Gemeinsam über alle drei"])
elif ansicht == "Vergleich":
    gewaehlt = st.sidebar.multiselect("Standorte vergleichen", list(optionen), default=list(optionen)[:2], max_selections=3)
elif ansicht == "Erklärung":
    wahl = st.sidebar.selectbox("Standort", list(optionen))
elif ansicht == "Rangliste":
    zeige_wahl = st.sidebar.selectbox("Auf der Karte zeigen", list(optionen))
    st.sidebar.button("Zur Karte", on_click=lambda: (st.session_state["auswahl"].__setitem__(key, optionen[zeige_wahl]),
                                                     st.session_state.update(ansicht="Karte")))
if ist_demo:
    st.sidebar.markdown('<div class="demo">Demo-Daten, synthetisch. Keine echten Ergebnisse.</div>', unsafe_allow_html=True)

QUELLE = "Quellen: OpenStreetMap-Mitwirkende, Statistisches Bundesamt (Zensus 2022)." + (
    " Demo-Daten, synthetisch." if ist_demo else "")


def zweispaltig():
    """Exhibit links, Kommentarfeld rechts. Ist das Kommentarfeld ausgeblendet, bekommt das Exhibit die volle Breite."""
    if zeige_panel:
        return st.columns([7.4, 3.6], gap="medium")
    return st.container(), None


# ---------------------------------------------------------------------- Karte
if ansicht == "Karte":
    kopf("Karte", f"{stadt_name}: {n_konsens} der zehn besten Standorte liegen in beiden Sichten vorn" if n_konsens
         else f"{stadt_name}: Die zehn besten Standorte im Überblick")
    spalte = EBENEN[ebene]
    werte = df[spalte] if spalte.startswith("pr_") else prozent(df[spalte])
    karte = df.copy()
    karte["farbe"] = farbe(werte, deckkraft)
    if nur_lagen:
        kein = karte["rang"].isna()
        karte.loc[kein, "farbe"] = pd.Series([(NICHT_LAGE_DUNKEL if DUNKEL else NICHT_LAGE_HELL) + [int(110 * deckkraft)]] * int(kein.sum()),
                                             index=karte.index[kein])
    karte["rang_txt"] = karte["rang"].apply(lambda r: "–" if pd.isna(r) else str(int(r)))
    karte["staerke"] = karte.apply(staerken_satz, axis=1)

    auswahl = st.session_state["auswahl"].get(key)
    if auswahl is not None and auswahl in set(df["h3"]):
        zentrum = df.loc[df["h3"] == auswahl, ["lat", "lon"]].iloc[0]
        view = pdk.ViewState(latitude=zentrum["lat"], longitude=zentrum["lon"], zoom=14.5, min_zoom=8, max_zoom=20)
    else:
        view = pdk.data_utils.compute_view(df[["lon", "lat"]].to_numpy().tolist(), view_proportion=0.92)
        view.min_zoom, view.max_zoom = 8, 20

    nummern = top.copy()
    nummern["text"] = nummern["rang"].astype(int).astype(str)
    schichten = [
        pdk.Layer("H3HexagonLayer", karte, get_hexagon="h3", get_fill_color="farbe",
                  get_line_color=[255, 255, 255, 90], line_width_min_pixels=0.4,
                  extruded=False, opacity=1, pickable=True),
        pdk.Layer("H3HexagonLayer", top, get_hexagon="h3", get_fill_color=[0, 0, 0, 0],
                  get_line_color=CORAL_RGB + [255], stroked=True, filled=False,
                  line_width_min_pixels=4, extruded=False),
        pdk.Layer("TextLayer", nummern, get_position=["lon", "lat"], get_text="text", get_size=15,
                  get_color=[255, 255, 255, 255], get_background_color=[44, 110, 242, 255], background=True,
                  background_padding=[5, 3]),
    ]
    if zeige_portfolio:
        port = lade_portfolio(key)
        if port is None:
            st.info("Für das Portfolio liegt keine Datei vor.")
        else:
            port = port.merge(df[["h3", "lat", "lon"]], on="h3", how="left").dropna(subset=["lat"])
            port["text"] = port["schritt"].astype(int).astype(str)
            schichten.append(pdk.Layer("ScatterplotLayer", port, get_position=["lon", "lat"], get_radius=140,
                                       get_fill_color=CORAL_RGB + [230], get_line_color=[255, 255, 255, 255],
                                       stroked=True, line_width_min_pixels=2))
            schichten.append(pdk.Layer("TextLayer", port, get_position=["lon", "lat"], get_text="text", get_size=14,
                                       get_color=[255, 255, 255, 255]))
    tooltip = {"html": "<b>Rang {rang_txt}</b> · Score-Prozentrang {pr_score}<br>{profil}<br><i>{staerke}</i>",
               "style": {"fontSize": "13px", "maxWidth": "320px", "fontFamily": "Arial"}}

    links, rechts = zweispaltig()
    with links:
        if rechts is None:  # ohne Kommentarfeld sitzt die Legende über der Karte
            st.markdown(legende_html(ebene, stadt_name, nur_lagen, senkrecht=False), unsafe_allow_html=True)
        st.pydeck_chart(pdk.Deck(layers=schichten, initial_view_state=view, map_style=T["karte"], tooltip=tooltip),
                        width="stretch", height=600)
    if rechts is not None:
        with rechts:
            reihen = ""
            for r in top.head(3).itertuples():
                konsens = " · Konsens" if r.konsens else ""
                reihen += (f'<div class="rang"><span class="pin">{int(r.rang)}</span><div class="rang-t"><b>{escape(r.lage)}</b>'
                           f'<span>{escape(r.profil)} · {escape(stabilitaet(r.top10_anteil))}{konsens}</span></div>'
                           f'<span class="rang-s">{r.pr_score:.0f}</span></div>')
            panel(legende_html(ebene, stadt_name, nur_lagen, senkrecht=True)
                  + '<div class="abschnitt"><h4>Die drei besten Standorte</h4>' + reihen
                  + '<p class="klein" style="margin-top:0.4rem">Zahl rechts: Score-Prozentrang. Alle zehn in der Rangliste.</p></div>')
    bumper(f"Priorität: {top.iloc[0]['lage']} zuerst prüfen, danach die Standorte mit Konsens-Kennzeichnung.")
    quelle(QUELLE)

# ------------------------------------------------------------------- Rangliste
elif ansicht == "Rangliste":
    n_sicher = int((top["top10_anteil"] >= 0.7).sum())
    kopf("Rangliste", f"{stadt_name}: {n_sicher} der zehn besten Standorte sind sichere Kandidaten")
    exhibit_titel("Die zehn besten Standorte", "PR = Prozentrang innerhalb der Stadt, 0 bis 100")
    tab = pd.DataFrame({
        "Rang": top["rang"].astype(int),
        "Lage": top["lage"],
        "Score (PR)": top["pr_score"].round(0).astype(int),
        "Lücke (PR)": top["pr_luecke"].round(0).astype(int),
        "Konsens": top["konsens"].map({True: "✓", False: ""}),
        **{k: top[c].round(0).astype(int) for k, c in TREIBER.items()},
        "Profil": top["profil"],
        "Stabilität": top["top10_anteil"].map(stabilitaet),
    })
    st.markdown(tabelle(tab), unsafe_allow_html=True)
    bumper("Konsens heißt: in Score und Angebotslücke im obersten Zehntel. Diese Standorte zuerst vor Ort prüfen.")
    quelle(QUELLE)

# --------------------------------------------------------------------- Vergleich
elif ansicht == "Vergleich":
    if len(gewaehlt) < 2:
        kopf("Vergleich", f"Standorte in {stadt_name} nebeneinander")
        st.info("Wähle in der Seitenleiste mindestens zwei Standorte.")
    else:
        zeilen = top.set_index("h3").loc[[optionen[g] for g in gewaehlt]]
        balken = pd.DataFrame({g: zeilen.iloc[i][list(TREIBER.values())].to_numpy() for i, g in enumerate(gewaehlt)},
                              index=list(TREIBER))
        kopf("Vergleich", f"Die Standorte unterscheiden sich am stärksten beim Treiber {(balken.max(axis=1) - balken.min(axis=1)).idxmax()}")
        links, rechts = zweispaltig()
        with links:
            exhibit_titel("Treiber im Vergleich", "Prozentrang innerhalb der Stadt")
            lang = balken.reset_index(names="Treiber").melt("Treiber", var_name="Standort", value_name="Prozentrang")
            st.altair_chart(theme_chart(
                alt.Chart(lang).mark_bar().encode(
                    x=alt.X("Standort:N", axis=None), y=alt.Y("Prozentrang:Q", scale=alt.Scale(domain=[0, 100]), title=None),
                    color=alt.Color("Standort:N", scale=alt.Scale(range=T["serie"]), legend=alt.Legend(orient="bottom", title=None)),
                    column=alt.Column("Treiber:N", title=None, header=alt.Header(labelFontSize=13, labelFontWeight="bold")),
                ).properties(width=200, height=300)), width="content")
        roh = pd.DataFrame({
            "Einwohner (400 m)": zeilen["einwohner_400m"].round(0).astype(int).to_numpy(),
            "Miete (€/m²)": zeilen["miete_qm"].round(2).to_numpy(),
            "Wettbewerber (400 m)": zeilen["wettbewerber_400m"].round(0).astype(int).to_numpy(),
            "Profil": zeilen["profil"].to_numpy(),
        }, index=[f"#{int(r)}" for r in zeilen["rang"]]).T.reset_index(names=" ")
        if rechts is not None:
            with rechts:
                panel('<h4>Rohwerte</h4>' + tabelle(roh) + '<p class="klein" style="margin-top:0.8rem">#1 bis #3 sind die Ränge in der Rangliste.</p>')
        else:
            with links:
                st.markdown(tabelle(roh), unsafe_allow_html=True)
        bumper("Standort mit höherer Wettbewerbsfreiheit wählen, wenn das Potenzial vergleichbar ist.")
        quelle(QUELLE)

# ---------------------------------------------------------------------- Erklärung
elif ansicht == "Erklärung":
    z = df.loc[df["h3"] == optionen[wahl]].iloc[0]
    kopf("Treiber-Erklärung", f"{wahl}: {staerken_satz(z)}")
    links, rechts = zweispaltig()
    with links:
        exhibit_titel("Woraus der Score besteht", "Prozentrang innerhalb der Stadt")
        zerlegung = pd.DataFrame({
            "Prozentrang": [prozent(df["p_anw"]).loc[z.name], prozent(df["p_tag"]).loc[z.name], z["pr_wettbewerbsfreiheit"]]
        }, index=["Potenzial Anwohner", "Potenzial Tagesbevölkerung", "Wettbewerbsfreiheit"])
        st.altair_chart(theme_chart(balkendiagramm(zerlegung.reset_index(names="Treiber"), "Prozentrang", T["balken"], [0, 100], 190)), width="stretch")
        exhibit_titel("Datenbasierte Treiber der Angebotslücke", "Beitrag zur erwarteten Ladenzahl, logarithmische Skala")
        namen = ["einwohner", "kaufkraft", "alter", "affinitaet", "tag"]
        beitraege = pd.DataFrame({"Beitrag": [z[f"beitrag_{n}"] for n in namen]},
                                 index=["Einwohner", "Kaufkraft", "Alter", "Affinität", "Tag"])
        st.altair_chart(theme_chart(balkendiagramm(beitraege.reset_index(names="Treiber"), "Beitrag", T["balken2"], None, 190)), width="stretch")
    if rechts is not None:
        with rechts:
            chips = f'<span class="chip">{escape(str(z["profil"]))}</span><span class="chip">{escape(stabilitaet(z["top10_anteil"]))}</span>'
            if z["konsens"]:
                chips = '<span class="chip konsens">Konsens-Standort</span>' + chips
            panel(f'<div class="gross">{z["pr_score"]:.0f}</div><p class="klein" style="margin:0.3rem 0 1rem 0">Score-Prozentrang in {escape(stadt_name)}</p>'
                  + chips + f'<div class="abschnitt"><p>{escape(staerken_satz(z))}</p>'
                  '<p class="klein">Der Score ist Potenzial mal Wettbewerbsfreiheit.</p></div>')
    bumper("Gut ist ein Standort, wenn das Potenzial hoch und der Wettbewerb gering ist.")
    quelle(QUELLE)

# ----------------------------------------------------------------------- Annahmen
else:
    kopf("Annahmen", "Jede Zahl beruht auf Setzungen, deshalb zeigen wir sie offen")
    c1, c2, c3 = st.columns([1.3, 1, 1], gap="medium")
    with c1:
        exhibit_titel("Grenzen des Modells")
        st.markdown('<div class="spalte"><ul>' + "".join(f"<li>{escape(g)}</li>" for g in GRENZEN) + "</ul></div>", unsafe_allow_html=True)
    with c2:
        exhibit_titel("Parameter", "alle Werte sind Setzungen")
        par = lade_parameter()
        if par:
            st.markdown(f'<div class="spalte">{tabelle(pd.DataFrame({"Parameter": list(par), "Startwert": [str(v) for v in par.values()]}))}</div>',
                        unsafe_allow_html=True)
        else:
            st.caption("Parameter nicht verfügbar (analyse.py oder config.yaml fehlt).")
    with c3:
        exhibit_titel("Plausibilitätstest", "Wettbewerber in den 20 % Zellen mit dem höchsten Potenzial")
        pl = lade_json(f"{key}_plausibilitaet.json")
        html = ""
        if pl:
            html += (f'<div class="gross">{pl["anteil_pois_in_top_zellen"] * 100:.0f} %</div>'
                     f'<p class="klein" style="margin:0.3rem 0 0.8rem 0">statt {pl["erwartet_ohne_vorhersagekraft"] * 100:.0f} % ohne Vorhersagekraft, '
                     f'bei {pl["pois_direkt"]} direkten Wettbewerbern</p>')
        else:
            html += '<p class="klein">Noch nicht berechnet.</p>'
        lm = lade_json("luecke_modell.json")
        if lm:
            koef = pd.DataFrame({"Merkmal": list(lm["koeffizienten"]), "Koeffizient": [round(v, 3) for v in lm["koeffizienten"].values()],
                                 "Std.fehler": [round(lm["standardfehler"][k], 3) for k in lm["koeffizienten"]]})
            html += ('<div class="exh" style="margin-top:0.8rem">Angebotslücke <span>Poisson-Regression, Merkmale standardisiert</span></div>'
                     + tabelle(koef)
                     + f'<p class="klein" style="margin-top:0.5rem">Variante: {escape(str(lm.get("variante", "–")))}. Standardfehler sind zu klein, weil Nachbarzellen nicht unabhängig sind.</p>')
        st.markdown(f'<div class="spalte">{html}</div>', unsafe_allow_html=True)
    bumper("Der Score ordnet Standorte, er sagt keinen Umsatz voraus. Vor einer Investition Standort und Fläche vor Ort prüfen.")
    quelle(QUELLE + " Lizenztexte vor dem Pitch prüfen.")
