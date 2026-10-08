import os
import yaml
import json
import numpy as np
import pandas as pd
import h3
from sklearn.neighbors import BallTree
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import scipy.stats

# Fester Startwert für reproduzierbare Stochastik
np.random.seed(42)

def load_config(path='config.yaml'):
    """Lädt die Modellparameter deterministisch in den Arbeitsspeicher."""
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def build_sparse_distance_matrix(df, d_max_m, umwegfaktor, d_selbst_m):
    """
    Konstruiert die räumliche Adjazenzliste via BallTree. 
    Verhindert N^2 Komplexität durch strikte Kappung bei d_max_m.
    """
    # Überführung der geodätischen Koordinaten in Bogenmaß für Haversine-Metrik
    rad = np.deg2rad(df[['lat', 'lon']].values)
    tree = BallTree(rad, metric='haversine')
    
    # Radius in Bogenmaß (Erdradius = 6.371.000 m)
    r_rad = (d_max_m / umwegfaktor) / 6371000
    indices, distances = tree.query_radius(rad, r=r_rad, return_distance=True)
    
    # Transformation der nested Arrays in flache 1D-Vektoren (Sparse Format: i, j, d)
    lengths = np.array([len(idx) for idx in indices])
    i = np.repeat(np.arange(len(df)), lengths)
    j = np.concatenate(indices)
    d = np.concatenate(distances) * 6371000 * umwegfaktor
    
    # Eigendistanz der Zelle korrigieren, um Division durch Null oder Singularitäten zu vermeiden
    d[i == j] = d_selbst_m
    return i, j, d

def calculate_base_demand(df, config):
    """Berechnet die nicht-distanzgewichtete Basisnachfrage N_i und t_i."""
    # Median-Miete über validierte städtische H3-Zellen ermitteln
    med_miete = df.loc[df['in_stadt'] & ~df['miete_geschaetzt'], 'miete_qm'].median()
    
    # Kaufkraftfaktor k_i mit Sättigungsgrenzen und Elastizität gamma
    k_i = np.clip(df['miete_qm'] / med_miete, config['k_min'], config['k_max']) ** config['gamma']
    # Fehlende Miete (NaN) bedeutet Faktor 1.0 (neutral)
    k_i = k_i.fillna(1.0)
    
    df['n_anwohner'] = df['einwohner'] * df['anteil_20_49'] * k_i
    
    # Tagesbevölkerungsindex als lineare Kombination der Frequenz-POIs
    frequenz_kategorien = ['bahnhof', 'tram_ubahn', 'bus', 'buero', 'hochschule']
    df['t_index'] = sum(
        df[f'poi_{cat}'] * config[f'w_{cat}'] 
        for cat in frequenz_kategorien if f'poi_{cat}' in df.columns
    )
    return df

def calculate_affinity(df, i, j, d, config, stadt):
    """
    Isoliert das latente Konstrukt der 'Zentralität' mittels PCA über 
    räumlich geglättete Affinitäts-POIs.
    """
    N = len(df)
    aff_kategorien = [
        'cafe', 'restaurant', 'bar', 'buchhandlung', 'interior', 'boutique', 
        'blumen', 'fitness_yoga', 'kultur', 'galerie_museum', 'coworking', 'fahrradladen'
    ]
    
    s_matrix = []
    # 1. Geglättete Dichte je Kategorie berechnen
    for cat in aff_kategorien:
        col = f'poi_{cat}'
        if col not in df.columns:
            continue
        # Distanzzerfall anwenden und auf Zielknoten i aggregieren
        weight = df[col].values[j] * (2 ** (-d / config['h_affinitaet_m']))
        s_c = np.bincount(i, weights=weight, minlength=N)
        s_matrix.append(np.log1p(s_c))
    # Mathematischer Grenzfall: Der Spaltenraum ist leer (z.B. durch API-Timeouts)
    if not s_matrix:
        df['q'] = 1.0  # Neutrales Element (Identität) für den Affinitätsfaktor
        df['aff_index'] = 0.0
        
        with open(f"data/{stadt}_pca.json", 'w', encoding='utf-8') as f:
            json.dump({"variante": "Fallback_Fehlende_Daten"}, f)
        return df
        
    s_matrix = np.column_stack(s_matrix)
    
    # 2. Standardisierung und 3. PCA
    X_std = StandardScaler().fit_transform(s_matrix)
    pca = PCA(n_components=1)
    pc1 = pca.fit_transform(X_std).flatten()
    
    # 4. Vorzeichenkorrektur: PC1 muss positiv mit der mittleren Dichte korrelieren
    mean_dichte = X_std.mean(axis=1)
    korrelation = np.corrcoef(pc1, mean_dichte)[0, 1]
    
    fallback_aktiv = False
    if korrelation < 0:
        pc1 = -pc1
        korrelation = -korrelation
        
    if korrelation < 0.9:
        # Rückfall auf simplen Mittelwert bei unzureichender Dimensionsreduktion
        pc1 = mean_dichte
        fallback_aktiv = True
        
    # JSON Protokollierung
    pca_log = {
        "erklaerte_varianz": float(pca.explained_variance_ratio_[0]) if not fallback_aktiv else None,
        "korrelation_pc1_mittelwert": float(korrelation),
        "variante": "Mittelwert" if fallback_aktiv else "PCA"
    }
    with open(f"data/{stadt}_pca.json", 'w', encoding='utf-8') as f:
        json.dump(pca_log, f)

    # 5. Prozentrang-Skalierung strikt bezogen auf Stadt-Zellen
    idx_stadt = df['in_stadt']
    pc1_stadt = pc1[idx_stadt]
    
    # Vektorisierte Zuordnung des empirischen Prozentrangs (0 bis 1)
    ranks = np.searchsorted(np.sort(pc1_stadt), pc1) / len(pc1_stadt)
    df['q'] = config['q_min'] + (config['q_max'] - config['q_min']) * ranks
    df['aff_index'] = pc1
    return df

def apply_huff_model(df, i, j, d, config):
    """
    Berechnet die stochastischen Kaufwahrscheinlichkeiten. Löst Quellnachfrage, 
    Wettbewerbsdruck am Quellort und das resultierende Marktpotenzial am Zielort.
    """
    N = len(df)
    
    # 6.5 Quellnachfrage O_i (normiert auf Gesamtnetzwerk)
    sum_n = df['n_anwohner'].sum()
    sum_t = df['t_index'].sum()
    
    df['o_anw'] = df['q'] * (1 - config['theta']) * (df['n_anwohner'] / sum_n if sum_n else 0)
    df['o_tag'] = df['q'] * config['theta'] * (df['t_index'] / sum_t if sum_t else 0)
    
    # 6.7 Wettbewerbsstärke A_j pro Zelle
    wettbewerb_cats = {
        'deli': 'alpha_deli', 'feinkost_kaese': 'alpha_feinkost_kaese', 'wein': 'alpha_wein', 
        'bio_markt': 'alpha_bio_markt', 'reformhaus': 'alpha_reformhaus', 'markthalle': 'alpha_markthalle', 
        'pasta': 'alpha_pasta', 'supermarkt': 'alpha_supermarkt', 'obst_gemuese': 'alpha_obst_gemuese', 
        'metzger': 'alpha_metzger', 'baecker': 'alpha_baecker', 'fisch': 'alpha_fisch'
    }
    
    A_j = np.zeros(N)
    for cat, param in wettbewerb_cats.items():
        if f'poi_{cat}' in df.columns:
            A_j += df[f'poi_{cat}'] * config[param]
            
    # Wettbewerbsdruck K_i, den die Quellzelle i erfährt
    K_A = np.bincount(i, weights=A_j[j] * (2 ** (-d / config['h_anwohner_m'])), minlength=N)
    K_T = np.bincount(i, weights=A_j[j] * (2 ** (-d / config['h_tag_m'])), minlength=N)
    
    # 6.6 Potenzial P_c (Zielort c ist in der Sparse-Matrix j, Quellort ist i)
    f_A = 2 ** (-d / config['h_anwohner_m'])
    f_T = 2 ** (-d / config['h_tag_m'])
    A_neu = config['a_neu']
    A_0 = config['a_0']
    
    # Probabilitäten ohne Wettbewerb (nur Außenoption A_0)
    prob_P_A = (A_neu * f_A) / (A_neu * f_A + A_0)
    prob_P_T = (A_neu * f_T) / (A_neu * f_T + A_0)
    
    df['p_anw'] = np.bincount(j, weights=df['o_anw'].values[i] * prob_P_A, minlength=N)
    df['p_tag'] = np.bincount(j, weights=df['o_tag'].values[i] * prob_P_T, minlength=N)
    df['p'] = df['p_anw'] + df['p_tag']
    
    # 6.7 Score U_c (mit Wettbewerbsdruck K_i der Quellzelle i)
    prob_U_A = (A_neu * f_A) / (A_neu * f_A + K_A[i] + A_0)
    prob_U_T = (A_neu * f_T) / (A_neu * f_T + K_T[i] + A_0)
    
    df['u_anw'] = np.bincount(j, weights=df['o_anw'].values[i] * prob_U_A, minlength=N)
    df['u_tag'] = np.bincount(j, weights=df['o_tag'].values[i] * prob_U_T, minlength=N)
    df['u'] = df['u_anw'] + df['u_tag']
    
    # Wettbewerbsfreiheit W_c. Division durch 0 via np.where abfangen
    df['w'] = np.where(df['p'] > 0, df['u'] / df['p'], np.nan)
    return df

def calculate_profiles(df, config):
    """Ermittelt Geschäftslagen über H3-Topologie und ordnet Typologien zu."""
    # Definition der relevanten POIs für Geschäftslage (Wettbewerb + Affinität)
    alle_cats = [c.replace('poi_', '') for c in df.columns if c.startswith('poi_')]
    frequenz_cats = {'bahnhof', 'tram_ubahn', 'bus', 'buero', 'hochschule'}
    rel_cats = [c for c in alle_cats if c not in frequenz_cats]
    
    df['poi_summe_geschaeft'] = df[[f'poi_{c}' for c in rel_cats]].sum(axis=1)
    poi_dict = dict(zip(df['h3'], df['poi_summe_geschaeft']))
    
    # 6.8 Geschäftslage über direkte topologische Nachbarn (Disk Radius 1)
    df['geschaeftslage'] = df['h3'].apply(
        lambda cell: sum(poi_dict.get(neighbor, 0) for neighbor in h3.grid_disk(cell, 1)) >= config['n_min_geschaeftslage']
    )
    
    # 6.9 Ränge und Prozentränge
    mask_valid = df['in_stadt'] & df['geschaeftslage']
    df['rang'] = np.nan
    # Rang absteigend (höchster Score = Rang 1)
    df.loc[mask_valid, 'rang'] = df.loc[mask_valid, 'u'].rank(method='first', ascending=False)
    
    # Prozentränge von 0 bis 100 über Zellen mit in_stadt
    for col, out_col in [('u', 'pr_score'), ('p', 'pr_potenzial'), ('w', 'pr_wettbewerbsfreiheit'), ('q', 'pr_affinitaet')]:
        df[out_col] = df.loc[df['in_stadt'], col].rank(pct=True) * 100
        # Pufferzellen erhalten keinen Rang für die Endausgabe
        df[out_col] = df[out_col].fillna(0)
        
    # Tagesanteil und Profil
    df['anteil_tag'] = np.where(df['p'] > 0, df['p_tag'] / df['p'], 0)
    
    cond_mittag = df['anteil_tag'] > (config['profil_schwelle_hoch'] * config['theta'])
    cond_feierabend = df['anteil_tag'] < (config['profil_schwelle_tief'] * config['theta'])
    
    df['profil'] = 'Ganztagsstandort'
    df.loc[cond_mittag, 'profil'] = 'Mittagsstandort'
    df.loc[cond_feierabend, 'profil'] = 'Feierabendstandort'
    
    return df

def run_plausibility_test(df, config, stadt):
    """
    6.10 Plausibilitätstest. Prüft, ob das berechnete ex-ante Potenzial P 
    mit der empirischen Allokation bestehender direkter Wettbewerber korreliert.
    """
    df_stadt = df[df['in_stadt']].copy()
    schwelle = df_stadt['p'].quantile(1 - config['plausibilitaet_anteil'])
    top_p_zellen = df_stadt[df_stadt['p'] >= schwelle]
    
    direkt_cats = ['deli', 'feinkost_kaese', 'wein', 'bio_markt', 'reformhaus', 'markthalle', 'pasta']
    poi_cols = [f'poi_{c}' for c in direkt_cats if f'poi_{c}' in df.columns]
    
    total_direkt = df_stadt[poi_cols].sum().sum()
    top_direkt = top_p_zellen[poi_cols].sum().sum()
    
    anteil = float(top_direkt / total_direkt) if total_direkt > 0 else 0.0
    
    log_data = {
        "anteil_in_top20": anteil,
        "zahl_pois": int(total_direkt),
        "zahl_zellen": int(len(df_stadt))
    }
    
    with open(f"data/{stadt}_plausibilitaet.json", 'w', encoding='utf-8') as f:
        json.dump(log_data, f)

def prozessiere_stadt(stadt, config):
    print(f"Modelliere {stadt}...")
    df = pd.read_csv(f"data/{stadt}_grid.csv")
    
    i, j, d = build_sparse_distance_matrix(df, config['d_max_m'], config['umwegfaktor'], config['d_selbst_m'])
    
    df = calculate_base_demand(df, config)
    df = calculate_affinity(df, i, j, d, config, stadt)
    df = apply_huff_model(df, i, j, d, config)
    df = calculate_profiles(df, config)
    
    run_plausibility_test(df, config, stadt)
    
    output_path = f"data/{stadt}_scored.csv"
    df.to_csv(output_path, index=False)
    print(f"Abgeschlossen: {len(df)} Parzellen berechnet. Zeilen geschrieben: {len(df)}")

if __name__ == "__main__":
    config = load_config()
    staedte = ['muenchen', 'frankfurt', 'berlin']
    for stadt in staedte:
        prozessiere_stadt(stadt, config)