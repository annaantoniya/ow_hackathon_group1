import os
import yaml
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree
import logging

# Logging-Konfiguration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def load_config(path='config.yaml'):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def build_sparse_distance_matrix(df, d_max_m, umwegfaktor, d_selbst_m):
    """Rekonstruiert die statische Adjazenzliste für die räumlichen Operationen."""
    rad = np.deg2rad(df[['lat', 'lon']].values)
    tree = BallTree(rad, metric='haversine')
    r_rad = (d_max_m / umwegfaktor) / 6371000
    indices, distances = tree.query_radius(rad, r=r_rad, return_distance=True)
    
    lengths = np.array([len(idx) for idx in indices])
    i = np.repeat(np.arange(len(df)), lengths)
    j = np.concatenate(indices)
    d = np.concatenate(distances) * 6371000 * umwegfaktor
    d[i == j] = d_selbst_m
    return i, j, d

def draw_parameters(config):
    """Zieht einen Satz von Parametern zufällig aus den spezifizierten Spannen."""
    p = config.copy()
    
    # Absolute Spannen
    p['h_anwohner_m'] = np.random.uniform(300, 500)
    p['h_tag_m'] = np.random.uniform(150, 350)
    p['gamma'] = np.random.uniform(0.5, 1.5)
    p['theta'] = np.random.uniform(0.1, 0.5)
    
    # Multiplikative Faktoren (0.5 bis 1.5)
    multiplikatoren = [
        'w_buero', 'w_hochschule', 'w_bahnhof', 'w_tram_ubahn', 'w_bus', 'a_0',
        'alpha_markthalle', 'alpha_bio_markt', 'alpha_deli', 'alpha_feinkost_kaese',
        'alpha_wein', 'alpha_pasta', 'alpha_reformhaus', 'alpha_supermarkt',
        'alpha_baecker', 'alpha_metzger', 'alpha_obst_gemuese', 'alpha_fisch'
    ]
    
    for m in multiplikatoren:
        p[m] = config[m] * np.random.uniform(0.5, 1.5)
        
    return p

def run_monte_carlo(stadt, config):
    logging.info(f"Starte Robustheitstest für {stadt} ({config['n_laeufe']} Läufe)...")
    
    # Startwert für exakte Reproduzierbarkeit garantieren
    np.random.seed(config.get('zufall_startwert', 42))
    
    filepath = f"data/{stadt}_scored.csv"
    df = pd.read_csv(filepath)
    N = len(df)
    
    # Matrix aufbauen (bleibt fest für alle Iterationen)
    i, j, d = build_sparse_distance_matrix(df, config['d_max_m'], config['umwegfaktor'], config['d_selbst_m'])
    
    # Vektoren vorbereiten (verhindert langsames DataFrame-Slicing in der Schleife)
    mask_valid = (df['in_stadt'] == True) & (df['geschaeftslage'] == True)
    valid_indices = df.index[mask_valid].to_numpy()
    n_valid = len(valid_indices)
    
    if n_valid == 0:
        logging.warning(f"Keine Geschäftslagen in {stadt} gefunden. Überspringe Robustheit.")
        return

    # Statische Attribute
    einwohner = df['einwohner'].values
    anteil_20_49 = df['anteil_20_49'].values
    miete_qm = df['miete_qm'].values
    q = df['q'].values
    
    # Median-Miete (bleibt fest, da Rohdaten unverändert)
    med_miete = df.loc[df['in_stadt'] & ~df['miete_geschaetzt'], 'miete_qm'].median()
    
    # POI-Kategorien cachen
    frequenz_cats = ['bahnhof', 'tram_ubahn', 'bus', 'buero', 'hochschule']
    wettbewerb_cats = {
        'deli': 'alpha_deli', 'feinkost_kaese': 'alpha_feinkost_kaese', 'wein': 'alpha_wein', 
        'bio_markt': 'alpha_bio_markt', 'reformhaus': 'alpha_reformhaus', 'markthalle': 'alpha_markthalle', 
        'pasta': 'alpha_pasta', 'supermarkt': 'alpha_supermarkt', 'obst_gemuese': 'alpha_obst_gemuese', 
        'metzger': 'alpha_metzger', 'baecker': 'alpha_baecker', 'fisch': 'alpha_fisch'
    }
    
    poi_freq = {c: df[f'poi_{c}'].values for c in frequenz_cats if f'poi_{c}' in df.columns}
    poi_wett = {c: df[f'poi_{c}'].values for c in wettbewerb_cats.keys() if f'poi_{c}' in df.columns}
    
    # Ergebnis-Matrix für die Ränge (Zeilen = Iterationen, Spalten = valide Geschäftslagen)
    ranks_matrix = np.zeros((config['n_laeufe'], n_valid), dtype=np.float32)
    
    # Monte-Carlo Schleife
    for lauf in range(config['n_laeufe']):
        p = draw_parameters(config)
        
        # --- Schritt 4: Nachfrage ---
        k_i = np.clip(miete_qm / med_miete, p['k_min'], p['k_max']) ** p['gamma']
        k_i = np.where(np.isnan(k_i), 1.0, k_i)
        n_anw = einwohner * anteil_20_49 * k_i
        
        t_idx = np.zeros(N)
        for cat, arr in poi_freq.items():
            t_idx += arr * p[f'w_{cat}']
            
        sum_n = n_anw.sum()
        sum_t = t_idx.sum()
        
        o_anw = q * (1 - p['theta']) * (n_anw / sum_n if sum_n > 0 else 0)
        o_tag = q * p['theta'] * (t_idx / sum_t if sum_t > 0 else 0)
        
        # --- Schritt 6: Wettbewerb & Score ---
        A_j = np.zeros(N)
        for cat, arr in poi_wett.items():
            A_j += arr * p[wettbewerb_cats[cat]]
            
        f_A = 2 ** (-d / p['h_anwohner_m'])
        f_T = 2 ** (-d / p['h_tag_m'])
        
        # np.bincount ist signifikant schneller als Pandas groupby
        K_A = np.bincount(i, weights=A_j[j] * f_A, minlength=N)
        K_T = np.bincount(i, weights=A_j[j] * f_T, minlength=N)
        
        prob_U_A = (p['a_neu'] * f_A) / (p['a_neu'] * f_A + K_A[i] + p['a_0'])
        prob_U_T = (p['a_neu'] * f_T) / (p['a_neu'] * f_T + K_T[i] + p['a_0'])
        
        u_anw = np.bincount(j, weights=o_anw[i] * prob_U_A, minlength=N)
        u_tag = np.bincount(j, weights=o_tag[i] * prob_U_T, minlength=N)
        u_gesamt = u_anw + u_tag
        
        # --- Schritt 7: Ränge berechnen ---
        u_valid = u_gesamt[valid_indices]
        
        # Äquivalent zu df.rank(method='first', ascending=False)
        # Die Negation -u_valid sortiert absteigend. argsort.argsort liefert den Rang (0-basiert).
        sorted_indices = np.argsort(-u_valid)
        ranks = np.empty_like(sorted_indices)
        ranks[sorted_indices] = np.arange(1, n_valid + 1)
        
        ranks_matrix[lauf, :] = ranks

    # Auswertung der Matrix über die Spalten (axis=0)
    df['top10_anteil'] = np.nan
    df['rang_median'] = np.nan
    df['rang_p10'] = np.nan
    df['rang_p90'] = np.nan
    
    df.loc[mask_valid, 'top10_anteil'] = np.mean(ranks_matrix <= 10, axis=0) * 100 # In Prozent für einfachere Deutung (optional)
    df.loc[mask_valid, 'rang_median'] = np.median(ranks_matrix, axis=0)
    df.loc[mask_valid, 'rang_p10'] = np.percentile(ranks_matrix, 10, axis=0)
    df.loc[mask_valid, 'rang_p90'] = np.percentile(ranks_matrix, 90, axis=0)
    
    # Rückschreiben in die Datei
    df.to_csv(filepath, index=False)
    logging.info(f"Robustheit für {stadt} beendet. Zeilen geschrieben: {len(df)}")

if __name__ == "__main__":
    config = load_config()
    staedte = ['muenchen', 'frankfurt', 'berlin']
    for stadt in staedte:
        run_monte_carlo(stadt, config)