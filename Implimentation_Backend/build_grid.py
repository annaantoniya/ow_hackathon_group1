import os
import glob
import numpy as np
import pandas as pd
import h3
import pyproj
import shapefile
from shapely.geometry import shape, Point, box
from shapely.ops import transform
from sklearn.cluster import DBSCAN
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Definition des topologischen Raumes
STAEDTE = {
    "muenchen": {"ags": "09162", "bbox": (48.048, 11.341, 48.262, 11.743)},
    "frankfurt": {"ags": "06412", "bbox": (50.002, 8.452, 50.240, 8.822)},
    "berlin": {"ags": "11000", "bbox": (52.325, 13.066, 52.689, 13.782)}
}

RES = 9
PUFFER_M = 1500

def get_city_polygon(ags):
    """
    Liest das amtliche Shapefile (VG250) und extrahiert die Landfläche (GF=4) 
    der Stadt. Projiziert das EPSG:25832 Polygon nach WGS84.
    """
    shp_path = glob.glob("zensus/**/VG250_KRS.shp", recursive=True)
    if not shp_path:
        raise FileNotFoundError("Shapefile VG250_KRS.shp nicht im Ordner zensus/ gefunden.")
        
    sf = shapefile.Reader(shp_path[0])
    records = sf.records()
    shapes = sf.shapes()
    
    # Filtern nach Amtlichem Gemeindeschlüssel (AGS) und Landfläche (GF == 4)
    target_idx = [i for i, r in enumerate(records) if r['AGS'] == ags and r['GF'] == 4]
    if not target_idx:
        raise ValueError(f"Geometrie für AGS {ags} nicht gefunden.")
        
    poly_25832 = shape(shapes[target_idx[0]])
    
    # Koordinatentransformation
    project = pyproj.Transformer.from_crs("epsg:25832", "epsg:4326", always_xy=True).transform
    import shapely
    poly_wgs84 = shapely.transform(
        poly_25832, 
        lambda coords: np.column_stack(project(coords[:, 0], coords[:, 1]))
    )
    return poly_wgs84

def build_base_grid(stadt, config):
    """
    Erzeugt das fundamentale Hexagon-Raster aus der Bounding-Box inklusive 1.500m Puffer.
    Bestimmt deterministisch für jede Zelle das Prädikat 'in_stadt'.
    """
    bbox = config['bbox']
    poly_wgs84 = get_city_polygon(config['ags'])
    
    # Puffer in Grad approximieren (1.500m -> ~0.0135 Grad)
    d_deg = PUFFER_M / 111320.0
    padded_box = box(bbox[1]-d_deg, bbox[0]-d_deg, bbox[3]+d_deg, bbox[2]+d_deg)
    
    # H3 v4 API: Polyfill über strikte GeoJSON-Struktur
    geojson_geom = {
        "type": "Polygon",
        "coordinates": [[[lon, lat] for lon, lat in padded_box.exterior.coords]]
    }
    hexagons = h3.geo_to_cells(geojson_geom, RES)
    
    grid = []
    for h in hexagons:
        lat, lon = h3.cell_to_latlng(h)
        # Topologischer Einschluss-Test für die Stadtgrenze (ohne Puffer)
        in_stadt = poly_wgs84.contains(Point(lon, lat))
        grid.append({'h3': h, 'lat': lat, 'lon': lon, 'stadt': stadt, 'in_stadt': in_stadt})
        
    return pd.DataFrame(grid)

def process_zensus_file(filepath, hex_set, agg_dict, col_mapping=None, sep=';', decimal='.', na_values=None):
    """
    Iteriert in 500k-Blöcken durch Zensus-Gitterdaten.
    Transformiert EPSG:3035 -> WGS84, filtert O(1) gegen das H3-Set und aggregiert.
    """
    transformer = pyproj.Transformer.from_crs("epsg:3035", "epsg:4326", always_xy=True)
    chunks = []
    
    usecols = ['x_mp_100m', 'y_mp_100m'] + list(agg_dict.keys())
    
    for chunk in pd.read_csv(filepath, sep=sep, chunksize=500000, usecols=usecols, 
                             decimal=decimal, na_values=na_values, encoding='utf-8-sig'):
        
        lon, lat = transformer.transform(chunk['x_mp_100m'].values, chunk['y_mp_100m'].values)
        
        # Vektorisierte H3 Abbildung
        chunk['h3'] = [h3.latlng_to_cell(y, x, RES) for y, x in zip(lat, lon)]
        
        # Filtern auf die definierten Rasterzellen des Gebietes
        chunk = chunk[chunk['h3'].isin(hex_set)]
        
        if col_mapping:
            chunk = chunk.rename(columns=col_mapping)
            
        chunks.append(chunk)
        
    df_all = pd.concat(chunks)
    # Aggregation der 100m Zensus-Punkte auf das gröbere H3-Raster
    return df_all.groupby('h3').agg({(col_mapping[k] if col_mapping else k): v for k, v in agg_dict.items()}).reset_index()

def integrate_zensus(df_grid):
    """
    Führt die vier Zensus-Archive über das H3-Raster zusammen und berechnet 
    die demografischen Faktoren.
    """
    hex_set = set(df_grid['h3'])
    
    # 1. Einwohner
    f_einw = glob.glob("zensus/**/*Bevoelkerungszahl_100m-Gitter.csv", recursive=True)[0]
    df_einw = process_zensus_file(f_einw, hex_set, {'Einwohner': 'sum'}, {'Einwohner': 'einwohner'}, na_values=['-', '–'])
    
    # 2. Miete
    f_miete = glob.glob("zensus/**/*Nettokaltmiete_Anzahl_der_Wohnungen_100m-Gitter.csv", recursive=True)[0]
    df_miete = process_zensus_file(f_miete, hex_set, {'durchschnMieteQM': 'mean', 'AnzahlWohnungen': 'sum'}, 
                                   {'durchschnMieteQM': 'miete_qm', 'AnzahlWohnungen': 'mietwohnungen'}, 
                                   decimal=',', na_values=['-', '–'])
    
    # 3. Alter
    f_alter = glob.glob("zensus/**/*Alter_in_10er-Jahresgruppen_100m-Gitter.csv", recursive=True)[0]
    age_cols = {'Insgesamt_Bevoelkerung': 'sum', 'a20bis29': 'sum', 'a30bis39': 'sum', 'a40bis49': 'sum'}
    df_alter = process_zensus_file(f_alter, hex_set, age_cols, na_values=['-', '–'])
    
    # 4. Haushalte
    f_hh = glob.glob("zensus/**/*Groesse_des_privaten_Haushalts_100m-Gitter.csv", recursive=True)[0]
    hh_cols = {'Insgesamt_Haushalte': 'sum', '1_Person': 'sum', '2_Personen': 'sum'}
    df_hh = process_zensus_file(f_hh, hex_set, hh_cols, na_values=['-', '–'])
    
    # Joins auf das H3-Fundament
    for df_sub in [df_einw, df_miete, df_alter, df_hh]:
        df_grid = pd.merge(df_grid, df_sub, on='h3', how='left')
        
    df_grid['einwohner'] = df_grid['einwohner'].fillna(0)
    
    # Demografische Verhältnisse (Division durch Null abfangen)
    alter_ziel = df_grid[['a20bis29', 'a30bis39', 'a40bis49']].sum(axis=1)
    alter_basis = df_grid['Insgesamt_Bevoelkerung']
    df_grid['anteil_20_49'] = np.where(alter_basis > 0, alter_ziel / alter_basis, np.nan)
    
    hh_ziel = df_grid[['1_Person', '2_Personen']].sum(axis=1)
    df_grid['anteil_hh_1_2'] = np.where(df_grid['Insgesamt_Haushalte'] > 0, hh_ziel / df_grid['Insgesamt_Haushalte'], np.nan)
    df_grid['haushalte'] = df_grid['Insgesamt_Haushalte'].fillna(0)
    
    return df_grid

def impute_missing_values(df):
    """
    Imputiert Lücken in den Zensusdaten gemäß Spezifikation (Abschnitt 4.1).
    - Miete: Gewichteter Mittelwert der Nachbarn aus h3.grid_disk(..., 2)
    - Alter/Haushalte: Substitution durch städtischen Durchschnitt bei < 50% Abdeckung
    """
    df['miete_geschaetzt'] = False
    df['alter_geschaetzt'] = False
    
    # Miete Imputation via topologische Nachbarschaft
    miete_dict = df.set_index('h3')['miete_qm'].to_dict()
    wohn_dict = df.set_index('h3')['mietwohnungen'].to_dict()
    
    def get_ring_mean(h3_id):
        if pd.notna(miete_dict.get(h3_id)):
            return miete_dict[h3_id], False
            
        neighbors = h3.grid_disk(h3_id, 2)
        sum_w_m, sum_w = 0, 0
        for n in neighbors:
            if n != h3_id and n in miete_dict and pd.notna(miete_dict[n]) and pd.notna(wohn_dict.get(n)):
                sum_w_m += miete_dict[n] * wohn_dict[n]
                sum_w += wohn_dict[n]
                
        if sum_w > 0:
            return sum_w_m / sum_w, True
        return np.nan, True

    res = df['h3'].apply(get_ring_mean)
    df['miete_qm'] = [r[0] for r in res]
    df['miete_geschaetzt'] = [r[1] for r in res]
    
    # Alter Imputation (Stadtdurchschnitt, wenn Anteil berechnet auf < 50% der Einwohner basiert)
    abdeckung_alter = df['Insgesamt_Bevoelkerung'] / df['einwohner'].replace(0, np.nan)
    mean_alter = df.loc[df['in_stadt'], 'anteil_20_49'].mean()
    
    mask_alter = (abdeckung_alter < 0.5) | df['anteil_20_49'].isna()
    # Nur für bewohnte Zellen anwenden
    mask_bewohnt = df['einwohner'] > 0
    df.loc[mask_alter & mask_bewohnt, 'anteil_20_49'] = mean_alter
    df.loc[mask_alter & mask_bewohnt, 'alter_geschaetzt'] = True
    
    # Haushalte Imputation
    abdeckung_hh = df['Insgesamt_Haushalte'] / df['haushalte'].replace(0, np.nan)
    mean_hh = df.loc[df['in_stadt'], 'anteil_hh_1_2'].mean()
    df.loc[(abdeckung_hh < 0.5) | df['anteil_hh_1_2'].isna(), 'anteil_hh_1_2'] = mean_hh

    return df

def deduplicate_and_map_pois(stadt, hex_set):
    """
    Liest POIs, dedupliziert diese mittels DBSCAN (Cluster < 20m) 
    strikt pro Kategorie und aggregiert sie auf die H3-Zellen.
    """
    poi_file = f"data/{stadt}_pois.csv"
    if not os.path.exists(poi_file):
        raise FileNotFoundError(f"POI Datei {poi_file} fehlt. Bitte fetch_osm.py ausführen.")
        
    df_pois = pd.read_csv(poi_file)
    
    # 20m Suchradius in Bogenmaß für Haversine Metrik
    eps_rad = 20.0 / 6371000.0
    
    deduped_pois = []
    for kategorie, group in df_pois.groupby('kategorie'):
        if len(group) > 1:
            coords = np.deg2rad(group[['lat', 'lon']].values)
            clustering = DBSCAN(eps=eps_rad, min_samples=1, metric='haversine').fit(coords)
            group = group.copy()
            group['cluster'] = clustering.labels_
            # Pro Cluster nur den ersten POI behalten
            group = group.drop_duplicates(subset=['cluster'])
        deduped_pois.append(group)
        
    df_pois_clean = pd.concat(deduped_pois)
    
    # Abbildung der bereinigten POIs auf H3-Zellen
    df_pois_clean['h3'] = [h3.latlng_to_cell(lat, lon, RES) for lat, lon in zip(df_pois_clean['lat'], df_pois_clean['lon'])]
    
    # Zählung pro Kategorie und Hexagon
    poi_counts = df_pois_clean.groupby(['h3', 'kategorie']).size().unstack(fill_value=0)
    poi_counts.columns = [f"poi_{c}" for c in poi_counts.columns]
    
    # Filter auf gültige Zellen des definierten Rasters
    poi_counts = poi_counts[poi_counts.index.isin(hex_set)]
    
    return poi_counts.reset_index()

def main():
    logging.info("Starte H3-Raster Konstruktion...")
    
    for stadt, config in STAEDTE.items():
        logging.info(f"Prozessiere räumliches Gitter für {stadt}...")
        
        # 1. Fundamentalgeometrie anlegen
        df_grid = build_base_grid(stadt, config)
        
        # 2. Zensus-Vektoren integrieren
        df_grid = integrate_zensus(df_grid)
        df_grid = impute_missing_values(df_grid)
        
        # 3. POIs bereinigen und mappen
        df_pois_agg = deduplicate_and_map_pois(stadt, set(df_grid['h3']))
        df_grid = pd.merge(df_grid, df_pois_agg, on='h3', how='left').fillna(0)
        
        # Aufräumen nicht spezifizierter Temporär-Spalten
        keep_cols = ['h3', 'lat', 'lon', 'stadt', 'in_stadt', 'einwohner', 'miete_qm', 
                     'mietwohnungen', 'miete_geschaetzt', 'anteil_20_49', 'alter_geschaetzt', 
                     'haushalte', 'anteil_hh_1_2'] + [c for c in df_grid.columns if c.startswith('poi_')]
        
        df_grid = df_grid[keep_cols]
        
        output_path = f"data/{stadt}_grid.csv"
        df_grid.to_csv(output_path, index=False)
        logging.info(f"Abgeschlossen: {len(df_grid)} Hexagone für {stadt} in {output_path} geschrieben.")

if __name__ == "__main__":
    main()