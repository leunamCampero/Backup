# Results

Every file here is written by one notebook; re-running the notebook overwrites it with the same content.

| Folder | Written by | Main files |
|---|---|---|
| `lts_networks/<city>/<run>/` | 01 | `<city>_2017_2022_2026_SIMPLIFIED_metrics.csv` (full precision) and `.txt` (readable, used by step 3); `<year>/<city>_lts_<year>_SIMPLE.pkl` = simplified network (`networkx.Graph`, only Grenoble's are in git) |
| `calibration/` | 03 | `city_infrastructure_mode_panel.csv` (input panel), `weight_model_LOYO_CV.csv` (cross-validation of every weight × model), `city_model_parameters.csv` (α, β per city), `historical_fitted_predictions.csv`, `predictions_2026_all_models.csv`, `calibration_summary.txt` |
| `ga_vs_mlcc/` | 04 | `comparison.csv` (baseline / MLCC / GA), `ga_history.csv`, `mlcc_selected_edges.csv`, `ga_selected_edges.csv`, `mlcc_upgrades.csv` (order of the MLCC upgrades) |
| `mlcc_lookup/` | 05 | `grenoble_mlcc_lookup_1000.csv` (1000 budgets → network metrics), `grenoble_lookup_with_mode_share.csv` (+ predicted share), `budget_vs_*.csv`, `mlcc_response_magnitudes.csv` (gain per M€), `surrogate_*.csv` (smooth curves) |
| `order_of_magnitude/` | 06 | `order_of_magnitude_summary.csv` (budget and km for +2.5 / +5 / +10 points, both models), `harmonised_alpha_comparison.csv`, `k_*.csv` (calibrations of the first-order model), `mlcc_upgrade_log.csv` |
| `backcasting/target_35pct/` | 07a | yearly plans and scenarios to reach 35 % in 2050 |
| `backcasting/co2_target/` | 07b | feasibility and cost per scenario, least-cost plan, cost vs CO₂ target |

## Main columns

* `normalized_network_length` (**N**) — cycling km (LTS 1–4) / reference km of the city.
* `weighted_lcc_normalized` (**C**) — weighted largest connected component (see `cyclelts/metrics.py`).
* `lcc_ltsT_km` — length of the largest connected network using only LTS ≤ T edges.
* `share` / `predicted_share` — two-wheeler commuting share as a **fraction** (0–0.5); `*_percent` / `*_pct` columns are in %.
* `budget_allocated_eur` — cumulative money made available; `actual_spent_eur` — money actually used by MLCC
  (it stops at the first street it cannot afford; the rest is carried over).

## Network files (`*.pkl`)

Python pickles of `networkx.Graph` objects. Each edge has `key`/`lts` (1–4, or 5 for car roads in 2026),
`distance` (metres), `geometry` (Shapely line), `facility_type`, and for LTS 5 the flags
`mandatory_upgrade_to_lts1`, `bicycle_prohibited`. Nodes have `x` (longitude) and `y` (latitude).
Load them with `cyclelts.config.load_simplified_graph(city, year)`. Only open pickle files from a source you trust.
