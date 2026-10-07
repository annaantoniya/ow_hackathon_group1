"""
Analyse: Die Mathematik hinter den White Spots
==============================================

Dieses Skript setzt `Specs/maths.md` Abschnitt für Abschnitt um. Jede Funktion trägt im
Kommentar die Nummer des Abschnitts, damit sich Formel und Code nebeneinanderlegen lassen.

Aufruf
------
    pip install pandas numpy h3 scikit-learn statsmodels
    python analyse.py --demo                 # synthetische Städte, läuft sofort ohne Daten
    python analyse.py                        # echte Daten aus datengrundlage.py
    python analyse.py --staedte frankfurt --laeufe 200

Eingabe:  data/<stadt>_grid.csv   (von datengrundlage.py; im Demo-Modus erzeugt)
Ausgaben: data/<stadt>_scored.csv           Score, Treiber, Lücke, Stabilität je Hexagon
          data/<stadt>_pca.json             Ladungen der Affinitäts-PCA
          data/<stadt>_plausibilitaet.json  Plausibilitätstest
          data/<stadt>_portfolio.csv        gierig gewählte Standortkombination
          data/luecke_modell.json           Regression der Angebotslücke
Im Demo-Modus landet alles in data/demo/.

Gesamtlogik (maths.md, Abschnitt 19)
------------------------------------
    Raster -> Distanzgewichte -> Nachfrage N, Tagesindex t, Affinität q
           -> Potenzial P -> Wettbewerbsdruck K -> Huff-Score U, Wettbewerbsfreiheit W = U/P
    parallel: Merkmale -> Poisson/NB-Regression -> erwartete Läden ŷ -> Lücke g
    danach:   Konsens (PR(U) >= 90 und PR(g) >= 90), Robustheit, Portfolio
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.neighbors import BallTree

ROOT = Path(__file__).resolve().parent
ERDRADIUS_M = 6_371_000

# ---------------------------------------------------------------------------
# Parameter (Umsetzungsspezifikation, Abschnitt 7)
# ---------------------------------------------------------------------------
# Jeder Wert ist eine Setzung ohne Messung. Die Spannen gelten nur für den Robustheitstest.
# Ein Eintrag ("faktor", a, b) heißt: der Startwert wird mit einem Faktor aus [a, b] multipliziert.

PARAMETER = {
    # Raster und Distanz
    "d_max_m": 1500, "umwegfaktor": 1.3, "d_selbst_m": 100,
    "h_anwohner_m": 400, "h_tag_m": 250, "h_affinitaet_m": 400,
    # Nachfrage
    "gamma": 1.0, "k_min": 0.5, "k_max": 2.0, "theta": 0.3,
    "w_buero": 1.0, "w_hochschule": 5.0, "w_bahnhof": 5.0, "w_tram_ubahn": 2.0, "w_bus": 0.5,
    "q_min": 0.5, "q_max": 1.5,
    # Wettbewerb. a_0 = 1,33 heißt: ohne Wettbewerb gewinnt der Laden direkt vor der Tür
    # (Distanz d_selbst) rund 60 Prozent der Nachfrage: 2*2^(-100/400) / (2*2^(-100/400) + 1,33).
    "a_neu": 2.0, "a_0": 1.33,
    "alpha_markthalle": 3.0, "alpha_bio_markt": 2.0,
    "alpha_deli": 1.0, "alpha_feinkost_kaese": 1.0, "alpha_wein": 1.0, "alpha_pasta": 1.0,
    "alpha_reformhaus": 1.0, "alpha_supermarkt": 0.5,
    "alpha_baecker": 0.2, "alpha_metzger": 0.2, "alpha_obst_gemuese": 0.2, "alpha_fisch": 0.2,
    # Auswertung
    "n_min_geschaeftslage": 5, "profil_schwelle_hoch": 1.5, "profil_schwelle_tief": 0.5,
    "plausibilitaet_anteil": 0.2, "top_n": 10, "n_laeufe": 1000,
    "k_portfolio": 5, "n_kandidaten_portfolio": 300, "zufall_startwert": 42,
    "konsens_schwelle": 90, "cv_teile": 5, "cv_h3_eltern": 6,
    "min_devianz_oos": 0.05, "max_dispersion": 1.5,
}

SPANNEN = {
    "h_anwohner_m": ("wert", 300, 500), "h_tag_m": ("wert", 150, 350),
    "gamma": ("wert", 0.5, 1.5), "theta": ("wert", 0.1, 0.5),
    "a_0": ("faktor", 0.5, 1.5),
    **{k: ("faktor", 0.5, 1.5) for k in PARAMETER if k.startswith(("w_", "alpha_"))},
}

WETTBEWERB_DIREKT = ["deli", "feinkost_kaese", "wein", "bio_markt", "reformhaus", "markthalle", "pasta"]
WETTBEWERB_BREIT = ["supermarkt", "obst_gemuese", "metzger", "baecker", "fisch"]
AFFINITAET = ["cafe", "restaurant", "bar", "buchhandlung", "interior", "boutique", "blumen",
              "fitness_yoga", "kultur", "galerie_museum", "coworking", "fahrradladen"]
FREQUENZ = ["bahnhof", "tram_ubahn", "bus", "buero", "hochschule"]
ALLE_KATEGORIEN = WETTBEWERB_DIREKT + WETTBEWERB_BREIT + AFFINITAET + FREQUENZ
MERKMALE = ["einwohner", "kaufkraft", "alter", "affinitaet", "tag"]


# ---------------------------------------------------------------------------
# Abschnitte 2 und 3: Nachbarschaft und Distanzgewicht
# ---------------------------------------------------------------------------

class Paare:
    """Alle Zellpaare (i, j) mit Wegstrecke d_ij <= d_max, symmetrisch, inklusive (i, i).

    Jede räumliche Größe des Modells ist eine gewichtete Nachbarschaftssumme
        S_i = sum_j wert_j * gewicht_ij,
    die sich über diese Liste mit einem einzigen np.bincount berechnen lässt.
    """

    def __init__(self, lat: np.ndarray, lon: np.ndarray, p: dict):
        koord = np.radians(np.column_stack([lat, lon]))
        radius = p["d_max_m"] / p["umwegfaktor"] / ERDRADIUS_M
        idx, dist = BallTree(koord, metric="haversine").query_radius(koord, r=radius, return_distance=True)
        self.n = len(lat)
        self.i = np.repeat(np.arange(self.n), [len(x) for x in idx]).astype(np.int32)
        self.j = np.concatenate(idx).astype(np.int32)
        # Luftlinie mal Umwegfaktor approximiert die Wegstrecke.
        self.d = np.concatenate(dist) * ERDRADIUS_M * p["umwegfaktor"]
        # Eine Zelle hat ~0,1 km²; Kunden aus der eigenen Zelle laufen im Mittel ~100 m, nicht 0 m.
        self.d[self.i == self.j] = p["d_selbst_m"]
        self.d_max = p["d_max_m"]

    def f(self, h: float) -> np.ndarray:
        """f_h(d) = 2^(-d/h) für d <= d_max, sonst 0. f_h(h) = 1/2: h ist die Halbwertsdistanz."""
        return np.where(self.d <= self.d_max, np.exp2(-self.d / h), 0.0)

    def summe(self, wert: np.ndarray, gewicht: np.ndarray) -> np.ndarray:
        """S_i = sum_j wert_j * gewicht_ij."""
        return np.bincount(self.i, weights=wert[self.j] * gewicht, minlength=self.n)


def prozentrang(werte: np.ndarray, referenz: np.ndarray) -> np.ndarray:
    """Anteil der Referenzwerte <= Wert, in [0, 1]. NaN bleibt NaN.

    Die Referenz sind die Stadtzellen; Pufferzellen bekommen den Rang, den sie dort hätten.
    """
    ref = np.sort(referenz[~np.isnan(referenz)])
    pr = np.searchsorted(ref, werte, side="right") / max(len(ref), 1)
    return np.where(np.isnan(werte), np.nan, pr)


def standardisiere(x: np.ndarray, maske: np.ndarray) -> np.ndarray:
    """z = (x - mu) / sigma mit mu, sigma aus den Stadtzellen. Konstante Spalten werden 0."""
    mu, sd = x[maske].mean(), x[maske].std()
    return (x - mu) / sd if sd > 0 else np.zeros_like(x)


# ---------------------------------------------------------------------------
# Abschnitte 4 und 5: Einwohnernachfrage und Tagesbevölkerung
# ---------------------------------------------------------------------------

def nachfrage_anwohner(g: pd.DataFrame, p: dict, median_miete: float) -> np.ndarray:
    """N_i = E_i * a_i * k_i  mit  k_i = clip(m_i / median(m), k_min, k_max)^gamma.

    Die Miete ist der Ersatz für Kaufkraft. Der Median kommt aus der eigenen Stadt, weil
    Mieten zwischen Städten nicht vergleichbar sind. Ohne Mietwert ist k = 1.
    """
    verh = (g["miete_qm"].to_numpy() / median_miete)
    k = np.clip(verh, p["k_min"], p["k_max"]) ** p["gamma"]
    k = np.where(np.isnan(k), 1.0, k)
    return g["einwohner"].to_numpy() * g["anteil_20_49"].fillna(0).to_numpy() * k


def tagesindex(g: pd.DataFrame, p: dict) -> np.ndarray:
    """t_i = sum_c w_c * POI_c,i. Relativer Frequenzindikator, keine Personenzahl."""
    return sum(p[f"w_{c}"] * g[f"poi_{c}"].to_numpy() for c in FREQUENZ)


# ---------------------------------------------------------------------------
# Abschnitt 6: Standortaffinität per PCA
# ---------------------------------------------------------------------------

def affinitaet(g: pd.DataFrame, paare: Paare, p: dict) -> tuple[np.ndarray, np.ndarray, dict]:
    """s_c,i = sum_j POI_c,j f(d_ij);  x = log(1+s);  z = standardisiert;  A_i = v1' z_i;
    q_i = q_min + (q_max - q_min) * PR(A_i).

    v1 ist der Eigenvektor der Korrelationsmatrix der z mit dem größten Eigenwert.
    """
    maske = g["in_stadt"].to_numpy()
    fa = paare.f(p["h_affinitaet_m"])
    z = np.column_stack([
        standardisiere(np.log1p(paare.summe(g[f"poi_{c}"].to_numpy(float), fa)), maske)
        for c in AFFINITAET
    ])
    # PCA über die Eigenzerlegung der Kovarianz der Stadtzellen.
    eigwerte, eigvek = np.linalg.eigh(np.cov(z[maske], rowvar=False))
    v1 = eigvek[:, -1]
    index = z @ v1
    # Vorzeichen so drehen, dass "mehr Umfeld" auch "mehr Affinität" heißt.
    if np.corrcoef(index[maske], z[maske].mean(axis=1))[0, 1] < 0:
        v1, index = -v1, -index

    # Rückfall: Ist die Komponente fast nur die POI-Dichte, misst sie Zentralität statt Passung.
    # Dann zählt der Anteil der Affinitäts-POIs an allen POIs.
    alle = np.column_stack([g[f"poi_{c}"].to_numpy(float) for c in ALLE_KATEGORIEN]).sum(axis=1)
    aff = np.column_stack([g[f"poi_{c}"].to_numpy(float) for c in AFFINITAET]).sum(axis=1)
    s_alle, s_aff = paare.summe(alle, fa), paare.summe(aff, fa)
    korr = float(np.corrcoef(index[maske], np.log1p(s_alle[maske]))[0, 1])
    variante = "pca"
    if korr > 0.9:
        variante = "anteil_affinitaet"
        index = np.divide(s_aff, s_alle, out=np.zeros_like(s_aff), where=s_alle > 0)

    q = p["q_min"] + (p["q_max"] - p["q_min"]) * prozentrang(index, index[maske])
    info = {
        "variante": variante,
        "korrelation_mit_gesamtdichte": round(korr, 3),
        "erklaerte_varianz_pc1": round(float(eigwerte[-1] / eigwerte.sum()), 3),
        "ladungen": {c: round(float(w), 3) for c, w in zip(AFFINITAET, v1)},
    }
    return index, q, info


# ---------------------------------------------------------------------------
# Abschnitte 7 bis 10: Quellnachfrage, Potenzial, Wettbewerb, Huff-Score
# ---------------------------------------------------------------------------

def wettbewerbsstaerke(g: pd.DataFrame, p: dict) -> np.ndarray:
    """A_j = sum_c alpha_c * POI_c,j über direkte und breite Wettbewerber. Gastronomie zählt nicht."""
    return sum(p[f"alpha_{c}"] * g[f"poi_{c}"].to_numpy() for c in WETTBEWERB_DIREKT + WETTBEWERB_BREIT)


def huff(paare: Paare, O: np.ndarray, K: np.ndarray, fh: np.ndarray, p: dict) -> np.ndarray:
    """U_c = sum_i O_i * a_neu f(d_ic) / (a_neu f(d_ic) + K_i + A_0).

    Über die Paarliste: Kandidat c = paare.i, Quelle i = paare.j (die Liste ist symmetrisch).
    Mit K = 0 ergibt sich das Potenzial P (Abschnitt 8), deshalb gilt immer U <= P.
    """
    anziehung = p["a_neu"] * fh
    anteil = anziehung / (anziehung + K[paare.j] + p["a_0"])
    return np.bincount(paare.i, weights=O[paare.j] * anteil, minlength=paare.n)


def score(g: pd.DataFrame, paare: Paare, q: np.ndarray, p: dict, median_miete: float) -> dict:
    """Rechnet die Abschnitte 4, 5 und 7 bis 10 für einen Parametersatz.

    Getrennt für Anwohner (A, Halbwert h_anwohner) und Tagesbevölkerung (T, Halbwert h_tag),
    weil beide Gruppen unterschiedlich weit laufen.
    """
    N = nachfrage_anwohner(g, p, median_miete)
    t = tagesindex(g, p)
    # Abschnitt 7: beide Teile summieren sich mit q = 1 zu 1; theta teilt die Nachfrage auf.
    OA = q * (1 - p["theta"]) * N / N.sum()
    OT = q * p["theta"] * t / t.sum() if t.sum() > 0 else np.zeros_like(t, dtype=float)

    fA, fT = paare.f(p["h_anwohner_m"]), paare.f(p["h_tag_m"])
    # Abschnitt 9: Wettbewerbsdruck an der Quelle, K_i = sum_j A_j f(d_ij).
    A = wettbewerbsstaerke(g, p)
    KA, KT = paare.summe(A, fA), paare.summe(A, fT)
    null = np.zeros(paare.n)
    r = {"N": N, "t": t, "OA": OA, "OT": OT, "KA": KA, "KT": KT,
         "PA": huff(paare, OA, null, fA, p), "PT": huff(paare, OT, null, fT, p),
         "UA": huff(paare, OA, KA, fA, p), "UT": huff(paare, OT, KT, fT, p)}
    r["P"], r["U"] = r["PA"] + r["PT"], r["UA"] + r["UT"]
    # W = U/P: Anteil des Potenzials, den der Wettbewerb übrig lässt. Ohne Potenzial undefiniert.
    r["W"] = np.divide(r["U"], r["P"], out=np.full(paare.n, np.nan), where=r["P"] > 0)
    return r


def geschaeftslage(g: pd.DataFrame, p: dict) -> np.ndarray:
    """Zelle plus sechs direkte Nachbarn haben zusammen >= n_min POIs aus Wettbewerb und Affinität.

    Filtert Parks, Gleisfelder und reine Wohnstraßen heraus, wo kein Laden Laufkundschaft fände.
    """
    pois = g[[f"poi_{c}" for c in WETTBEWERB_DIREKT + WETTBEWERB_BREIT + AFFINITAET]].sum(axis=1)
    zaehlung = dict(zip(g["h3"], pois))
    umfeld = [sum(zaehlung.get(n, 0) for n in h3.grid_disk(c, 1)) for c in g["h3"]]
    return np.array(umfeld) >= p["n_min_geschaeftslage"]


# ---------------------------------------------------------------------------
# Abschnitt 11: Rangbildung und Profil
# ---------------------------------------------------------------------------

def raenge(U: np.ndarray, maske: np.ndarray) -> np.ndarray:
    """Rang 1 = höchstes U, nur innerhalb der Maske, sonst NaN. Gleichstände nach Index."""
    rang = np.full(len(U), np.nan)
    pos = np.flatnonzero(maske)
    reihenfolge = pos[np.argsort(-U[pos], kind="stable")]
    rang[reihenfolge] = np.arange(1, len(pos) + 1)
    return rang


def bewerte_stadt(g: pd.DataFrame, p: dict) -> tuple[pd.DataFrame, dict]:
    g = g.copy()
    in_stadt = g["in_stadt"].to_numpy()
    paare = Paare(g["lat"].to_numpy(), g["lon"].to_numpy(), p)
    # Median über gemessene Mieten der Stadt; geschätzte Werte würden ihn glätten.
    gemessen = in_stadt & g["miete_qm"].notna().to_numpy() & ~g["miete_geschaetzt"].astype(bool).to_numpy()
    median_miete = float(np.median(g.loc[gemessen, "miete_qm"]))

    aff_index, q, pca_info = affinitaet(g, paare, p)
    r = score(g, paare, q, p, median_miete)
    lage = geschaeftslage(g, p)

    g["n_anwohner"], g["t_index"] = r["N"], r["t"]
    g["aff_index"], g["q"] = aff_index, q
    g["p_anw"], g["p_tag"], g["p"] = r["PA"], r["PT"], r["P"]
    g["u_anw"], g["u_tag"], g["u"], g["w"] = r["UA"], r["UT"], r["U"], r["W"]
    g["geschaeftslage"] = lage
    g["rang"] = raenge(r["U"], in_stadt & lage)
    for spalte, wert in [("pr_score", r["U"]), ("pr_potenzial", r["P"]),
                         ("pr_wettbewerbsfreiheit", r["W"]), ("pr_affinitaet", q)]:
        g[spalte] = 100 * prozentrang(wert, wert[in_stadt])
    g["anteil_tag"] = np.divide(r["PT"], r["P"], out=np.full(len(g), np.nan), where=r["P"] > 0)
    hoch, tief = p["profil_schwelle_hoch"] * p["theta"], p["profil_schwelle_tief"] * p["theta"]
    g["profil"] = np.select([g["anteil_tag"] > hoch, g["anteil_tag"] < tief],
                            ["Mittagsstandort", "Feierabendstandort"], "Ganztagsstandort")

    ctx = {"paare": paare, "q": q, "median_miete": median_miete, "r": r, "lage": lage,
           "pca": pca_info, "aff_index": aff_index}
    return g, ctx


def plausibilitaet(g: pd.DataFrame, p: dict) -> dict:
    """Liegen heutige Feinkostläden überproportional in den 20 % Zellen mit höchstem P?

    Nicht zirkulär: Wettbewerber gehen weder in N noch in t noch in q ein.
    Ein Anteil nahe 20 % hieße, das Potenzial sagt nichts voraus.
    """
    s = g[g["in_stadt"]]
    grenze = s["p"].quantile(1 - p["plausibilitaet_anteil"])
    direkt = s[[f"poi_{c}" for c in WETTBEWERB_DIREKT]].sum(axis=1)
    oben = s["p"] >= grenze
    return {"anteil_pois_in_top_zellen": round(float(direkt[oben].sum() / max(direkt.sum(), 1)), 3),
            "erwartet_ohne_vorhersagekraft": p["plausibilitaet_anteil"],
            "pois_direkt": int(direkt.sum()), "zellen_oben": int(oben.sum())}


# ---------------------------------------------------------------------------
# Abschnitte 12 bis 16: Angebotslücke per Poisson- bzw. Negativ-Binomial-Regression
# ---------------------------------------------------------------------------

def merkmale(g: pd.DataFrame, ctx: dict, p: dict) -> pd.DataFrame:
    """Die fünf erklärenden Merkmale, je Stadt standardisiert (Abschnitt 12).

    Alle sind Umfeldgrößen, weil Läden auf das Umfeld reagieren, nicht auf die eigene Zelle.
    """
    paare, maske = ctx["paare"], g["in_stadt"].to_numpy()
    fA, fT = paare.f(p["h_anwohner_m"]), paare.f(p["h_tag_m"])
    E = g["einwohner"].to_numpy(float)
    m = g["miete_qm"].to_numpy()
    hat_m = ~np.isnan(m)
    ew_umfeld = paare.summe(E, fA)
    ew_m = paare.summe(np.where(hat_m, E, 0), fA)
    miete_umfeld = np.divide(paare.summe(np.where(hat_m, E * m, 0), fA), ew_m,
                             out=np.full(len(g), np.nan), where=ew_m > 0)
    alter_umfeld = np.divide(paare.summe(E * g["anteil_20_49"].fillna(0).to_numpy(), fA), ew_umfeld,
                             out=np.full(len(g), np.nan), where=ew_umfeld > 0)
    stadt_alter = np.nanmedian(alter_umfeld[maske])
    roh = {
        "einwohner": np.log1p(ew_umfeld),
        "kaufkraft": np.nan_to_num(np.log(miete_umfeld / ctx["median_miete"]), nan=0.0),
        "alter": np.where(np.isnan(alter_umfeld), stadt_alter, alter_umfeld),
        "affinitaet": ctx["aff_index"],
        "tag": np.log1p(paare.summe(ctx["r"]["t"], fT)),
    }
    return pd.DataFrame({f"x_{k}": standardisiere(v, maske) for k, v in roh.items()}, index=g.index)


def design(df: pd.DataFrame, staedte: list[str], mit_x: bool = True) -> np.ndarray:
    """Konstante + feste Stadteffekte (erste Stadt ist Referenz) + fünf Merkmale."""
    spalten = [np.ones(len(df))]
    spalten += [(df["stadt"] == s).to_numpy(float) for s in staedte[1:]]
    if mit_x:
        spalten += [df[f"x_{k}"].to_numpy() for k in MERKMALE]
    return np.column_stack(spalten)


def nb_alpha(y: np.ndarray, mu: np.ndarray) -> float:
    """Dispersion alpha aus der Hilfsregression nach Cameron und Trivedi:
    ((y - mu)^2 - y) / mu = alpha * mu + e, ohne Konstante. Var(y) = mu + alpha * mu^2."""
    z = ((y - mu) ** 2 - y) / mu
    return max(float((mu @ z) / (mu @ mu)), 1e-6)


def angebotsluecke(alle: dict[str, pd.DataFrame], ctxs: dict, p: dict) -> dict:
    """Abschnitte 13 bis 16.

    E[y_c] = exp(beta_0 + delta_Stadt + sum_k beta_k x_k,c),  geschätzt auf allen Stadtzellen.
    Lücke:  g_c = sum_j (ŷ_j - y_j) f_hA(d_cj)  > 0 heißt: weniger Läden als erwartet.
    """
    staedte = list(alle)
    for s in staedte:
        alle[s] = pd.concat([alle[s], merkmale(alle[s], ctxs[s], p)], axis=1)
        alle[s]["y_direkt"] = alle[s][[f"poi_{c}" for c in WETTBEWERB_DIREKT]].sum(axis=1)
    df = pd.concat(alle.values(), ignore_index=True)
    train = df[df["in_stadt"]].reset_index(drop=True)
    y = train["y_direkt"].to_numpy(float)

    # Abschnitt 13: erst Poisson. Abschnitt 16: bei Überdispersion Negativ-Binomial.
    poisson = sm.GLM(y, design(train, staedte), family=sm.families.Poisson()).fit()
    dispersion = float(poisson.pearson_chi2 / poisson.df_resid)
    if dispersion > p["max_dispersion"]:
        alpha = nb_alpha(y, poisson.mu)
        familie, variante = sm.families.NegativeBinomial(alpha=alpha), "negativ_binomial"
        modell = sm.GLM(y, design(train, staedte), family=familie).fit()
    else:
        alpha, familie, variante, modell = None, sm.families.Poisson(), "poisson", poisson
    beta = modell.params
    namen = ["konstante", *[f"stadt_{s}" for s in staedte[1:]], *MERKMALE]

    # Abschnitt 16: räumliche Kreuzvalidierung. Ganze H3-Elternzellen (Auflösung 6, ~36 km²)
    # bleiben zusammen, sonst läge die Nachbarzelle einer Testzelle im Training.
    rng = np.random.default_rng(p["zufall_startwert"])
    eltern = np.array([h3.cell_to_parent(c, p["cv_h3_eltern"]) for c in train["h3"]])
    einzig = np.unique(eltern)
    teil_von = dict(zip(rng.permutation(einzig), np.arange(len(einzig)) % p["cv_teile"]))
    teil = np.array([teil_von[e] for e in eltern])
    D = D0 = 0.0
    for k in range(p["cv_teile"]):
        tr, te = teil != k, teil == k
        m1 = sm.GLM(y[tr], design(train[tr], staedte), family=familie).fit()
        m0 = sm.GLM(y[tr], design(train[tr], staedte, mit_x=False), family=familie).fit()
        D += familie.deviance(y[te], m1.predict(design(train[te], staedte)))
        D0 += familie.deviance(y[te], m0.predict(design(train[te], staedte, mit_x=False)))
    # Erklärte Devianz gegenüber einem Modell nur mit Stadteffekten.
    devianz_oos = 1 - D / D0
    if devianz_oos < p["min_devianz_oos"]:
        print(f"WARNUNG: Erklärte Devianz außerhalb der Stichprobe nur {devianz_oos:.3f}. "
              "Die Merkmale erklären die Ladenstandorte kaum; die Lücke ist mit Vorsicht zu lesen.")

    # Vorhersage für alle Zellen, auch im Puffer: deren Residuen fließen in die Glättung ein.
    for s in staedte:
        g = alle[s]
        g["y_erwartet"] = modell.predict(design(g, staedte))
        for k, name in enumerate(MERKMALE):
            # Beiträge addieren sich auf der log-Skala exakt (plus Konstante und Stadteffekt).
            g[f"beitrag_{name}"] = beta[len(staedte) + k] * g[f"x_{name}"]
        paare = ctxs[s]["paare"]
        resid = (g["y_erwartet"] - g["y_direkt"]).to_numpy()
        g["luecke"] = paare.summe(resid, paare.f(p["h_anwohner_m"]))
        maske = g["in_stadt"].to_numpy()
        g["pr_luecke"] = 100 * prozentrang(g["luecke"].to_numpy(), g.loc[maske, "luecke"].to_numpy())
        # Abschnitt 15: Konsens, wenn beide Sichten den Standort vorn sehen.
        g["konsens"] = (g["pr_score"] >= p["konsens_schwelle"]) & (g["pr_luecke"] >= p["konsens_schwelle"])
        summe_ist = g.loc[maske, "y_direkt"].sum()
        summe_erw = g.loc[maske, "y_erwartet"].sum()
        print(f"  {s}: Läden vorhanden {summe_ist:.1f}, erwartet {summe_erw:.1f}"
              + ("" if variante == "poisson" else " (NB: Summen stimmen nur näherungsweise)"))

    return {
        "variante": variante, "nb_alpha": alpha, "dispersion_poisson": round(dispersion, 3),
        "koeffizienten": {n: round(float(b), 4) for n, b in zip(namen, beta)},
        "standardfehler": {n: round(float(se), 4) for n, se in zip(namen, modell.bse)},
        "erklaerte_devianz_in_stichprobe": round(float(1 - modell.deviance / modell.null_deviance), 4),
        "erklaerte_devianz_ausserhalb": round(float(devianz_oos), 4),
        "hinweis": "Standardfehler sind zu klein, weil Nachbarzellen nicht unabhängig sind.",
        "negative_vorzeichen": [n for n, b in zip(namen, beta) if n in MERKMALE and b < 0],
    }


# ---------------------------------------------------------------------------
# Abschnitt 17: Robustheit
# ---------------------------------------------------------------------------

def ziehe_parameter(p: dict, rng: np.random.Generator) -> dict:
    neu = dict(p)
    for k, (art, a, b) in SPANNEN.items():
        neu[k] = rng.uniform(a, b) if art == "wert" else p[k] * rng.uniform(a, b)
    return neu


def robustheit(g: pd.DataFrame, ctx: dict, p: dict, laeufe: int) -> pd.DataFrame:
    """R Läufe mit zufällig gezogenen Parametern; je Lauf ein neuer Rang R_c^(r).

    Paarliste und q bleiben fest. Der Umwegfaktor wird nicht gezogen: Er skaliert alle
    Distanzen gleich und wirkt deshalb wie die Halbwertsdistanzen, die schon variieren.
    """
    rng = np.random.default_rng(p["zufall_startwert"])
    maske = g["in_stadt"].to_numpy() & ctx["lage"]
    pos = np.flatnonzero(maske)
    alle_raenge = np.empty((laeufe, len(pos)), dtype=np.int32)
    for r in range(laeufe):
        U = score(g, ctx["paare"], ctx["q"], ziehe_parameter(p, rng), ctx["median_miete"])["U"]
        alle_raenge[r] = raenge(U, maske)[pos]
    aus = pd.DataFrame(index=g.index, columns=["top10_anteil", "rang_median", "rang_p10", "rang_p90"],
                       dtype=float)
    aus.iloc[pos, 0] = (alle_raenge <= p["top_n"]).mean(axis=0)
    aus.iloc[pos, 1] = np.median(alle_raenge, axis=0)
    aus.iloc[pos, 2] = np.percentile(alle_raenge, 10, axis=0)
    aus.iloc[pos, 3] = np.percentile(alle_raenge, 90, axis=0)
    return aus


# ---------------------------------------------------------------------------
# Abschnitt 18: Portfolio mehrerer Standorte
# ---------------------------------------------------------------------------

def portfolio(g: pd.DataFrame, ctx: dict, p: dict) -> tuple[pd.DataFrame, float]:
    """Gierige Maximierung von
        F(S) = sum_i O^A_i X^A_i(S) / (X^A_i(S) + K^A_i + A_0) + (gleich für T),
        X_i(S) = sum_{c in S} a_neu f(d_ic).
    F ist monoton und submodular; gierig erreicht mindestens 1 - 1/e ≈ 63 % des Optimums.
    """
    r, paare = ctx["r"], ctx["paare"]
    fA, fT = paare.f(p["h_anwohner_m"]), paare.f(p["h_tag_m"])
    ordnung = np.argsort(paare.i, kind="stable")
    start = np.searchsorted(paare.i[ordnung], np.arange(paare.n + 1))

    def nachbarn(c):
        sel = ordnung[start[c]:start[c + 1]]
        return paare.j[sel], fA[sel], fT[sel]

    def F(XA, XT):
        return float((r["OA"] * XA / (XA + r["KA"] + p["a_0"])).sum()
                     + (r["OT"] * XT / (XT + r["KT"] + p["a_0"])).sum())

    def zugewinn(c, XA, XT):
        # Nur Quellen im Umkreis von c ändern sich; das macht jeden Schritt billig.
        i, a, t = nachbarn(c)
        alt = (r["OA"][i] * XA[i] / (XA[i] + r["KA"][i] + p["a_0"])
               + r["OT"][i] * XT[i] / (XT[i] + r["KT"][i] + p["a_0"])).sum()
        nA, nT = XA[i] + p["a_neu"] * a, XT[i] + p["a_neu"] * t
        neu = (r["OA"][i] * nA / (nA + r["KA"][i] + p["a_0"])
               + r["OT"][i] * nT / (nT + r["KT"][i] + p["a_0"])).sum()
        return neu - alt

    def hinzufuegen(c, XA, XT):
        i, a, t = nachbarn(c)
        XA[i] += p["a_neu"] * a
        XT[i] += p["a_neu"] * t

    kandidaten = g.loc[g["rang"].notna()].nsmallest(p["n_kandidaten_portfolio"], "rang").index.to_numpy()
    XA, XT = np.zeros(paare.n), np.zeros(paare.n)
    zeilen, gewaehlt = [], []
    for schritt in range(1, p["k_portfolio"] + 1):
        offen = [c for c in kandidaten if c not in gewaehlt]
        gewinne = [zugewinn(c, XA, XT) for c in offen]
        best = offen[int(np.argmax(gewinne))]
        hinzufuegen(best, XA, XT)
        gewaehlt.append(best)
        zeilen.append({"schritt": schritt, "h3": g.at[best, "h3"], "rang_einzeln": int(g.at[best, "rang"]),
                       "zugewinn": max(gewinne), "f_nach_schritt": F(XA, XT)})

    # Vergleich: die k besten Einzelstandorte zusammen, ohne Rücksicht auf Überschneidung.
    XA2, XT2 = np.zeros(paare.n), np.zeros(paare.n)
    for c in kandidaten[: p["k_portfolio"]]:
        hinzufuegen(c, XA2, XT2)
    verhaeltnis = zeilen[-1]["f_nach_schritt"] / F(XA2, XT2)
    return pd.DataFrame(zeilen), verhaeltnis


# ---------------------------------------------------------------------------
# Prüfungen (Umsetzungsspezifikation, Abschnitt 9)
# ---------------------------------------------------------------------------

def handrechnung(p: dict) -> None:
    """Drei Zellen in einer Reihe (je 300 m Abstand), ein Wettbewerber in Zelle 3.
    Der Score von Zelle 1 wird mit einfachen Schleifen nachgerechnet und verglichen."""
    d = np.array([[100, 300, 600], [300, 100, 300], [600, 300, 100]], float)
    paare = Paare.__new__(Paare)
    paare.n, paare.d_max = 3, p["d_max_m"]
    paare.i, paare.j = np.repeat(np.arange(3), 3), np.tile(np.arange(3), 3)
    paare.d = d.ravel()
    O = np.array([0.5, 0.3, 0.2])
    A = np.array([0.0, 0.0, 1.0])
    fh = paare.f(p["h_anwohner_m"])
    K = paare.summe(A, fh)
    U1 = 0.0
    for i in range(3):
        a = p["a_neu"] * 2 ** (-d[i, 0] / p["h_anwohner_m"])
        k = sum(A[j] * 2 ** (-d[i, j] / p["h_anwohner_m"]) for j in range(3))
        U1 += O[i] * a / (a + k + p["a_0"])
    assert np.isclose(huff(paare, O, K, fh, p)[0], U1), "Handrechnung weicht ab"


def pruefe(g: pd.DataFrame, ctx: dict, p: dict) -> list[str]:
    fehler = []
    paare, r = ctx["paare"], ctx["r"]
    paar_set = set(zip(paare.i.tolist(), paare.j.tolist()))
    if any((j, i) not in paar_set for i, j in paar_set):
        fehler.append("Paarliste nicht symmetrisch")
    if paare.d.max() > p["d_max_m"] + 1e-6:
        fehler.append("Distanz über d_max")
    # Die Normierung gilt nur mit q = 1, deshalb wird q herausgerechnet.
    norm = (1 - p["theta"]) + (p["theta"] if r["t"].sum() > 0 else 0)
    if not np.isclose((r["OA"] / ctx["q"]).sum() + (r["OT"] / ctx["q"]).sum(), norm):
        fehler.append("Quellnachfrage summiert sich mit q = 1 nicht zu 1")
    if not ((ctx["q"] >= p["q_min"] - 1e-9) & (ctx["q"] <= p["q_max"] + 1e-9)).all():
        fehler.append("q außerhalb [q_min, q_max]")
    if (r["U"] > r["P"] + 1e-12).any():
        fehler.append("U > P")
    ohne = score(g.assign(**{f"poi_{c}": 0 for c in WETTBEWERB_DIREKT + WETTBEWERB_BREIT}),
                 paare, ctx["q"], p, ctx["median_miete"])["W"]
    if not np.allclose(ohne[~np.isnan(ohne)], 1):
        fehler.append("Ohne Wettbewerber ist W nicht überall 1")
    rang = g["rang"].dropna().to_numpy()
    if not np.array_equal(np.sort(rang), np.arange(1, len(rang) + 1)):
        fehler.append("Ränge nicht eindeutig")
    try:
        handrechnung(p)
    except AssertionError as e:
        fehler.append(str(e))
    return fehler


# ---------------------------------------------------------------------------
# Demo-Daten: synthetische Städte mit derselben Spaltenstruktur wie datengrundlage.py
# ---------------------------------------------------------------------------

DEMO_ZENTREN = {"muenchen": (48.137, 11.575, 13.19), "frankfurt": (50.111, 8.682, 9.94),
                "berlin": (52.520, 13.405, 7.71)}


def demo_raster(stadt: str, rng: np.random.Generator) -> pd.DataFrame:
    """Kreisförmige Stadt mit drei Zentren. Bevölkerung, Miete und POIs hängen von der Nähe
    zu den Zentren ab, die Feinkostläden zusätzlich von Miete und Umfeld, damit die
    Regression etwas zu finden hat. Nur zum Ausprobieren, keine echten Werte."""
    lat0, lon0, median = DEMO_ZENTREN[stadt]
    mitte = h3.latlng_to_cell(lat0, lon0, 9)
    zellen = sorted(h3.grid_disk(mitte, 22))
    ll = np.array([h3.cell_to_latlng(c) for c in zellen])
    n = len(zellen)
    zentren = [mitte, *rng.choice(zellen, 2, replace=False)]
    abstand = np.array([[h3.grid_distance(c, z) for z in zentren] for c in zellen]).min(axis=1)
    naehe = np.exp(-abstand / 6)
    park = rng.random(n) < 0.12
    g = pd.DataFrame({"h3": zellen, "lat": ll[:, 0], "lon": ll[:, 1], "stadt": stadt,
                      "in_stadt": [h3.grid_distance(mitte, c) <= 17 for c in zellen]})
    g["einwohner"] = np.where(park, 0, rng.poisson(150 + 900 * naehe))
    g["miete_qm"] = np.where(park, np.nan, median * np.exp(0.25 * naehe - 0.1 + 0.15 * rng.normal(size=n)))
    g["mietwohnungen"] = np.where(park, 0, g["einwohner"] // 2)
    g["miete_geschaetzt"] = rng.random(n) < 0.3
    g["anteil_20_49"] = np.clip(0.35 + 0.15 * naehe + 0.04 * rng.normal(size=n), 0.15, 0.7)
    g["alter_geschaetzt"] = False
    g["haushalte"] = g["einwohner"] // 2
    g["anteil_hh_1_2"] = 0.78
    for c in AFFINITAET + FREQUENZ + WETTBEWERB_BREIT:
        g[f"poi_{c}"] = rng.poisson(0.4 * naehe ** 1.5 * (3 if c in ("bus", "buero", "restaurant") else 1))
    miete_rel = np.nan_to_num(g["miete_qm"].to_numpy() / median, nan=1.0)
    for c in WETTBEWERB_DIREKT:
        g[f"poi_{c}"] = rng.poisson(0.05 * naehe * miete_rel ** 2 * (1 + g["poi_cafe"]))
    return g


# ---------------------------------------------------------------------------
# Hauptprogramm
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="White-Spot-Analyse nach Specs/maths.md")
    parser.add_argument("--demo", action="store_true", help="synthetische Daten statt data/<stadt>_grid.csv")
    parser.add_argument("--staedte", nargs="+", choices=list(DEMO_ZENTREN), default=list(DEMO_ZENTREN))
    parser.add_argument("--laeufe", type=int, default=PARAMETER["n_laeufe"], help="Läufe im Robustheitstest")
    parser.add_argument("--ohne-robustheit", action="store_true")
    args = parser.parse_args()
    p = dict(PARAMETER)

    ordner = ROOT / "data" / ("demo" if args.demo else "")
    ordner.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(p["zufall_startwert"])
    raster = {}
    for s in args.staedte:
        datei = ROOT / "data" / f"{s}_grid.csv"
        if args.demo:
            raster[s] = demo_raster(s, rng)
        elif datei.exists():
            raster[s] = pd.read_csv(datei)
        else:
            raise SystemExit(f"{datei} fehlt. Erst `python datengrundlage.py` ausführen "
                             "oder `python analyse.py --demo` nutzen.")

    bewertet, ctxs = {}, {}
    for s, g in raster.items():
        print(f"\n=== {s}: {len(g):,} Hexagone, {int(g['in_stadt'].sum()):,} in der Stadt ===")
        bewertet[s], ctxs[s] = bewerte_stadt(g, p)
        print(f"  Paare {len(ctxs[s]['paare'].d):,}, Geschäftslagen {int(bewertet[s]['rang'].notna().sum()):,}, "
              f"Affinität: {ctxs[s]['pca']['variante']} "
              f"(PC1 erklärt {ctxs[s]['pca']['erklaerte_varianz_pc1']:.0%})")
        (ordner / f"{s}_pca.json").write_text(json.dumps(ctxs[s]["pca"], indent=2, ensure_ascii=False))
        plaus = plausibilitaet(bewertet[s], p)
        (ordner / f"{s}_plausibilitaet.json").write_text(json.dumps(plaus, indent=2))
        print(f"  Plausibilität: {plaus['anteil_pois_in_top_zellen']:.0%} der Feinkostläden in den "
              f"oberen 20 % nach Potenzial (ohne Vorhersagekraft: 20 %)")
        fehler = pruefe(bewertet[s], ctxs[s], p)
        print("  Prüfungen: " + ("alle bestanden" if not fehler else "FEHLER: " + "; ".join(fehler)))

    print("\n=== Angebotslücke (Regression über alle Städte) ===")
    luecke = angebotsluecke(bewertet, ctxs, p)
    (ordner / "luecke_modell.json").write_text(json.dumps(luecke, indent=2, ensure_ascii=False))
    print(f"  Modell: {luecke['variante']}, Dispersion Poisson {luecke['dispersion_poisson']}, "
          f"erklärte Devianz in/außerhalb {luecke['erklaerte_devianz_in_stichprobe']:.3f} / "
          f"{luecke['erklaerte_devianz_ausserhalb']:.3f}")
    print("  Koeffizienten: " + ", ".join(f"{k} {luecke['koeffizienten'][k]:+.3f}" for k in MERKMALE))

    for s, g in bewertet.items():
        print(f"\n=== {s}: Robustheit und Portfolio ===")
        if not args.ohne_robustheit:
            rob = robustheit(g, ctxs[s], p, args.laeufe)
            g[rob.columns] = rob
            print(f"  {args.laeufe} Läufe gerechnet")
        port, verh = portfolio(g, ctxs[s], p)
        port.to_csv(ordner / f"{s}_portfolio.csv", index=False)
        if (np.diff(port["zugewinn"]) > 1e-12).any():
            print("  WARNUNG: Zugewinn steigt zwischen zwei Schritten, F ist nicht submodular.")
        if verh < 1:
            print("  WARNUNG: Portfolio schlechter als die k besten Einzelstandorte.")
        print(f"  Portfolio aus {p['k_portfolio']} Standorten erreicht {verh:.2f}-mal das F "
              "der k besten Einzelstandorte")

        g.to_csv(ordner / f"{s}_scored.csv", index=False, float_format="%.6g")
        spalten = ["rang", "h3", "pr_score", "pr_potenzial", "pr_wettbewerbsfreiheit", "pr_affinitaet",
                   "pr_luecke", "konsens", "profil"] + (["top10_anteil"] if not args.ohne_robustheit else [])
        top = g[g["rang"] <= p["top_n"]].sort_values("rang")[spalten]
        print(top.to_string(index=False, float_format=lambda x: f"{x:.0f}" if abs(x) >= 1 else f"{x:.2f}"))
        print(f"  geschrieben: {ordner.relative_to(ROOT)}/{s}_scored.csv ({len(g):,} Zeilen)")


if __name__ == "__main__":
    main()
