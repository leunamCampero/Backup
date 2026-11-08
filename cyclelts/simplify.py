"""Simplify an LTS network without changing its total length or LTS pattern.

OSMnx graphs contain many nodes that are not real junctions (a node every time
the street bends or a tag changes). For the metrics and the optimisation we
only need junctions and the points where the LTS level changes. The rules:

1. Work on one **undirected** ``nx.Graph``: a street that exists in both
   directions becomes one edge. When two parallel edges join the same pair of
   nodes, the **worst** (highest) LTS is kept; for equal LTS, the shortest one.
2. Keep only the **largest connected component**.
3. Remove every node of degree 2 whose two edges have the **same LTS**; the
   two edges are merged and their lengths are **added**.
4. For LTS 5 (car roads without cycling facility, 2026 only) the merged edge
   is flagged ``mandatory_upgrade_to_lts1`` if at least one of the two parts
   was flagged (logical OR); the same for ``bicycle_prohibited``.

Edge geometry is kept so the simplified network can still be drawn on a map.
"""
from __future__ import annotations

from collections import Counter, deque

import networkx as nx
from shapely.geometry import LineString


def _coordinates(G, u, v, data):
    """Points of edge u-v ordered from u to v (straight line if no geometry)."""
    geom = data.get('geometry')
    if getattr(geom, 'geom_type', None) == 'LineString':
        points = list(geom.coords)
        if points:
            start = (float(G.nodes[u]['x']), float(G.nodes[u]['y']))
            if sum((points[-1][i]-start[i])**2 for i in (0, 1)) < sum((points[0][i]-start[i])**2 for i in (0, 1)):
                points.reverse()
            return points
    return [(float(G.nodes[u]['x']), float(G.nodes[u]['y'])), (float(G.nodes[v]['x']), float(G.nodes[v]['y']))]


def _edge_data(d):
    """Copy of edge attributes with integer ``key``/``lts`` and ``distance`` in metres."""
    e = dict(d)
    level = int(e.get('lts', e.get('key')))
    e['key'] = e['lts'] = level
    e['distance'] = float(e.get('distance', e.get('length', 0.0)))
    e['length'] = e['distance']
    if level == 5:
        e['mandatory_upgrade_to_lts1'] = bool(e.get('mandatory_upgrade_to_lts1', False))
    else:
        e['mandatory_upgrade_to_lts1'] = False
    return e


def _choose_parallel(a, b):
    """Between two parallel edges keep the worst LTS (shortest if equal LTS)."""
    chosen = dict(b if (b['key'] > a['key'] or (b['key'] == a['key'] and b['distance'] < a['distance'])) else a)
    if a['key'] == b['key'] == 5:
        # Do not lose a mandatory flag when dropping a parallel alternative.
        chosen['mandatory_upgrade_to_lts1'] = bool(a.get('mandatory_upgrade_to_lts1') or b.get('mandatory_upgrade_to_lts1'))
        chosen['bicycle_prohibited'] = bool(a.get('bicycle_prohibited') or b.get('bicycle_prohibited'))
        chosen['high_stress_car_road'] = bool(a.get('high_stress_car_road') or b.get('high_stress_car_road'))
    return chosen


def simplify_lts_graph(G, lts_attr='key'):
    """Return a connected ``nx.Graph`` with all same-LTS degree-2 nodes removed.

    ``G`` can be a MultiDiGraph (OSMnx) or a Graph whose edges carry an integer
    LTS in ``key``/``lts`` (1-4 for cycling, 5 for car roads) and a length in
    ``distance`` or ``length`` (metres).

    The result never has parallel edges. If contracting a node creates an edge
    a-b that already exists, the "worst LTS, then shortest" rule is applied
    again; such collisions are counted in ``H.graph`` and may slightly change
    the total retained length.
    """
    H = nx.Graph()
    H.add_nodes_from((n, dict(attrs)) for n, attrs in G.nodes(data=True))
    H.graph.update(G.graph)
    edges = G.edges(keys=True, data=True) if G.is_multigraph() else ((u, v, None, d) for u, v, d in G.edges(data=True))
    parallel_collisions = 0
    for u, v, _, d in edges:
        if u == v:
            continue
        e = _edge_data(d)
        if e['key'] not in (1, 2, 3, 4, 5):
            continue
        if H.has_edge(u, v):
            parallel_collisions += 1
            H[u][v].update(_choose_parallel(dict(H[u][v]), e))
        else:
            H.add_edge(u, v, **e)
    H.remove_nodes_from(list(nx.isolates(H)))
    if H.number_of_nodes() and not nx.is_connected(H):
        H = H.subgraph(max(nx.connected_components(H), key=len)).copy()
    before_nodes, before_edges = H.number_of_nodes(), H.number_of_edges()
    # Queue of degree-2 nodes (avoids scanning the whole graph after each merge).
    q = deque(n for n in H.nodes if H.degree(n) == 2)
    contracted = 0
    created_parallel = 0
    while q:
        n = q.popleft()
        if n not in H or H.degree(n) != 2:
            continue
        a, b = list(H.neighbors(n))
        if a == b:
            continue
        e1, e2 = dict(H[a][n]), dict(H[n][b])
        if e1['key'] != e2['key']:
            continue  # the LTS changes at n: keep the node
        merged = dict(e1)
        merged['distance'] = merged['length'] = e1['distance'] + e2['distance']
        merged['lts'] = merged['key'] = e1['key']
        if merged['key'] == 5:
            merged['mandatory_upgrade_to_lts1'] = bool(e1.get('mandatory_upgrade_to_lts1') or e2.get('mandatory_upgrade_to_lts1'))
            merged['bicycle_prohibited'] = bool(e1.get('bicycle_prohibited') or e2.get('bicycle_prohibited'))
            merged['high_stress_car_road'] = bool(e1.get('high_stress_car_road') or e2.get('high_stress_car_road'))
            merged['optimization_candidate'] = bool(e1.get('optimization_candidate', True) and e2.get('optimization_candidate', True)) and not merged['bicycle_prohibited']
            merged['target_lts'] = 1 if merged['mandatory_upgrade_to_lts1'] else None
        else:
            merged['mandatory_upgrade_to_lts1'] = False
        merged['geometry'] = LineString(_coordinates(H, a, n, e1)+_coordinates(H, n, b, e2)[1:])
        prior = dict(H[a][b]) if H.has_edge(a, b) else None
        H.remove_node(n)
        if prior is not None:
            created_parallel += 1
            merged = _choose_parallel(prior, merged)
        H.add_edge(a, b, **merged)
        contracted += 1
        for candidate in (a, b):
            if H.degree(candidate) == 2:
                q.append(candidate)
    H.graph.update(degree2_contracted=contracted, nodes_before_contraction=before_nodes,
                   edges_before_contraction=before_edges, parallel_collisions=parallel_collisions,
                   contractions_with_existing_direct_edge=created_parallel,
                   simplification_rule='worst parallel, equal-LTS degree2, summed distance, largest connected component')
    assert type(H) is nx.Graph
    assert H.number_of_nodes() == 0 or nx.is_connected(H)
    assert not any(H.degree(n) == 2 and len({H[n][m]['key'] for m in H.neighbors(n)}) == 1 for n in H)
    return H


def check_graph(H, verbose=True):
    """Sanity checks of a simplified graph; returns (and prints) a summary dict."""
    same_lts_degree2 = sum(H.degree(n) == 2 and len({H[n][m]['key'] for m in H.neighbors(n)}) == 1 for n in H)
    result = {'nodes': H.number_of_nodes(), 'edges': H.number_of_edges(), 'multigraph': H.is_multigraph(),
              'connected': nx.is_connected(H) if len(H) else False,
              'remaining_contractible_degree2_nodes': same_lts_degree2,
              'lts_counts': dict(Counter(d['key'] for _, _, d in H.edges(data=True))),
              'mandatory_lts5_edges': sum(d['key'] == 5 and bool(d.get('mandatory_upgrade_to_lts1')) for _, _, d in H.edges(data=True))}
    if verbose:
        print(result)
    return result
