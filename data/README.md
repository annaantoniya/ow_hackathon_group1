# Daten

Erzeugt mit `python datengrundlage.py`. Im Repo liegen nur die Eingaben für `analyse.py`:

| Datei | Inhalt |
| --- | --- |
| `<stadt>_grid.csv` | eine Zeile pro H3-Hexagon (Auflösung 9): Zensus-Merkmale und POI-Zählung |
| `<stadt>_pois.csv` | eine Zeile pro POI aus OpenStreetMap mit Kategorie |

Die Ergebnisse (`*_scored.csv`, `*_portfolio.csv`, `*.json`) entstehen mit `python analyse.py` und werden nicht versioniert.

## Quellen und Lizenzen

- **Zensus 2022:** © Statistisches Bundesamt (Destatis), Zensus 2022, Gitterdaten im 100-m-Raster.
  Lizenz: [Datenlizenz Deutschland – Namensnennung – Version 2.0](https://www.govdata.de/dl-de/by-2-0).
  Die Werte wurden auf H3-Hexagone umgerechnet.
- **OpenStreetMap:** © OpenStreetMap-Mitwirkende, abgefragt über die Overpass API.
  Lizenz: [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
  Die POI-Daten in diesem Ordner stehen als abgeleitete Datenbank ebenfalls unter ODbL 1.0.
