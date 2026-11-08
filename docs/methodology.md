# Methodology

This page summarises the method of each step. The code is in `cyclelts/`; each module's docstring repeats the
relevant part in more detail.

## 1. LTS networks (`cyclelts/lts.py`, `network.py`, `simplify.py`)

**Data.** For each city the OSMnx `bike` network inside the official commune boundary is downloaded from the
Overpass API. Historical years use Overpass "attic" queries (`[date:"YYYY-12-31T23:59:59Z"]`), so 2017–2022 are
the map as it was on 31 December of each year; 2026 is the current map. Steps (stairs) are removed.

**Facility type.** Each edge is assigned one facility type from its tags, in this order of priority:
steps · bicycle street (`cyclestreet`, `bicycle_road`) · shared street (`living_street`) · independent path ·
separated bike lane (`cycleway=track`) · dedicated cycleway / sidepath · segregated or non-segregated shared-use
path · pedestrian zone with bicycle access · painted bike lane · bikeable shoulder · shared-lane marking ·
shared bus lane · mixed traffic.

**Speed and lanes.** Highest tagged `maxspeed` (French codes such as `FR:zone30` are understood), else a default
per road class (e.g. residential 30 km/h, primary 50 km/h); `lanes` tag, else a default per class.

**Raw LTS score.**

| Facility | Rule |
|---|---|
| independent path | 0 |
| bicycle street, shared street, dedicated cycleway, segregated path | 1 |
| separated lane / sidepath | 1 if speed ≤ 60 and lanes ≤ 5, else 2 |
| shared-use path | 2 |
| pedestrian zone | 1 if speed ≤ 20, else 2 |
| painted lane | ≤ 50 km/h: 2 (≤ 3 lanes), 2.5 (≤ 5), 3 · ≤ 60: 3 · < 70: 4 · else 5 |
| shoulder | as painted lane, but 3–4 between 60 and 70 km/h and 4 above |
| shared-lane marking | max(2, mixed traffic) |
| shared bus lane | 2.5 (≤ 30 km/h, ≤ 2 lanes) · 3 (≤ 50, ≤ 3) · 4 |
| mixed traffic | 1 (≤ 20 km/h, ≤ 2 lanes) · 2 (≤ 30, ≤ 2) · 2.5 (≤ 40, ≤ 3) · 3 (≤ 50, ≤ 3) · 4 (≤ 70) · 5 |

The raw score is mapped to the four levels used everywhere: 0–1 → **LTS 1**, 2 → **LTS 2**, 2.5–3 → **LTS 3**,
4–5 → **LTS 4**. Only the largest weakly connected component is kept.

**LTS 5 (2026).** The OSMnx `drive` network is downloaded too; car edges whose OSM ways are not in the bike
network are added with LTS 5. They are flagged `bicycle_prohibited` (motorway, trunk, `bicycle=no/private`) or
`mandatory_upgrade_to_lts1` (≥ 50 km/h, ≥ 4 lanes, or primary/secondary/tertiary_link class, and not prohibited).

**Simplification.** Undirected graph; on parallel edges keep the worst LTS (shortest if tied); largest connected
component; repeatedly remove degree-2 nodes whose two edges have the same LTS, adding the lengths. The flags of LTS
5 edges are merged with a logical OR.

## 2. Infrastructure metrics (`cyclelts/metrics.py`)

For a city with yearly networks G_y and reference length L_ref = max_y (km of LTS 1–4 edges):

* N_y = km(LTS 1–4 of G_y) / L_ref
* LCC_t,y = km of the connected component with the most nodes in the sub-network {edges with LTS ≤ t}, t = 1..4
* C_y = Σ_t w_t · LCC_t,y / L_ref, with w_t = e^{−(t−1)} / Σ_s e^{−(s−1)} = 0.644, 0.237, 0.087, 0.032

## 3. Mode-share model (`cyclelts/mode_share.py`)

* Dependent variable: INSEE *Deux-roues total* share p_c,y (fraction), 11 cities × 2017–2022.
* Index: I = w_N · N + (1 − w_N) · C, w_N ∈ {0, 0.05, …, 1}.
* Model: p = 0.5 · logistic(α_c + β_c · I), fitted as a binomial GLM (fractional logit) on p / 0.5.
* Structures: pooled (α, β), city intercepts (α_c, β), city intercepts and slopes (α_c, β_c).
* Selection: leave-one-calendar-year-out cross-validation, RMSE in percentage points.
* Retained: city intercepts + common slope, w_N = 0.40 → α_Grenoble = −3.40675, β = 5.01498, CV RMSE 1.05 pp.

## 4–5. Investment optimisation (`cyclelts/optimization.py`)

* Decision: upgrade an eligible edge (LTS 2–5, not prohibited) directly to LTS 1.
* Cost: length × c(LTS). Step 4: c = 175 / 225 / 240 / 250 €/m; step 5: c = 200 / 415 / 590 / 750 €/m.
* Objective: predicted share with the Grenoble model, **with L_ref kept at its calibration value** (418.26 km).
* MLCC: (i) while the LTS-1 network has ≥ 2 components, upgrade the shortest physical path between the two
  longest; (ii) for γ = 2..5, take the longest LTS ≤ γ component that still contains non-LTS-1 edges, connect it to
  the main LTS-1 component by the shortest path, upgrade its edges by increasing distance from the connection
  point; stop at the first unaffordable edge.
* GA: binary chromosome over eligible edges; population 30, 30 generations, tournament size 3, uniform crossover
  0.85, bit-flip mutation 0.02, 2 elites + the best-so-far, random repair of over-budget plans, seed 42, MLCC plan
  in generation 0.
* Lookup table: 1000 equally spaced cumulative budgets from 0 to 0.5 · B_max (B_max = cost of upgrading every
  LTS 2–5 edge); MLCC is re-run from the previous state with the new money plus the unspent balance.

## 6. First-order comparison

P(u) = P0 + (P∞ − P0)(1 − e^{−k u}), u = added km of piste + bande (OSM facility classes mapped to French
categories), c = 400 €/m. k is calibrated three ways (ρ-transfer from Paris at equal share, generalised ρ on
2017–2022, direct Grenoble 2017→2022); the MLCC upgrades are converted to "new piste-equivalent km" (upgraded edges
that were not piste/bande before).

## 7. Backcasting

Least-cost yearly allocation 2027–2050 on the lookup table, subject to an annual cap (2 M€), either for a 35 %
share in 2050 (07a, PCHIP response curves) or for a −10 % cumulative car-CO₂ target with discounting (07b, exact
dynamic programming on the 1000 lookup states; car share, distance and emission equations of the colleagues'
model documents, see `docs/references/README.md`).
