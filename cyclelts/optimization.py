"""Steps 4-6 - where to invest: upgrade streets to LTS 1 under a budget.

The decision
------------
Every street of the 2026 network with LTS 2, 3, 4 or 5 can be upgraded
**directly to LTS 1** (for example by building a protected cycle track). The
cost is ``length (m) x cost per metre of its current LTS``. LTS 5 roads where
cycling is prohibited (motorways, ``bicycle=no``) cannot be upgraded. A plan is
a yes/no choice for every eligible edge (a "chromosome").

Two algorithms
--------------
**MLCC** (*Maximise the Largest Connected Component*), a greedy heuristic:

1. *Connect LTS 1 islands.* While the LTS 1 network has two or more pieces,
   upgrade the shortest physical path joining the two longest pieces.
2. *Expand outward*, threshold by threshold (gamma = 2, 3, 4, 5): take the
   longest connected piece of the network with LTS <= gamma that still has
   non-LTS 1 edges, connect it to the main LTS 1 piece by the shortest path,
   then upgrade its edges in order of distance from the connection point.
3. Stop at the **first edge that does not fit in the budget**.

**Genetic algorithm (GA)**: a population of plans evolves by tournament
selection, uniform crossover and bit-flip mutation; the fitness is the
predicted bike share; plans over budget are repaired by randomly dropping
edges. The MLCC plan is put in the first generation, so the GA can only do
at least as well as MLCC. No global optimality is claimed for either method.

Both use exactly the same metrics and mode-share model as the calibration
(:class:`cyclelts.mode_share.CityShareModel`).
"""
from __future__ import annotations

import numpy as np
import networkx as nx
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra as sparse_dijkstra

from .metrics import edge_length_m as meters
from .metrics import edge_level as level

#: Cost (EUR per metre) of upgrading an edge from its LTS to LTS 1, used by the
#: GA vs MLCC comparison (step 4).
COSTS_GA_COMPARISON = {1: 0.0, 2: 175.0, 3: 225.0, 4: 240.0, 5: 250.0}

#: Cost scenario of the lookup table (step 5), inspired by 2023 French
#: public-works prices (higher than the scenario above).
COSTS_LOOKUP = {1: 0.0, 2: 200.0, 3: 415.0, 4: 590.0, 5: 750.0}


def eligible(d):
    """Can this edge be upgraded? (LTS > 1 and not a prohibited LTS 5 road)."""
    return level(d) > 1 and not (level(d) == 5 and
                                 (bool(d.get("bicycle_prohibited", False)) or d.get("optimization_candidate") is False))


def threshold_graph(H, gamma):
    """Sub-network of the edges with LTS <= gamma (lengths only)."""
    T = nx.Graph()
    T.add_edges_from((u, v, {"distance": meters(d)}) for u, v, d in H.edges(data=True) if level(d) <= gamma)
    return T


def components_by_length(T):
    """Connected components, longest (total edge length) first."""
    comps = list(nx.connected_components(T))
    if not comps:
        return []
    membership = {node: i for i, nodes in enumerate(comps) for node in nodes}
    lengths = [0.0]*len(comps)
    for u, v, d in T.edges(data=True):    # one pass over the edges (fast with many islands)
        lengths[membership[u]] += d["distance"]
    return [comps[i] for i in sorted(range(len(comps)), key=lambda i: lengths[i], reverse=True)]


def ordered_edges(T, component, anchor):
    """Edges of ``component`` sorted by distance from ``anchor`` (closest first)."""
    S = T.subgraph(component)
    if anchor not in S:
        anchor = next(iter(component))
    dist = nx.single_source_dijkstra_path_length(S, anchor, weight="distance")
    return sorted(S.edges(), key=lambda e: (min(dist.get(e[0], float('inf')), dist.get(e[1], float('inf'))), str(e)))


class UpgradeProblem:
    """A network, upgrade costs and the model that scores a network.

    Parameters
    ----------
    G : simplified 2026 network (connected ``nx.Graph``), never modified
    cost_to_lts1 : ``{lts: EUR per metre}`` to upgrade an edge of that LTS to LTS 1
    model : :class:`cyclelts.mode_share.CityShareModel`

    Attributes
    ----------
    gene_edges : eligible edges, in a fixed order (= positions of a chromosome)
    edge_costs : upgrade cost (EUR) of each eligible edge
    """

    def __init__(self, G, cost_to_lts1, model):
        assert type(G) is nx.Graph and nx.is_connected(G), "Expected connected, undirected simple nx.Graph"
        self.G, self.cost_to_lts1, self.model = G, dict(cost_to_lts1), model
        self.gene_edges = [(u, v) for u, v, d in G.edges(data=True) if eligible(d)]
        self.gene_index = {frozenset((u, v)): i for i, (u, v) in enumerate(self.gene_edges)}
        self.edge_costs = np.array([meters(G[u][v])*self.cost_to_lts1[level(G[u][v])] for u, v in self.gene_edges], dtype=float)
        assert np.all(self.edge_costs >= 0)
        # Physical distances do not change when an edge is upgraded, so the
        # routing matrix is built once (sparse Dijkstra is much faster than networkx).
        self._nodes = list(G.nodes())
        self._node_index = {node: i for i, node in enumerate(self._nodes)}
        ii, jj, dd = [], [], []
        for u, v, d in G.edges(data=True):
            i, j = self._node_index[u], self._node_index[v]
            ii.extend((i, j))
            jj.extend((j, i))
            dd.extend((meters(d), meters(d)))
        self._routing = csr_matrix((dd, (ii, jj)), shape=(len(self._nodes), len(self._nodes)))

    # ----- budget ------------------------------------------------------------
    @property
    def full_cost_all(self):
        """Theoretical cost of upgrading every LTS 2-5 edge (prohibited ones included)."""
        return sum(meters(d)*self.cost_to_lts1[level(d)] for _, _, d in self.G.edges(data=True))

    @property
    def full_cost_eligible(self):
        """Cost of upgrading every eligible edge."""
        return float(self.edge_costs.sum())

    def chromosome_cost(self, chromosome):
        return float(self.edge_costs[np.asarray(chromosome, dtype=bool)].sum())

    def to_graph(self, chromosome, algorithm="GA"):
        """Copy of G with the selected edges upgraded to LTS 1 (and flagged ``upgraded``)."""
        H = self.G.copy()
        for u, v, d in H.edges(data=True):
            d["original_lts"] = level(d)
            d["original_mandatory_upgrade_to_lts1"] = bool(d.get("mandatory_upgrade_to_lts1", False))
            d["upgraded"] = False
            d["upgrade_cost_eur"] = 0.0
        for selected, (u, v), cost in zip(chromosome, self.gene_edges, self.edge_costs):
            if selected:
                d = H[u][v]
                d["key"] = 1
                d["lts"] = 1
                d["upgraded"] = True
                d["upgrade_cost_eur"] = float(cost)
                d["upgrade_algorithm"] = algorithm
        return H

    def selected_edges_table(self, chromosome):
        """One row per selected edge: LTS before, length, cost."""
        rows = []
        for i, (u, v) in enumerate(self.gene_edges):
            if chromosome[i]:
                d = self.G[u][v]
                rows.append({"u": u, "v": v, "original_lts": level(d), "target_lts": 1,
                             "length_m": meters(d), "cost_eur": float(self.edge_costs[i]),
                             "original_mandatory_upgrade_to_lts1": bool(d.get("mandatory_upgrade_to_lts1", False))})
        return pd.DataFrame(rows, columns=["u", "v", "original_lts", "target_lts", "length_m", "cost_eur",
                                           "original_mandatory_upgrade_to_lts1"])

    # ----- MLCC -------------------------------------------------------------
    def shortest_connector(self, sources, targets):
        """Shortest physical path (list of nodes) from any source to any target node."""
        sources = set(sources)
        targets = set(targets)
        if not sources or not targets:
            return None
        common = sources & targets
        if common:
            return [next(iter(common))]
        si = np.fromiter((self._node_index[x] for x in sources), dtype=int)
        ti = np.fromiter((self._node_index[x] for x in targets), dtype=int)
        distances, predecessors, _ = sparse_dijkstra(self._routing, directed=False, indices=si,
                                                     min_only=True, return_predecessors=True)
        best = ti[np.argmin(distances[ti])]
        if not np.isfinite(distances[best]):
            return None
        route = [int(best)]
        for _ in range(len(self._nodes)):
            if route[-1] in si:
                break
            prev = int(predecessors[route[-1]])
            if prev < 0:
                raise RuntimeError("Sparse Dijkstra path reconstruction failed")
            route.append(prev)
        else:
            raise RuntimeError("Predecessor cycle")
        return [self._nodes[x] for x in reversed(route)]

    def run_mlcc(self, H_start=None, budget_eur=0.0, max_iterations=20000, verbose=False):
        """Run MLCC from network ``H_start`` (default: G) with ``budget_eur``.

        Returns ``(chromosome, upgraded network, state)``; ``state`` holds the
        money spent, the reason for stopping and a log of every upgrade.
        """
        H = (self.G if H_start is None else H_start).copy()
        selected = np.zeros(len(self.gene_edges), dtype=bool)
        state = {"spent_budget": 0.0, "stop_reason": "completed", "log": []}

        def apply(edges, phase):
            # Upgrade one edge at a time; stop at the first unaffordable edge.
            for u, v in edges:
                if level(H[u][v]) == 1:
                    continue
                idx = self.gene_index.get(frozenset((u, v)))
                if idx is None:
                    state["stop_reason"] = f"Ineligible edge {u}-{v} (e.g. cycling prohibited)"
                    return False
                cost = float(self.edge_costs[idx])
                if state["spent_budget"]+cost > budget_eur+1e-7:
                    state["stop_reason"] = f"Insufficient budget for edge {u}-{v}"
                    return False
                old = level(H[u][v])
                selected[idx] = True
                H[u][v]["key"] = H[u][v]["lts"] = 1
                state["spent_budget"] += cost
                state["log"].append({"phase": phase, "u": u, "v": v, "from_lts": old, "to_lts": 1,
                                     "cost_eur": cost, "cumulative_eur": state["spent_budget"]})
            return True

        # Phase 1: connect the LTS 1 islands, longest two first
        for iteration in range(max_iterations):
            if verbose and iteration % 50 == 0:
                print(f"MLCC phase LTS1 connection {iteration}, spent €{state['spent_budget']:,.0f}", flush=True)
            comps = components_by_length(threshold_graph(H, 1))
            if len(comps) < 2:
                break
            path = self.shortest_connector(comps[0], comps[1])
            if path is None or not apply(list(zip(path, path[1:])), "LTS1_connect"):
                state["iterations"] = iteration
                return selected, H, state
        else:
            raise RuntimeError("MLCC phase1 iteration cap reached")
        # Phase 2: expand outward through LTS <= 2, 3, 4, 5 components
        for gamma in (2, 3, 4, 5):
            for iteration in range(max_iterations):
                T = threshold_graph(H, gamma)
                comps = components_by_length(T)
                candidates = [nodes for nodes in comps if any(level(H[u][v]) > 1 for u, v in T.subgraph(nodes).edges())]
                if not candidates:
                    break
                target = candidates[0]
                ones = components_by_length(threshold_graph(H, 1))
                source = ones[0] if ones else set()
                overlap = set(source) & set(target)
                if overlap:
                    anchor = next(iter(overlap))
                elif not source:
                    anchor = next(iter(target))
                else:
                    path = self.shortest_connector(source, target)
                    if path is None or not apply(list(zip(path, path[1:])), f"LTS{gamma}_connect"):
                        state["iterations"] = iteration
                        return selected, H, state
                    anchor = path[-1]
                if not apply(ordered_edges(T, target, anchor), f"LTS{gamma}_component"):
                    state["iterations"] = iteration
                    return selected, H, state
            else:
                raise RuntimeError(f"MLCC phase{gamma} iteration cap reached")
        return selected, H, state

    def upgraded_edge_set(self, H):
        """Edges that were LTS > 1 in G and are LTS 1 in H."""
        return frozenset(frozenset((u, v)) for u, v, d in self.G.edges(data=True)
                         if level(d) > 1 and level(H[u][v]) == 1)

    # ----- Genetic algorithm ------------------------------------------------
    def run_ga(self, budget_eur, seed_chromosome, population_size=30, n_generations=30,
               crossover_rate=0.85, mutation_rate=0.02, elite_size=2, tournament_size=3,
               random_seed=42, verbose=True):
        """Genetic algorithm maximising the predicted share; returns ``(best, history)``.

        ``seed_chromosome`` (normally the MLCC plan) is put in generation 0 and
        the best plan found is always kept, so the result is never worse than it.
        """
        n_genes = len(self.gene_edges)
        cache = {}

        def fitness(chromosome):
            key = np.asarray(chromosome, dtype=bool).tobytes()
            if key not in cache:
                if self.chromosome_cost(chromosome) > budget_eur+1e-7:
                    return -np.inf
                cache[key] = self.model.share_of_graph(self.to_graph(chromosome))
            return cache[key]

        def repair(chromosome, rng):
            a = np.asarray(chromosome, dtype=bool).copy()
            if self.chromosome_cost(a) > budget_eur:
                active = np.flatnonzero(a)
                rng.shuffle(active)
                for i in active:
                    a[i] = False
                    if self.chromosome_cost(a) <= budget_eur+1e-7:
                        break
            return a

        def random_individual(rng):
            a = np.zeros(n_genes, dtype=bool)
            left = budget_eur
            for i in rng.permutation(n_genes):
                if self.edge_costs[i] <= left and rng.random() < 0.65:
                    a[i] = True
                    left -= self.edge_costs[i]
            return a

        def tournament(pop, scores, rng):
            ids = rng.choice(len(pop), size=min(tournament_size, len(pop)), replace=False)
            return pop[int(ids[np.argmax(scores[ids])])].copy()

        rng = np.random.default_rng(random_seed)
        pop = [seed_chromosome.copy()]+[random_individual(rng) for _ in range(population_size-1)]
        best = seed_chromosome.copy()
        best_score = fitness(best)
        history = []
        for generation in range(n_generations+1):
            scores = np.array([fitness(a) for a in pop])
            idx = int(scores.argmax())
            if scores[idx] > best_score:
                best = pop[idx].copy()
                best_score = float(scores[idx])
            history.append({"generation": generation, "best_share_percent": best_score,
                            "generation_best_percent": float(scores.max()), "mean_share_percent": float(scores.mean()),
                            "best_cost_eur": self.chromosome_cost(best)})
            if verbose:
                print(f"GA {generation:3d}/{n_generations}: best {best_score:.5f}% | mean {scores.mean():.5f}% | "
                      f"cost €{self.chromosome_cost(best):,.0f}", flush=True)
            if generation == n_generations:
                break
            elites = np.argsort(scores)[-elite_size:]
            nxt = [pop[i].copy() for i in elites]
            if len(nxt) < population_size:
                nxt.append(best.copy())   # never lose the best plan found so far
            while len(nxt) < population_size:
                a, b = tournament(pop, scores, rng), tournament(pop, scores, rng)
                if rng.random() < crossover_rate:
                    mask = rng.random(n_genes) < 0.5
                    a, b = np.where(mask, a, b), np.where(mask, b, a)
                for child in (a, b):
                    flips = rng.random(n_genes) < mutation_rate
                    child = np.logical_xor(child, flips)
                    nxt.append(repair(child, rng))
                    if len(nxt) >= population_size:
                        break
            pop = nxt
        self.ga_fitness_evaluations = len(cache)
        return best, pd.DataFrame(history)


# ---------------------------------------------------------------------------
# Step 5: cumulative lookup table budget -> network
# ---------------------------------------------------------------------------
def mlcc_lookup(problem, budget_grid, H_start=None, rows=None, start_idx=1, spent=0.0,
                checkpoint=None, checkpoint_every=20, on_step=None, verbose=True):
    """Run MLCC for an increasing list of cumulative budgets.

    At state ``i`` the network of state ``i-1`` is upgraded with the new money
    plus everything not yet spent (unspent funds are carried over). Returns
    the list of rows (one per state) and the final network.

    ``checkpoint(next_index, H, rows, spent)`` is called every
    ``checkpoint_every`` states so a long run can be resumed;
    ``on_step(i, state)`` receives the MLCC state of every step (upgrade log).
    """
    H = (problem.G if H_start is None else H_start).copy()
    rows = rows if rows is not None else [dict(index=0, budget_allocated_eur=0.0, budget_fraction=0.0,
                                               actual_spent_eur=0.0, unspent_eur=0.0, upgraded_edges=0,
                                               **problem.model.metrics(H))]
    b_max = problem.full_cost_all
    n = len(budget_grid)
    for i in range(start_idx, n):
        allocated = float(budget_grid[i])
        _, H, state = problem.run_mlcc(H, max(0.0, allocated - spent))
        spent += float(state['spent_budget'])
        if on_step is not None:
            on_step(i, state)
        rows.append(dict(index=i, budget_allocated_eur=allocated, budget_fraction=allocated/b_max,
                         actual_spent_eur=spent, unspent_eur=max(0.0, allocated-spent),
                         upgraded_edges=len(problem.upgraded_edge_set(H)), **problem.model.metrics(H)))
        if checkpoint is not None and (i % checkpoint_every == 0 or i == n-1):
            checkpoint(i+1, H, rows, spent)
        if verbose and (i % checkpoint_every == 0 or i == n-1):
            print(f'{i}/{n-1}: allocated €{allocated:,.0f}; spent €{spent:,.0f}; '
                  f'normalized length {rows[-1]["normalized_network_length"]:.5f}; '
                  f'weighted LCC {rows[-1]["weighted_lcc_normalized"]:.5f}', flush=True)
    return rows, H
