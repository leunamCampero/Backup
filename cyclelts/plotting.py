"""Interactive Plotly maps of LTS networks (no Matplotlib).

Colours: green = LTS 1, light green = LTS 2, orange = LTS 3, red = LTS 4,
grey = LTS 5 (car road, planning layer), purple = LTS 5 that must be upgraded
to LTS 1 if it is ever selected, blue = edge upgraded by an optimisation.

The simplified networks are drawn as straight lines between their remaining
nodes ("topology view"), which is how the algorithms see the network.
"""
from __future__ import annotations

import math

import networkx as nx
import plotly.graph_objects as go
from plotly.subplots import make_subplots

LTS_COLORS = {1: '#2ca25f', 2: '#99d8c9', 3: '#fdae61', 4: '#d73027', 5: '#808080', 6: '#8e44ad'}


def _aspect(G):
    """y/x scale ratio so that longitude/latitude maps are not distorted."""
    lat = sum(float(d['y']) for _, d in G.nodes(data=True)) / max(len(G), 1)
    return 1 / max(math.cos(math.radians(lat)), 0.01)


def plot_topology(H, show_nodes=False, title='Simplified topology (endpoint edges; not road geometry)', show=True):
    """Draw a simplified LTS graph, one colour per LTS level."""
    groups = {i: ([], []) for i in LTS_COLORS}
    for u, v, d in H.edges(data=True):
        level = int(d.get('key', d.get('lts')))
        category = 6 if level == 5 and d.get('mandatory_upgrade_to_lts1') else level
        xx, yy = groups[category]
        xx.extend([H.nodes[u]['x'], H.nodes[v]['x'], None])
        yy.extend([H.nodes[u]['y'], H.nodes[v]['y'], None])
    fig = go.Figure()
    for category in [5, 6, 4, 3, 2, 1]:
        x, y = groups[category]
        if x:
            fig.add_trace(go.Scattergl(x=x, y=y, mode='lines', line=dict(color=LTS_COLORS[category], width=1.6),
                                       name={5: 'LTS5', 6: 'LTS5 mandatory'}.get(category, f'LTS {category}')))
    if show_nodes:
        fig.add_trace(go.Scattergl(x=[d['x'] for _, d in H.nodes(data=True)], y=[d['y'] for _, d in H.nodes(data=True)],
                                   mode='markers', marker=dict(size=2, color='#202020'), name='Remaining nodes'))
    fig.update_layout(width=1000, height=800, template='plotly_white', title=title,
                      yaxis=dict(scaleanchor='x', scaleratio=_aspect(H)))
    if show:
        fig.show()
    return fig


# ---------------------------------------------------------------------------
# 2026: before vs after simplification
# ---------------------------------------------------------------------------
STYLE = {  # category: (label, color, width)
    1: ("LTS 1", "#1a9850", 2.0),
    2: ("LTS 2", "#91cf60", 2.0),
    3: ("LTS 3", "#fc8d59", 2.0),
    4: ("LTS 4", "#d73027", 2.4),
    "5m": ("LTS 5 – must upgrade to LTS 1", "#7b3294", 3.0),
    "5p": ("LTS 5 – cycling prohibited", "#404040", 1.6),
    "5o": ("LTS 5 – other car road", "#a6a6a6", 1.6),
}


def _category(d):
    lts = int(d.get("key", d.get("lts")))
    if lts < 5:
        return lts
    if d.get("mandatory_upgrade_to_lts1"):
        return "5m"
    return "5p" if d.get("bicycle_prohibited") else "5o"


def _undirected_edges(G):
    """One entry per node pair (works for MultiDiGraph and Graph)."""
    seen = {}
    for u, v, d in G.edges(data=True):
        if int(d.get("key", d.get("lts", 0))) not in (1, 2, 3, 4, 5):
            continue
        seen.setdefault(frozenset((u, v)), (u, v, d))
    return list(seen.values())


def _add_graph(fig, G, col, show_legend):
    xs = {c: [] for c in STYLE}
    ys = {c: [] for c in STYLE}
    hx, hy, htext = [], [], []
    for u, v, d in _undirected_edges(G):
        c = _category(d)
        x0, y0, x1, y1 = G.nodes[u]["x"], G.nodes[u]["y"], G.nodes[v]["x"], G.nodes[v]["y"]
        xs[c] += [x0, x1, None]
        ys[c] += [y0, y1, None]
        hx.append((x0 + x1) / 2)
        hy.append((y0 + y1) / 2)
        htext.append(f"{STYLE[c][0]}<br>length {float(d.get('distance', d.get('length', 0))):.0f} m")
    for c in ["5o", "5p", 1, 2, 3, 4, "5m"]:          # LTS 5 below, upgrades on top
        if xs[c]:
            label, color, width = STYLE[c]
            fig.add_trace(go.Scattergl(x=xs[c], y=ys[c], mode="lines", name=label, legendgroup=str(c),
                                       showlegend=show_legend, line=dict(color=color, width=width),
                                       hoverinfo="skip"), row=1, col=col)
    # invisible points at edge midpoints so you can hover an edge and read its LTS and length
    fig.add_trace(go.Scattergl(x=hx, y=hy, mode="markers", marker=dict(size=6, opacity=0),
                               text=htext, hoverinfo="text", showlegend=False), row=1, col=col)
    # nodes: degree-2 nodes left after simplification should all sit where the LTS changes
    U = nx.Graph()
    U.add_edges_from((u, v) for u, v, _ in _undirected_edges(G))
    deg2 = [n for n in U if U.degree(n) == 2]
    other = [n for n in U if U.degree(n) != 2]
    fig.add_trace(go.Scattergl(x=[G.nodes[n]["x"] for n in other], y=[G.nodes[n]["y"] for n in other],
                               mode="markers", marker=dict(size=3, color="black"), name="Junction / dead end",
                               legendgroup="nodes", showlegend=show_legend, hoverinfo="skip"), row=1, col=col)
    fig.add_trace(go.Scattergl(x=[G.nodes[n]["x"] for n in deg2], y=[G.nodes[n]["y"] for n in deg2],
                               mode="markers", marker=dict(size=5, color="#00a6d6"), name="Degree-2 node",
                               legendgroup="deg2", showlegend=show_legend, hoverinfo="skip"), row=1, col=col)
    return U.number_of_nodes(), U.number_of_edges(), len(deg2)


def plot_before_after(G_before, G_after, title="Grenoble 2026", show=True):
    """Side-by-side map of a network before and after simplification."""
    fig = make_subplots(rows=1, cols=2, shared_xaxes=True, shared_yaxes=True, horizontal_spacing=0.02,
                        subplot_titles=["Before simplification", "After simplification"])
    nb, eb, db = _add_graph(fig, G_before, 1, show_legend=True)
    na, ea, da = _add_graph(fig, G_after, 2, show_legend=False)
    fig.layout.annotations[0].text = f"Before: {nb:,} nodes, {eb:,} edges, {db:,} degree-2 nodes"
    fig.layout.annotations[1].text = f"After: {na:,} nodes, {ea:,} edges, {da:,} degree-2 nodes"
    ratio = _aspect(G_after)
    fig.update_yaxes(scaleanchor="x", scaleratio=ratio, row=1, col=1)
    fig.update_yaxes(scaleanchor="x2", scaleratio=ratio, row=1, col=2)
    fig.update_xaxes(showticklabels=False)
    fig.update_yaxes(showticklabels=False)
    fig.update_layout(title=title + " – bike LTS 1–4 + car roads LTS 5 (straight lines between nodes)",
                      width=1500, height=800, template="plotly_white",
                      legend=dict(orientation="h", y=-0.03), margin=dict(l=10, r=10, t=70, b=10))
    if show:
        fig.show()
    return fig


def leftover_degree2(G):
    """Check: every degree-2 node left after simplification must separate two different LTS."""
    bad = [n for n in G if G.degree(n) == 2 and len({G[n][m]["key"] for m in G.neighbors(n)}) == 1]
    kept = sum(G.degree(n) == 2 for n in G)
    print(f"Degree-2 nodes kept: {kept:,} (all because the LTS changes there) | wrongly kept: {len(bad)}")
    return len(bad)


# ---------------------------------------------------------------------------
# Optimisation results
# ---------------------------------------------------------------------------
def plot_solutions(graphs, names, show=True):
    """Side-by-side maps of several networks; upgraded edges are drawn in blue."""
    fig = make_subplots(rows=1, cols=len(graphs), subplot_titles=names, horizontal_spacing=0.02)
    palette = {1: "#2ca25f", 2: "#99d8c9", 3: "#fdae61", 4: "#d73027", 5: "#a0a0a0", 6: "#8e44ad", 7: "#1765c1"}
    labels = {1: "LTS 1", 2: "LTS 2", 3: "LTS 3", 4: "LTS 4", 5: "LTS 5", 6: "LTS5 mandatory", 7: "Upgraded to LTS1"}
    for col, H in enumerate(graphs, 1):
        groups = {k: ([], []) for k in palette}
        for u, v, d in H.edges(data=True):
            level = int(d.get("key", d.get("lts")))
            c = 7 if d.get("upgraded", False) else 6 if level == 5 and d.get("mandatory_upgrade_to_lts1", False) else level
            X, Y = groups[c]
            X.extend([H.nodes[u]["x"], H.nodes[v]["x"], None])
            Y.extend([H.nodes[u]["y"], H.nodes[v]["y"], None])
        for k in (5, 6, 4, 3, 2, 1, 7):
            X, Y = groups[k]
            if X:
                fig.add_trace(go.Scattergl(x=X, y=Y, mode="lines", name=labels[k], legendgroup=str(k),
                                           showlegend=(col == 1),
                                           line=dict(color=palette[k], width=2.8 if k == 7 else 1.3),
                                           hoverinfo="skip"), row=1, col=col)
    fig.update_layout(template="plotly_white", height=630, width=1450,
                      title=" vs ".join(names) + " — simplified topology", legend=dict(orientation="h", y=-0.08))
    fig.update_xaxes(showticklabels=False)
    fig.update_yaxes(showticklabels=False)
    if show:
        fig.show()
    return fig
