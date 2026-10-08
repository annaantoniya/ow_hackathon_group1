"""
Datengrundlage: White Spots in München, Frankfurt und Berlin
=============================================================

Dieses Skript baut die komplette Datengrundlage des Projekts aus offenen Quellen
und schreibt sie in eine Form, mit der `analyse.py` sofort rechnen kann.

Aufruf
------
    pip install pandas numpy h3 pyproj pyshp shapely scikit-learn requests
    python datengrundlage.py                      # alle drei Städte
    python datengrundlage.py --staedte frankfurt  # nur eine Stadt
    python datengrundlage.py --ohne-osm           # nur Zensus, POI-Spalten bleiben null

Quellen
-------
1. Statistisches Bundesamt, Zensus 2022, Gitterdaten im 100-m-Raster
   https://www.destatis.de/DE/Themen/Gesellschaft-Umwelt/Bevoelkerung/Zensus2022/_inhalt.html
   Download: https://www.destatis.de/static/DE/zensus/gitterdaten/<Archiv>
   Lizenz: Datenlizenz Deutschland – Namensnennung – Version 2.0
2. Verwaltungsgrenzen VG250 (im Shapefile-Archiv des Zensus enthalten), EPSG:25832
3. OpenStreetMap über die Overpass API, https://overpass-api.de
   © OpenStreetMap-Mitwirkende, Lizenz ODbL 1.0

Ablauf je Stadt
---------------
1. Zensus-Archive herunterladen (einmalig, rund 155 MB, landen in `zensus/`).
2. Stadtgrenze aus VG250 lesen und um 1.500 m puffern.
3. Das gepufferte Gebiet in H3-Hexagone der Auflösung 9 zerlegen.
4. Die 100-m-Zensuszellen auf die Hexagone verteilen (Einwohner, Miete, Alter, Haushalte).
5. Lücken der Miete aus Nachbarzellen schließen, Lücken im Alter mit dem Stadtwert.
6. POIs per Overpass abrufen, eine Abfrage je Gruppe (Antwort in `cache/`), Kategorien zuordnen, Dubletten entfernen.
7. POIs je Hexagon und Kategorie zählen.
8. Ergebnis schreiben und gegen die Sollwerte aus der Spezifikation prüfen.

Ausgaben
--------
`data/<stadt>_pois.csv`  eine Zeile pro POI
    osm_id, lat, lon, gruppe, kategorie, name, brand, cuisine, organic

`data/<stadt>_grid.csv`  eine Zeile pro Hexagon, die Analysetabelle
    h3                Kennung des Hexagons (H3, Auflösung 9, rund 0,1 km²)
    lat, lon          Mittelpunkt in WGS84
    stadt             Schlüssel der Stadt
    in_stadt          True, wenn der Mittelpunkt in der Stadtgrenze liegt (sonst Puffer)
    einwohner         Einwohner, 0 bei unbewohnten Zellen
    miete_qm          Nettokaltmiete in Euro je m², mit Wohnungen gewichtet
    mietwohnungen     Zahl der Wohnungen hinter dem Mietwert
    miete_geschaetzt  True, wenn der Mietwert aus Nachbarzellen stammt
    anteil_20_49      Anteil der 20- bis 49-Jährigen
    alter_geschaetzt  True, wenn der Stadtwert eingesetzt wurde
    haushalte         Zahl der Haushalte
    anteil_hh_1_3     Anteil der Haushalte mit einer bis drei Personen
    poi_<kategorie>   Anzahl POIs je Kategorie (34 Spalten)

Laufzeit beim ersten Start: Download wenige Minuten, Zensus je Stadt rund eine Minute,
Overpass je Stadt bis zu einigen Minuten. Danach kommt alles aus `zensus/` und `cache/`.
"""

from __future__ import annotations

import argparse
import io
import json
import time
import zipfile
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import requests
import shapefile  # Paket pyshp
import shapely
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform as shp_transform
from sklearn.neighbors import BallTree

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
ZENSUS = ROOT / "zensus"
CACHE = ROOT / "cache"
DATA = ROOT / "data"

H3_AUFLOESUNG = 9
PUFFER_M = 1500
DUBLETTEN_RADIUS_M = 20
ERDRADIUS_M = 6_371_000
CHUNK_ZEILEN = 500_000

# AGS = Amtlicher Gemeindeschlüssel der kreisfreien Stadt in VG250_KRS.
# Die Sollwerte stammen aus dem Testlauf vom 7. Oktober 2026 (Umsetzungsspezifikation, Abschnitt 3).
STAEDTE = {
    "muenchen": {"name": "München", "ags": "09162", "soll_hex": 3055, "soll_einwohner": 1_475_469},
    "frankfurt": {"name": "Frankfurt am Main", "ags": "06412", "soll_hex": 2590, "soll_einwohner": 744_205},
    "berlin": {"name": "Berlin", "ags": "11000", "soll_hex": 9472, "soll_einwohner": 3_594_123},
}

ZENSUS_URL = "https://www.destatis.de/static/DE/zensus/gitterdaten/"
ZENSUS_ARCHIVE = {
    "bevoelkerung": "Zensus2022_Bevoelkerungszahl.zip",
    "miete": "Durchschnittliche_Nettokaltmiete_und_Anzahl_der_Wohnungen.zip",
    "alter": "Alter_in_10er-Jahresgruppen.zip",
    "haushalte": "Zensus2022_Groesse_des_privaten_Haushalts_in_Gitterzellen.zip",
    "grenzen": "Shapefile_Zensus2022.zip",
}
# Nur die 100-m-Datei jedes Archivs wird gelesen; die Endung identifiziert sie eindeutig.
ZENSUS_DATEI = {
    "bevoelkerung": "Bevoelkerungszahl_100m-Gitter.csv",
    "miete": "Nettokaltmiete_Anzahl_der_Wohnungen_100m-Gitter.csv",
    "alter": "Alter_in_10er-Jahresgruppen_100m-Gitter.csv",
    "haushalte": "Groesse_des_privaten_Haushalts_100m-Gitter.csv",
}
ZENSUS_SPALTEN = {
    "bevoelkerung": ["Einwohner"],
    "miete": ["durchschnMieteQM", "AnzahlWohnungen", "werterlaeuternde_Zeichen"],
    "alter": ["Unter10", "a10bis19", "a20bis29", "a30bis39", "a40bis49",
              "a50bis59", "a60bis69", "a70bis79", "a80undaelter"],
    "haushalte": ["Insgesamt_Haushalte", "1_Person", "2_Personen", "3_Personen",
                  "4_Personen", "5_Personen", "6_Personen_und_mehr"],
}

# Der Hauptserver ist oft überlastet (504); dann wird der nächste Spiegel versucht.
OVERPASS_URLS = ["https://overpass-api.de/api/interpreter",
                 "https://overpass.private.coffee/api/interpreter",
                 "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
# Overpass lehnt Anfragen ohne User-Agent mit 406 ab.
USER_AGENT = "whitespot-hackathon/1.0 (Standortanalyse, nicht kommerziell)"
PAUSE_ZWISCHEN_STAEDTEN_S = 20

# ---------------------------------------------------------------------------
# POI-Kategorien
# ---------------------------------------------------------------------------
# Jede Regel: (gruppe, kategorie, [Bedingungen]). Eine Bedingung ist ein dict
# Tag -> erlaubte Werte; None heißt "Tag vorhanden, Wert egal". Eine Regel greift,
# wenn mindestens eine ihrer Bedingungen vollständig erfüllt ist.
# Die Reihenfolge ist die Priorität: Ein POI bekommt die erste passende Kategorie.
# Deshalb steht z. B. U-Bahn vor Bahnhof und Bio-Markt vor Supermarkt.

BIO_MARKEN = {"alnatura", "denn's biomarkt", "denns biomarkt", "bio company", "basic",
              "lpg biomarkt", "ebl naturkost", "vollcorner", "erdkorn", "superbiomarkt",
              "aleco biomarkt", "naturgut"}

POI_REGELN: list[tuple[str, str, list[dict[str, set[str] | None]]]] = [
    # wettbewerb_direkt: ähnliches Sortiment, Zielgröße der Angebotslücke
    ("wettbewerb_direkt", "markthalle", [{"amenity": {"marketplace"}}]),
    ("wettbewerb_direkt", "bio_markt", [{"shop": {"supermarket"}, "organic": {"only"}},
                                        {"shop": {"organic"}}]),
    ("wettbewerb_direkt", "reformhaus", [{"shop": {"health_food"}}]),
    ("wettbewerb_direkt", "deli", [{"shop": {"deli", "delicatessen"}}]),
    ("wettbewerb_direkt", "feinkost_kaese", [{"shop": {"cheese", "dairy"}}]),
    ("wettbewerb_direkt", "wein", [{"shop": {"wine"}}]),
    ("wettbewerb_direkt", "pasta", [{"shop": {"pasta"}}]),
    # wettbewerb_breit: deckt nur einen Teil des Bedarfs, geringes Gewicht im Huff-Modell
    ("wettbewerb_breit", "supermarkt", [{"shop": {"supermarket"}}]),
    ("wettbewerb_breit", "obst_gemuese", [{"shop": {"greengrocer"}}]),
    ("wettbewerb_breit", "metzger", [{"shop": {"butcher"}}]),
    ("wettbewerb_breit", "baecker", [{"shop": {"bakery", "pastry"}}]),
    ("wettbewerb_breit", "fisch", [{"shop": {"seafood"}}]),
    # affinitaet: Umfeld, in dem die Zielgruppe lebt und unterwegs ist
    ("affinitaet", "cafe", [{"amenity": {"cafe"}}]),
    ("affinitaet", "restaurant", [{"amenity": {"restaurant"}}]),
    ("affinitaet", "bar", [{"amenity": {"bar", "pub", "biergarten"}}]),
    ("affinitaet", "buchhandlung", [{"shop": {"books"}}]),
    ("affinitaet", "interior", [{"shop": {"interior_decoration", "houseware"}}]),
    # clothes ist breiter als "Boutique", aber shop=boutique allein ist in OSM zu selten getaggt.
    ("affinitaet", "boutique", [{"shop": {"boutique", "clothes"}}]),
    ("affinitaet", "blumen", [{"shop": {"florist"}}]),
    ("affinitaet", "fitness_yoga", [{"leisure": {"fitness_centre"}}, {"sport": {"yoga"}}]),
    ("affinitaet", "kultur", [{"amenity": {"theatre", "cinema", "arts_centre"}}]),
    ("affinitaet", "galerie_museum", [{"tourism": {"museum", "gallery"}}, {"shop": {"art"}}]),
    ("affinitaet", "coworking", [{"amenity": {"coworking_space"}}, {"office": {"coworking"}}]),
    ("affinitaet", "fahrradladen", [{"shop": {"bicycle"}}]),
    # frequenz: Index der Tagesbevölkerung
    ("frequenz", "tram_ubahn", [{"railway": {"station"}, "station": {"subway"}},
                                {"railway": {"tram_stop"}}]),
    ("frequenz", "bahnhof", [{"railway": {"station", "halt"}}]),
    ("frequenz", "bus", [{"highway": {"bus_stop"}}]),
    ("frequenz", "hochschule", [{"amenity": {"university", "college"}}]),
    ("frequenz", "buero", [{"office": None}]),
    # milieu: Umfeld, das Laufkundschaft für Feinkost abschreckt (Ersatz für fehlende Kriminalitätsdaten)
    ("milieu", "spielhalle", [{"amenity": {"gambling", "casino"}}, {"leisure": {"adult_gaming_centre"}}]),
    ("milieu", "wettbuero", [{"shop": {"bookmaker"}}]),
    ("milieu", "erotik", [{"shop": {"erotic"}}, {"amenity": {"stripclub", "brothel", "love_hotel"}}]),
    ("milieu", "drogenhilfe", [{"amenity": {"social_facility"}, "social_facility:for": {"drug_addicted"}}]),
    ("milieu", "pfandleiher", [{"shop": {"pawnbroker"}}]),
]
# Gruppen, die ein Overpass-Cache ohne Gruppenliste enthält (Stand vor der Gruppe milieu).
GRUPPEN_ALTER_CACHE = ["wettbewerb_direkt", "wettbewerb_breit", "affinitaet", "frequenz"]

KATEGORIEN = list(dict.fromkeys(k for _, k, _ in POI_REGELN))
GRUPPE_VON = {k: g for g, k, _ in POI_REGELN}
TAGS_BEHALTEN = {"name", "brand", "cuisine", "organic"} | {
    tag for _, _, bedingungen in POI_REGELN for b in bedingungen for tag in b
}


# ---------------------------------------------------------------------------
# 1. Zensus herunterladen
# ---------------------------------------------------------------------------

def lade_zensus_archive() -> None:
    """Lädt fehlende Zensus-Archive. Die ZIPs werden nicht entpackt, sondern direkt gelesen."""
    ZENSUS.mkdir(exist_ok=True)
    for archiv in ZENSUS_ARCHIVE.values():
        ziel = ZENSUS / archiv
        if ziel.exists() and ziel.stat().st_size > 0:
            continue
        print(f"  Lade {archiv} ...")
        tmp = ziel.with_suffix(".part")
        with requests.get(ZENSUS_URL + archiv, headers={"User-Agent": USER_AGENT},
                          stream=True, timeout=600) as antwort, open(tmp, "wb") as f:
            antwort.raise_for_status()
            for block in antwort.iter_content(1 << 20):
                f.write(block)
        tmp.rename(ziel)


def zip_mitglied(archiv: Path, endung: str) -> str:
    with zipfile.ZipFile(archiv) as z:
        treffer = [n for n in z.namelist() if n.endswith(endung)]
    if not treffer:
        raise FileNotFoundError(f"{endung} nicht in {archiv.name}")
    return treffer[0]


# ---------------------------------------------------------------------------
# 2. Stadtgrenze und Untersuchungsgebiet
# ---------------------------------------------------------------------------

UTM_ZU_WGS = Transformer.from_crs(25832, 4326, always_xy=True)
WGS_ZU_LAEA = Transformer.from_crs(4326, 3035, always_xy=True)
LAEA_ZU_WGS = Transformer.from_crs(3035, 4326, always_xy=True)


def lade_stadtgrenze(ags: str) -> tuple[shapely.Geometry, shapely.Geometry]:
    """Gibt (Stadtgrenze, Stadtgrenze plus Puffer) in WGS84 zurück.

    GF == 4 sind die Landflächen; die anderen Zeilen enthalten Wasserflächen der Küsten.
    Gepuffert wird in EPSG:25832, weil der Puffer in Metern angegeben ist.
    """
    archiv = ZENSUS / ZENSUS_ARCHIVE["grenzen"]
    basis = zip_mitglied(archiv, "VG250_KRS.shp")[: -len(".shp")]
    with zipfile.ZipFile(archiv) as z:
        teile = {e: io.BytesIO(z.read(basis + "." + e)) for e in ("shp", "shx", "dbf")}
    leser = shapefile.Reader(shp=teile["shp"], shx=teile["shx"], dbf=teile["dbf"], encoding="utf-8")
    felder = [f[0] for f in leser.fields[1:]]
    flaechen = []
    for rec in leser.iterShapeRecords():
        attr = dict(zip(felder, rec.record))
        if str(attr["AGS"]) == ags and int(attr["GF"]) == 4:
            flaechen.append(shape(rec.shape.__geo_interface__))
    if not flaechen:
        raise ValueError(f"AGS {ags} nicht in VG250_KRS gefunden")
    grenze_utm = shapely.union_all(flaechen)
    puffer_utm = grenze_utm.buffer(PUFFER_M)
    return (shp_transform(UTM_ZU_WGS.transform, grenze_utm),
            shp_transform(UTM_ZU_WGS.transform, puffer_utm))


def baue_hexagone(grenze: shapely.Geometry, gebiet: shapely.Geometry) -> pd.DataFrame:
    """Alle H3-Zellen, deren Mittelpunkt im gepufferten Gebiet liegt."""
    zellen = sorted(h3.geo_to_cells(gebiet, H3_AUFLOESUNG))
    mitte = np.array([h3.cell_to_latlng(c) for c in zellen])
    df = pd.DataFrame({"h3": zellen, "lat": mitte[:, 0], "lon": mitte[:, 1]})
    # Bewertet werden später nur Zellen in der Stadt; der Puffer dient nur als Nachbarschaft.
    df["in_stadt"] = shapely.contains_xy(grenze, df["lon"].to_numpy(), df["lat"].to_numpy())
    return df


# ---------------------------------------------------------------------------
# 3. Zensus lesen und auf Hexagone bringen
# ---------------------------------------------------------------------------

def zahl(serie: pd.Series) -> pd.Series:
    """Zensuswerte in Zahlen umwandeln.

    Unterdrückte Werte stehen als Halbgeviertstrich (cp1252), die Miete nutzt das Komma
    als Dezimalzeichen. Alles, was danach keine Zahl ist, wird zu NaN.
    """
    return pd.to_numeric(serie.astype(str).str.strip().str.replace(",", ".", regex=False),
                         errors="coerce")


def lese_zensus(thema: str, gebiet: shapely.Geometry, zellen: set[str]) -> pd.DataFrame:
    """Liest eine 100-m-Gitterdatei in Stücken und behält nur Zeilen im Untersuchungsgebiet.

    Zuerst wird grob über ein Rechteck in EPSG:3035 geschnitten (billig), erst dann werden
    die verbleibenden Mittelpunkte nach WGS84 umgerechnet und einem Hexagon zugeordnet.
    """
    archiv = ZENSUS / ZENSUS_ARCHIVE[thema]
    mitglied = zip_mitglied(archiv, ZENSUS_DATEI[thema])
    west, sued, ost, nord = gebiet.bounds
    ecken_x, ecken_y = WGS_ZU_LAEA.transform([west, west, ost, ost], [sued, nord, sued, nord])
    rand = 1000  # die Projektion verzerrt das Rechteck leicht
    xmin, xmax = min(ecken_x) - rand, max(ecken_x) + rand
    ymin, ymax = min(ecken_y) - rand, max(ecken_y) + rand

    teile = []
    with zipfile.ZipFile(archiv) as z, z.open(mitglied) as f:
        leser = pd.read_csv(f, sep=";", encoding="latin-1", dtype=str, chunksize=CHUNK_ZEILEN,
                            usecols=["x_mp_100m", "y_mp_100m", *ZENSUS_SPALTEN[thema]])
        for stueck in leser:
            x = zahl(stueck["x_mp_100m"])
            y = zahl(stueck["y_mp_100m"])
            maske = x.between(xmin, xmax) & y.between(ymin, ymax)
            if maske.any():
                teile.append(stueck[maske].assign(x=x[maske], y=y[maske]))
    df = pd.concat(teile, ignore_index=True)

    lon, lat = LAEA_ZU_WGS.transform(df["x"].to_numpy(), df["y"].to_numpy())
    df["h3"] = [h3.latlng_to_cell(a, b, H3_AUFLOESUNG) for a, b in zip(lat, lon)]
    df = df[df["h3"].isin(zellen)].copy()
    for spalte in ZENSUS_SPALTEN[thema]:
        if spalte != "werterlaeuternde_Zeichen":
            df[spalte] = zahl(df[spalte])
    return df.drop(columns=["x_mp_100m", "y_mp_100m", "x", "y"])


def zensus_auf_hexagone(hexa: pd.DataFrame, gebiet: shapely.Geometry) -> pd.DataFrame:
    zellen = set(hexa["h3"])
    df = hexa.set_index("h3")

    # Einwohner: unbewohnte Zellen fehlen in der Datei und bekommen 0.
    bev = lese_zensus("bevoelkerung", gebiet, zellen)
    df["einwohner"] = bev.groupby("h3")["Einwohner"].sum(min_count=1)
    df["einwohner"] = df["einwohner"].fillna(0)

    # Miete: Mittel über die 100-m-Zellen, gewichtet mit der Zahl der Wohnungen.
    # KLAMMERN-Zeilen bleiben drin, bis die Datensatzbeschreibung geklärt ist (Spezifikation 4.1).
    miete = lese_zensus("miete", gebiet, zellen).dropna(subset=["durchschnMieteQM", "AnzahlWohnungen"])
    miete["gewicht"] = miete["durchschnMieteQM"] * miete["AnzahlWohnungen"]
    agg = miete.groupby("h3")[["gewicht", "AnzahlWohnungen"]].sum()
    df["miete_qm"] = agg["gewicht"] / agg["AnzahlWohnungen"]
    df["mietwohnungen"] = agg["AnzahlWohnungen"]
    df["mietwohnungen"] = df["mietwohnungen"].fillna(0)
    df["miete_geschaetzt"] = False
    fuelle_miete_aus_nachbarn(df)

    # Alter: Anteil 20-49 an allen veröffentlichten Klassen. Sind zu viele Klassen unterdrückt,
    # wäre der Anteil Zufall; dann gilt der Stadtwert.
    alter = lese_zensus("alter", gebiet, zellen)
    klassen = ZENSUS_SPALTEN["alter"]
    a = alter.groupby("h3")[klassen].sum(min_count=1)
    kern = a[["a20bis29", "a30bis39", "a40bis49"]].sum(axis=1)
    alle = a[klassen].sum(axis=1)
    stadtzellen = df.index[df["in_stadt"]]
    stadtwert = kern.reindex(stadtzellen).sum() / alle.reindex(stadtzellen).sum()
    deckung = alle.reindex(df.index) / df["einwohner"].replace(0, np.nan)
    df["anteil_20_49"] = (kern / alle.replace(0, np.nan)).reindex(df.index)
    df["alter_geschaetzt"] = ~(deckung >= 0.5)
    df.loc[df["alter_geschaetzt"], "anteil_20_49"] = stadtwert
    # Unbewohnte Zellen tragen nichts bei; die Markierung "geschätzt" wäre dort irreführend.
    df.loc[df["einwohner"] == 0, "alter_geschaetzt"] = False

    # Haushalte: gleiche Logik. Der Anteil mit 1 bis 3 Personen geht in die Anwohnernachfrage ein.
    hh = lese_zensus("haushalte", gebiet, zellen)
    hk = ZENSUS_SPALTEN["haushalte"][1:]
    h = hh.groupby("h3")[["Insgesamt_Haushalte", *hk]].sum(min_count=1)
    klein = h[["1_Person", "2_Personen", "3_Personen"]].sum(axis=1)
    alle_hh = h[hk].sum(axis=1)
    hh_stadt = klein.reindex(stadtzellen).sum() / alle_hh.reindex(stadtzellen).sum()
    df["haushalte"] = h["Insgesamt_Haushalte"].reindex(df.index).fillna(0)
    df["anteil_hh_1_3"] = (klein / alle_hh.replace(0, np.nan)).reindex(df.index)
    hh_deckung = alle_hh.reindex(df.index) / df["haushalte"].replace(0, np.nan)
    df.loc[~(hh_deckung >= 0.5), "anteil_hh_1_3"] = hh_stadt

    return df.reset_index()


def fuelle_miete_aus_nachbarn(df: pd.DataFrame) -> None:
    """Bewohnte Zellen ohne Mietwert bekommen das gewichtete Mittel der Nachbarn in zwei Ringen.

    Nur gemessene Werte dienen als Quelle, damit sich Schätzungen nicht fortpflanzen.
    """
    gemessen = df["miete_qm"].notna()
    quelle_miete = df.loc[gemessen, "miete_qm"].to_dict()
    quelle_wohn = df.loc[gemessen, "mietwohnungen"].to_dict()
    luecken = df.index[(df["einwohner"] > 0) & ~gemessen]
    for zelle in luecken:
        nachbarn = [n for n in h3.grid_disk(zelle, 2) if n in quelle_miete]
        if not nachbarn:
            continue
        gew = np.array([quelle_wohn[n] for n in nachbarn])
        werte = np.array([quelle_miete[n] for n in nachbarn])
        df.at[zelle, "miete_qm"] = float((gew * werte).sum() / gew.sum())
        df.at[zelle, "miete_geschaetzt"] = True


# ---------------------------------------------------------------------------
# 4. OpenStreetMap über Overpass
# ---------------------------------------------------------------------------

def overpass_filter(bedingung: dict[str, set[str] | None]) -> str:
    teile = []
    for tag, werte in bedingung.items():
        if werte is None:
            teile.append(f'["{tag}"]')
        elif len(werte) == 1:
            teile.append(f'["{tag}"="{next(iter(werte))}"]')
        else:
            teile.append(f'["{tag}"~"^({"|".join(sorted(werte))})$"]')
    return "".join(teile)


def overpass_abfrage(gebiet: shapely.Geometry, kategorien: set[str]) -> str:
    """Baut eine Overpass-Abfrage für die Regeln der genannten Kategorien.

    `nwr` holt Knoten, Wege und Relationen; `out center` liefert für Flächen den Mittelpunkt,
    denn jede Größe wird ohnehin am Mittelpunkt ihres Hexagons verortet.
    """
    west, sued, ost, nord = gebiet.bounds
    zeilen = sorted({
        f"  nwr{overpass_filter(b)};"
        for _, k, bedingungen in POI_REGELN if k in kategorien
        for b in bedingungen
    })
    # Kleine Limits: Server vergeben Plätze nach angefragtem Zeit- und Speicherbedarf.
    return (f"[out:json][timeout:180]"
            f"[bbox:{sued:.5f},{west:.5f},{nord:.5f},{ost:.5f}];\n(\n"
            + "\n".join(zeilen) + "\n);\nout center tags;")


def overpass_senden(abfrage: str, versuche: int = 8) -> list[dict]:
    """Schickt eine Abfrage und wechselt bei Fehlern den Server.

    Die öffentlichen Server antworten unter Last oft nach Sekunden mit 504; ein späterer
    Versuch klappt meist. Deshalb viele Versuche mit wachsender Pause.
    """
    # requests statt urllib: Das python.org-Python auf macOS findet sonst keine SSL-Zertifikate.
    for versuch in range(1, versuche + 1):
        url = OVERPASS_URLS[(versuch - 1) % len(OVERPASS_URLS)]
        try:
            antwort = requests.post(url, data={"data": abfrage},
                                    headers={"User-Agent": USER_AGENT}, timeout=300)
            antwort.raise_for_status()
            inhalt = antwort.json()
            # Bei Zeitüberschreitung liefert Overpass HTTP 200 mit "remark" und unvollständigen Daten.
            if "remark" in inhalt and "runtime error" in inhalt["remark"]:
                raise RuntimeError(inhalt["remark"])
            return inhalt["elements"]
        except Exception as fehler:  # noqa: BLE001 - jede Störung soll erneut versucht werden
            print(f"    Versuch {versuch}/{versuche} bei {url.split('/')[2]} fehlgeschlagen: "
                  f"{str(fehler)[:60]}")
            if versuch == versuche:
                raise
            time.sleep(min(10 * versuch, 60))
    return []


def kuerze(elemente: list[dict]) -> list[dict]:
    """Nur Koordinaten und die Tags behalten, die das Modell braucht: hält den Cache klein."""
    gekuerzt = []
    for e in elemente:
        lat = e.get("lat", e.get("center", {}).get("lat"))
        lon = e.get("lon", e.get("center", {}).get("lon"))
        if lat is None or lon is None:
            continue
        tags = {k: v for k, v in e.get("tags", {}).items() if k in TAGS_BEHALTEN}
        gekuerzt.append({"osm_id": f"{e['type']}/{e['id']}", "lat": lat, "lon": lon, "tags": tags})
    return gekuerzt


def lade_osm(stadt: str, gebiet: shapely.Geometry) -> list[dict]:
    """Holt alle POIs einer Stadt; das Ergebnis liegt danach in `cache/` und wird nie erneut geholt.

    Eine Gesamtabfrage läuft auf den öffentlichen Servern in den Timeout (getestet im Oktober 2026).
    Deshalb eine Abfrage je Gruppe; scheitert eine Gruppe, wird sie nach Kategorien geteilt.
    Jeder fertige Teil wird sofort gespeichert, damit ein Abbruch nichts Geholtes verwirft.
    Kommt eine Gruppe neu hinzu, wird nur sie nachgeholt und in den bestehenden Cache gemischt.
    """
    CACHE.mkdir(exist_ok=True)
    datei = CACHE / f"{stadt}_overpass.json"
    gruppen_datei = CACHE / f"{stadt}_overpass_gruppen.json"
    alle_gruppen = list(dict.fromkeys(GRUPPE_VON.values()))
    elemente, vorhanden = [], []
    if datei.exists():
        elemente = json.loads(datei.read_text(encoding="utf-8"))
        vorhanden = (json.loads(gruppen_datei.read_text(encoding="utf-8")) if gruppen_datei.exists()
                     else GRUPPEN_ALTER_CACHE)
    fehlend = [g for g in alle_gruppen if g not in vorhanden]
    if not fehlend:
        return elemente

    def teil(name: str, kategorien: set[str]) -> list[dict]:
        tdatei = CACHE / f"{stadt}_teil_{name}.json"
        if tdatei.exists():
            return json.loads(tdatei.read_text(encoding="utf-8"))
        daten = kuerze(overpass_senden(overpass_abfrage(gebiet, kategorien)))
        tdatei.write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")
        return daten

    nach_id = {e["osm_id"]: e for e in elemente}
    for gruppe in fehlend:
        kategorien = {k for k, g in GRUPPE_VON.items() if g == gruppe}
        print(f"  Overpass: {stadt}, Gruppe {gruppe} ...")
        try:
            teile = [teil(gruppe, kategorien)]
        except Exception:  # noqa: BLE001
            print(f"  Gruppe {gruppe} gescheitert, teile nach Kategorien.")
            teile = [teil(k, {k}) for k in sorted(kategorien)]
        for e in (e for t in teile for e in t):
            if e["osm_id"] in nach_id:
                # Schon aus einer anderen Gruppe bekannt: nur die neu benötigten Tags ergänzen.
                nach_id[e["osm_id"]]["tags"].update(e["tags"])
            else:
                nach_id[e["osm_id"]] = e
                elemente.append(e)

    datei.write_text(json.dumps(elemente, ensure_ascii=False), encoding="utf-8")
    gruppen_datei.write_text(json.dumps(alle_gruppen), encoding="utf-8")
    for tdatei in CACHE.glob(f"{stadt}_teil_*.json"):
        tdatei.unlink()
    return elemente


def kategorie_von(tags: dict[str, str]) -> str | None:
    for _, kategorie, bedingungen in POI_REGELN:
        for b in bedingungen:
            if all(tag in tags and (werte is None or tags[tag] in werte) for tag, werte in b.items()):
                # Bio-Supermärkte sind oft nur über die Marke erkennbar.
                if kategorie == "supermarkt" and tags.get("brand", "").strip().lower() in BIO_MARKEN:
                    return "bio_markt"
                return kategorie
    return None


def entferne_dubletten(pois: pd.DataFrame) -> pd.DataFrame:
    """POIs derselben Kategorie unter 20 m Abstand zählen einmal.

    Typisch: ein Laden als Punkt und als Gebäudefläche, oder Bushalte je Straßenseite.
    Gierig nach osm_id sortiert, damit das Ergebnis bei jedem Lauf gleich ist.
    """
    behalten = []
    radius = DUBLETTEN_RADIUS_M / ERDRADIUS_M
    for _, teil in pois.sort_values("osm_id").groupby("kategorie", sort=True):
        koord = np.radians(teil[["lat", "lon"]].to_numpy())
        nachbarn = BallTree(koord, metric="haversine").query_radius(koord, r=radius)
        weg = np.zeros(len(teil), dtype=bool)
        for i, nb in enumerate(nachbarn):
            if not weg[i]:
                weg[nb[nb > i]] = True
        behalten.append(teil[~weg])
    return pd.concat(behalten, ignore_index=True)


def baue_pois(stadt: str, gebiet: shapely.Geometry) -> pd.DataFrame:
    zeilen = []
    for e in lade_osm(stadt, gebiet):
        kategorie = kategorie_von(e["tags"])
        if kategorie is None:
            continue
        zeilen.append({
            "osm_id": e["osm_id"], "lat": e["lat"], "lon": e["lon"],
            "gruppe": GRUPPE_VON[kategorie], "kategorie": kategorie,
            **{t: e["tags"].get(t, "") for t in ("name", "brand", "cuisine", "organic")},
        })
    pois = pd.DataFrame(zeilen)
    # Das Rechteck der Abfrage ist größer als das Gebiet; Ecken außerhalb fallen weg.
    pois = pois[shapely.contains_xy(gebiet, pois["lon"].to_numpy(), pois["lat"].to_numpy())]
    vorher = len(pois)
    pois = entferne_dubletten(pois)
    print(f"  POIs: {vorher} gefunden, {vorher - len(pois)} Dubletten entfernt, {len(pois)} bleiben")
    return pois


def zaehle_pois(hexa: pd.DataFrame, pois: pd.DataFrame | None) -> pd.DataFrame:
    """Eine Spalte poi_<kategorie> je Kategorie; fehlende Kategorien werden 0."""
    zaehlung = pd.DataFrame(0, index=hexa["h3"], columns=[f"poi_{k}" for k in KATEGORIEN])
    if pois is not None and len(pois):
        zellen = [h3.latlng_to_cell(a, b, H3_AUFLOESUNG) for a, b in zip(pois["lat"], pois["lon"])]
        tabelle = pd.crosstab(pd.Index(zellen, name="h3"), "poi_" + pois["kategorie"].to_numpy())
        tabelle = tabelle.reindex(index=zaehlung.index, fill_value=0)
        for spalte in tabelle.columns:
            zaehlung[spalte] = tabelle[spalte].to_numpy()
    return hexa.merge(zaehlung.reset_index(), on="h3")


# ---------------------------------------------------------------------------
# 5. Prüfungen und Hauptprogramm
# ---------------------------------------------------------------------------

def pruefe(stadt: str, grid: pd.DataFrame, pois: pd.DataFrame | None) -> None:
    """Vergleich mit den Sollwerten aus Spezifikation Abschnitt 9 (Schritte 1 und 2)."""
    info = STAEDTE[stadt]
    in_stadt = grid[grid["in_stadt"]]
    ew = in_stadt["einwohner"].sum()
    abw_ew = ew / info["soll_einwohner"] - 1
    print(f"  Hexagone gesamt {len(grid):,}, in der Stadt {len(in_stadt):,} (Soll {info['soll_hex']:,})")
    print(f"  Einwohner in der Stadt {ew:,.0f} (Soll {info['soll_einwohner']:,}, Abweichung {abw_ew:+.2%})")
    if abs(abw_ew) >= 0.01:
        print("  WARNUNG: Einwohner weichen um 1 Prozent oder mehr vom Sollwert ab.")
    bewohnt = in_stadt[in_stadt["einwohner"] > 0]
    gemessen = bewohnt["miete_qm"].notna() & ~bewohnt["miete_geschaetzt"]
    print(f"  Median-Miete (gemessen) {bewohnt.loc[gemessen, 'miete_qm'].median():.2f} Euro/m², "
          f"geschätzt {bewohnt['miete_geschaetzt'].mean():.0%} der bewohnten Zellen")
    if pois is not None:
        leer = [k for k in KATEGORIEN if (pois["kategorie"] == k).sum() == 0]
        if leer:
            print(f"  WARNUNG: Kategorien ohne Treffer: {', '.join(leer)}")


def baue_stadt(stadt: str, mit_osm: bool) -> pd.DataFrame:
    info = STAEDTE[stadt]
    print(f"\n=== {info['name']} ({stadt}) ===")
    grenze, gebiet = lade_stadtgrenze(info["ags"])
    hexa = baue_hexagone(grenze, gebiet)
    hexa.insert(3, "stadt", stadt)
    grid = zensus_auf_hexagone(hexa, gebiet)

    pois = None
    if mit_osm:
        pois = baue_pois(stadt, gebiet)
        pois.to_csv(DATA / f"{stadt}_pois.csv", index=False)
    grid = zaehle_pois(grid, pois)

    spalten = ["h3", "lat", "lon", "stadt", "in_stadt", "einwohner", "miete_qm", "mietwohnungen",
               "miete_geschaetzt", "anteil_20_49", "alter_geschaetzt", "haushalte", "anteil_hh_1_3",
               *[f"poi_{k}" for k in KATEGORIEN]]
    grid = grid[spalten].sort_values("h3").reset_index(drop=True)
    grid.to_csv(DATA / f"{stadt}_grid.csv", index=False, float_format="%.6g")
    pruefe(stadt, grid, pois)
    print(f"  geschrieben: data/{stadt}_grid.csv ({len(grid):,} Zeilen)"
          + (f", data/{stadt}_pois.csv ({len(pois):,} Zeilen)" if pois is not None else ""))
    return grid


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--staedte", nargs="+", choices=list(STAEDTE), default=list(STAEDTE))
    parser.add_argument("--ohne-osm", action="store_true", help="Overpass überspringen")
    args = parser.parse_args()

    DATA.mkdir(exist_ok=True)
    print("Zensus-Archive prüfen ...")
    lade_zensus_archive()
    for n, stadt in enumerate(args.staedte):
        # Overpass ist ein geteilter, kostenloser Dienst: Pause nur, wenn wirklich abgefragt wird.
        if n and not args.ohne_osm and not (CACHE / f"{stadt}_overpass.json").exists():
            time.sleep(PAUSE_ZWISCHEN_STAEDTEN_S)
        baue_stadt(stadt, mit_osm=not args.ohne_osm)
    print("\nFertig. Weiter mit: python analyse.py")


if __name__ == "__main__":
    main()
