"""Metrics for M6. Participant-level aggregation and participant bootstrap only."""

from __future__ import annotations

import numpy as np


def hr_stats(errors) -> dict:
    e = np.asarray(errors, dtype=float)
    n = int(e.size)
    if n == 0:
        return {"n": 0, "mae": None, "rmse": None, "bias": None, "sd_error": None,
                "median_abs_error": None, "loa_low": None, "loa_high": None}
    bias = float(np.mean(e))
    sd = float(np.std(e, ddof=1)) if n > 1 else None
    return {"n": n, "mae": float(np.mean(np.abs(e))), "rmse": float(np.sqrt(np.mean(e ** 2))),
            "bias": bias, "sd_error": sd, "median_abs_error": float(np.median(np.abs(e))),
            "loa_low": None if sd is None else bias - 1.96 * sd,
            "loa_high": None if sd is None else bias + 1.96 * sd}


def bootstrap_indices(n_units: int, resamples: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).integers(0, n_units, size=(resamples, n_units))


def aggregate(values: list[float], boot_idx: np.ndarray) -> dict:
    v = np.asarray(values, dtype=float)
    means = v[boot_idx].mean(axis=1)
    return {"n_participants": int(v.size), "mean": float(v.mean()), "median": float(np.median(v)),
            "min": float(v.min()), "max": float(v.max()),
            "sd": float(v.std(ddof=1)) if v.size > 1 else None,
            "ci_low": float(np.percentile(means, 2.5)), "ci_high": float(np.percentile(means, 97.5))}


def confusion(true_idx, pred_idx, n_classes: int) -> np.ndarray:
    cm = np.zeros((n_classes, n_classes), dtype=np.int64)
    for t, p in zip(true_idx, pred_idx):
        cm[int(t), int(p)] += 1
    return cm


def class_metrics(cm: np.ndarray, classes: list[str]) -> dict:
    """Per class: precision (None if never predicted), recall (None if absent), F1.
    F1 = 0 for a class present in truth but never predicted (precision undefined)."""
    out = {}
    for k, name in enumerate(classes):
        tp, pred_sum, true_sum = int(cm[k, k]), int(cm[:, k].sum()), int(cm[k, :].sum())
        precision = tp / pred_sum if pred_sum else None
        recall = tp / true_sum if true_sum else None
        if recall is None:
            f1 = None
        elif precision is None or precision + recall == 0:
            f1 = 0.0
        else:
            f1 = 2 * precision * recall / (precision + recall)
        out[name] = {"support": true_sum, "predicted": pred_sum, "precision": precision, "recall": recall, "f1": f1}
    return out


def classification_summary(cm: np.ndarray, classes: list[str]) -> dict:
    per = class_metrics(cm, classes)
    present = [c for c in classes if per[c]["support"] > 0]
    total = int(cm.sum())
    summary = {"n": total, "accuracy": float(np.trace(cm) / total) if total else None,
               "classes_present": present,
               "balanced_accuracy": float(np.mean([per[c]["recall"] for c in present])) if present else None,
               "per_class": per}
    if len(present) < 2:
        summary["macro_f1"] = None
        summary["macro_f1_note"] = "n/a: single-class test fold"
    else:
        summary["macro_f1"] = float(np.mean([per[c]["f1"] for c in present]))
        summary["macro_f1_note"] = ("over all classes" if len(present) == len(classes)
                                    else f"over the {len(present)} classes present only")
    return summary


def majority_vote(pred_idx, n_classes: int) -> int:
    return int(np.argmax(np.bincount(np.asarray(pred_idx, dtype=np.int64), minlength=n_classes)))
