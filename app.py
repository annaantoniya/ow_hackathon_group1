"""Decision Platform: White Spots für einen Premium-Food-Market.

Liest nur fertige Dateien aus data/ und rechnet nichts Schweres (Spec, Abschnitt 8).
Fehlen die echten Dateien, nimmt die App die Demo-Daten aus data/demo/ (python analyse.py --demo).
Aufbau: Alles Wichtige passt in eine Bildschirmhöhe. Blau gehört den Daten und aktiven Elementen,
Flächen und Rahmen bleiben neutral. Start: streamlit run app.py
"""
import base64
import json
from html import escape
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st
from sklearn.neighbors import BallTree

import konzept as K

DATA = Path(__file__).parent / "data"
DEMO = DATA / "demo"
STAEDTE = {"München": "muenchen", "Frankfurt": "frankfurt", "Berlin": "berlin"}
ERDRADIUS_M = 6_371_000
ZOOM_STADT = 11.3
WETTBEWERB_DIREKT = ["deli", "feinkost_kaese", "wein", "bio_markt", "reformhaus", "markthalle", "pasta"]
ANSICHTEN = ["Konzept", "Karte", "Rangliste", "Vergleich", "Erklärung", "Annahmen"]

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

st.set_page_config(page_title="White Spots", layout="wide", initial_sidebar_state="collapsed")

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
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"] {{ display: none !important; }}
section[data-testid="stSidebar-unused"] {{ background: {T['sidebar']}; border-right: 1px solid {T['rand']}; box-shadow: 2px 0 14px {T['schatten']}; }}
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
.panel small, .klein, p.klein {{ color: {T['grau']} !important; font-size: 0.78rem !important; line-height: 1.4 !important; }}
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
.st-key-rk_karte, .st-key-rk_pilot {{ height: 0; position: relative; z-index: 30; overflow: visible; }}
.st-key-rk_karte [data-testid="stHorizontalBlock"], .st-key-rk_pilot [data-testid="stHorizontalBlock"] {{ padding: 0.55rem 0 0 0.55rem; }}
.st-key-rk_karte button, .st-key-rk_pilot button {{ min-height: 2.1rem; font-size: 0.82rem; box-shadow: 0 1px 6px rgba(0, 0, 0, 0.25); }}
.statraster {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0.6rem 0.9rem; }}
.stat {{ border-top: 1px solid {T['rand']}; padding-top: 0.35rem; }}
.stat span {{ display: block; font-size: 0.72rem; color: {T['grau']}; }}
.stat b {{ font-size: 1.05rem; color: {T['titel']}; }}
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

/* Startseite: Aufbau nach dem Vorbild von M&S Food und Waitrose. Überschriften in der Serifenschrift der Marke. */
.w-intro h1 {{ font-family: Georgia, "Times New Roman", serif; font-weight: 400; font-size: 3.1rem; line-height: 1.1; letter-spacing: -0.015em; color: {T['titel']}; margin: 0.4rem 0 1.1rem 0; }}
.w-intro h1 u {{ text-decoration-thickness: 3px; text-underline-offset: 7px; }}
.w-intro-zeile {{ display: grid; grid-template-columns: 1fr 11rem; border-top: 1px solid {T['titel']}; }}
.w-intro-zeile p {{ margin: 0; padding: 1.2rem 2rem 1.3rem 0; font-size: 1rem; line-height: 1.65; color: {T['text']}; max-width: 54rem; }}
.w-intro-zeile .l {{ border-left: 1px solid {T['titel']}; display: flex; align-items: center; justify-content: center; }}
.w-intro-zeile img {{ width: 4.4rem; height: 4.4rem; border-radius: 50%; }}
.w-split {{ display: grid; grid-template-columns: 1.45fr 1fr; min-height: 540px; margin-top: 0.8rem; }}
.w-split .bild {{ background-size: cover; background-position: center 10%; position: relative; }}
.w-split .text {{ background: {MIDNIGHT}; color: #FFFFFF; padding: 2.2rem 2.6rem; display: flex; flex-direction: column; justify-content: center; }}
.w-kicker {{ font-size: 0.74rem; font-weight: 600; letter-spacing: 0.16em; text-transform: uppercase; color: #8E9AC2; }}
.w-marke {{ font-family: Georgia, "Times New Roman", serif; font-size: 5rem; line-height: 1; letter-spacing: 0.08em; margin: 0.6rem 0 0.4rem 0; color: #FFFFFF; }}
.w-bez {{ font-family: Georgia, "Times New Roman", serif; font-style: italic; font-size: 1.35rem; color: #CEECFF; }}
.w-claim {{ font-family: Georgia, "Times New Roman", serif; font-size: 2.5rem; line-height: 1.1; margin-top: 1.4rem; color: #FFFFFF; }}
.w-sub {{ color: #D6DCEB; font-size: 1rem; margin-top: 0.5rem; }}
.w-namen {{ margin-top: 1.6rem; font-size: 0.78rem; letter-spacing: 0.28em; color: #8E9AC2; }}
.w-namen .treffer {{ color: #FFFFFF; font-weight: 700; }}
.w-namen small {{ letter-spacing: 0.02em; margin-left: 0.8rem; font-size: 0.72rem; }}
.fallback {{ background: #CEECFF; color: {MIDNIGHT}; display: flex; align-items: center; justify-content: center; text-align: center; font-family: Georgia, "Times New Roman", serif; font-size: 1.1rem; font-style: italic; }}
.w-usp {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 1.8rem; background: #CEECFF; padding: 1.7rem 2rem 1.4rem 2rem; margin: 1rem 0 0 0; }}
.w-usp .u {{ display: flex; gap: 0.9rem; align-items: flex-start; border-bottom: 1px solid {MIDNIGHT}; padding-bottom: 1rem; }}
.w-usp .ik {{ flex: none; width: 2.7rem; height: 2.7rem; border-radius: 8px; background: {MIDNIGHT}; display: flex; align-items: center; justify-content: center; }}
.w-usp svg {{ width: 1.45rem; height: 1.45rem; stroke: #FFFFFF; fill: none; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }}
.w-usp b {{ display: block; font-family: Georgia, "Times New Roman", serif; font-weight: 400; font-size: 1.1rem; line-height: 1.2; color: {MIDNIGHT}; margin-bottom: 0.2rem; }}
.w-usp span {{ font-size: 0.84rem; line-height: 1.45; color: {MIDNIGHT}; }}
.w-kopf {{ margin: 2.6rem 0 1.1rem 0; border-bottom: 1px solid {T['titel']}; padding-bottom: 0.5rem; display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; }}
.w-kopf .w-t {{ font-family: Georgia, "Times New Roman", serif; font-weight: 400; font-size: 2.2rem !important; line-height: 1.1; letter-spacing: -0.01em; margin: 0; color: {T['titel']} !important; }}
.w-kopf > span {{ font-size: 0.86rem; color: {T['grau']}; text-align: right; max-width: 28rem; }}
.w-promos {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.1rem; }}
.w-promo {{ display: grid; grid-template-columns: 0.8fr 1.3fr; min-height: 400px; color: #FFFFFF; }}
.w-promo .t {{ padding: 1.6rem 1.4rem; display: flex; flex-direction: column; justify-content: center; }}
.w-promo h3 {{ font-family: Georgia, "Times New Roman", serif; font-weight: 400; font-size: 1.85rem; line-height: 1.15; color: #CEECFF; margin: 0; }}
.w-promo p {{ font-size: 0.94rem; line-height: 1.55; margin: 0; color: #FFFFFF; }}
.w-promo .b {{ background-size: cover; background-position: center 22%; position: relative; }}
.w-badge {{ position: absolute; top: 1rem; right: 1rem; width: 6rem; height: 6rem; border-radius: 50%; background: #CEECFF; color: {MIDNIGHT}; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; font-family: Georgia, "Times New Roman", serif; line-height: 1.05; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.25); }}
.w-badge b {{ font-size: 1.35rem; font-weight: 400; display: block; }}
.w-badge span {{ font-size: 0.95rem; font-style: italic; display: block; }}
.w-cards {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.1rem; }}
.w-card {{ background: {T['flaeche']}; border: 1px solid {T['rand']}; }}
.w-card .b {{ height: auto; aspect-ratio: 16 / 10; background-size: cover; background-position: center; position: relative; }}
.w-card .b span {{ position: absolute; left: 0; bottom: 0; background: {MIDNIGHT}; color: #fff; padding: 0.3rem 0.9rem; font-family: Georgia, "Times New Roman", serif; font-size: 1.15rem; }}
.w-card.slim .b {{ height: auto; aspect-ratio: 16 / 10; background-position: center 45%; }}
.w-card.slim .i {{ padding: 0.7rem 1.1rem 0.8rem 1.1rem; }}
.w-card.slim h4 {{ margin: 0; font-size: 1.3rem; }}
.w-card .i {{ padding: 1rem 1.3rem 1.2rem 1.3rem; }}
.w-card h4 {{ font-family: Georgia, "Times New Roman", serif; font-weight: 400; font-size: 1.45rem; line-height: 1.15; margin: 0 0 0.4rem 0; color: {T['titel']}; }}
.w-card p {{ margin: 0; font-size: 0.88rem; line-height: 1.5; color: {T['text']}; }}
.w-liefer {{ display: grid; grid-template-columns: 1fr 1.7fr; gap: 2.2rem; align-items: center; }}
.w-liefer p {{ margin: 0 0 0.4rem 0; font-size: 0.98rem; line-height: 1.6; color: {T['text']}; }}
.w-liefer small {{ color: {T['grau']}; }}
.w-logos {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 0.8rem; }}
.w-logos div {{ background: #FFFFFF; border: 1px solid {T['rand']}; border-radius: 14px; display: flex; align-items: center; justify-content: center; height: 4.6rem; padding: 0.6rem 0.8rem; }}
.w-logos img {{ max-height: 2.2rem; max-width: 100%; object-fit: contain; }}
.review {{ background: {T['flaeche']}; border: 1px solid {T['rand']}; padding: 1.1rem 1.2rem 1rem 1.2rem; display: flex; flex-direction: column; }}
.review .foto {{ height: auto; aspect-ratio: 4 / 3; background-size: cover; background-position: center 22%; margin: -1.1rem -1.2rem 0.9rem -1.2rem; }}
.review .kopfzeile {{ display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.7rem; }}
.review .avatar {{ flex: none; width: 3.2rem; height: 3.2rem; border-radius: 50%; background: #CEECFF; color: {MIDNIGHT}; font-weight: 700; display: flex; align-items: center; justify-content: center; font-size: 0.85rem; background-size: cover; background-position: center; }}
.review .wer b {{ display: block; color: {T['titel']}; font-size: 0.98rem; }}
.review .wer span {{ font-size: 0.8rem; color: {T['grau']}; }}
.review .sterne {{ color: #F2A900; letter-spacing: 0.12em; font-size: 0.95rem; }}
.review h5 {{ margin: 0.2rem 0 0.4rem 0; font-size: 0.98rem; color: {T['titel']}; line-height: 1.3; }}
.review p {{ margin: 0 0 0.6rem 0; font-size: 0.86rem; line-height: 1.5; color: {T['text']}; flex: 1; }}
.review .daten {{ border-top: 1px solid {T['rand']}; padding-top: 0.6rem; }}
.review .daten small {{ display: block; color: {T['grau']}; font-size: 0.74rem; margin-top: 0.2rem; }}
.fiktiv {{ margin-left: auto; font-size: 0.66rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: {T['grau']}; border: 1px solid {T['rand']}; padding: 0.1rem 0.45rem; }}
.frage {{ border-left: 4px solid {T['akzent']}; padding: 0.2rem 0 0.2rem 1rem; margin: 1.4rem 0 0.8rem 0; font-weight: 700; color: {T['titel']}; font-size: 1.05rem; line-height: 1.4; max-width: 56rem; }}
.frage small {{ display: block; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; font-size: 0.68rem; color: {T['akzent']}; margin-bottom: 0.2rem; }}
.fuss {{ margin-top: 1.4rem; font-size: 0.72rem; color: {T['grau']}; line-height: 1.5; }}
.st-key-pilotkarte [data-testid="stElementContainer"]:has([data-testid="stDeckGlJsonChart"]), .st-key-pilotkarte [data-testid="stDeckGlJsonChart"], .st-key-pilotkarte [data-testid="stDeckGlJsonChart"] > div, .st-key-pilotkarte [data-testid="stDeckGlJsonChart"] iframe {{ height: 520px !important; }}
.st-key-pilotkarte .panel {{ height: 520px; }}

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
[data-testid="stElementContainer"]:has([data-testid="stDeckGlJsonChart"]), [data-testid="stDeckGlJsonChart"], [data-testid="stDeckGlJsonChart"] > div, [data-testid="stDeckGlJsonChart"] iframe {{ height: calc({KOERPER} - 3.5rem) !important; max-height: calc({KOERPER} - 3.5rem) !important; min-height: 0 !important; overflow: hidden; }}
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


@st.cache_data(show_spinner=False)
def viertel(lat: float, lon: float):
    """Viertel und Bezirk zu einer Koordinate über Nominatim (OpenStreetMap). Ohne Netz gibt es None."""
    import urllib.request
    url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=14&addressdetails=1&accept-language=de&lat={lat:.5f}&lon={lon:.5f}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "olive-whitespot-hackathon/1.0"})
        a = json.load(urllib.request.urlopen(req, timeout=6)).get("address", {})
    except Exception:
        return None
    teil = a.get("suburb") or a.get("neighbourhood") or a.get("quarter") or a.get("city_district") or a.get("town") or a.get("village")
    bezirk = a.get("city_district") if a.get("city_district") != teil else a.get("borough")
    return (teil, bezirk) if teil else None


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


@st.cache_data
def _bild_lesen(pfad_: str, geaendert: float) -> str:
    """Bild als eingebetteter Datenstrom. Der Änderungszeitpunkt steckt im Cache-Schlüssel, damit neue oder ersetzte Dateien sofort erscheinen."""
    p = Path(pfad_)
    mime = {".png": "image/png", ".svg": "image/svg+xml", ".webp": "image/webp"}.get(p.suffix.lower(), "image/jpeg")
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def bild_uri(relativ: str):
    """Bild unter dem relativen Pfad. Fehlt die Datei, gibt es None und die Seite zeigt eine Fläche."""
    p = Path(__file__).parent / relativ
    return _bild_lesen(str(p), p.stat().st_mtime) if p.exists() else None


def generiert(schluessel: str):
    """Selbst erzeugtes Bild unter assets/bilder/<schluessel>.jpg, .png oder .webp. Fehlt es, gibt es None."""
    for endung in ("jpg", "jpeg", "png", "webp"):
        uri_ = bild_uri(f"assets/bilder/{schluessel}.{endung}")
        if uri_:
            return uri_
    return None


def flaeche(schluessel: str, klasse: str, extra: str = "") -> str:
    """HTML-Element mit dem Bild als Hintergrund. Fehlt das Bild, steht eine Farbfläche mit "Bild folgt"."""
    uri_ = generiert(schluessel)
    if uri_:
        return f'<div class="{klasse}" style="background-image:url({uri_})">{extra}</div>'
    return f'<div class="{klasse} fallback">{extra}<span>Bild folgt</span></div>'


def laden_icon() -> dict:
    """Kleines Laden-Symbol (Markise, Schaufenster, Tür) als SVG. Kein Emoji."""
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">'
           '<circle cx="64" cy="64" r="58" fill="#2C6EF2" stroke="#EF4E45" stroke-width="8"/>'
           '<path d="M32 52 L40 34 H88 L96 52 Z" fill="#fff"/>'
           '<path d="M32 52 a8 8 0 0 0 16 0 a8 8 0 0 0 16 0 a8 8 0 0 0 16 0 a8 8 0 0 0 16 0" fill="#CEECFF"/>'
           '<rect x="38" y="62" width="52" height="30" fill="none" stroke="#fff" stroke-width="5"/>'
           '<rect x="56" y="70" width="16" height="22" fill="#fff"/></svg>')
    return {"url": "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode(), "width": 128, "height": 128, "anchorY": 64}


ICONS = {
    "phone": '<rect x="7" y="2.5" width="10" height="19" rx="2.2"/><line x1="11" y1="18" x2="13" y2="18"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.2 2"/>',
    "moon": '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
    "bag": '<path d="M6 8h12l1 12H5L6 8z"/><path d="M9 8a3 3 0 0 1 6 0"/>',
    "leaf": '<path d="M5 19c0-8 5-14 15-14 0 10-6 15-14 15"/><path d="M5 19c3-5 6-8 11-10"/>',
}


def marke_im_namen(marke: str, voll: str) -> str:
    """Der volle Name mit den Buchstaben der Marke hervorgehoben. Jeder Buchstabe wird höchstens einmal benutzt."""
    uebrig = list(marke.upper().replace(" ", ""))
    teile = []
    for zeichen in voll:
        if zeichen != " " and zeichen.upper() in uebrig:
            uebrig.remove(zeichen.upper())
            teile.append(f'<span class="treffer">{escape(zeichen)}</span>')
        else:
            teile.append("&nbsp;&nbsp;" if zeichen == " " else escape(zeichen))
    return "".join(teile)


def bildnachweise() -> str:
    """Autor und Lizenz aller geladenen Fotos und Logos, aus den quellen.json neben den Bildern."""
    teile = set()
    for ordner in ("assets/staedte", "assets/partner"):
        p = Path(__file__).parent / ordner / "quellen.json"
        if p.exists():
            for v in json.loads(p.read_text(encoding="utf-8")).values():
                teile.add(f'{v["autor"]} ({v["lizenz"]})')
    return "Städtefotos und Partner-Logos: Wikimedia Commons. " + "; ".join(sorted(teile)) + ". Das runde Logo stellt die Gruppe bereit."


@st.cache_data
def pilotstandorte():
    """Die drei bestplatzierten Standorte je Stadt, für die Karte auf der Startseite."""
    teile = []
    for c in K.STAEDTE:
        d, _ = lade_stadt(c["key"])
        if d is None:
            continue
        t = d[d["rang"].notna()].nsmallest(3, "rang").copy()
        t["stadt_name"] = c["name"]
        t["nr"] = range(1, len(t) + 1)
        t["lage"] = t.apply(lagebezeichnung, axis=1, pois=lade_pois(c["key"]))
        teile.append(t[["stadt_name", "nr", "lage", "lat", "lon", "profil"]])
    return pd.concat(teile, ignore_index=True) if teile else None


# ---------------------------------------------------------------- Seitenleiste
# Kopfzeile: Ansichten zum Durchklicken, Stadt, Optionen der Ansicht und Einstellungen. Keine Seitenleiste.
nav, c_stadt, c_opt, zahnrad = st.columns([6.4, 1.7, 1.6, 1.9], vertical_alignment="center")
with nav:
    gewaehlte_ansicht = st.segmented_control("Ansicht", ANSICHTEN, default="Konzept", key="ansicht",
                                             label_visibility="collapsed")
ansicht = gewaehlte_ansicht or "Konzept"  # ein Klick auf die aktive Ansicht würde sie abwählen
stadt_name = c_stadt.selectbox("Stadt", list(STAEDTE), label_visibility="collapsed", key="stadt")
key = STAEDTE[stadt_name]
df, ist_demo = lade_stadt(key)
if df is None:
    st.error(f"Für {stadt_name} liegen keine Daten vor. Demo erzeugen mit: python analyse.py --demo")
    st.stop()
pois = lade_pois(key)
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

# Optionen der gerade offenen Ansicht in einem Menü neben den Einstellungen
ebene, nur_lagen, zeige_portfolio = "Score", True, False
gewaehlt, wahl = [], None
if ansicht != "Konzept" and ansicht != "Annahmen":
    with c_opt.popover("Optionen", icon=":material/tune:", use_container_width=True):
        if ansicht == "Karte":
            ebene = st.selectbox("Ebene", list(EBENEN))
            nur_lagen = st.toggle("Nur Geschäftslagen", value=True)
            zeige_portfolio = st.toggle("Portfolio zeigen", value=False)
            if "rang_gemeinsam" in df.columns:
                st.radio("Maßstab", ["Innerhalb der Stadt", "Gemeinsam über alle drei"])
        elif ansicht == "Vergleich":
            gewaehlt = st.multiselect("Standorte vergleichen", list(optionen), default=list(optionen)[:2], max_selections=3)
        elif ansicht == "Erklärung":
            wahl = st.selectbox("Standort", list(optionen))
        elif ansicht == "Rangliste":
            zeige_wahl = st.selectbox("Auf der Karte zeigen", list(optionen))
            st.button("Zur Karte", on_click=lambda: (st.session_state["auswahl"].__setitem__(key, optionen[zeige_wahl]),
                                                     st.session_state.update(ansicht="Karte")))

QUELLE = "Quellen: OpenStreetMap-Mitwirkende, Statistisches Bundesamt (Zensus 2022)."


def karten_leiste(callback_reset, key_: str):
    """Leiste oben links auf der Karte: Ansicht zurücksetzen und Vollbild. Gilt für beide Karten gleich.
    Der Zoom steckt in der Karte selbst (Plus und Minus oben rechts). Im Vollbild bleiben alle drei bedienbar."""
    vb_key = f"vb_{key_}"
    voll = st.session_state.get(vb_key, False)
    with st.container(key=f"rk_{key_}"):  # liegt als Overlay oben links auf der Karte, damit das Layout nicht verrutscht
        c1, c2, _ = st.columns([1.5, 1.2, 2.2])
        c1.button("Ansicht zurücksetzen", on_click=callback_reset, key=f"reset_{key_}", icon=":material/restart_alt:", use_container_width=True)
        c2.button("Vollbild beenden" if voll else "Vollbild", on_click=lambda: st.session_state.update({vb_key: not voll}),
                  key=f"vbknopf_{key_}", icon=":material/close_fullscreen:" if voll else ":material/fullscreen:", use_container_width=True)
    if voll:  # Karte füllt die Seite, Seitenleiste ausgeblendet
        st.markdown("""<style>
        section[data-testid="stSidebar"], [data-testid="stExpandSidebarButton"] { display: none !important; }
        [data-testid="stElementContainer"]:has([data-testid="stDeckGlJsonChart"]), [data-testid="stDeckGlJsonChart"],
        [data-testid="stDeckGlJsonChart"] > div, [data-testid="stDeckGlJsonChart"] iframe,
        .st-key-pilotkarte [data-testid="stElementContainer"]:has([data-testid="stDeckGlJsonChart"]), .st-key-pilotkarte [data-testid="stDeckGlJsonChart"],
        .st-key-pilotkarte [data-testid="stDeckGlJsonChart"] > div, .st-key-pilotkarte [data-testid="stDeckGlJsonChart"] iframe { height: calc(100vh - 17rem) !important; max-height: calc(100vh - 17rem) !important; }
        </style>""", unsafe_allow_html=True)
    return voll


def zweispaltig():
    """Exhibit links, Kommentarfeld rechts. Ist das Kommentarfeld ausgeblendet, bekommt das Exhibit die volle Breite."""
    if zeige_panel:
        return st.columns([7.4, 3.6], gap="medium")
    return st.container(), None


# --------------------------------------------------------------------- Konzept
if ansicht == "Konzept":
    def uri(pfad_):
        return bild_uri(pfad_) or ""

    logo = bild_uri("assets/logo.png")
    titel_html = escape(K.INTRO_TITEL).replace(escape(K.INTRO_UNTERSTRICHEN), f"<u>{escape(K.INTRO_UNTERSTRICHEN)}</u>", 1)
    usps = "".join(
        f'<div class="u"><div class="ik"><svg viewBox="0 0 24 24">{ICONS.get(ic, "")}</svg></div><div><b>{escape(t)}</b><span>{escape(x)}</span></div></div>'
        for ic, t, x in K.USPS)
    wert = "".join(
        f'<div class="w-promo" style="background:{w["farbe"]}"><div class="t"><h3>{escape(w["titel"])}</h3></div>'
        + flaeche(w["bild"], "b")
        + "</div>" for w in K.WERT)
    sortiment = "".join(
        f'<div class="w-card slim">{flaeche(bild, "b")}<div class="i"><h4>{escape(titel)}</h4></div></div>'
        for titel, text, bild in K.SORTIMENT)
    staedte = ""
    for c in K.STAEDTE:
        bild_c = generiert("stadt_" + c["key"]) or bild_uri(c["bild"]) or ""
        staedte += (f'<div class="w-card"><div class="b" style="background-image:url({bild_c}); background-color:{MIDNIGHT}"><span>{escape(c["name"])}</span></div>'
                    f'<div class="i"><p>{escape(c["text"])}</p></div></div>')
    personas = ""
    for p in K.PERSONAS:
        foto = bild_uri(p["foto"])
        avatar = "" if foto else f'<div class="avatar">{escape(p["kuerzel"])}</div>'
        bild_p = f'<div class="foto" style="background-image:url({foto})"></div>' if foto else ""
        personas += (f'<div class="review">{bild_p}<div class="kopfzeile">{avatar}'
                     f'<div class="wer"><b>{escape(p["name"])}, {escape(p["alter"])}</b><span>{escape(p["rolle"])} aus {escape(p["stadt"])}</span></div>'
                     f'<span class="fiktiv">fiktiv</span></div>'
                     f'<div class="sterne">{"★" * p["sterne"]}</div><h5>{escape(p["titel"])}</h5><p>„{escape(p["text"])}“</p>'
                     f'<div class="daten">' + "".join(f'<span class="chip">{escape(c)}</span>' for c in p["signale"])
                     + f'<small>Quelle: {escape(p["quelle"])} · Im Modell: {escape(p["modell"])}</small></div></div>')
    logos = "".join(f'<div title="{escape(n)}"><img src="{uri(l)}" alt="{escape(n)}"></div>' for n, l in K.LIEFERUNG_PARTNER)

    st.markdown(f"""
<div class="w-intro">
  <h1>{titel_html}</h1>
  <div class="w-intro-zeile"><p>{escape(K.INTRO_TEXT)}</p><div class="l">{f'<img src="{logo}" alt="Logo">' if logo else ""}</div></div>
</div>

<div class="w-split">
  {flaeche(K.HERO_BILD, "bild")}
  <div class="text">
    <div class="w-kicker">{escape(K.VERANSTALTUNG)}</div>
    <div class="w-marke">{escape(K.MARKE)}</div>
    <div class="w-bez">{escape(K.BEZEICHNUNG)}</div>
    <div class="w-claim">{escape(K.CLAIM)}</div>
    <div class="w-sub">{escape(K.UNTERZEILE)}</div>
  </div>
</div>
<div class="w-usp">{usps}</div>

<div class="w-kopf"><div class="w-t">Wertversprechen</div><span>Zwei Momente, ein Laden</span></div>
<div class="w-promos">{wert}</div>

<div class="w-kopf"><div class="w-t">Vom Deli-Tresen</div><span>Italienisch, mediterran, französisch, regional und gesund</span></div>
<div class="w-cards">{sortiment}</div>

<div class="w-kopf"><div class="w-t">Drei Städte, drei Hypothesen</div><span>Was jede Stadt dem Modell abverlangt</span></div>
<div class="w-cards">{staedte}</div>

<div class="w-kopf"><div class="w-t">Zielgruppen</div><span>Drei fiktive Personas, die unsere Datenwahl begründen</span></div>
<div class="w-cards">{personas}</div>

<div class="w-kopf"><div class="w-t">Lieferung</div><span>Mögliche Partner</span></div>
<div class="w-liefer"><div><p>{escape(K.LIEFERUNG_TEXT)}</p><small>{escape(K.LIEFERUNG_HINWEIS)}</small></div><div class="w-logos">{logos}</div></div>

<div class="w-kopf"><div class="w-t">Pilotstandorte</div><span>So finden Sie uns</span></div>
<p style="margin:0 0 0.9rem 0; font-size:0.95rem; color:{T['text']}">{escape(K.PILOT_TEXT)}</p>
""", unsafe_allow_html=True)

    pil = pilotstandorte()
    if pil is not None and len(pil):
        sicht = pil[pil["nr"] == 1].reset_index(drop=True)  # je Stadt der beste White Spot
        sicht["text"] = ""
        sicht["icon_data"] = [laden_icon()] * len(sicht)
        st.session_state.setdefault("pilot_stadt", None)   # None = ganz Deutschland, sonst Name der herangezoomten Stadt
        st.session_state.setdefault("pilot_zaehler", 0)
        fokus = st.session_state["pilot_stadt"]
        if fokus is not None and fokus in set(sicht["stadt_name"]):
            z_ = sicht[sicht["stadt_name"] == fokus].iloc[0]
            ansicht_pilot = pdk.ViewState(latitude=float(z_["lat"]), longitude=float(z_["lon"]), zoom=12.5, min_zoom=5.0, max_zoom=17)
        else:
            ansicht_pilot = pdk.ViewState(latitude=50.6, longitude=10.8, zoom=5.0, min_zoom=5.0, max_zoom=17)  # Deutschland
        schichten_p = [
            pdk.Layer("IconLayer", sicht, get_icon="icon_data", get_position=["lon", "lat"], get_size=46, size_scale=1, size_min_pixels=40, size_max_pixels=40,
                      pickable=True, id="pilot"),
        ]
        with st.container(key="pilotkarte"):
            voll_p = st.session_state.get("vb_pilot", False)
            links, rechts = (st.container(), st.container()) if voll_p else st.columns([7.4, 3.6], gap="medium")
            with links:
                karten_leiste(lambda: st.session_state.update(
                    pilot_stadt=None, pilot_zaehler=st.session_state.get("pilot_zaehler", 0) + 1), "pilot")
                ereignis_p = st.pydeck_chart(
                    pdk.Deck(layers=schichten_p, initial_view_state=ansicht_pilot, map_style=T["karte"],
                             tooltip={"html": "<b>{stadt_name}</b><br>{lage}<br>Klicken zum Hinein- und Herauszoomen",
                                      "style": {"fontSize": "13px", "fontFamily": "Arial"}}),
                    width="stretch", height=520, on_select="rerun", selection_mode="single-object",
                    key=f"pilotkarte_{st.session_state['pilot_zaehler']}")
                obj = (ereignis_p.selection.objects.get("pilot") if ereignis_p and ereignis_p.selection else None) or []
                if obj:  # Klick: Stadt heranzoomen, bei erneutem Klick auf dieselbe Stadt wieder herauszoomen
                    gewaehlt_p = obj[0].get("stadt_name")
                    st.session_state["pilot_stadt"] = None if st.session_state["pilot_stadt"] == gewaehlt_p else gewaehlt_p
                    st.session_state["pilot_zaehler"] += 1  # neuer Schlüssel setzt die Auswahl zurück, damit jeder Klick zählt
                    st.rerun()
            if not voll_p:  # im Vollbild füllt die Karte die Seite
                with rechts:
                    gruppen = '<h4>Bester White Spot je Stadt</h4>'
                    for r in sicht.itertuples():
                        gruppen += (f'<div class="rang"><span class="pin">{r.Index + 1}</span><div class="rang-t"><b>{escape(r.stadt_name)}</b>'
                                    f'<span>{escape(r.lage)} · {escape(r.profil)}</span></div></div>')
                    panel(gruppen + '<p class="klein" style="margin-top:0.8rem">Marker anklicken zoomt in die Stadt, ein weiterer Klick zoomt zurück.</p>')
    st.markdown(f'<div class="frage"><small>Business-Frage</small>{escape(K.BUSINESS_FRAGE)}</div>', unsafe_allow_html=True)
    st.button("Zur Karte öffnen", on_click=lambda: st.session_state.update(ansicht="Karte"), type="primary")
    st.markdown(f'<div class="fuss">{escape(K.HINWEIS)}<br>{escape(bildnachweise())}</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------- Karte
elif ansicht == "Karte":
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
                  extruded=False, opacity=1, pickable=True, id="hex"),
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

    if auswahl is not None and auswahl in set(df["h3"]):  # gewähltes Feld hervorheben und Einzugsgebiet (400 m) zeigen
        zeile_a = df[df["h3"] == auswahl]
        schichten.append(pdk.Layer("H3HexagonLayer", zeile_a, get_hexagon="h3", get_fill_color=[0, 0, 0, 0],
                                   get_line_color=[255, 255, 255, 255] if DUNKEL else [11, 27, 77, 255], stroked=True, filled=False,
                                   line_width_min_pixels=5, extruded=False))
        schichten.append(pdk.Layer("ScatterplotLayer", zeile_a, get_position=["lon", "lat"], get_radius=400,
                                   get_fill_color=[44, 110, 242, 30], get_line_color=[44, 110, 242, 220], stroked=True,
                                   line_width_min_pixels=2))

    voll_k = st.session_state.get("vb_karte", False)
    links, rechts = (st.container(), None) if voll_k else zweispaltig()
    with links:
        if rechts is None:  # ohne Kommentarfeld oder im Vollbild sitzt die Legende über der Karte
            st.markdown(legende_html(ebene, stadt_name, nur_lagen, senkrecht=False), unsafe_allow_html=True)
        karten_leiste(lambda: (st.session_state["auswahl"].pop(key, None),
                               st.session_state.update(karte_zaehler=st.session_state.get("karte_zaehler", 0) + 1)), "karte")
        ereignis = st.pydeck_chart(pdk.Deck(layers=schichten, initial_view_state=view, map_style=T["karte"], tooltip=tooltip),
                                   width="stretch", height=600, on_select="rerun", selection_mode="single-object",
                                   key=f"karte_{key}_{st.session_state.get('karte_zaehler', 0)}")
        objekte = (ereignis.selection.objects.get("hex") if ereignis and ereignis.selection else None) or []
        if objekte and objekte[0].get("h3") != auswahl:
            st.session_state["auswahl"][key] = objekte[0]["h3"]
            st.rerun()
    if rechts is not None:
        with rechts:
            if auswahl is not None and auswahl in set(df["h3"]):
                st.button("Auswahl aufheben", on_click=lambda: st.session_state["auswahl"].pop(key, None))
                z = df[df["h3"] == auswahl].iloc[0]
                v = viertel(round(float(z["lat"]), 4), round(float(z["lon"]), 4))
                titel_v = v[0] if v else f"{z['lat']:.4f}, {z['lon']:.4f}"
                bezirk_v = f"{v[1]}, {stadt_name}" if v and v[1] else stadt_name
                rang_v = f"Rang {int(z['rang'])}" if pd.notna(z["rang"]) else "keine Geschäftslage"
                stat = lambda w, x: f'<div class="stat"><span>{escape(w)}</span><b>{escape(str(x))}</b></div>'
                miete_v = f"{z['miete_qm']:.2f} €/m²" if pd.notna(z["miete_qm"]) else "–"
                panel(f'<div class="kicker">Gewählter Standort</div><h4 style="font-size:1.25rem;margin:0.2rem 0 0">{escape(titel_v)}</h4>'
                      f'<p class="klein" style="margin:0 0 0.7rem 0">{escape(bezirk_v)} · {rang_v}</p>'
                      f'<div class="statraster">{stat("Score (PR)", f"{z.pr_score:.0f}" if pd.notna(z.pr_score) else "–")}'
                      f'{stat("Angebotslücke (PR)", f"{z.pr_luecke:.0f}" if pd.notna(z.pr_luecke) else "–")}'
                      f'{stat("Einwohner (400 m)", f"{z.einwohner_400m:,.0f}".replace(",", "."))}'
                      f'{stat("Wettbewerber (400 m)", f"{z.wettbewerber_400m:.0f}")}'
                      f'{stat("Miete", miete_v)}{stat("Profil", z.profil)}</div>'
                      f'<div class="abschnitt"><p>{escape(staerken_satz(z))}</p>'
                      f'<p class="klein">Der blaue Kreis zeigt das Einzugsgebiet von 400 m.</p></div>')
            else:
                reihen = ""
                for r in top.head(3).itertuples():
                    konsens = " · Konsens" if r.konsens else ""
                    reihen += (f'<div class="rang"><span class="pin">{int(r.rang)}</span><div class="rang-t"><b>{escape(r.lage)}</b>'
                               f'<span>{escape(r.profil)} · {escape(stabilitaet(r.top10_anteil))}{konsens}</span></div>'
                               f'<span class="rang-s">{r.pr_score:.0f}</span></div>')
                panel(legende_html(ebene, stadt_name, nur_lagen, senkrecht=True)
                      + '<div class="abschnitt"><h4>Die drei besten Standorte</h4>' + reihen
                      + '<p class="klein" style="margin-top:0.4rem">Zahl rechts: Score-Prozentrang. Ein Feld anklicken zeigt Viertel und Kennzahlen.</p></div>')
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
        st.info("Wähle unter Optionen mindestens zwei Standorte.")
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
