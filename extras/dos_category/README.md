# Side study · Degree of Separation (DoS) of the Grenoble cycling network

Instead of a Level of Traffic Stress, each cycling way is classified by its **Degree of Separation** from motor
traffic, using the **Geovélo** query set for French cycling facilities (`sql/*.sql`, described in French in
[`sql/README.md`](sql/README.md)): *pistes cyclables, bandes cyclables, voies vertes, zones 30, vélorues…*

| Geovélo group | a_High | b_Medium_High | c_Medium | d_Medium_Low | e_Low | f_Null_or_Others |
|---|---|---|---|---|---|---|
| **DoS** | **6** (completely separated) | 5 | 4 | 3 | 2 | **1** |

The mapping is `sql/<query>.sql` → `tagsmapping.csv` (query → category) → `tags_mapping_final.csv`
(category → group). A way matched by several queries takes the highest DoS. In 2026, car roads missing from the
bike network get DoS 0 (the analogue of LTS 5).

The `WHERE` clauses of the SQL files are run unchanged on an in-memory SQLite table that mimics the PostGIS
`planet_osm_line` table, so no database is needed (`dos_network.py`).

| File | What it does |
|---|---|
| `Grenoble_DoS_2017_2022_2026.ipynb` | DoS networks 2017–2022 + 2026, reusing the OSM downloads of the LTS study (same snapshots) |
| `Grenoble_LTS_DoS_from_scratch.ipynb` | fresh download, then LTS **and** DoS from the same data |
| `dos_network.py` | DoS classification, simplification and plots |
| `Grenoble_study.ipynb` | original PostGIS version — kept locally only, not published (it contains local database settings) |
| `run.py`, `name_format.py`, `sql_template.sql`, `bicycle.style` | tools of the original PostGIS workflow (osm2pgsql style, SQL templating) |
| `dos_output/grenoble/<run>/` | lengths per DoS category (CSV) and maps (PNG, HTML); network pickles are not in git |
| `osm_snapshots/grenoble_<run>.tar.xz` | the Overpass answers of the two published runs (1.3 MB each), unpacked automatically so both notebooks rebuild them without internet |

Requires the `cyclelts` package of this repository (the notebooks find it automatically) and `matplotlib`.
