"""Step 3 - the model linking cycling infrastructure to bike mode share.

The model
---------
For city *c* and year *t* the infrastructure index is a weighted mix of the two
metrics of :mod:`cyclelts.metrics`::

    I = w_N * N  +  (1 - w_N) * C

and the predicted two-wheeler commuting share is a *capped logistic curve*::

    p = P_MAX * logistic(alpha_c + beta_c * I),    logistic(z) = 1 / (1 + e^-z)

``P_MAX = 50 %`` is a modelling assumption (a ceiling the share can approach
but never exceed), not a measured value.

It is fitted as a *fractional logit*: a binomial GLM on ``share / P_MAX``
(statsmodels). Three structures are compared:

* ``pooled``     - one intercept and one slope for all cities;
* ``intercepts`` - one intercept per city, a common slope (**retained model**);
* ``slopes``     - one intercept and one slope per city.

The weight ``w_N`` and the structure are chosen by *leave-one-year-out*
cross-validation on 2017-2022 (one calendar year removed for all cities at a
time). 2026 is never used for fitting.

The retained Grenoble model (``GRENOBLE_MODEL``) is what the optimisation
notebooks use to turn a network into a predicted share.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.special import expit

from .metrics import network_metrics

MAX_SHARE = 0.50

STRUCTURES = {
    "Common intercept + slope": "pooled",
    "City intercepts + common slope": "intercepts",
    "City intercepts + city slopes": "slopes",
}


def with_weight(df, weight):
    """Add the column ``index`` = weight * N + (1 - weight) * C."""
    out = df.copy()
    out["index"] = weight * out["normalized_network_length"] + (1-weight) * out["weighted_lcc_normalized"]
    return out


def design(data, structure, city_order):
    """Design matrix of a model structure (first city of ``city_order`` = reference)."""
    n = len(data)
    x = np.asarray(data["index"], dtype=float)
    cities = np.asarray(data["city"], dtype=str)
    cols = [np.ones(n)]
    labels = ["Intercept"]
    if structure in ("intercepts", "slopes"):
        for city in city_order[1:]:
            cols.append((cities == city).astype(float))
            labels.append(f"Intercept adjustment: {city}")
    cols.append(x)
    labels.append("Slope")
    if structure == "slopes":
        for city in city_order[1:]:
            cols.append(x * (cities == city).astype(float))
            labels.append(f"Slope adjustment: {city}")
    return np.column_stack(cols), labels


def fit_model(train, structure, city_order, max_share=MAX_SHARE):
    """Fractional-logit fit of ``share / max_share`` (binomial GLM)."""
    X, names = design(train, structure, city_order)
    y = np.asarray(train.share, dtype=float) / max_share
    fit = sm.GLM(y, X, family=sm.families.Binomial()).fit(maxiter=200)
    if not np.all(np.isfinite(fit.params)):
        raise ValueError("Non-finite estimated parameters")
    return fit, names


def predict_share(fit, frame, structure, city_order, max_share=MAX_SHARE):
    """Predicted share (fraction, 0-``max_share``)."""
    X, _ = design(frame, structure, city_order)
    return max_share * expit(X @ np.asarray(fit.params))


def city_parameters(fit, structure, city_order):
    """``{city: (alpha_c, beta_c)}`` on the logit scale."""
    params = np.asarray(fit.params, dtype=float)
    out = {}
    for city in city_order:
        test = pd.DataFrame({"city": [city, city], "index": [0.0, 1.0]})
        X, _ = design(test, structure, city_order)
        alpha = float(X[0] @ params)
        out[city] = (alpha, float((X[1] - X[0]) @ params))
    return out


# ---------------------------------------------------------------------------
# The calibrated Grenoble model used by the optimisation (steps 4-7)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CityShareModel:
    """Calibrated capped-logit model of one city.

    The numbers come from notebook 03 (structure "City intercepts + common
    slope", w_N = 0.40). ``reference_length_m`` is the city's fixed reference
    length (largest yearly cycling length) used to normalise N and C.
    """

    alpha: float
    beta: float
    w_length: float
    w_lcc: float
    reference_length_m: float
    p_max: float = MAX_SHARE
    kappa: float = 1.0

    def share_from_metrics(self, N, C):
        """Predicted share in percent from normalised length N and weighted LCC C (vectorised)."""
        indicator = self.w_length * np.asarray(N, dtype=float) + self.w_lcc * np.asarray(C, dtype=float)
        return 100.0 * self.p_max * expit(self.alpha + self.beta * indicator)

    def metrics(self, H):
        """N, C and LCC lengths of graph ``H`` with this model's reference length."""
        return network_metrics(H, self.reference_length_m, self.kappa)

    def metrics_and_share(self, H):
        """Metrics + infrastructure index + predicted share (%) of graph ``H``."""
        rec = self.metrics(H)
        rec['indicator_I'] = self.w_length * rec['normalized_network_length'] + self.w_lcc * rec['weighted_lcc_normalized']
        rec['predicted_share_percent'] = float(self.share_from_metrics(
            rec['normalized_network_length'], rec['weighted_lcc_normalized']))
        return rec

    def share_of_graph(self, H):
        """Predicted share (%) of graph ``H``."""
        return self.metrics_and_share(H)['predicted_share_percent']


#: Grenoble, "City intercepts + common slope" calibrated on 11 cities, 2017-2022
#: (results/calibration/city_model_parameters.csv). The 2026 network gives 22.820 %.
GRENOBLE_MODEL = CityShareModel(alpha=-3.40675, beta=5.01498, w_length=0.40, w_lcc=0.60,
                                reference_length_m=418_262.360)

#: Predicted 2026 share of Grenoble with GRENOBLE_MODEL (used as a regression check)
GRENOBLE_2026_SHARE = 22.82022
