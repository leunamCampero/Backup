"""Infrastructure metrics of a simplified LTS network.

Two numbers summarise a city's cycling network each year:

**Normalized network length** ``N``
    total length of the cycling network (LTS 1-4 edges) divided by a fixed
    reference length (by default the largest yearly length of that city).

**Weighted largest connected component** ``C``
    For each threshold t = 1, 2, 3, 4 keep only the edges with LTS <= t and
    measure the length of the largest connected piece (``LCC_t``): how far you
    can ride while never exceeding stress level t. The four values are then
    combined with weights that favour low-stress connectivity::

        w_t = exp(-kappa (t-1)) / sum_s exp(-kappa (s-1))     (kappa = 1)
        C   = sum_t w_t * LCC_t / reference_length

    With kappa = 1 the weights are 0.64, 0.24, 0.09, 0.03 for t = 1..4.

LTS 5 edges (car roads without facility, 2026) are **never** counted. The
"largest" component is the one with the most **nodes**, measured by the sum of
its edge lengths (the convention used for the calibration).
"""
from __future__ import annotations

import math
import re
from io import StringIO
from pathlib import Path

import networkx as nx
import pandas as pd

THRESHOLDS = (1, 2, 3, 4)


def exponential_weights(kappa=1.0):
    """Normalised weights ``w_t`` of the four LTS thresholds."""
    if kappa < 0:
        raise ValueError('kappa must be nonnegative')
    terms = {t: math.exp(-kappa*(t-1)) for t in THRESHOLDS}
    denominator = sum(terms.values())
    return {t: value/denominator for t, value in terms.items()}


def edge_level(data):
    """Integer LTS of an edge (1-5)."""
    return int(data.get('key', data.get('lts')))


def edge_length_m(data):
    """Length of an edge in metres."""
    return float(data.get('distance', data.get('length', 0.0)))


# Backwards-compatible private names
_level, _length = edge_level, edge_length_m


def graph_metrics(G):
    """Cycling length and LCC lengths (km) of ONE simplified graph.

    ``G`` must be a connected, simplified, undirected ``nx.Graph``. It may
    contain LTS 5 edges; they are ignored.
    """
    if type(G) is not nx.Graph or not nx.is_connected(G):
        raise ValueError('Expected nonempty connected, simplified undirected nx.Graph')
    levels = {_level(d) for _, _, d in G.edges(data=True)}
    if not levels.issubset({1, 2, 3, 4, 5}):
        raise ValueError(f'Unexpected levels: {levels}')
    total = sum(_length(d) for _, _, d in G.edges(data=True) if _level(d) <= 4)
    row = {'cycling_length_km': total/1000,
           'graph_nodes': G.number_of_nodes(), 'graph_edges': G.number_of_edges(),
           'lts5_edges': sum(_level(d) == 5 for _, _, d in G.edges(data=True)),
           'lts5_mandatory_edges': sum(_level(d) == 5 and bool(d.get('mandatory_upgrade_to_lts1', False)) for _, _, d in G.edges(data=True))}
    for t in THRESHOLDS:
        sub = nx.Graph()
        sub.add_edges_from((u, v, {'distance': _length(d)}) for u, v, d in G.edges(data=True) if _level(d) <= t)
        if sub.number_of_edges():
            largest = max(nx.connected_components(sub), key=len)
            L = sum(_length(d) for _, _, d in sub.subgraph(largest).edges(data=True))
        else:
            L = 0.0
        row[f'lcc_lts{t}_km'] = L/1000
        row[f'lcc_lts{t}_share_of_year'] = L/total if total else 0.0
    return row


def annual_metrics(graphs, kappa=1.0, reference_length_km=None):
    """Metrics table for a ``{year: simplified graph}`` dictionary.

    The same reference length is used for every year (default: the largest
    yearly cycling length), so the normalised values are comparable in time.
    """
    rows = []
    for year, G in sorted(graphs.items()):
        rec = graph_metrics(G)
        rec['year'] = int(year)
        rows.append(rec)
    df = pd.DataFrame(rows)
    if not len(df):
        raise ValueError('No annual graphs')
    ref = float(df['cycling_length_km'].max() if reference_length_km is None else reference_length_km)
    if ref <= 0:
        raise ValueError('Reference cycling length must be positive')
    w = exponential_weights(kappa)
    df['reference_length_km'] = ref
    df['normalized_network_length'] = df['cycling_length_km']/ref
    for t in THRESHOLDS:
        df[f'normalized_lcc_lts{t}'] = df[f'lcc_lts{t}_km']/ref
        df[f'weight_lts{t}'] = w[t]
    df['weighted_lcc_normalized'] = sum(w[t]*df[f'normalized_lcc_lts{t}'] for t in THRESHOLDS)
    df['kappa'] = kappa
    return df


def network_metrics(H, reference_length_m, kappa=1.0):
    """``N``, ``C`` and the LCC lengths of one graph, with a GIVEN reference length.

    Used by the optimisation (steps 4-6): the reference length of the
    calibration is kept fixed, it is NOT recomputed from the upgraded network.
    """
    lts_w = {g: math.exp(-kappa*(g-1)) for g in range(1, 5)}
    z = sum(lts_w.values())
    lts_w = {g: v/z for g, v in lts_w.items()}
    cycling_m = sum(edge_length_m(d) for _, _, d in H.edges(data=True) if edge_level(d) <= 4)
    N = cycling_m / reference_length_m
    C = 0.0
    lcc = {}
    for gamma in range(1, 5):
        T = nx.Graph()
        T.add_edges_from((u, v, {'distance': edge_length_m(d)})
                         for u, v, d in H.edges(data=True) if edge_level(d) <= gamma)
        if T.number_of_edges():
            biggest = max(nx.connected_components(T), key=len)   # largest by NODE count
            L = sum(d['distance'] for _, _, d in T.subgraph(biggest).edges(data=True))
        else:
            L = 0.0
        lcc[gamma] = L / 1000.0
        C += lts_w[gamma] * L / reference_length_m
    return dict(cycling_length_km=cycling_m/1000.0,
                normalized_network_length=N,
                weighted_lcc_normalized=C,
                **{f'lcc_lts{g}_km': lcc[g] for g in range(1, 5)})


# ---------------------------------------------------------------------------
# Metrics files (written by notebook 01, read by notebook 03)
# ---------------------------------------------------------------------------
def write_metrics_files(metrics, folder, slug, city_name, run_name, match, kappa):
    """Write the metrics table as CSV (full precision) and TXT (readable, 6 decimals)."""
    folder = Path(folder)
    csv_path = folder / f"{slug}_2017_2022_2026_SIMPLIFIED_metrics.csv"
    txt_path = folder / f"{slug}_2017_2022_2026_SIMPLIFIED_metrics.txt"
    metrics.to_csv(csv_path, index=False)
    with txt_path.open("w", encoding="utf-8") as f:
        f.write(f"{city_name} simplified cycling metrics, fresh build {run_name}\n")
        f.write("2017-2022: bicycle LTS1-4 simplified graphs (historical OSM, 31 Dec)\n")
        f.write("2026: bicycle LTS1-4 + missing car roads LTS5 simplified together; LTS5 excluded from metrics\n")
        f.write(f"Car matching rule: {match}; kappa={kappa}\n\n")
        f.write(metrics.to_string(index=False, float_format=lambda x: f"{x:.6f}") + "\n")
    return csv_path, txt_path


def find_metrics_file(city_folder):
    """Metrics file of the latest ``fresh_*`` run of a city (TXT preferred).

    The TXT file is preferred because the published calibration (notebook 03)
    was computed from it (values rounded to 6 decimals).
    """
    base = Path(city_folder)
    slug = base.name
    candidates = list(base.glob("fresh_*/" + slug + "*_SIMPLIFIED_metrics.txt"))
    candidates += list(base.glob("fresh_*/" + slug + "*_SIMPLIFIED_metrics.csv"))
    candidates += list(base.glob("**/" + slug + "*_SIMPLIFIED_metrics.txt"))
    candidates += list(base.glob("**/" + slug + "*_SIMPLIFIED_metrics.csv"))
    candidates = list({str(p): p for p in candidates}.values())
    if not candidates:
        raise FileNotFoundError(f"No LTS metrics file found under {base}")
    # Latest dated folder first; TXT before CSV when both exist.
    return sorted(candidates, key=lambda p: (re.findall(r"fresh_\d{4}-\d{2}-\d{2}", str(p)) or [""])[-1]
                  + ("z" if p.suffix == ".txt" else "a"))[-1]


def read_metrics_file(path):
    """Read ``year``, ``normalized_network_length`` and ``weighted_lcc_normalized``."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        header_idx = next((i for i, line in enumerate(lines)
                           if "normalized_network_length" in line and "weighted_lcc_normalized" in line), None)
        if header_idx is None:
            raise ValueError(f"Metric columns not found in {path}")
        df = pd.read_csv(StringIO("\n".join(lines[header_idx:])), sep=r"\s+")
    df.columns = df.columns.str.strip()
    if "year" not in df.columns and "Year" in df.columns:
        df = df.rename(columns={"Year": "year"})
    needed = ["year", "normalized_network_length", "weighted_lcc_normalized"]
    missing = [x for x in needed if x not in df.columns]
    if missing:
        raise ValueError(f"Missing columns {missing} in {path}; found {list(df.columns)}")
    df = df[needed].copy()
    for col in needed:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna().copy()
    df["year"] = df["year"].astype(int)
    if df.year.duplicated().any():
        raise ValueError(f"Duplicate years: {path}")
    return df
