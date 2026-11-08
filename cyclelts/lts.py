"""Classify every street segment by its Level of Traffic Stress (LTS) for cyclists.

What is LTS?
------------
The *Level of Traffic Stress* (Mekuria, Furth & Nixon, 2012; revised by Furth
et al.) rates how stressful a street feels for a person on a bike:

* **LTS 1** - comfortable for almost everybody, including children
  (separated cycle tracks, car-free paths, very calm streets);
* **LTS 2** - comfortable for most adults (painted lanes on 50 km/h streets,
  30 km/h residential streets, shared paths);
* **LTS 3** - acceptable only for confident cyclists;
* **LTS 4** - only for the "strong and fearless" (fast, wide roads).

How it is computed here
-----------------------
The classifier is an **approximation based on OpenStreetMap (OSM) tags**. OSM
rarely contains traffic volumes, parking turnover, buffer widths or crossing
details, so each segment is classified from:

1. its *facility type* (cycle track, painted lane, shared path, mixed traffic,
   ...), read from tags such as ``highway``, ``cycleway``, ``bicycle``;
2. the *speed limit* (``maxspeed``, or a default for the road class);
3. the *number of lanes* (``lanes``, or a default for the road class).

When information is missing, the more stressful (conservative) value is used.

The raw score can be 0, 1, 2, 2.5, 3, 4 or 5. The study then maps it to four
integer levels (see :func:`cyclelts.network.classify_integer_lts`):
``0, 1 -> 1``, ``2 -> 2``, ``2.5, 3 -> 3``, ``4, 5 -> 4``.
Steps (stairs) get no score and are removed from the cycling network.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

import networkx as nx
import osmnx as ox
import pandas as pd

# OSM tags needed by the classifier. OSMnx otherwise drops many of them when
# it builds the graph, so they are added to ``ox.settings.useful_tags_way``.
REQUIRED_WAY_TAGS = {
    "access", "bicycle", "bicycle_road", "bus", "busway",
    "cycleway", "cycleway:both", "cycleway:both:buffer", "cycleway:both:lane", "cycleway:both:oneway",
    "cycleway:left", "cycleway:left:buffer", "cycleway:left:lane", "cycleway:left:oneway",
    "cycleway:right", "cycleway:right:buffer", "cycleway:right:lane", "cycleway:right:oneway",
    "cyclestreet", "foot", "footway", "highway", "is_sidepath", "junction", "lanes", "lit",
    "maxspeed", "motor_vehicle", "name", "oneway", "oneway:bicycle",
    "parking", "parking:both", "parking:left", "parking:right",
    "segregated", "separation", "shoulder", "sidewalk",
    "sidewalk:both:bicycle", "sidewalk:left:bicycle", "sidewalk:right:bicycle",
    "smoothness", "surface", "tracktype", "width",
}

# Display groups of the raw score (LTS 4 and 5 are merged only for display).
LTS_DISPLAY_GROUPS: dict[str, tuple[float, ...]] = {
    "LTS 0 - no traffic": (0.0,),
    "LTS 1 - very low": (1.0,),
    "LTS 2 - low": (2.0,),
    "LTS 2.5 - moderate-low": (2.5,),
    "LTS 3 - moderate-high": (3.0,),
    "LTS 4-5 - high/very high": (4.0, 5.0),
}

# Default speed (km/h) when ``maxspeed`` is missing, by OSM road class.
# Deliberately conservative; can be changed for a local calibration.
DEFAULT_SPEED_KMH = {
    "motorway": 110.0, "motorway_link": 70.0, "trunk": 90.0, "trunk_link": 70.0,
    "primary": 50.0, "primary_link": 50.0, "secondary": 50.0, "secondary_link": 50.0,
    "tertiary": 50.0, "tertiary_link": 50.0, "unclassified": 30.0, "residential": 30.0,
    "living_street": 20.0, "service": 20.0, "pedestrian": 20.0, "cycleway": 20.0,
    "path": 15.0, "footway": 10.0, "steps": 5.0,
}

# Default total number of through lanes when ``lanes`` is missing.
DEFAULT_LANES = {
    "motorway": 4, "trunk": 4, "primary": 2, "secondary": 2, "tertiary": 2,
    "unclassified": 2, "residential": 2, "living_street": 1, "service": 1,
    "pedestrian": 1, "cycleway": 1, "path": 1, "footway": 1, "steps": 1,
}

# When OSMnx merges several OSM ways into one edge, the most stressful road
# class (first in this list) is used.
HIGHWAY_STRESS_ORDER = [
    "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
    "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified",
    "residential", "service", "living_street", "pedestrian", "cycleway", "path",
    "footway", "steps",
]


# ---------------------------------------------------------------------------
# Tag parsing helpers
# ---------------------------------------------------------------------------
def _flatten(value: Any) -> list[Any]:
    """Flatten OSMnx list-valued attributes without treating strings as lists."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        output: list[Any] = []
        for item in value:
            output.extend(_flatten(item))
        return output
    return [value]


def _values(data: dict[str, Any], *keys: str) -> set[str]:
    """All lower-case values of the given tags (``a;b`` values are split)."""
    values: set[str] = set()
    for key in keys:
        for item in _flatten(data.get(key)):
            text = str(item).strip().lower()
            if text:
                # OSMnx can aggregate values; OSM tags may also use semicolons.
                values.update(part.strip() for part in text.split(";") if part.strip())
    return values


def _has(data: dict[str, Any], keys: Iterable[str], wanted: Iterable[str]) -> bool:
    found = _values(data, *keys)
    target = {str(value).lower() for value in wanted}
    return bool(found & target)


def _has_fragment(data: dict[str, Any], keys: Iterable[str], fragments: Iterable[str]) -> bool:
    found = _values(data, *keys)
    return any(fragment in value for value in found for fragment in fragments)


def _worst_highway(data: dict[str, Any]) -> str:
    highways = _values(data, "highway")
    for highway in HIGHWAY_STRESS_ORDER:
        if highway in highways:
            return highway
    return next(iter(highways), "unclassified")


def _parse_numbers(value: Any) -> list[float]:
    numbers: list[float] = []
    for item in _flatten(value):
        text = str(item).strip().lower().replace(",", ".")
        if not text:
            continue
        for part in text.split(";"):
            match = re.search(r"\d+(?:\.\d+)?", part)
            if match:
                number = float(match.group())
                if "mph" in part:
                    number *= 1.609344
                numbers.append(number)
    return numbers


def infer_speed_kmh(data: dict[str, Any]) -> float:
    """Speed of motor traffic: highest tagged speed, else the road-class default."""
    raw = _values(data, "maxspeed")
    coded_speeds = {
        "fr:urban": 50.0, "fr:rural": 80.0, "fr:motorway": 130.0,
        "fr:zone30": 30.0, "fr:living_street": 20.0, "walk": 10.0,
    }
    candidates = [coded_speeds[value] for value in raw if value in coded_speeds]
    candidates.extend(_parse_numbers(data.get("maxspeed")))
    if candidates:
        return max(candidates)
    return DEFAULT_SPEED_KMH.get(_worst_highway(data), 50.0)


def infer_lanes(data: dict[str, Any]) -> int:
    """Number of through lanes: tagged value, else the road-class default."""
    candidates = _parse_numbers(data.get("lanes"))
    if candidates:
        return max(1, int(round(max(candidates))))
    highway = _worst_highway(data)
    default = DEFAULT_LANES.get(highway, 2)
    if _has(data, ["oneway"], ["yes", "1", "true", "-1"]):
        return min(default, 1)
    return default


# ---------------------------------------------------------------------------
# Facility and LTS classification
# ---------------------------------------------------------------------------
def classify_facility(data: dict[str, Any]) -> str:
    """Type of cycling facility of one edge, from its OSM tags.

    Returns one of: ``steps``, ``bicycle street``, ``shared street``,
    ``independent path``, ``separated bike lane``, ``dedicated cycleway``,
    ``sidepath/separated path``, ``segregated shared-use path``,
    ``shared-use path``, ``pedestrian zone with bicycle access``,
    ``painted bike lane``, ``bikeable shoulder``, ``shared-lane marking``,
    ``shared bus lane`` or ``mixed traffic``.
    """
    highway = _worst_highway(data)
    cycleway_keys = ("cycleway", "cycleway:left", "cycleway:right", "cycleway:both")
    cycleway_values = _values(data, *cycleway_keys)

    if highway == "steps":
        return "steps"

    if _has(data, ["cyclestreet", "bicycle_road"], ["yes", "1", "true"]):
        return "bicycle street"

    if highway == "living_street":
        return "shared street"

    if _has(data, ["is_sidepath"], ["no"]) or _has(data, ["separation"], ["independent"]):
        if highway in {"cycleway", "path", "footway"}:
            return "independent path"

    is_sidepath = (
        _has(data, ["is_sidepath"], ["yes"])
        or _has(data, ["footway"], ["sidewalk"])
        or bool(_values(data, "sidewalk:both:bicycle", "sidewalk:left:bicycle", "sidewalk:right:bicycle"))
    )

    if any(value in cycleway_values for value in {"track", "opposite_track", "separate"}):
        return "separated bike lane"

    if highway == "cycleway":
        return "sidepath/separated path" if is_sidepath else "dedicated cycleway"

    if highway in {"path", "footway"} and _has(
        data, ["bicycle"], ["yes", "designated", "official", "permissive", "destination"],
    ):
        if _has(data, ["segregated"], ["yes"]):
            return "segregated shared-use path"
        return "shared-use path"

    if highway == "pedestrian" and not _has(data, ["bicycle"], ["no"]):
        return "pedestrian zone with bicycle access"

    if any(value in cycleway_values for value in {"lane", "opposite_lane"}):
        return "painted bike lane"

    if "shoulder" in cycleway_values or _has(data, ["shoulder"], ["yes", "both", "left", "right"]):
        return "bikeable shoulder"

    if any(value in cycleway_values for value in {"shared_lane", "shared", "opposite"}):
        return "shared-lane marking"

    if any(value in cycleway_values for value in {"share_busway", "opposite_share_busway"}) or _has_fragment(
        data, ["busway"], ["lane"]
    ):
        return "shared bus lane"

    return "mixed traffic"


def _mixed_traffic_lts(speed: float, lanes: int, highway: str) -> float:
    # Metric adaptation of the revised mixed-traffic table. Because OSM rarely
    # contains ADT, center-line, and parking-turnover data, ambiguous cases are
    # assigned the more conservative (higher-stress) value.
    if highway == "living_street":
        return 1.0
    if speed <= 20 and lanes <= 2:
        return 1.0
    if speed <= 30 and lanes <= 2:
        return 2.0
    if speed <= 40 and lanes <= 3:
        return 2.5
    if speed <= 50 and lanes <= 3:
        return 3.0
    if speed <= 50:
        return 4.0
    if speed < 70:
        return 4.0
    return 5.0


def _painted_lane_lts(speed: float, lanes: int) -> float:
    # Metric adaptation of the revised bike-lane table.
    if speed <= 50:
        if lanes <= 3:
            return 2.0
        if lanes <= 5:
            return 2.5
        return 3.0
    if speed <= 60:
        return 3.0
    if speed < 70:
        return 4.0
    return 5.0


def _shoulder_lts(speed: float, lanes: int) -> float:
    # Metric adaptation of the revised bikeable-shoulder table.
    if speed <= 50:
        if lanes <= 3:
            return 2.0
        if lanes <= 5:
            return 2.5
        return 3.0
    if speed <= 60:
        return 3.0
    if speed < 70:
        return 3.0 if lanes <= 3 else 4.0
    return 4.0


def classify_lts(data: dict[str, Any]) -> tuple[float | None, str, str]:
    """Return ``(raw LTS score, facility type, explanation)`` for one edge."""
    facility = classify_facility(data)
    speed = infer_speed_kmh(data)
    lanes = infer_lanes(data)
    highway = _worst_highway(data)

    # Steps are a physical-access/rideability issue, not a traffic-stress class.
    if facility == "steps":
        return None, facility, "Steps are excluded from segment LTS; treat them as a separate impedance."

    if facility == "independent path":
        return 0.0, facility, "Explicit independent right-of-way."

    if facility in {"bicycle street", "shared street"}:
        return 1.0, facility, "Neighborhood greenway/shared-street treatment."

    if facility in {"dedicated cycleway", "segregated shared-use path"}:
        return 1.0, facility, "Dedicated or segregated facility; roadside buffer detail is unavailable in OSM."

    if facility in {"sidepath/separated path", "separated bike lane"}:
        if speed <= 60 and lanes <= 5:
            return 1.0, facility, "Separated facility on a lower-speed/moderate-width road."
        return 2.0, facility, "Separated facility, but adjacent traffic speed/width raises stress."

    if facility == "shared-use path":
        # Shared paths are separated from motor traffic but not necessarily from
        # pedestrians or driveway conflicts. Use LTS 2 unless explicitly segregated.
        return 2.0, facility, "Shared path; buffer and driveway frequency are not reliably tagged."

    if facility == "pedestrian zone with bicycle access":
        return 1.0 if speed <= 20 else 2.0, facility, "Pedestrian-priority area with bicycle access."

    if facility == "painted bike lane":
        score = _painted_lane_lts(speed, lanes)
        return score, facility, f"Painted lane with estimated {speed:g} km/h and {lanes} through lane(s)."

    if facility == "bikeable shoulder":
        score = _shoulder_lts(speed, lanes)
        return score, facility, f"Bikeable shoulder with estimated {speed:g} km/h and {lanes} through lane(s)."

    if facility == "shared-lane marking":
        score = max(2.0, _mixed_traffic_lts(speed, lanes, highway))
        return score, facility, f"Shared-lane marking; cyclist remains in mixed traffic at about {speed:g} km/h."

    if facility == "shared bus lane":
        if speed <= 30 and lanes <= 2:
            score = 2.5
        elif speed <= 50 and lanes <= 3:
            score = 3.0
        else:
            score = 4.0
        return score, facility, f"Shared bus lane with estimated {speed:g} km/h and {lanes} lane(s)."

    score = _mixed_traffic_lts(speed, lanes, highway)
    return score, facility, f"Mixed traffic with estimated {speed:g} km/h and {lanes} through lane(s)."


def display_group(score: float | None) -> str:
    """Name of the display group of a raw score (``Unknown`` for steps)."""
    if score is None:
        return "Unknown"
    for label, values in LTS_DISPLAY_GROUPS.items():
        if score in values:
            return label
    return "Unknown"


# ---------------------------------------------------------------------------
# Whole-graph helpers
# ---------------------------------------------------------------------------
def normalize_polygon(poly: Any) -> Any:
    """Return a single WGS84 Shapely geometry from a polygon/GeoSeries/GeoDataFrame."""
    if hasattr(poly, "geometry"):
        frame = poly
        if getattr(frame, "crs", None) is not None:
            try:
                frame = frame.to_crs(4326)
            except Exception as exc:
                raise ValueError("Could not transform the polygon to EPSG:4326.") from exc
        geometry = frame.geometry
        return geometry.union_all() if hasattr(geometry, "union_all") else geometry.unary_union

    if hasattr(poly, "crs") and hasattr(poly, "to_crs"):
        series = poly.to_crs(4326) if poly.crs is not None else poly
        return series.union_all() if hasattr(series, "union_all") else series.unary_union

    # A bare Shapely geometry has no CRS metadata. OSMnx expects longitude/latitude.
    return poly


def configure_osmnx() -> None:
    """Make OSMnx keep every tag needed by the classifier (call before downloading)."""
    ox.settings.use_cache = True
    ox.settings.log_console = True
    ox.settings.useful_tags_way = sorted(set(ox.settings.useful_tags_way) | REQUIRED_WAY_TAGS)


def annotate_graph(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Classify every edge of an OSMnx graph in place and return it.

    Adds the edge attributes ``lts_score`` (raw score, -1 for steps), ``lts``,
    ``lts_group``, ``facility_type``, ``lts_reason``, ``estimated_speed_kmh``
    and ``estimated_lanes``.
    """
    for _, _, _, data in G.edges(keys=True, data=True):
        score, facility, explanation = classify_lts(data)
        data["lts_score"] = -1.0 if score is None else float(score)
        data["lts"] = "unknown" if score is None else str(score).rstrip("0").rstrip(".")
        data["lts_group"] = display_group(score)
        data["facility_type"] = facility
        data["lts_reason"] = explanation
        data["estimated_speed_kmh"] = float(infer_speed_kmh(data))
        data["estimated_lanes"] = int(infer_lanes(data))
    return G


def largest_weak_component(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Largest weakly connected component (one-way streets do not split the network)."""
    if len(G) == 0:
        return G.copy()
    if G.is_directed():
        nodes = max(nx.weakly_connected_components(G), key=len)
    else:
        nodes = max(nx.connected_components(G), key=len)
    return G.subgraph(nodes).copy()


def summarize_lts(G: nx.MultiDiGraph) -> pd.DataFrame:
    """Number of directed edges and km per display group."""
    rows: list[dict[str, Any]] = []
    for label in [*LTS_DISPLAY_GROUPS, "Unknown"]:
        matching = [data for _, _, _, data in G.edges(keys=True, data=True) if data.get("lts_group") == label]
        rows.append({
            "lts_group": label,
            "directed_edges": len(matching),
            "directed_length_km": sum(float(data.get("length", 0.0)) for data in matching) / 1000.0,
        })
    return pd.DataFrame(rows)
