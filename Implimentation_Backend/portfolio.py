import os
import yaml
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree
import logging

# Konfiguration des Loggings und Reproduzierbarkeit
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
np.random.seed(42)

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

def berechne_portfolio(stadt, config):
    logging.info(f"Optimiere Portfolio für {stadt}...")
    filepath = f"data/{stadt}_scored.csv"
    df = pd.read_csv(filepath)
    N = len(df)
    
    # Sicherstellen, dass Quellnachfrage-Spalten existieren
    if 'o_anw' not in df.columns or 'o_tag' not in df.columns:
        sum_n, sum_t = df['n_anwohner'].sum(), df['t_index'].sum()
        df['o_anw'] = df['q'] * (1 - config['theta']) * (df['n_anwohner'] / sum_n if sum_n else 0)
        df['o_tag'] = df['q'] * config['theta'] * (df['t_index'] / sum_t if sum_t else 0)
        
    O_A = df['o_anw'].values
    O_T = df['o_tag'].values
    
    # 1. Wettbewerbsdruck (Denominatoren) ex-ante rekonstruieren
    wettbewerb_cats = {
        'deli': 'alpha_deli', 'feinkost_kaese': 'alpha_feinkost_kaese', 'wein': 'alpha_wein', 
        'bio_markt': 'alpha_bio_markt', 'reformhaus': 'alpha_reformhaus', 'markthalle': 'alpha_markthalle', 
        'pasta': 'alpha_pasta', 'supermarkt': 'alpha_supermarkt', 'obst_gemuese': 'alpha_obst_gemuese', 
        'metzger': 'alpha_metzger', 'baecker': 'alpha_baecker', 'fisch': 'alpha_fisch'
    }
    
    A_j = np.zeros(N)
    for cat, param in wettbewerb_cats.items():
        if f'poi_{cat}' in df.columns:
            A_j += df[f'poi_{cat}'].values * config[param]
            
    i, j, d = build_sparse_distance_matrix(df, config['d_max_m'], config['umwegfaktor'], config['d_selbst_m'])
    
    K_A = np.bincount(i, weights=A_j[j] * (2 ** (-d / config['h_anwohner_m'])), minlength=N)
    K_T = np.bincount(i, weights=A_j[j] * (2 ** (-d / config['h_tag_m'])), minlength=N)
    
    Denom_A = K_A + config['a_0']
    Denom_T = K_T + config['a_0']
    
    # 2. Kandidaten filtern (Top 300 Geschäftslagen nach Score U)
    n_kandidaten = config.get('n_kandidaten_portfolio', 300)
    cand_mask = df['in_stadt'] & df['geschaeftslage']
    cand_df = df[cand_mask].sort_values('u', ascending=False).head(n_kandidaten)
    
    cand_indices = cand_df.index.to_numpy()
    n_kandidaten = len(cand_indices)
    
    if n_kandidaten == 0:
        logging.warning(f"Keine Kandidaten für {stadt} gefunden!")
        return

    # 3. Attraktions-Matrix der Kandidaten aufbauen (N x C)
    Att_A = np.zeros((N, n_kandidaten))
    Att_T = np.zeros((N, n_kandidaten))
    
    # Effizientes Mapping: Globale H3-ID (j) -> Lokale Kandidaten-ID (0 bis 299)
    j_to_cand = np.full(N, -1)
    j_to_cand[cand_indices] = np.arange(n_kandidaten)
    
    valid_mask = j_to_cand[j] != -1
    i_valid, cand_valid, d_valid = i[valid_mask], j_to_cand[j[valid_mask]], d[valid_mask]
    
    Att_A[i_valid, cand_valid] = config['a_neu'] * (2 ** (-d_valid / config['h_anwohner_m']))
    Att_T[i_valid, cand_valid] = config['a_neu'] * (2 ** (-d_valid / config['h_tag_m']))
    
    # 4. Greedy-Algorithmus (Submodulare Maximierung)
    k_portfolio = min(config.get('k_portfolio', 5), n_kandidaten)
    selected = []
    
    X_A, X_T = np.zeros(N), np.zeros(N)
    F_history, zugewinn_history = [], []
    current_F = 0.0
    
    for step in range(k_portfolio):
        # Broadcasting: Simuliert das Hinzufügen JEDES Kandidaten simultan
        New_X_A = X_A[:, None] + Att_A
        New_X_T = X_T[:, None] + Att_T
        
        # F für alle Kandidaten berechnen
        Term_A = O_A[:, None] * (New_X_A / (New_X_A + Denom_A[:, None]))
        Term_T = O_T[:, None] * (New_X_T / (New_X_T + Denom_T[:, None]))
        F_all = np.sum(Term_A + Term_T, axis=0)
        
        # Bereits gewählte Kandidaten aus der Suche ausschließen
        for c in selected:
            F_all[c] = -1.0
            
        best_c = np.argmax(F_all)
        best_F = F_all[best_c]
        zugewinn = best_F - current_F
        
        # Prüfung: Monotonie und Submodularität (Marginaler Zugewinn darf nie steigen)
        if step > 0 and zugewinn > zugewinn_history[-1] + 1e-6:
            logging.warning(f"Warnung: Submodularität in Schritt {step+1} verletzt!")
            
        selected.append(best_c)
        zugewinn_history.append(zugewinn)
        F_history.append(best_F)
        
        # Aktualisiere die akkumulierte Netzwerkkraft für die nächste Iteration
        X_A += Att_A[:, best_c]
        X_T += Att_T[:, best_c]
        current_F = best_F
        
    # 5. Vergleich mit der naiven Top-K Auswahl
    # Die naiven Top-K sind genau die ersten k Elemente, da `cand_df` nach Score 'u' absteigend sortiert ist
    X_A_naive = np.sum(Att_A[:, :k_portfolio], axis=1)
    X_T_naive = np.sum(Att_T[:, :k_portfolio], axis=1)
    
    Term_A_naive = O_A * (X_A_naive / (X_A_naive + Denom_A))
    Term_T_naive = O_T * (X_T_naive / (X_T_naive + Denom_T))
    F_naive = np.sum(Term_A_naive + Term_T_naive)
    
    ratio = current_F / F_naive if F_naive > 0 else 1.0
    
    # Prüfung: Portfolio muss mindestens so gut sein wie die naiven Top K
    if current_F < F_naive - 1e-5:
        logging.warning("Warnung: F des Portfolios liegt unter F der k besten Einzelstandorte!")
        
    # 6. Ergebnisse formatieren und speichern
    results = []
    for step_idx in range(k_portfolio):
        c_idx = selected[step_idx]
        real_idx = cand_indices[c_idx]
        h3_id = df.loc[real_idx, 'h3']
        
        results.append({
            'reihenfolge': step_idx + 1,
            'h3': h3_id,
            'zugewinn': zugewinn_history[step_idx],
            'f_gesamt': F_history[step_idx],
            'verhaeltnis_portfolio_zu_top_k': ratio
        })
        
    df_port = pd.DataFrame(results)
    df_port.to_csv(f"data/{stadt}_portfolio.csv", index=False)
    logging.info(f"Portfolio für {stadt} berechnet (Ratio: {ratio:.3f}).")

if __name__ == "__main__":
    config = load_config()
    staedte = ['muenchen', 'frankfurt', 'berlin']
    for stadt in staedte:
        berechne_portfolio(stadt, config)