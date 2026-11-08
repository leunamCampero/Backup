# Input data

| Path | In git? | What it is |
|---|---|---|
| `city_polygons.geojson` | yes (0.5 MB) | Official boundary of the 11 studied communes (+ Nancy), extracted from the OpenStreetMap French communes file below. Used by notebook 01. |
| `insee_modal_shares/` | yes | Commuting mode shares 2006–2022 per city, produced by notebook 02. Columns: `Year, CODGEO, Commune, Pas de déplacement, Marche, Deux-roues total, Vélo, Deux-roues motorisé, Voiture, TC` (percent of employed residents). |
| `insee_raw/NAV2A_<year>/` | **no** (~600 MB) | Raw INSEE census tables, needed only to *rebuild* `insee_modal_shares/`. |

## The 11 cities

| City | INSEE code | | City | INSEE code |
|---|---|---|---|---|
| Angers | 49007 | | Nantes | 44109 |
| Annecy | 74010 | | Paris | 75056 |
| Bordeaux | 33063 | | Rennes | 35238 |
| Chambéry | 73065 | | Strasbourg | 67482 |
| Grenoble | 38185 | | Tours | 37261 |
| Lyon | 69123 | | *(Nancy, 54395 — INSEE only)* | |

## Getting the raw INSEE tables (optional)

Notebook 02 reads the census table **NAV2A** — *employed population aged 15 or more by sex, place of work and
main mode of transport to work* — published by INSEE (https://www.insee.fr) for each census year in the
"tableaux détaillés" of the population census (*Recensement de la population*, theme *Déplacements domicile-travail*).

1. Download the commune-level NAV2A file of each year 2006–2022 (`BTX_TD_NAV2A_<year>.xls` up to 2016,
   `BTX_TD_NAV2A_<year>.xlsx` / `TD_NAV2A_<year>.xlsx` from 2017).
2. Put each file in its own folder: `data/insee_raw/NAV2A_2006/BTX_TD_NAV2A_2006.xls`, …,
   `data/insee_raw/NAV2A_2022/TD_NAV2A_2022.xlsx`.

The reader looks for the sheet `COM` and the header row containing `CODGEO`, and handles both the 2006–2016 and
the 2017–2022 transport classifications (see `cyclelts/insee.py`).

## Adding a city that is not in the study

`city_polygons.geojson` only contains the studied communes. For any other French commune, download the
OpenStreetMap export of French communes (*Découpage administratif communal français issu d'OpenStreetMap*,
edition of 1 January 2022, file `communes-20220101.json`, on https://www.data.gouv.fr) and pass it to
`config.load_city_polygon("Name", communes_file="path/to/communes-20220101.json")`.
