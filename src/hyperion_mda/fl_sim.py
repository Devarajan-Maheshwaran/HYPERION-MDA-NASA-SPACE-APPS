"""FL SIMULATION: a small, reproducible FedAvg demonstration on generated toy data.

What this is
    One Python process on one computer. Toy 2-D points are generated from a fixed
    seed and split into N simulated clients. Each round, every client trains a tiny
    logistic-regression model locally (full-batch gradient descent), and a simulated
    server averages the client weights, weighted by client sample count (FedAvg).

What this is NOT
    Not independent habitats, sites or devices; not astronaut, NASA, WESAD or any real
    data; not Flower (not installed; its Python 3.14 support is unverified); and NOT a
    privacy protection: federated averaging by itself gives no formal privacy guarantee,
    and no differential privacy is applied. No accuracy or performance is reported,
    and nothing here has clinical meaning.

Separation: this module imports nothing from the NASA lab-data or wearable pipelines.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

FL_LABEL = "FL SIMULATION"
MIN_CLIENTS, MAX_CLIENTS = 2, 8
MIN_ROUNDS, MAX_ROUNDS = 1, 30
Weights = tuple[float, float, float]  # (w1, w2, bias)


@dataclass(frozen=True)
class ToyClient:
    client_id: str
    points: tuple[tuple[float, float], ...]
    labels: tuple[int, ...]

    @property
    def n(self) -> int:
        return len(self.labels)


@dataclass(frozen=True)
class ClientUpdate:
    client_id: str
    n: int
    weights: Weights
    update_size: float  # Euclidean length of (local weights - global weights before the round)


@dataclass(frozen=True)
class RoundLog:
    round_no: int
    updates: tuple[ClientUpdate, ...]
    global_weights: Weights


@dataclass
class FLRun:
    n_clients: int
    rounds: int
    seed: int
    client_sizes: dict[str, int]
    logs: list[RoundLog] = field(default_factory=list)


def make_toy_clients(n_clients: int, seed: int = 7) -> list[ToyClient]:
    """Generated toy points; client sizes and centres differ so the split is uneven."""
    rng = random.Random(seed)
    clients = []
    for k in range(n_clients):
        size = 30 + 10 * (k % 3)
        shift = 0.4 * (k - (n_clients - 1) / 2)
        pts, labels = [], []
        for _ in range(size):
            label = rng.randint(0, 1)
            cx, cy = (1.0, 1.0) if label else (-1.0, -1.0)
            pts.append((cx + shift + rng.gauss(0, 0.8), cy + rng.gauss(0, 0.8)))
            labels.append(label)
        clients.append(ToyClient(f"client-{k + 1}", tuple(pts), tuple(labels)))
    return clients


def _sigmoid(z: float) -> float:
    return 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))


def local_train(weights: Weights, client: ToyClient, epochs: int = 5, lr: float = 0.2) -> Weights:
    """Full-batch gradient descent on the client's own toy data only."""
    w1, w2, b = weights
    for _ in range(epochs):
        g1 = g2 = gb = 0.0
        for (x1, x2), y in zip(client.points, client.labels):
            err = _sigmoid(w1 * x1 + w2 * x2 + b) - y
            g1 += err * x1
            g2 += err * x2
            gb += err
        n = client.n
        w1, w2, b = w1 - lr * g1 / n, w2 - lr * g2 / n, b - lr * gb / n
    return (w1, w2, b)


def fedavg(updates: list[tuple[Weights, int]]) -> Weights:
    """Server step: sample-count-weighted average of client weights.

    The server receives only (weights, sample count) pairs, never client data.
    """
    total = sum(n for _, n in updates)
    if total <= 0:
        raise ValueError("FedAvg needs at least one client with data.")
    return tuple(sum(w[i] * n for w, n in updates) / total for i in range(3))  # type: ignore[return-value]


def validate_params(n_clients, rounds) -> tuple[int, int]:
    try:
        c, r = int(n_clients), int(rounds)
    except (TypeError, ValueError):
        raise ValueError("Clients and rounds must be whole numbers.") from None
    if str(n_clients).strip() != str(c) or str(rounds).strip() != str(r):
        raise ValueError("Clients and rounds must be whole numbers.")
    if not MIN_CLIENTS <= c <= MAX_CLIENTS:
        raise ValueError(f"Clients must be between {MIN_CLIENTS} and {MAX_CLIENTS}.")
    if not MIN_ROUNDS <= r <= MAX_ROUNDS:
        raise ValueError(f"Rounds must be between {MIN_ROUNDS} and {MAX_ROUNDS}.")
    return c, r


def run_fedavg(n_clients=3, rounds=5, seed: int = 7) -> FLRun:
    n_clients, rounds = validate_params(n_clients, rounds)
    clients = make_toy_clients(n_clients, seed)
    run = FLRun(n_clients, rounds, seed, {c.client_id: c.n for c in clients})
    global_w: Weights = (0.0, 0.0, 0.0)
    for r in range(1, rounds + 1):
        updates = []
        for c in clients:
            local_w = local_train(global_w, c)
            size = math.sqrt(sum((a - b) ** 2 for a, b in zip(local_w, global_w)))
            updates.append(ClientUpdate(c.client_id, c.n, local_w, size))
        global_w = fedavg([(u.weights, u.n) for u in updates])
        run.logs.append(RoundLog(r, tuple(updates), global_w))
    return run
