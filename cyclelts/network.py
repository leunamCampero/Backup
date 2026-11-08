"""Step 1 - build the yearly cycling network of a city, with an LTS on every street.

For each city and year the pipeline is::

    OpenStreetMap (Overpass)  ->  bike graph  ->  LTS per edge  ->  LTS 1..4
                                                                     |
    2026 only: car roads missing from the bike graph  ->  "LTS 5"  --+
                                                                     v
                                               simplified nx.Graph (saved as .pkl)

* **2017-2022** use the historical OSM map of 31 December of each year.
* **2026** uses the current OSM map. Car roads that are not part of the bike
  network are added as **LTS 5**: a *planning layer* of streets that could
  receive a cycling facility. LTS 5 is never counted in the cycling metrics.
  An LTS 5 road is flagged ``mandatory_upgrade_to_lts1`` when it is dangerous
  (speed >= 50 km/h, >= 4 lanes, or primary/secondary class) and cycling is
  allowed on it; motorways, trunks and ``bicycle=no`` roads are flagged
  ``bicycle_prohibited`` instead and can never be upgraded.

Every intermediate graph is saved, so an interrupted run resumes where it stopped.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import networkx as nx

from .config import CURRENT_YEAR, REPO_ROOT, load_pickle, save_pickle
from .lts import _values, annotate_graph, infer_lanes, infer_speed_kmh, largest_weak_component
from .overpass import OVERPASS_ENDPOINTS, download_graph
from .simplify import check_graph, simplify_lts_graph


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _short(path):
    """Path relative to the repository (for messages), absolute if outside it."""
    try:
        return Path(path).resolve().relative_to(REPO_ROOT)
    except ValueError:
        return Path(path)


def normalize_snapshot_date(snapshot_date: str | datetime) -> str:
    """Return an ISO-8601 UTC timestamp accepted by Overpass.

    ``"2019"`` -> ``"2019-12-31T23:59:59Z"`` (end of the year);
    ``"2019-06-30"`` -> ``"2019-06-30T23:59:59Z"``.
    """
    if isinstance(snapshot_date, datetime):
        value = snapshot_date
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    text = str(snapshot_date).strip()
    if len(text) == 4 and text.isdigit():
        text = f"{text}-12-31T23:59:59Z"
    elif len(text) == 10:
        text = f"{text}T23:59:59Z"
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def classify_integer_lts(raw):
    """Raw score 0, 1, 2, 2.5, 3, 4, 5 -> integer LTS 1, 1, 2, 3, 3, 4, 4 (None for steps)."""
    if raw is None or float(raw) < 0:
        return None
    return min(4, 1 if raw <= 1 else 2 if raw <= 2 else 3 if raw <= 3 else 4)


def prepare_bike(G):
    """Keep classified bike edges, store the integer LTS in ``key``/``lts``, keep the largest component."""
    H = G.copy()
    drop = []
    for u, v, k, d in H.edges(keys=True, data=True):
        lts = classify_integer_lts(d.get('lts_score', -1))
        if lts is None:
            drop.append((u, v, k))
            continue
        d['key'] = lts
        d['lts'] = lts
        d['network_layer'] = 'cycling'
        d['distance'] = float(d.get('distance', d.get('length', 0)))
        d['mandatory_upgrade_to_lts1'] = False
    H.remove_edges_from(drop)
    H.remove_nodes_from(list(nx.isolates(H)))
    if H.number_of_nodes():
        biggest = max(nx.weakly_connected_components(H), key=len)
        H = H.subgraph(biggest).copy()
    return H


def osm_way_ids(d):
    """Set of OSM way ids (as strings) of one edge."""
    x = d.get('osmid', [])
    if not isinstance(x, (list, tuple, set)):
        x = [x]
    return set(str(i) for i in x)


def missing_car_network(bike, car, match='endpoints', year=CURRENT_YEAR):
    """Add to ``bike`` the car roads it does not contain, as LTS 5 edges.

    match : ``'way'`` - a car edge is skipped when all its OSM ways are already
        in the bike graph (robust when OSMnx split the street differently);
        ``'endpoints'`` - original rule: skip only car edges with the same end
        nodes (or same way + same end nodes) as a bike edge.
    """
    combined = bike.copy()
    bike_way_ids = set().union(*(osm_way_ids(d) for _, _, _, d in bike.edges(keys=True, data=True))) if bike.number_of_edges() else set()
    bike_pairs = {frozenset((u, v)) for u, v, _, _ in bike.edges(keys=True, data=True)}
    bike_ways = {(w, frozenset((u, v))) for u, v, _, d in bike.edges(keys=True, data=True) for w in osm_way_ids(d)}
    added = 0
    for u, v, _, data in car.edges(keys=True, data=True):
        pair = frozenset((u, v))
        if match == 'way' and osm_way_ids(data) and osm_way_ids(data) <= bike_way_ids:
            continue
        if pair in bike_pairs or any((w, pair) in bike_ways for w in osm_way_ids(data)):
            continue
        highway = _values(data, 'highway')
        speed = float(infer_speed_kmh(data))
        lanes = int(infer_lanes(data))
        prohibited = bool(highway & {'motorway', 'motorway_link', 'trunk', 'trunk_link'}) or bool(_values(data, 'bicycle') & {'no', 'private'})
        dangerous = speed >= 50 or lanes >= 4 or bool(highway & {'primary', 'primary_link', 'secondary', 'secondary_link', 'tertiary_link'})
        mandatory = bool(dangerous and not prohibited)
        for node in (u, v):
            if node not in combined:
                combined.add_node(node, **dict(car.nodes[node]))
        attrs = dict(data)
        attrs.update(key=5, lts=5, network_layer='missing_car',
                     distance=float(data.get('length', data.get('distance', 0.0))),
                     estimated_speed_kmh=speed, estimated_lanes=lanes,
                     bicycle_prohibited=prohibited, high_stress_car_road=dangerous,
                     mandatory_upgrade_to_lts1=mandatory,
                     target_lts=1 if mandatory else None,
                     optimization_candidate=not prohibited,
                     upgrade_reason=('independent facility required' if prohibited else 'high speed/lanes/class' if mandatory else 'no mandatory upgrade under rule'))
        # add_edge's "key" is a networkx multigraph positional argument; remove it
        attrs.pop('key', None)
        new_key = combined.add_edge(u, v, **attrs)
        combined[u][v][new_key]['key'] = 5
        added += 1
    combined.graph.update(year=year, snapshot_mode='current/live OSM', lts5_meaning='missing car-road planning layer')
    print(f'[{year}] Added {added:,} directed missing-car edges (matching by endpoint/OSM way is approximate).')
    return combined


# ---------------------------------------------------------------------------
# Build one city-year
# ---------------------------------------------------------------------------
class CityNetworkBuilder:
    """Download, classify and simplify the networks of one city.

    Parameters
    ----------
    city_name : name used in titles and stored in the graphs
    slug : lower-case name used in file names
    polygon : city boundary (Shapely, WGS84)
    run : output folder of this run, e.g. ``results/lts_networks/grenoble/fresh_2026-10-21``
    rebuild : True = ignore the pickles already in ``run`` and redo everything
    timeout : seconds the Overpass server may work on one query
    match : rule used to add missing car roads in 2026 (see :func:`missing_car_network`)
    """

    def __init__(self, city_name, slug, polygon, run, *, rebuild=False, timeout=600,
                 match="way", endpoints=OVERPASS_ENDPOINTS, current_year=CURRENT_YEAR):
        self.city_name, self.slug, self.polygon = city_name, slug, polygon
        self.run = Path(run)
        self.cache = self.run / "osm_http_cache"
        self.rebuild, self.timeout, self.match = rebuild, timeout, match
        self.endpoints, self.current_year = endpoints, current_year

    def snapshot(self, year):
        """Historical years -> 31 Dec timestamp; current year -> None (current OSM)."""
        return None if year == self.current_year else normalize_snapshot_date(str(year))

    def _download(self, year, network_type):
        date = self.snapshot(year)
        return download_graph(self.polygon, network_type, date=date, server_timeout=self.timeout,
                              endpoints=self.endpoints,
                              cache_folder=self.cache / (date[:10] if date else "current"))

    def get_bike(self, year):
        """Bicycle network of ``year`` with integer LTS 1-4 (cached in ``<year>/..._prepared.pkl``)."""
        path = self.run / str(year) / f"{self.slug}_bike_{year}_prepared.pkl"
        if path.exists() and not self.rebuild:
            return load_pickle(path)
        G = self._download(year, "bike")
        steps = [(u, v, k) for u, v, k, d in G.edges(keys=True, data=True) if "steps" in _values(d, "highway")]
        G.remove_edges_from(steps)
        G.remove_nodes_from(list(nx.isolates(G)))
        G = annotate_graph(G)                            # raw lts_score 0,1,2,2.5,3,4,5
        bike = prepare_bike(largest_weak_component(G))   # -> key/lts 1..4
        bike.graph["year"] = year
        save_pickle(bike, path)
        return bike

    def get_cars(self, year):
        """Raw car network of ``year`` (cached in ``<year>/..._car_<year>_raw.pkl``)."""
        path = self.run / str(year) / f"{self.slug}_car_{year}_raw.pkl"
        if path.exists() and not self.rebuild:
            return load_pickle(path)
        cars = self._download(year, "drive")
        save_pickle(cars, path)
        return cars

    def build_year(self, year):
        """Return the simplified network of ``year`` (built and saved if needed)."""
        out = self.run / str(year) / f"{self.slug}_lts_{year}_SIMPLE.pkl"
        if out.exists() and not self.rebuild:
            print(f"[{year}] loaded {_short(out)}")
            return load_pickle(out)
        bike = self.get_bike(year)
        if year == self.current_year:
            source = missing_car_network(bike, self.get_cars(year), match=self.match, year=year)  # LTS 1-4 + LTS 5
            save_pickle(source, self.run / str(year) / f"{self.slug}_lts5_{year}_pre_simplification.pkl")
        else:
            source = bike
        H = simplify_lts_graph(source)   # same-LTS degree-2 removal, summed length, OR of upgrade flag
        H.graph.update(year=year, city=self.city_name, snapshot=self.snapshot(year) or "current OSM")
        check = check_graph(H)
        assert type(H) is nx.Graph and check["connected"]
        assert check["remaining_contractible_degree2_nodes"] == 0
        levels = {d["key"] for _, _, d in H.edges(data=True)}
        if year == self.current_year:
            assert levels <= {1, 2, 3, 4, 5} and 5 in levels, f"No LTS 5 roads in {year}"
        else:
            assert levels <= {1, 2, 3, 4}
        save_pickle(H, out)
        print(f"[{year}] saved {_short(out)}")
        return H
