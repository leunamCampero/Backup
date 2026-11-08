"""Project folders, the studied cities, and small loading helpers.

All paths are computed from the location of this file, so the notebooks work
on any computer without editing paths, wherever the repository is cloned.

Folder layout::

    <repo>/
      data/                         inputs (small ones are in git)
        city_polygons.geojson       official boundary of each studied commune
        insee_raw/NAV2A_<year>/     raw INSEE census tables (download, not in git)
        insee_modal_shares/         commuting mode shares per city (step 2 output)
      results/
        lts_networks/<city>/<run>/  yearly LTS networks and their metrics (step 1)
        calibration/                infrastructure -> bike-share model (step 3)
        ga_vs_mlcc/                 MLCC vs genetic algorithm (step 4)
        mlcc_lookup/                budget -> network -> bike share table (step 5)
        order_of_magnitude/         comparison with a first-order model (step 6)
        backcasting/                2026-2050 investment plans (step 7)
"""
from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
RESULTS_DIR = REPO_ROOT / "results"

CITY_POLYGONS = DATA_DIR / "city_polygons.geojson"
INSEE_RAW_DIR = DATA_DIR / "insee_raw"
INSEE_SHARES_DIR = DATA_DIR / "insee_modal_shares"

LTS_DIR = RESULTS_DIR / "lts_networks"
CALIBRATION_DIR = RESULTS_DIR / "calibration"
GA_VS_MLCC_DIR = RESULTS_DIR / "ga_vs_mlcc"
LOOKUP_DIR = RESULTS_DIR / "mlcc_lookup"
ORDER_OF_MAGNITUDE_DIR = RESULTS_DIR / "order_of_magnitude"
BACKCASTING_DIR = RESULTS_DIR / "backcasting"

# Name of the run folder used for every result in the repository.
# A new name = a completely fresh download (see notebooks/01_build_lts_networks.ipynb).
DEFAULT_RUN = "fresh_2026-10-21"

# Years of the study: historical OpenStreetMap snapshots (31 December of each
# year) and the "current" network, downloaded in 2026.
HISTORICAL_YEARS = list(range(2017, 2023))
CURRENT_YEAR = 2026
ALL_YEARS = HISTORICAL_YEARS + [CURRENT_YEAR]


# ---------------------------------------------------------------------------
# Cities
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class City:
    """One French commune of the study.

    name : official name, exactly as in the commune boundary file
    insee : 5-digit INSEE commune code (``CODGEO`` in INSEE tables)
    """

    name: str
    insee: str

    @property
    def slug(self) -> str:
        """Lower-case name used in file and folder names (accents are kept)."""
        return self.name.lower().replace(" ", "_").replace("'", "")


#: The 11 cities used to calibrate the infrastructure -> bike-share model.
CITIES = [
    City("Angers", "49007"),
    City("Annecy", "74010"),
    City("Bordeaux", "33063"),
    City("Chambéry", "73065"),
    City("Grenoble", "38185"),
    City("Lyon", "69123"),
    City("Nantes", "44109"),
    City("Paris", "75056"),
    City("Rennes", "35238"),
    City("Strasbourg", "67482"),
    City("Tours", "37261"),
]

#: Extra commune with INSEE data but no LTS network (not used in the model).
EXTRA_CITIES = [City("Nancy", "54395")]


def get_city(name: str) -> City:
    """Return the :class:`City` called ``name`` (case-insensitive)."""
    for city in CITIES + EXTRA_CITIES:
        if city.name.lower() == name.lower() or city.slug == name.lower():
            return city
    raise KeyError(f"Unknown city {name!r}. Known: {[c.name for c in CITIES + EXTRA_CITIES]}")


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------
def load_city_polygon(name: str, insee: str | None = None, communes_file: str | Path | None = None):
    """Return the boundary of a commune as a Shapely (Multi)Polygon in WGS84.

    By default the polygon is read from ``data/city_polygons.geojson`` (the 11
    studied cities + Nancy). For any other French commune, pass the full
    ``communes-20220101.json`` file (OpenStreetMap French communes export, see
    ``data/README.md``) as ``communes_file``. ``insee`` is only needed when
    several communes share the same name.
    """
    from shapely.geometry import shape

    path = Path(communes_file) if communes_file else CITY_POLYGONS
    with path.open("r", encoding="utf-8") as f:
        features = json.load(f)["features"]
    matches = [
        feat for feat in features
        if feat["properties"].get("nom") == name
        and (insee is None or str(feat["properties"].get("insee")) == str(insee))
    ]
    if not matches:
        raise ValueError(f"No commune named {name!r} in {path.name} (check spelling/accents, "
                         "or pass communes_file= for a city that is not in the study)")
    if len(matches) > 1:
        codes = [m["properties"].get("insee") for m in matches]
        raise ValueError(f"{len(matches)} communes are named {name!r}; pass insee= one of {codes}")
    poly = shape(matches[0]["geometry"])
    if not poly.is_valid:
        poly = poly.buffer(0)  # repairs self-intersections without moving the boundary
    if poly.is_empty:
        raise ValueError("The selected city polygon is empty")
    return poly


def save_pickle(obj, path: str | Path) -> Path:
    """Save ``obj`` with pickle, creating the parent folder if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
    return path


def load_pickle(path: str | Path):
    """Load a pickle file. Only open pickle files you created yourself."""
    with Path(path).open("rb") as f:
        return pickle.load(f)


def run_dir(city: str, run: str = DEFAULT_RUN) -> Path:
    """Folder holding the yearly LTS networks of ``city`` for one run."""
    return LTS_DIR / get_city(city).slug / run


def simplified_graph_path(city: str, year: int, run: str = DEFAULT_RUN) -> Path:
    """Path of the simplified LTS network of ``city`` in ``year`` (step 1 output)."""
    slug = get_city(city).slug
    return run_dir(city, run) / str(year) / f"{slug}_lts_{year}_SIMPLE.pkl"


def load_simplified_graph(city: str, year: int, run: str = DEFAULT_RUN):
    """Load the simplified LTS network of ``city`` in ``year``."""
    path = simplified_graph_path(city, year, run)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Build it with notebooks/01_build_lts_networks.ipynb "
            "(only the Grenoble networks are shipped in the repository).")
    return load_pickle(path)


def grenoble_graph(year: int = CURRENT_YEAR, run: str = DEFAULT_RUN):
    """Shortcut for the simplified Grenoble network (used by steps 4-6)."""
    return load_simplified_graph("Grenoble", year, run)


def metrics_file(city: str, run: str = DEFAULT_RUN) -> Path:
    """CSV with the yearly infrastructure metrics of ``city`` (step 1 output)."""
    slug = get_city(city).slug
    return run_dir(city, run) / f"{slug}_2017_2022_2026_SIMPLIFIED_metrics.csv"
