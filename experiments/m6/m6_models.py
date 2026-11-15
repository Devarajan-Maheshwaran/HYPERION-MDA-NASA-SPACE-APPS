"""Baseline models (numpy/scipy only) and the leave-one-participant-out driver.

Every fitted transform (standardiser) lives inside the model and is fitted on the
rows passed to `fit`, which the LOPO driver restricts to training participants.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize


class Standardizer:
    def fit(self, X: np.ndarray) -> "Standardizer":
        self.mean_ = X.mean(axis=0)
        sd = X.std(axis=0)
        self.sd_ = np.where(sd > 0, sd, 1.0)
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        return (X - self.mean_) / self.sd_


class MeanRegressor:
    def fit(self, X, y):
        self.value_ = float(np.mean(y))
        return self

    def predict(self, X):
        return np.full(len(X), self.value_)


class RidgeRegressor:
    def __init__(self, alpha: float):
        self.alpha = alpha

    def fit(self, X, y):
        self.scaler_ = Standardizer().fit(X)
        Z = self.scaler_.transform(X)
        self.intercept_ = float(np.mean(y))
        A = Z.T @ Z + self.alpha * np.eye(Z.shape[1])
        self.coef_ = np.linalg.solve(A, Z.T @ (y - self.intercept_))
        return self

    def predict(self, X):
        return self.scaler_.transform(X) @ self.coef_ + self.intercept_


class MajorityClassifier:
    def __init__(self, n_classes: int):
        self.n_classes = n_classes

    def fit(self, X, y):
        counts = np.bincount(y, minlength=self.n_classes)
        self.label_ = int(np.argmax(counts))  # argmax returns the first maximum: label-set order tie-break
        return self

    def predict(self, X):
        return np.full(len(X), self.label_, dtype=np.int64)


class LogisticClassifier:
    """Multinomial logistic regression: C * sum(CE) + 0.5 * ||W||^2, intercept unpenalised."""

    def __init__(self, n_classes: int, C: float, maxiter: int, gtol: float):
        self.n_classes, self.C, self.maxiter, self.gtol = n_classes, C, maxiter, gtol

    def _objective(self, theta, Z, Y):
        d, K = Z.shape[1], self.n_classes
        W, b = theta[:d * K].reshape(d, K), theta[d * K:]
        S = Z @ W + b
        S = S - S.max(axis=1, keepdims=True)
        logp = S - np.log(np.exp(S).sum(axis=1, keepdims=True))
        loss = -self.C * float(np.sum(logp * Y)) + 0.5 * float(np.sum(W * W))
        G = np.exp(logp) - Y
        grad_W = self.C * (Z.T @ G) + W
        grad_b = self.C * G.sum(axis=0)
        return loss, np.concatenate([grad_W.ravel(), grad_b])

    def fit(self, X, y):
        self.scaler_ = Standardizer().fit(X)
        Z = self.scaler_.transform(X)
        Y = np.eye(self.n_classes)[y]
        d, K = Z.shape[1], self.n_classes
        res = minimize(self._objective, np.zeros(d * K + K), args=(Z, Y), jac=True, method="L-BFGS-B",
                       options={"maxiter": self.maxiter, "gtol": self.gtol})
        self.W_, self.b_ = res.x[:d * K].reshape(d, K), res.x[d * K:]
        self.converged_, self.n_iter_, self.message_ = bool(res.success), int(res.nit), str(res.message)
        return self

    def predict(self, X):
        return np.argmax(self.scaler_.transform(X) @ self.W_ + self.b_, axis=1).astype(np.int64)


@dataclass
class FoldRecord:
    test_participant: str
    train_participants: list[str]
    n_train: int
    n_test: int
    model: object = field(repr=False, default=None)


def lopo_folds(participants: list[str]) -> list[tuple[str, list[str]]]:
    ordered = sorted(set(participants))
    return [(p, [q for q in ordered if q != p]) for p in ordered]


def lopo_predict(X: np.ndarray, y: np.ndarray, groups: np.ndarray, make_model, dtype=float):
    """Each row is predicted by a model fitted only on rows of the other participants."""
    predictions = np.empty(len(y), dtype=dtype)
    predicted = np.zeros(len(y), dtype=bool)
    folds = []
    for test_p, train_ps in lopo_folds(list(groups)):
        train = np.isin(groups, train_ps)
        test = groups == test_p
        if (train & test).any() or test_p in set(groups[train]):
            raise AssertionError(f"participant leakage in fold {test_p}")
        model = make_model().fit(X[train], y[train])
        predictions[test] = model.predict(X[test])
        if predicted[test].any():
            raise AssertionError("a row was predicted by two folds")
        predicted[test] = True
        folds.append(FoldRecord(test_p, train_ps, int(train.sum()), int(test.sum()), model))
    if not predicted.all():
        raise AssertionError("a row was never predicted")
    return predictions, folds
