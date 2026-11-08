# Cycling networks, traffic stress and bike mode share in French cities

Does a **more comfortable and better connected cycling network** go together with **more people cycling to work**?
And if a city has a limited budget, **which streets should it improve first**?

This repository answers these questions for **11 French cities** (Angers, Annecy, Bordeaux, Chambéry, Grenoble,
Lyon, Nantes, Paris, Rennes, Strasbourg, Tours) with open data only:

* the street network comes from **OpenStreetMap**, including its history (the map as it was each year since 2017);
* commuting habits come from the French census (**INSEE**, 2006–2022).

Every street segment receives a **Level of Traffic Stress (LTS)** — from LTS 1, *comfortable for a child*, to LTS 4,
*only for confident cyclists*. The yearly networks are summarised by two numbers (size and low-stress connectivity),
linked to the observed share of two-wheeler commuters with a statistical model, and the model is then used to plan
investments in **Grenoble** up to 2050.

## The study in 7 steps

```
 OpenStreetMap ──► 1. LTS networks 2017-2026 ──► infrastructure metrics (N, C) ─┐
                                                                                ├─► 3. model: metrics → bike share
 INSEE census ───► 2. commuting mode shares 2006-2022 ──────────────────────────┘          │
                                                                                           ▼
            4. where to invest: MLCC heuristic vs genetic algorithm (Grenoble, one budget)
            5. lookup table: budget → network → predicted share (1000 budgets)
            6. order of magnitude vs a simple "km of cycle lanes" model
            7. backcasting 2026 → 2050: cheapest investment plan for a share or CO₂ target
```

| # | Notebook | Question | Run time* |
|---|---|---|---|
| 1 | [`01_build_lts_networks`](notebooks/01_build_lts_networks.ipynb) | How did each city's cycling network and its stress level evolve, 2017–2026? | 30 s (Grenoble, cached) · 10–60 min per city if downloaded |
| 2 | [`02_insee_mode_shares`](notebooks/02_insee_mode_shares.ipynb) | What share of workers commute by bike, car, transit, foot? | 7 min (or instant from the saved CSVs) |
| 3 | [`03_infrastructure_vs_bike_share`](notebooks/03_infrastructure_vs_bike_share.ipynb) | Do better networks go with more cycling? What does it predict for 2026? | 20 s |
| 4 | [`04_mlcc_vs_genetic_algorithm`](notebooks/04_mlcc_vs_genetic_algorithm.ipynb) | With a given budget, which streets to upgrade? Greedy heuristic vs genetic algorithm | 13 min |
| 5 | [`05_mlcc_lookup_table`](notebooks/05_mlcc_lookup_table.ipynb) | For every budget from 0 to 39 M€: what network, what predicted share? | 40 s (5 min to rebuild) |
| 6 | [`06_order_of_magnitude_vs_first_order_model`](notebooks/06_order_of_magnitude_vs_first_order_model.ipynb) | Is the predicted effect of the same order of magnitude as a classic "km of lanes" model? | 10 s (5 min first time) |
| 7a | [`07a_backcasting_2050_target_35pct`](notebooks/07a_backcasting_2050_target_35pct.ipynb) | Cheapest yearly plan to reach a 35 % bike share in 2050 | seconds |
| 7b | [`07b_backcasting_2050_co2_target`](notebooks/07b_backcasting_2050_co2_target.ipynb) | Cheapest yearly plan to cut cumulative car CO₂ by 10 % over 2027–2050 | 1 min |

\*on a standard laptop. Each notebook starts with a short explanation of its question, inputs and outputs.

## Main results

* **Calibration (step 3).** With one intercept per city and a common slope, the infrastructure index
  `I = 0.40·N + 0.60·C` explains the yearly two-wheeler share of the 11 cities with a cross-validated error of
  **1.05 percentage points** (66 city-years, 2017–2022). Grenoble's 2026 network predicts **22.8 %**
  (observed in 2022: 23.5 % two-wheelers, of which 22.7 % bicycles).
* **Where to invest (step 4).** With 25 % of the full upgrade cost (12.4 M€), the greedy **MLCC** plan
  (connect the low-stress islands, then grow outward) raises Grenoble's predicted share from 22.8 % to **34.8 %**;
  a genetic algorithm seeded with it finds no better plan in 30 generations.
* **Budget → share (step 5).** The first million euros brings about **+3.6 points per M€**, falling to about
  **+1 point per M€** over 10 M€ — connecting existing islands is by far the most effective spending.
* **Order of magnitude (step 6).** To gain +5 points, the LTS/MLCC model needs ~**3 M€**, while a first-order
  "km of piste + bande" model calibrated on Paris/Grenoble needs **32–40 M€**. The gap shrinks to a factor of
  2–4 once only the lane-attributable part of the growth is kept (harmonised comparison): the network model credits
  connectivity with effects the simpler model attributes to other factors.
* **Backcasting (step 7).** Reaching a **35 %** predicted share in 2050 needs about **16.4 M€** of cumulative
  investment (with at most 2 M€ per year). Cutting cumulative car CO₂ 2027–2050 by **10 %** through cycling
  infrastructure alone is only feasible in the optimistic car-substitution scenario (≈ 9.4 M€); in the
  intermediate scenario the maximum achievable cut is 9.3 %.

All numbers are **model predictions** (an association across cities and years, not a causal estimate) — see
*Limitations* below.

## Quick start

```bash
git clone https://github.com/leunamCampero/Backup.git
cd Backup
conda env create -f environment.yml      # creates the "cyclelts" environment (Python 3.11, OSMnx, …)
conda activate cyclelts
python -m ipykernel install --user --name cyclelts
jupyter lab notebooks/                    # or open the folder in VS Code
```

Run the notebooks in order. **Steps 3–7 run immediately**: the repository ships the simplified Grenoble networks,
the metrics of all 11 cities and the INSEE mode shares. To rebuild another city's networks, set
`CITIES_TO_BUILD` in notebook 01 (needs internet; public Overpass servers can be slow — re-run the cell to resume).

The code can also be used directly:

```python
from cyclelts.config import grenoble_graph
from cyclelts.mode_share import GRENOBLE_MODEL

G = grenoble_graph(2026)                  # simplified Grenoble network (networkx Graph)
GRENOBLE_MODEL.share_of_graph(G)          # -> 22.82 (% predicted two-wheeler share)
```

## Repository layout

```
cyclelts/                 Python package with all the code (documented module by module)
  config.py               folders, list of cities, loading helpers
  overpass.py             robust OpenStreetMap downloads (retries, mirrors, historical dates)
  lts.py                  Level of Traffic Stress classifier (OSM tags → LTS)
  network.py              build the yearly network of a city (step 1)
  simplify.py             network simplification that keeps lengths and LTS
  metrics.py              network length and largest-connected-component metrics
  insee.py                INSEE census tables → mode shares (step 2)
  mode_share.py           capped-logit model infrastructure → bike share (step 3)
  optimization.py         MLCC heuristic, genetic algorithm, lookup table (steps 4-6)
  plotting.py             interactive Plotly maps
notebooks/                the 7 steps, to run in order
data/                     inputs (see data/README.md for the large raw files)
results/                  every output, one folder per step (see results/README.md)
docs/                     methodology notes and references
extras/dos_category/      side study: "Degree of Separation" classification of the Grenoble network
```

## Key concepts

| Term | Meaning |
|---|---|
| **LTS** (Level of Traffic Stress) | 1 = comfortable for almost everybody (separated tracks, car-free paths, very calm streets) · 2 = most adults (painted lanes on 50 km/h streets, 30 km/h streets) · 3 = confident cyclists · 4 = only the "strong and fearless". Computed from OSM tags: facility type, speed limit, lanes. See [`docs/methodology.md`](docs/methodology.md). |
| **LTS 5** | Planning layer (2026 only): car roads with no cycling facility, candidates for an upgrade. Never counted as cycling network. |
| **N** — normalized network length | km of LTS 1–4 network / largest yearly km of that city. |
| **LCC** — largest connected component | the longest piece of network you can ride without exceeding a given LTS. |
| **C** — weighted LCC | LCC at LTS ≤ 1, 2, 3, 4 combined with weights 0.64 / 0.24 / 0.09 / 0.03, divided by the reference length. |
| **MLCC** | *Maximise the Largest Connected Component*: greedy plan that first links LTS 1 islands by shortest paths, then grows the LTS 1 network outward. |
| **GA** | Genetic algorithm: evolves a population of investment plans to maximise the predicted share. |
| **Backcasting** | Start from a target (e.g. 35 % in 2050) and find the cheapest path of yearly investments that reaches it. |

## Reproducibility

* Every number in `results/` was regenerated with the notebooks of this repository; re-running them reproduces
  the files exactly (checked when the repository was organised).
* OpenStreetMap downloads are cached on disk (`osm_http_cache/`, not in git). A *fresh* download can differ
  slightly from the published networks because OSM's history is edited over time; the run folder name
  (`fresh_2026-10-21`) records when the published networks were built.
* Not stored in git (size): raw INSEE tables (~600 MB, see [`data/README.md`](data/README.md)), the networks of the
  10 cities other than Grenoble (~1.5 GB, rebuilt by notebook 01), intermediate graphs and download caches.

## Limitations

* The LTS is an **approximation from OSM tags**: OSM rarely records traffic volumes, parking, buffer widths or
  intersection design; when information is missing the more stressful value is used.
* The dependent variable is INSEE **"two-wheelers"** (bicycles + motorbikes) to have a consistent series since 2006;
  the bicycle-only share exists only from 2017.
* The model is an **association** across 11 cities × 6 years with a 50 % ceiling assumed, not a causal effect;
  2026 and later values are extrapolations.
* Upgrade costs (€/m) are scenario values, not engineering estimates for specific streets.

## Extras

[`extras/dos_category/`](extras/dos_category/README.md) classifies the same Grenoble networks by **Degree of
Separation** (Geovélo rules for French cycling facilities, `sql/*.sql`) instead of LTS. It is a side study and is
not used by steps 1–7.
