import os
import time
import json
import requests
import zipfile
import io
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

STAEDTE = {
    "muenchen": (48.048, 11.341, 48.262, 11.743),
    "frankfurt": (50.002, 8.452, 50.240, 8.822),
    "berlin": (52.325, 13.066, 52.689, 13.782)
}

ZENSUS_URLS = [
    "https://www.destatis.de/static/DE/zensus/gitterdaten/Zensus2022_Bevoelkerungszahl.zip",
    "https://www.destatis.de/static/DE/zensus/gitterdaten/Durchschnittliche_Nettokaltmiete_und_Anzahl_der_Wohnungen.zip",
    "https://www.destatis.de/static/DE/zensus/gitterdaten/Alter_in_10er-Jahresgruppen.zip",
    "https://www.destatis.de/static/DE/zensus/gitterdaten/Zensus2022_Groesse_des_privaten_Haushalts_in_Gitterzellen.zip",
    "https://www.destatis.de/static/DE/zensus/gitterdaten/Shapefile_Zensus2022.zip"
]

# Bijektive Abbildung von OSM-Tags auf die exakten Modell-Kategorien der Spezifikation
TAG_MAPPING = {
    "shop=deli": ("wettbewerb_direkt", "deli"),
    "shop=cheese": ("wettbewerb_direkt", "feinkost_kaese"),
    "shop=wine": ("wettbewerb_direkt", "wein"),
    "shop=organic": ("wettbewerb_direkt", "bio_markt"),
    "shop=health_food": ("wettbewerb_direkt", "reformhaus"),
    "amenity=marketplace": ("wettbewerb_direkt", "markthalle"),
    "shop=pasta": ("wettbewerb_direkt", "pasta"),
    "shop=supermarket": ("wettbewerb_breit", "supermarkt"),
    "shop=greengrocer": ("wettbewerb_breit", "obst_gemuese"),
    "shop=butcher": ("wettbewerb_breit", "metzger"),
    "shop=bakery": ("wettbewerb_breit", "baecker"),
    "shop=seafood": ("wettbewerb_breit", "fisch"),
    "amenity=cafe": ("affinitaet", "cafe"),
    "amenity=restaurant": ("affinitaet", "restaurant"),
    "amenity=bar": ("affinitaet", "bar"),
    "shop=books": ("affinitaet", "buchhandlung"),
    "shop=interior_decoration": ("affinitaet", "interior"),
    "shop=boutique": ("affinitaet", "boutique"),
    "shop=florist": ("affinitaet", "blumen"),
    "leisure=fitness_centre": ("affinitaet", "fitness_yoga"),
    "amenity=arts_centre": ("affinitaet", "kultur"),
    "tourism=museum": ("affinitaet", "galerie_museum"),
    "amenity=coworking_space": ("affinitaet", "coworking"),
    "shop=bicycle": ("affinitaet", "fahrradladen"),
    "railway=station": ("frequenz", "bahnhof"),
    "railway=tram_stop": ("frequenz", "tram_ubahn"),
    "highway=bus_stop": ("frequenz", "bus"),
    "office=*": ("frequenz", "buero"),
    "amenity=university": ("frequenz", "hochschule")
}

def setup_directories():
    for folder in ["zensus", "cache", "data"]:
        os.makedirs(folder, exist_ok=True)
        logging.info(f"Topologie initialisiert: {folder}/")

def download_zensus_data():
    logging.info("Initiiere deterministischen Datentransfer der Zensus-Archive...")
    for url in ZENSUS_URLS:
        filename = url.split("/")[-1]
        logging.info(f"Extrahiere Vektorraum: {filename}")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            z.extractall("zensus/")

def build_overpass_query(bbox, group_name):
    query_body = ""
    for tag, (gruppe, _) in TAG_MAPPING.items():
        if gruppe == group_name:
            key, value = tag.split("=")
            if value == "*":
                query_body += f'nwr["{key}"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});\n'
            else:
                query_body += f'nwr["{key}"="{value}"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});\n'
    return f"[out:json][timeout:90];\n(\n{query_body});\nout center;"

def fetch_osm_data():
    overpass_url = "http://overpass-api.de/api/interpreter"
    gruppen = set(g for g, c in TAG_MAPPING.values())
    
    for stadt, bbox in STAEDTE.items():
        logging.info(f"Konstruiere OSM-Netzwerkgraph für: {stadt}")
        poi_records = []
        
        for gruppe in gruppen:
            logging.info(f" -> Lade Dimension: {gruppe}")
            query = build_overpass_query(bbox, gruppe)
            
            try:
                headers = {'User-Agent': 'WhiteSpotsApp/1.0 (Hackathon Project Group 1)'}
                response = requests.post(overpass_url, data={'data': query}, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                with open(f"cache/{stadt}_{gruppe}.json", 'w', encoding='utf-8') as f:
                    json.dump(data, f)
                    
                for element in data.get('elements', []):
                    lat = element.get('lat', element.get('center', {}).get('lat'))
                    lon = element.get('lon', element.get('center', {}).get('lon'))
                    tags_dict = element.get('tags', {})
                    
                    if not (lat and lon):
                        continue
                        
                    # Isoliere die exakte Kategorieklasse
                    kategorie_val = None
                    for tag_key, tag_val in tags_dict.items():
                        # Exakte Zuweisung prüfen
                        test_tag = f"{tag_key}={tag_val}"
                        if test_tag in TAG_MAPPING and TAG_MAPPING[test_tag][0] == gruppe:
                            kategorie_val = TAG_MAPPING[test_tag][1]
                            break
                        # Wildcard Zuweisung prüfen (z.B. office=*)
                        test_wildcard = f"{tag_key}=*"
                        if test_wildcard in TAG_MAPPING and TAG_MAPPING[test_wildcard][0] == gruppe:
                            kategorie_val = TAG_MAPPING[test_wildcard][1]
                            break
                            
                    if kategorie_val:
                        poi_records.append({
                            'osm_id': element['id'],
                            'lat': lat,
                            'lon': lon,
                            'gruppe': gruppe,
                            'kategorie': kategorie_val,
                            'name': tags_dict.get('name', ''),
                            'brand': tags_dict.get('brand', ''),
                            'cuisine': tags_dict.get('cuisine', ''),
                            'organic': tags_dict.get('organic', '')
                        })
                        
            except Exception as e:
                logging.error(f"Topologischer Fehler bei {stadt}/{gruppe}: {e}")
                
            time.sleep(20) # Strikte Einhaltung der API-Ratengrenzen
            
        df_pois = pd.DataFrame(poi_records)
        df_pois.to_csv(f"data/{stadt}_pois.csv", index=False)
        logging.info(f"Lokaler Zustandsvektor für {stadt} geschlossen.")

if __name__ == "__main__":
    setup_directories()
    download_zensus_data()
    fetch_osm_data()
    logging.info("Phase 1: Ingestion erfolgreich beendet.")