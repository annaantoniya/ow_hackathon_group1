import os
import json
import yaml
import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
import h3
from sklearn.neighbors import BallTree
import logging

# Setzungen nach Spezifikation
np.random.seed(42)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def load_config(path='config.yaml'):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def build_sparse_distance_matrix(df, d_max_m, umwegfaktor, d_selbst_m):
    """Berechnet die Nachbarschaftsmatrix für die räumliche Glättung."""
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

def berechne_umfeld_merkmale(df, i, j, d, config):
    """Kalkuliert die distanzgewichteten Merkmale für die Regression."""
    N = len(df)
    
    # Gewichtsfunktionen
    w_anw = 2 ** (-d / config['h_anwohner_m'])
    w_tag = 2 ** (-d / config['h_tag_m'])
    
    # 1. Einwohner
    sm_einw = np.bincount(i, weights=df['einwohner'].values[j] * w_anw, minlength=N)
    df['raw_einwohner'] = np.log1p(sm_einw)
    
    # 2. Kaufkraft (Miete gewichtet mit Einwohnern)
    median_miete = df.loc[df['in_stadt'] & ~df['miete_geschaetzt'], 'miete_qm'].median()
    sm_miete_gew = np.bincount(i, weights=(df['einwohner'] * df['miete_qm'].fillna(median_miete)).values[j] * w_anw, minlength=N)
    
    with np.errstate(divide='ignore', invalid='ignore'):
        # Sichere Division: Verhindert Division durch Null auf C-Ebene
        kaufkraft_ratio = np.divide(sm_miete_gew, sm_einw, out=np.zeros_like(sm_miete_gew), where=sm_einw > 0)
        ratio_norm = np.divide(kaufkraft_ratio, median_miete, out=np.ones_like(kaufkraft_ratio), where=kaufkraft_ratio > 0)
        df['raw_kaufkraft'] = np.log(ratio_norm)
    
    # 3. Alter (Anteil 20-49 gewichtet mit Einwohnern)
    mean_alter = df.loc[df['in_stadt'], 'anteil_20_49'].mean()
    sm_alter_gew = np.bincount(i, weights=(df['einwohner'] * df['anteil_20_49']).values[j] * w_anw, minlength=N)
    
    with np.errstate(divide='ignore', invalid='ignore'):
        raw_alter = np.divide(sm_alter_gew, sm_einw, out=np.full_like(sm_alter_gew, mean_alter), where=sm_einw > 0)
        df['raw_alter'] = np.nan_to_num(raw_alter, nan=mean_alter, posinf=mean_alter, neginf=mean_alter)
    
    # 4. Affinität
    df['raw_affinitaet'] = df['aff_index']
    
    # 5. Tagesbevölkerung
    sm_tag = np.bincount(i, weights=df['t_index'].values[j] * w_tag, minlength=N)
    df['raw_tag'] = np.log1p(sm_tag)
    
    # Zielgröße: Direkter Wettbewerb
    direkt_cats = ['deli', 'feinkost_kaese', 'wein', 'bio_markt', 'reformhaus', 'markthalle', 'pasta']
    df['y_direkt'] = sum(df.get(f'poi_{c}', np.zeros(N)) for c in direkt_cats)
    
    return df

def prozessiere_luecke():
    config = load_config()
    staedte = ['muenchen', 'frankfurt', 'berlin']
    
    dfs = {}
    dist_matrices = {}
    
    # 1. Merkmale je Stadt berechnen
    for stadt in staedte:
        filepath = f"data/{stadt}_scored.csv"
        df = pd.read_csv(filepath)
        i, j, d = build_sparse_distance_matrix(df, config['d_max_m'], config['umwegfaktor'], config['d_selbst_m'])
        dist_matrices[stadt] = (i, j, d)
        
        df = berechne_umfeld_merkmale(df, i, j, d, config)
        
        # Standardisierung je Stadt, gelernt nur auf in_stadt
        scaler = StandardScaler()
        cols_to_scale = ['raw_einwohner', 'raw_kaufkraft', 'raw_alter', 'raw_affinitaet', 'raw_tag']
        out_cols = ['x_einwohner', 'x_kaufkraft', 'x_alter', 'x_affinitaet', 'x_tag']
        
        df_stadt = df[df['in_stadt']]
        scaler.fit(df_stadt[cols_to_scale])
        df[out_cols] = scaler.transform(df[cols_to_scale])
        
        dfs[stadt] = df

    # 2. Modell-Datensatz zusammenführen (nur in_stadt für Training)
    df_all = pd.concat([dfs[s][dfs[s]['in_stadt']].assign(stadt=s) for s in staedte], ignore_index=True)
    
    X_cols = ['x_einwohner', 'x_kaufkraft', 'x_alter', 'x_affinitaet', 'x_tag']
    y = df_all['y_direkt'].values
    
    # Dummy-Codierung für festen Effekt der Stadt
    X_base = pd.get_dummies(df_all['stadt'], drop_first=True, dtype=float)
    X = sm.add_constant(pd.concat([df_all[X_cols], X_base], axis=1))



    # 3. Prüfung auf singulären Nullvektor in der Zielvariable
    if np.sum(y) == 0:
        logging.warning("Singularität: Zielvektor y_direkt ist der Nullvektor. Überspringe Regression.")
        for stadt in staedte:
            df = dfs[stadt]
            df['y_erwartet'] = 0.0
            for col in X_cols:
                df[f'beitrag_{col.replace("x_", "")}'] = 0.0
            df['luecke'] = 0.0
            df['pr_luecke'] = 0.0
            df['konsens'] = False
            df.to_csv(f"data/{stadt}_scored.csv", index=False)
            
        with open("data/luecke_modell.json", "w", encoding='utf-8') as f:
            json.dump({"variante": "Fallback_Nullvektor", "erklaerte_devianz_oos": 0.0}, f)
        return  # Beendet die Berechnung der Lücke vorzeitig
    # 3. GLM Schätzung (Poisson)
    family = sm.families.Poisson()
    model = sm.GLM(y, X, family=family)
    res = model.fit()
    
    # Überdispersion prüfen
    dispersion = res.pearson_chi2 / res.df_resid
    variante = "Poisson"
    
    if dispersion > 1.5:
        logging.info(f"Überdispersion erkannt ({dispersion:.2f} > 1.5). Wechsle zu Negativ-Binomial.")
        family = sm.families.NegativeBinomial()
        model = sm.GLM(y, X, family=family)
        res = model.fit()
        variante = "NegativeBinomial"
        dispersion = res.pearson_chi2 / res.df_resid
        
    # 4. Räumliche Kreuzvalidierung (H3 Res 6)
    df_all['h3_res6'] = df_all['h3'].apply(lambda x: h3.cell_to_parent(x, 6))
    gkf = GroupKFold(n_splits=5)
    
    dev_null_cv, dev_model_cv = 0, 0
    X_null = sm.add_constant(X_base)  # Null-Modell hat nur Stadt-Dummies
    
    for train_idx, test_idx in gkf.split(X, y, groups=df_all['h3_res6']):
        # Null-Modell Fold
        m_null = sm.GLM(y[train_idx], X_null.iloc[train_idx], family=family).fit()
        mu_null = m_null.predict(X_null.iloc[test_idx])
        dev_null_cv += family.deviance(y[test_idx], mu_null)
        
        # Full-Modell Fold
        m_full = sm.GLM(y[train_idx], X.iloc[train_idx], family=family).fit()
        mu_full = m_full.predict(X.iloc[test_idx])
        dev_model_cv += family.deviance(y[test_idx], mu_full)
        
    erklaerte_devianz_oos = 1 - (dev_model_cv / dev_null_cv) if dev_null_cv > 0 else 0
    erklaerte_devianz_in = 1 - (res.deviance / model.fit(X_null).deviance)
    
    if erklaerte_devianz_oos < 0.05:
        logging.warning(f"Modellkraft sehr gering! Erklärte Out-of-Sample Devianz: {erklaerte_devianz_oos:.3f}")
        
    for name, coef in res.params.items():
        if coef < 0 and name in X_cols:
            logging.warning(f"Unerwartetes negatives Vorzeichen beim Treiber {name}: {coef:.3f}")
            
    # JSON Output speichern
    modell_info = {
        "koeffizienten": res.params.to_dict(),
        "standardfehler": res.bse.to_dict(),
        "dispersion": float(dispersion),
        "variante": variante,
        "erklaerte_devianz_in": float(erklaerte_devianz_in),
        "erklaerte_devianz_oos": float(erklaerte_devianz_oos)
    }
    with open("data/luecke_modell.json", "w", encoding='utf-8') as f:
        json.dump(modell_info, f, indent=4)
        
    # 5. Anwendung auf die Rasternetzwerke und Glättung
    for stadt in staedte:
        df = dfs[stadt]
        i, j, d = dist_matrices[stadt]
        
        X_stadt_base = pd.DataFrame(0.0, index=np.arange(len(df)), columns=X_base.columns)
        if f'stadt_{stadt}' in X_stadt_base.columns:
            X_stadt_base[f'stadt_{stadt}'] = 1.0
            
        X_stadt = sm.add_constant(pd.concat([df[X_cols], X_stadt_base], axis=1), has_constant='add')
        
        # Vorhersage (Ex-ante Erwartung)
        df['y_erwartet'] = res.predict(X_stadt)
        
        # Beiträge extrahieren (Beta * X)
        for col in X_cols:
            df[f'beitrag_{col.replace("x_", "")}'] = df[col] * res.params[col]
            
        # Residuum und Glättung
        residuum = df['y_erwartet'] - df['y_direkt']
        w_aff = 2 ** (-d / config['h_affinitaet_m'])
        
        df['luecke'] = np.bincount(i, weights=residuum.values[j] * w_aff, minlength=len(df))
        
        # Prozentrang und Konsens auf in_stadt berechnen
        df['pr_luecke'] = 0.0
        mask = df['in_stadt']
        df.loc[mask, 'pr_luecke'] = df.loc[mask, 'luecke'].rank(pct=True) * 100
        
        df['konsens'] = False
        df.loc[mask, 'konsens'] = (df.loc[mask, 'pr_score'] >= 90) & (df.loc[mask, 'pr_luecke'] >= 90)
        
        # Spezifikationsprüfung: Summen
        sum_ist = df.loc[mask, 'y_direkt'].sum()
        sum_soll = df.loc[mask, 'y_erwartet'].sum()
        if not np.isclose(sum_ist, sum_soll, atol=0.1):
            logging.warning(f"Summen-Mismatch in {stadt}: Ist {sum_ist:.1f}, Soll {sum_soll:.1f}")
            
        # Überschreiben der scored.csv
        df.to_csv(f"data/{stadt}_scored.csv", index=False)
        logging.info(f"Angebotslücke für {stadt} erfolgreich integriert.")

if __name__ == "__main__":
    prozessiere_luecke()