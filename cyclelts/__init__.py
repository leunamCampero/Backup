"""cyclelts - cycling networks, Level of Traffic Stress (LTS) and bike mode share.

The package contains every piece of code used by the notebooks in ``notebooks/``.
Each module covers one step of the study:

=========================  ==================================================
module                     what it does
=========================  ==================================================
``cyclelts.config``        folders of the project and the list of studied cities
``cyclelts.overpass``      robust OpenStreetMap downloads (retries, mirrors, history)
``cyclelts.lts``           classify every street segment into an LTS level
``cyclelts.network``       build the yearly cycling network of a city (step 1)
``cyclelts.simplify``      simplify a network without changing its lengths
``cyclelts.metrics``       network length and largest-connected-component metrics
``cyclelts.plotting``      interactive Plotly maps of the networks
``cyclelts.insee``         read INSEE census tables -> commuting mode shares (step 2)
``cyclelts.mode_share``    the statistical model infrastructure -> bike share (step 3)
``cyclelts.optimization``  where to invest: MLCC heuristic and genetic algorithm (steps 4-5)
=========================  ==================================================

Quick example::

    from cyclelts.config import grenoble_graph
    from cyclelts.mode_share import GRENOBLE_MODEL

    G = grenoble_graph(2026)                # simplified Grenoble network, 2026
    print(GRENOBLE_MODEL.share_of_graph(G))  # -> 22.82 (% predicted bike share)
"""

__version__ = "1.0.0"
