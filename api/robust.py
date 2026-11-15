"""Cosine-median robust aggregation demo. Stdlib only, simulated silo updates.

This is the cosine-similarity-trimmed median used as a radiation bit-flip countermeasure in
the concept deck. It is exercised here on SIMULATED federated silo weight vectors from the
existing toy FedAvg module, with an injected bit-flip in silo 2. It is NOT real federated
learning across habitats, NOT Flower, and NOT differential privacy.
"""
from __future__ import annotations

import math
from typing import Sequence

Vector = tuple[float, ...]


def _norm(v: Sequence[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    na, nb = _norm(a), _norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def coordinate_median(vectors: Sequence[Sequence[float]]) -> Vector:
    if not vectors:
        raise ValueError("no vectors")
    dim = len(vectors[0])
    return tuple(sorted(v[d] for v in vectors)[len(vectors) // 2] for d in range(dim))


def cosine_median(vectors: Sequence[Sequence[float]], trim: int = 1) -> dict:
    """Drop the `trim` vectors least aligned with the coordinate-wise median, then average."""
    if not vectors:
        raise ValueError("no vectors")
    med = coordinate_median(vectors)
    scored = [(cosine(v, med), i, tuple(v)) for i, v in enumerate(vectors)]
    scored.sort(key=lambda t: t[0])
    rejected = scored[:trim] if trim < len(scored) else []
    kept = scored[trim:] if trim < len(scored) else scored
    agg = tuple(sum(v[d] for _, _, v in kept) / len(kept) for d in range(len(med)))
    return {
        "aggregate": agg,
        "median": med,
        "kept": [i for _, i, _ in kept],
        "rejected": [{"silo_index": i, "cosine": c} for c, i, _ in rejected],
        "label": "SIMULATED cosine-median filter on toy silo updates; not real FL, not DP",
    }


def bitflip_demo(vectors: Sequence[Sequence[float]], silo_index: int = 1) -> dict:
    """Inject a large bit-flip into one silo and show the filter rejecting it."""
    if not vectors:
        raise ValueError("no vectors")
    poisoned = [tuple(v) for v in vectors]
    target = list(poisoned[silo_index])
    target[0] += 1e6  # a radiation-style single-coordinate corruption
    poisoned[silo_index] = tuple(target)
    clean = cosine_median(vectors, trim=1)
    robust = cosine_median(poisoned, trim=1)
    naive = tuple(sum(v[d] for v in poisoned) / len(poisoned) for d in range(len(target)))
    return {
        "silo_index": silo_index,
        "clean_aggregate": clean["aggregate"],
        "robust_aggregate": robust["aggregate"],
        "naive_mean_with_flip": naive,
        "rejected": robust["rejected"],
        "caught": any(r["silo_index"] == silo_index for r in robust["rejected"]),
        "label": "SIMULATED bit-flip in silo 2; cosine-median rejects the corrupted update",
    }
