"""Robust OpenStreetMap downloads with OSMnx: long timeouts, retries, several mirrors.

OpenStreetMap data is downloaded through the *Overpass API*. Overpass can also
return the map **as it was at a past date** (``[date:"2019-12-31T23:59:59Z"]``),
which is how the historical networks 2017-2022 are rebuilt.

Why this module exists
----------------------
* OSMnx fills ``[timeout:{timeout}]`` with the SAME number it uses as the HTTP
  read timeout. With 120 s the client hangs up at the exact moment the server
  is still working, so a slow (busy) server always ends in ``ReadTimeout``.
  Here the server gets ``server_timeout`` and the client waits 120 s longer.
* OSMnx asks ``<endpoint>/status`` before every query. A ReadTimeout on that
  call is not caught by OSMnx, and some mirrors answer it slowly or not at all,
  so the rate-limit check is switched off here.
* If one mirror fails, wait and try the next one instead of crashing the cell.

Downloads are cached on disk (``cache_folder``), so running a notebook twice
does not download the same data twice.
"""
from __future__ import annotations

import time
from contextlib import contextmanager

import osmnx as ox

# Public Overpass servers that accept normal OSMnx queries. All three also
# accept historical ([date:"..."]) queries. Order = order tried.
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api",
    "https://overpass.private.coffee/api",
    "https://overpass.kumi.systems/api",
]


@contextmanager
def _settings(**values):
    """Temporarily change ``osmnx.settings`` and restore them afterwards."""
    old = {k: getattr(ox.settings, k) for k in values}
    try:
        for k, v in values.items():
            setattr(ox.settings, k, v)
        yield
    finally:
        for k, v in old.items():
            setattr(ox.settings, k, v)


def download_graph(polygon, network_type, *, date=None, server_timeout=600,
                   endpoints=None, attempts_per_endpoint=2, wait_seconds=30,
                   cache_folder=None, **graph_kwargs):
    """``ox.graph.graph_from_polygon`` with retries across Overpass mirrors.

    Parameters
    ----------
    polygon : shapely geometry in WGS84 (longitude/latitude)
    network_type : ``"bike"`` (streets usable by bike) or ``"drive"`` (car roads)
    date : ISO timestamp such as ``"2022-12-31T23:59:59Z"`` for a historical
        snapshot, or ``None`` for the current OSM data.
    server_timeout : seconds the Overpass server may work on the query.
    endpoints : list of Overpass URLs to try in order (default: OVERPASS_ENDPOINTS).
    cache_folder : folder of the OSMnx HTTP cache for this query.

    Returns
    -------
    networkx.MultiDiGraph as produced by OSMnx (one edge per street direction).
    """
    date_part = f'[date:"{date}"]' if date else ""
    overpass_settings = f"[out:json][timeout:{int(server_timeout)}]{date_part}{{maxsize}}"
    kwargs = dict(simplify=True, retain_all=True, truncate_by_edge=True)
    kwargs.update(graph_kwargs)
    tried = []
    for endpoint in (endpoints or OVERPASS_ENDPOINTS):
        for attempt in range(1, attempts_per_endpoint + 1):
            values = dict(
                overpass_url=endpoint.rstrip("/"),
                overpass_settings=overpass_settings,
                requests_timeout=int(server_timeout) + 120,
                overpass_rate_limit=False,
                use_cache=True,
            )
            if cache_folder is not None:
                values["cache_folder"] = str(cache_folder)
            print(f"[overpass] {network_type} | {endpoint} | attempt {attempt} | "
                  f"server timeout {server_timeout}s | date={date or 'current'}", flush=True)
            t0 = time.time()
            try:
                with _settings(**values):
                    G = ox.graph.graph_from_polygon(polygon, network_type=network_type, **kwargs)
                print(f"[overpass] OK in {time.time() - t0:.0f}s: "
                      f"{G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges", flush=True)
                return G
            except KeyboardInterrupt:
                raise
            except Exception as exc:  # timeouts, 429/504, empty responses ...
                msg = f"{type(exc).__name__}: {str(exc)[:200]}"
                tried.append(f"{endpoint} #{attempt}: {msg}")
                print(f"[overpass] failed after {time.time() - t0:.0f}s -> {msg}", flush=True)
                time.sleep(wait_seconds)
    raise RuntimeError("All Overpass endpoints failed:\n  " + "\n  ".join(tried))
