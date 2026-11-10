"""Degree of Separation (DoS) bicycle networks from Overpass, using the Geovelo SQL rules.

Before: OSM .pbf -> osm2pgsql -> PostGIS -> the queries in ./sql -> geojson per category.
Now:    Overpass (via cyclelts.overpass.download_graph, historical [date:] or current OSM)
        -> the SAME ./sql WHERE conditions evaluated in an in-memory SQLite table that
        mimics planet_osm_line (one row per OSM way, one column per tag)
        -> tagsmapping.csv (query -> category) -> tags_mapping_final.csv (category -> group)
        -> DoS level: a_High=6 (fully separated, safest) ... f_Null_or_Others=1.

* A way matched by several queries gets the HIGHEST DoS among them (best facility present).
* A bike-network way matched by no query (plain shared street) gets ``unmatched_dos`` (1 by default).
* 2026: drivable roads that are not in the bicycle network are added as DoS 0 = "car road",
  the planning layer equivalent to LTS 5 (flag ``mandatory_upgrade_to_dos6``).
* Simplification: single undirected nx.Graph (worst = lowest DoS kept on parallel edges),
  largest connected component, degree-2 nodes removed when both edges have the same DoS,
  summed length. For DoS 0 the upgrade flags are merged with OR.
"""
from __future__ import annotations

import re
import shutil
import sqlite3
from collections import Counter, deque
from contextlib import contextmanager
from pathlib import Path

import networkx as nx
import osmnx as ox
import pandas as pd
from shapely.geometry import LineString

from cyclelts.overpass import download_graph, OVERPASS_ENDPOINTS
from cyclelts.lts import infer_speed_kmh, infer_lanes, _values
from cyclelts.simplify import _coordinates

HERE = Path(__file__).resolve().parent

GROUP_TO_DOS = {"a_High": 6, "b_Medium_High": 5, "c_Medium": 4,
                "d_Medium_Low": 3, "e_Low": 2, "f_Null_or_Others": 1}
CAR_DOS = 0
DOS_LABELS = {6: "DoS 6 - High", 5: "DoS 5 - Medium High", 4: "DoS 4 - Medium",
              3: "DoS 3 - Medium Low", 2: "DoS 2 - Low", 1: "DoS 1 - Null or others",
              0: "Car road (2026)"}

color_v = ["#66CD00", "#FFFF00", "#EE5C42", "#FF0000", "#CD0000", "#000000"]
colors = {6: color_v[0], 5: color_v[1], 4: color_v[2], 3: color_v[3], 2: color_v[4], 1: color_v[5]}


def palette_from_groups(key_color_label):
    """{'a_High': color, ...} -> {6: color, ...}, e.g. for plot_dos(palette=...)."""
    return {GROUP_TO_DOS[group]: color for group, color in key_color_label.items()}


def _needs_outline(color):
    """Light colours (yellow, gold) get a dark outline to stay readable on a light background."""
    from matplotlib.colors import to_rgb
    r, g, b = to_rgb(color)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.7
CAR_COLOR, CAR_MANDATORY_COLOR = "#b3b3b3", "#7b3294"

# The OSMnx "bike" filter drops highway=footway/bus_guideway, but several Geovelo
# categories (Trottoirs cyclables, Pistes sur trottoirs, Footway designated, Voies bus)
# are exactly those ways when cycling is allowed. They are downloaded with this filter.
EXTRA_BIKE_FILTER = ('["highway"~"^(footway|bus_guideway)$"]["area"!~"yes"]'
                     '["access"!~"private"]["bicycle"~"^(yes|designated|permissive)$"]')


# ---------------------------------------------------------------------------
# Geovelo SQL rules
# ---------------------------------------------------------------------------

def _query_name(path):
    """Same naming as name_format.name(): no extension, '-' -> '_', ASCII only, lower case."""
    text = path.name.split(".sql")[0].replace("-", "_")
    text = "".join(text.split())
    return "".join(c for c in text if ord(c) < 128).lower()


def load_rules(sql_dir=HERE / "sql", mapping_csv=HERE / "tagsmapping.csv",
               final_csv=HERE / "tags_mapping_final.csv"):
    """DataFrame: query, category, group, dos, where (the SQL condition between the GEOVELO markers)."""
    mapping = pd.read_csv(mapping_csv, header=None, index_col=0, sep=";").squeeze("columns").to_dict()
    final = pd.read_csv(final_csv, header=None, index_col=0, sep=";").squeeze("columns").to_dict()
    rows, skipped = [], []
    for path in sorted(Path(sql_dir).glob("*.sql")):
        text = path.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"-- BEGIN GEOVELO SQL CONDITIONS(.*?)-- END GEOVELO SQL CONDITIONS", text, re.S)
        query = _query_name(path)
        if not m or query not in mapping:      # e.g. All.sql (catch-all, no category)
            skipped.append(path.name)
            continue
        category = mapping[query]
        group = final[category]
        rows.append(dict(query=query, category=category, group=group,
                         dos=GROUP_TO_DOS[group], where=m.group(1)))
    if skipped:
        print("[rules] skipped (not in tagsmapping.csv):", ", ".join(skipped))
    return pd.DataFrame(rows)


def classify_ways(way_tags, rules):
    """{way_id: tags} -> {way_id: (dos, category, all matched categories)} for matched ways only."""
    columns = sorted({c for w in rules["where"] for c in re.findall(r'"([^"]+)"', w)})
    con = sqlite3.connect(":memory:")
    try:
        con.execute("PRAGMA case_sensitive_like = ON")   # PostgreSQL LIKE is case sensitive
        col_sql = ", ".join(f'"{c}" TEXT' for c in columns)
        con.execute(f"CREATE TABLE planet_osm_line (osm_id INTEGER PRIMARY KEY, {col_sql})")
        con.executemany(
            f"INSERT INTO planet_osm_line VALUES (?{', ?' * len(columns)})",
            ((wid, *(tags.get(c) for c in columns)) for wid, tags in way_tags.items()))
        matched = {}
        for r in rules.itertuples():
            # newline before ')' because conditions can end with a '--' comment
            for (wid,) in con.execute(f"SELECT osm_id FROM planet_osm_line WHERE (\n{r.where}\n)"):
                matched.setdefault(wid, []).append((r.dos, r.category))
    finally:
        con.close()
    out = {}
    for wid, hits in matched.items():
        dos, category = max(hits)
        out[wid] = (dos, category, ";".join(sorted({c for _, c in hits})))
    return out


# ---------------------------------------------------------------------------
# Overpass download (keeping the raw OSM tags, e.g. oneway=-1, that OSMnx rewrites)
# ---------------------------------------------------------------------------

@contextmanager
def _capture_way_tags(store):
    original = ox._overpass._download_overpass_network

    def tee(*args, **kwargs):
        for response in original(*args, **kwargs):
            for element in response.get("elements", []):
                if element.get("type") == "way":
                    store[element["id"]] = element.get("tags", {})
            yield response

    ox._overpass._download_overpass_network = tee
    try:
        yield
    finally:
        ox._overpass._download_overpass_network = original


@contextmanager
def _offline():
    """Live requests fail at once (unreachable proxy); OSMnx cache hits still work."""
    old = ox.settings.requests_kwargs
    ox.settings.requests_kwargs = {**old, "proxies": {"http": "http://127.0.0.1:9", "https": "http://127.0.0.1:9"}}
    try:
        yield
    finally:
        ox.settings.requests_kwargs = old


def download_with_tags(polygon, network_type, *, date=None, cache_folder=None,
                       endpoints=None, server_timeout=600, **graph_kwargs):
    """Unsimplified OSMnx graph + {way_id: raw tags}.

    The OSMnx cache key contains the endpoint URL, so every mirror is first tried
    offline (cache only); only if none is cached is the live download started.
    """
    endpoints = endpoints or OVERPASS_ENDPOINTS
    kwargs = dict(date=date, cache_folder=cache_folder, server_timeout=server_timeout,
                  simplify=False, **graph_kwargs)
    tags = {}
    with _capture_way_tags(tags):
        for endpoint in endpoints:
            try:
                with _offline():
                    G = download_graph(polygon, network_type, endpoints=[endpoint],
                                       attempts_per_endpoint=1, wait_seconds=0, **kwargs)
                print("[cache] reused", endpoint, flush=True)
                return G, tags
            except RuntimeError:
                tags.clear()
        print("[cache] no cached response -> live Overpass download", flush=True)
        G = download_graph(polygon, network_type, endpoints=endpoints, **kwargs)
    return G, tags


def seed_cache(source, destination):
    """Copy an existing OSMnx cache (e.g. the LTS run) so both studies use the same OSM snapshot."""
    source, destination = Path(source), Path(destination)
    if not source.exists():
        print("[cache] nothing to reuse at", source)
        return
    copied = 0
    for f in source.rglob("*.json"):
        target = destination / f.relative_to(source)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)
            copied += 1
    print(f"[cache] copied {copied} cached Overpass responses from {source}")


def restore_cache(archive, run):
    """Unpack a shipped ``.tar.xz`` of this study's Overpass answers into ``<run>/osm_http_cache``.

    The two published runs ship their downloads in ``osm_snapshots/`` so they can
    be rebuilt without internet. Does nothing if the archive is missing or the
    cache already contains files.
    """
    import tarfile
    archive, run = Path(archive), Path(run)
    if not archive.exists() or any((run / "osm_http_cache").rglob("*.json")):
        return False
    with tarfile.open(archive, "r:xz") as tar:
        if not all(n.startswith("osm_http_cache") and ".." not in n for n in tar.getnames()):
            raise ValueError(f"Unexpected paths in {archive}")
        try:
            tar.extractall(run, filter="data")
        except TypeError:
            tar.extractall(run)
    print(f"[cache] unpacked the shipped Overpass answers {archive.name} -> {run / 'osm_http_cache'}")
    return True


# ---------------------------------------------------------------------------
# Graph building
# ---------------------------------------------------------------------------

def build_bike_dos(polygon, rules, *, date=None, cache_folder=None, endpoints=None,
                   server_timeout=600, unmatched_dos=1):
    """Bicycle network (OSMnx bike filter + cyclable footways) with key = DoS 1..6 per edge."""
    G, tags = download_with_tags(polygon, "bike", date=date, cache_folder=cache_folder,
                                 endpoints=endpoints, server_timeout=server_timeout)
    F, foot_tags = download_with_tags(polygon, "all", custom_filter=EXTRA_BIKE_FILTER, date=date,
                                      cache_folder=cache_folder, endpoints=endpoints,
                                      server_timeout=server_timeout)
    G.add_nodes_from(F.nodes(data=True))
    G.add_edges_from((u, v, d) for u, v, d in F.edges(data=True))
    tags.update(foot_tags)

    G.remove_edges_from([(u, v, k) for u, v, k, d in G.edges(keys=True, data=True)
                         if "steps" in _values(d, "highway")])
    G.remove_nodes_from(list(nx.isolates(G)))
    G = G.subgraph(max(nx.weakly_connected_components(G), key=len)).copy()

    wanted = {d["osmid"] for _, _, d in G.edges(data=True)}
    classes = classify_ways({w: tags.get(w, {}) for w in wanted}, rules)
    for _, _, d in G.edges(data=True):
        dos, category, matched = classes.get(d["osmid"], (unmatched_dos, "No_infrastructure", ""))
        d.update(key=dos, dos=dos, category=category, matched_categories=matched,
                 network_layer="cycling", distance=float(d.get("length", 0.0)),
                 mandatory_upgrade_to_dos6=False)
    G.graph.update(n_ways=len(wanted), n_ways_matched=len(set(classes) & wanted))
    return G


def add_car_layer(bike, cars):
    """Add drivable roads whose OSM way is not in the bicycle graph as DoS 0 (car road).

    A car road is flagged ``mandatory_upgrade_to_dos6`` when it is dangerous
    (speed >= 50 km/h, >= 4 lanes, or primary/secondary class) and cycling is not
    prohibited (motorway/trunk/bicycle=no get ``bicycle_prohibited`` instead).
    """
    combined = bike.copy()
    bike_ways = {d["osmid"] for _, _, d in bike.edges(data=True)}
    added = 0
    for u, v, data in cars.edges(data=True):
        if data["osmid"] in bike_ways:
            continue
        highway = _values(data, "highway")
        speed, lanes = float(infer_speed_kmh(data)), int(infer_lanes(data))
        prohibited = bool(highway & {"motorway", "motorway_link", "trunk", "trunk_link"}) \
            or bool(_values(data, "bicycle") & {"no", "private"})
        dangerous = speed >= 50 or lanes >= 4 or bool(
            highway & {"primary", "primary_link", "secondary", "secondary_link", "tertiary_link"})
        for node in (u, v):
            if node not in combined:
                combined.add_node(node, **cars.nodes[node])
        attrs = dict(data)
        attrs.update(dos=CAR_DOS, category="Car_road", matched_categories="", network_layer="car",
                     distance=float(data.get("length", 0.0)), estimated_speed_kmh=speed,
                     estimated_lanes=lanes, bicycle_prohibited=prohibited,
                     high_stress_car_road=dangerous,
                     mandatory_upgrade_to_dos6=bool(dangerous and not prohibited))
        attrs.pop("key", None)
        k = combined.add_edge(u, v, **attrs)
        combined[u][v][k]["key"] = CAR_DOS
        added += 1
    print(f"[cars] added {added:,} directed car-road edges (OSM ways not in the bicycle graph)")
    return combined


# ---------------------------------------------------------------------------
# Simplification (same rules as grenoble_simplification_exact, for DoS 0..6)
# ---------------------------------------------------------------------------

CAR_FLAGS = ("mandatory_upgrade_to_dos6", "bicycle_prohibited", "high_stress_car_road")


def _edge(d):
    e = dict(d)
    e["key"] = e["dos"] = int(e.get("dos", e.get("key")))
    e["distance"] = e["length"] = float(e.get("distance", e.get("length", 0.0)))
    for flag in CAR_FLAGS:
        e[flag] = bool(e.get(flag)) if e["key"] == CAR_DOS else False
    return e


def _or_flags(chosen, a, b):
    if a["key"] == b["key"] == CAR_DOS:
        for flag in CAR_FLAGS:
            chosen[flag] = bool(a.get(flag) or b.get(flag))
    return chosen


def _choose_parallel(a, b):
    """Worst (lowest) DoS, then shortest."""
    better_b = b["key"] < a["key"] or (b["key"] == a["key"] and b["distance"] < a["distance"])
    return _or_flags(dict(b if better_b else a), a, b)


def simplify_dos_graph(G):
    H = nx.Graph()
    H.add_nodes_from((n, dict(a)) for n, a in G.nodes(data=True))
    H.graph.update(G.graph)
    for u, v, d in G.edges(data=True):
        if u == v:
            continue
        e = _edge(d)
        if H.has_edge(u, v):
            H[u][v].update(_choose_parallel(dict(H[u][v]), e))
        else:
            H.add_edge(u, v, **e)
    H.remove_nodes_from(list(nx.isolates(H)))
    if H.number_of_nodes() and not nx.is_connected(H):
        H = H.subgraph(max(nx.connected_components(H), key=len)).copy()
    q = deque(n for n in H if H.degree(n) == 2)
    contracted = 0
    while q:
        n = q.popleft()
        if n not in H or H.degree(n) != 2:
            continue
        a, b = H.neighbors(n)
        e1, e2 = dict(H[a][n]), dict(H[n][b])
        if e1["key"] != e2["key"]:
            continue
        merged = _or_flags(dict(e1), e1, e2)
        merged["distance"] = merged["length"] = e1["distance"] + e2["distance"]
        merged["category"] = ";".join(sorted(set(e1["category"].split(";")) | set(e2["category"].split(";"))))
        merged["geometry"] = LineString(_coordinates(H, a, n, e1) + _coordinates(H, n, b, e2)[1:])
        prior = dict(H[a][b]) if H.has_edge(a, b) else None
        H.remove_node(n)
        if prior is not None:
            merged = _choose_parallel(prior, merged)
        H.add_edge(a, b, **merged)
        contracted += 1
        for c in (a, b):
            if H.degree(c) == 2:
                q.append(c)
    H.graph.update(degree2_contracted=contracted,
                   simplification_rule="worst (lowest) DoS on parallel edges, equal-DoS degree-2 "
                                       "contraction, summed distance, largest connected component")
    assert type(H) is nx.Graph and (not len(H) or nx.is_connected(H))
    return H


def check_graph(H):
    same = sum(H.degree(n) == 2 and len({H[n][m]["key"] for m in H.neighbors(n)}) == 1 for n in H)
    result = {"nodes": H.number_of_nodes(), "edges": H.number_of_edges(),
              "connected": nx.is_connected(H) if len(H) else False,
              "remaining_contractible_degree2_nodes": same,
              "dos_counts": dict(sorted(Counter(d["key"] for _, _, d in H.edges(data=True)).items())),
              "mandatory_car_edges": sum(bool(d.get("mandatory_upgrade_to_dos6")) for _, _, d in H.edges(data=True))}
    print(result)
    return result


# ---------------------------------------------------------------------------
# Summaries and plots
# ---------------------------------------------------------------------------

def length_by_dos(graphs):
    """km per DoS level (car roads in their own column) for {year: simplified graph}."""
    rows = []
    for year, H in sorted(graphs.items()):
        km = Counter()
        for _, _, d in H.edges(data=True):
            km[d["key"]] += d["distance"] / 1000
        row = {"year": year}
        row.update({f"DoS{lvl}_km": km.get(lvl, 0.0) for lvl in range(6, 0, -1)})
        row["cycling_km"] = sum(km[lvl] for lvl in range(1, 7))
        row["car_road_km"] = km.get(CAR_DOS, 0.0)
        row["car_mandatory_km"] = sum(d["distance"] for _, _, d in H.edges(data=True)
                                      if d.get("mandatory_upgrade_to_dos6")) / 1000
        rows.append(row)
    return pd.DataFrame(rows)


def length_by_category(G):
    """km per Geovelo category on an unsimplified bike graph (each OSM way segment counted once)."""
    seen, km = set(), Counter()
    for u, v, d in G.edges(data=True):
        pair = (frozenset((u, v)), d["osmid"])
        if pair in seen:
            continue
        seen.add(pair)
        km[(d["dos"], d["category"])] += d["distance"] / 1000
    df = pd.DataFrame([(dos, cat, k) for (dos, cat), k in km.items()], columns=["DoS", "category", "km"])
    return df.sort_values(["DoS", "km"], ascending=[False, False]).reset_index(drop=True)


def _segments(H, u, v, d):
    geom = d.get("geometry")
    if geom is not None and geom.geom_type == "LineString":
        return list(geom.coords)
    return [(H.nodes[u]["x"], H.nodes[u]["y"]), (H.nodes[v]["x"], H.nodes[v]["y"])]


def _clip(lines, boundary):
    """Cut a list of coordinate lists to the boundary polygon (display only)."""
    import shapely
    if boundary is None or not lines:
        return lines
    clipped = shapely.intersection([LineString(l) for l in lines], boundary)
    out = []
    for g in clipped:
        for part in getattr(g, "geoms", [g]):
            if part.geom_type == "LineString" and not part.is_empty:
                out.append(list(part.coords))
    return out


def _edge_groups(H, show_cars=True):
    groups = {}
    for u, v, d in H.edges(data=True):
        level = d["key"]
        if level == CAR_DOS:
            if not show_cars:
                continue
            level = "car_m" if d.get("mandatory_upgrade_to_dos6") else "car"
        groups.setdefault(level, []).append(_segments(H, u, v, d))
    return groups


def plot_dos(H, title, boundary=None, ax=None, show_cars=True, clip=True, palette=None):
    """Geographic plot of a simplified DoS graph with the requested DoS colours.

    clip=True cuts the drawn lines at the boundary polygon (the graph itself is unchanged).
    palette: {DoS level: colour}; default = ``colors``.
    """
    import math
    import matplotlib.pyplot as plt
    import matplotlib.patheffects as pe
    from matplotlib.collections import LineCollection
    from matplotlib.lines import Line2D

    widths = {6: 1.6, 5: 1.4, 4: 1.2, 3: 1.1, 2: 0.9, 1: 0.45}
    groups = _edge_groups(H, show_cars)
    if clip and boundary is not None:
        groups = {level: _clip(lines, boundary) for level, lines in groups.items()}
    palette = palette or colors
    style = {lvl: (palette[lvl], widths[lvl]) for lvl in palette}
    style.update(car=(CAR_COLOR, 0.7), car_m=(CAR_MANDATORY_COLOR, 1.6))

    if ax is None:
        fig, ax = plt.subplots(figsize=(11, 11))
    order = ["car", 1, 2, 3, 4, 5, 6, "car_m"]
    for level in order:
        if level not in groups:
            continue
        color, width = style[level]
        lc = LineCollection(groups[level], colors=color, linewidths=width, capstyle="round",
                            zorder=2 + order.index(level))
        if level in palette and _needs_outline(color):
            lc.set_path_effects([pe.Stroke(linewidth=width + 1.0, foreground="#5a5a00"), pe.Normal()])
        ax.add_collection(lc)
    if boundary is not None:
        polys = getattr(boundary, "geoms", [boundary])
        for p in polys:
            x, y = p.exterior.xy
            ax.plot(x, y, color="#4d4d4d", lw=0.8, ls="--", zorder=1)
    ax.autoscale()
    lat = sum(d["y"] for _, d in H.nodes(data=True)) / max(len(H), 1)
    ax.set_aspect(1 / math.cos(math.radians(lat)))
    ax.set_facecolor("#ececec")
    ax.set_xticks([]); ax.set_yticks([])
    km = Counter()
    for _, _, d in H.edges(data=True):
        km["car_m" if d.get("mandatory_upgrade_to_dos6") else "car" if d["key"] == CAR_DOS else d["key"]] += d["distance"] / 1000
    handles = [Line2D([], [], color=palette[l], lw=3, label=f"{DOS_LABELS[l]} ({km[l]:.1f} km)",
                      path_effects=[pe.Stroke(linewidth=4.5, foreground="#5a5a00"), pe.Normal()] if _needs_outline(palette[l]) else None)
               for l in range(6, 0, -1)]
    if show_cars and (km["car"] or km["car_m"]):
        handles += [Line2D([], [], color=CAR_COLOR, lw=3, label=f"Car road, other ({km['car']:.1f} km)"),
                    Line2D([], [], color=CAR_MANDATORY_COLOR, lw=3,
                           label=f"Car road, must upgrade to DoS 6 ({km['car_m']:.1f} km)")]
    ax.legend(handles=handles, loc="lower left", fontsize=9, framealpha=0.9)
    ax.set_title(title)
    return ax


def folium_dos(H, boundary, title="", show_cars=True, palette=None):
    """Interactive (zoomable) map: DoS layers clipped to the boundary, one toggle per level."""
    import folium
    from shapely.geometry import mapping

    cx, cy = boundary.centroid.x, boundary.centroid.y
    m = folium.Map(location=[cy, cx], zoom_start=13, tiles=None, control_scale=True)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap (faded)", opacity=0.45).add_to(m)
    folium.GeoJson(mapping(boundary), name="City boundary",
                   style_function=lambda _: {"color": "#4d4d4d", "weight": 2, "dashArray": "6",
                                             "fillOpacity": 0}).add_to(m)
    palette = palette or colors
    style = {lvl: (palette[lvl], w) for lvl, w in {6: 4, 5: 4, 4: 3.5, 3: 3, 2: 3, 1: 1.5}.items()}
    style.update(car=(CAR_COLOR, 2), car_m=(CAR_MANDATORY_COLOR, 4))
    names = {**DOS_LABELS, "car": "Car road, other", "car_m": "Car road, must upgrade to DoS 6"}
    groups = {lvl: _clip(lines, boundary) for lvl, lines in _edge_groups(H, show_cars).items()}
    for level in ["car", 1, 2, 3, 4, 5, 6, "car_m"]:
        if not groups.get(level):
            continue
        color, weight = style[level]
        layer = folium.FeatureGroup(name=f'<span style="color:{color};background:#888;padding:0 4px">&#9644;</span> '
                                         f'{names[level]}')
        folium.PolyLine([[(y, x) for x, y in line] for line in groups[level]],
                        color=color, weight=weight, opacity=0.95).add_to(layer)
        layer.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    if title:
        m.get_root().html.add_child(folium.Element(
            f'<h4 style="position:fixed;top:8px;left:60px;z-index:9999;background:white;'
            f'padding:4px 8px;border-radius:4px">{title}</h4>'))
    return m
