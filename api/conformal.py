"""Split-conformal quantile on demo calibration residuals. Stdlib only.

This is a genuine finite-sample split-conformal quantile, but it is computed on SIMULATED
resting residuals from the demo calibration. It carries NO coverage guarantee on real
astronaut data and is labelled as a demo interval everywhere it is shown. There is no
neural predictor and no MC-dropout sigma_epistemic; that field is NOT_AVAILABLE.
"""
from __future__ import annotations

import math
from typing import Sequence


def split_conformal_quantile(scores: Sequence[float], alpha: float) -> float | None:
    """Return the ceil((n+1)(1-alpha))/n empirical quantile of nonconformity scores.

    Returns None when there are no finite scores or alpha is outside (0, 1).
    """
    if not (0.0 < alpha < 1.0):
        return None
    finite = sorted(float(s) for s in scores if s is not None and math.isfinite(float(s)))
    n = len(finite)
    if n == 0:
        return None
    rank = math.ceil((n + 1) * (1.0 - alpha))
    if rank >= n:
        return finite[-1]  # cannot guarantee coverage beyond the sample; report the max
    return finite[rank - 1]


def upper_bound(prediction: float | None, scores: Sequence[float], alpha: float) -> dict:
    q = split_conformal_quantile(scores, alpha)
    return {
        "prediction": prediction,
        "q_hat": q,
        "upper": None if prediction is None or q is None else prediction + q,
        "alpha": alpha,
        "n_calibration": len([s for s in scores if s is not None and math.isfinite(float(s))]),
        "label": "demo split-conformal quantile on SIMULATED calibration residuals; no coverage guarantee",
        "sigma_epistemic": None,
        "sigma_note": "MC-dropout / HyperionCoreNet not implemented; no epistemic sigma exists.",
    }
