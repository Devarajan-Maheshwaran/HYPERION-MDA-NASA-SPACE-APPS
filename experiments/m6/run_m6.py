"""Run the M6 LOPO experiment exactly as frozen in m6-lopo-config.json.

Usage (from the project root):  .venv\\Scripts\\python experiments\\m6\\run_m6.py

RECORDED-NON-ASTRONAUT methods demonstration (PhysioNet Wrist PPG During Exercise,
8 adults, terrestrial lab exercise). Outputs are measurements of simple baselines on
this dataset only. No astronaut, clinical or validation claim is made.
"""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np
import scipy

from m6_data import (CONFIG_PATH, M6_DIR, ROOT, load_config, load_inputs, load_reference,
                     record_names, reference_for_windows, window_starts)
from m6_features import ACCEL_FEATURE_NAMES, PPG_FEATURE_NAMES, record_features
from m6_metrics import (aggregate, bootstrap_indices, classification_summary, confusion, hr_stats,
                        majority_vote)
from m6_models import (LogisticClassifier, MajorityClassifier, MeanRegressor, RidgeRegressor,
                       lopo_predict)
from hyperion_mda import dsp_hr

HR_MODELS = ["A0", "A1", "A2", "A3", "A4", "A5"]
ACT_MODELS = ["B0", "B1", "B2"]
HR_PAIRS = [("A4", "A5", "eligible"), ("A3", "A5", "eligible"), ("A4", "A3", "eligible"),
            ("A3", "A2", "eligible"), ("A2", "A0", "eligible"), ("A2", "A1", "common"), ("A1", "A0", "common")]
ACT_PAIRS = [("B1", "B0"), ("B2", "B0"), ("B2", "B1")]
R6 = 6


def r6(x):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), R6)


def clean(obj):
    """Round floats to 6 decimals recursively; numpy scalars to Python."""
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        return r6(float(obj))
    return obj


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Boot:
    """Paired participant-bootstrap indices, cached per number of participants (same seed)."""

    def __init__(self, cfg):
        self.resamples, self.seed, self._cache = cfg["bootstrap"]["resamples"], cfg["bootstrap"]["seed"], {}

    def __call__(self, n):
        if n not in self._cache:
            self._cache[n] = bootstrap_indices(n, self.resamples, self.seed)
        return self._cache[n]


# ----------------------------------------------------------------------------- stage 1: data
def build_dataset(cfg: dict) -> tuple[dict, dict]:
    expected = cfg["dataset"]["expected_records"]
    records = record_names()
    if records != expected:
        raise SystemExit(f"Record list does not match the frozen config: {records}")
    participants = sorted({r.split("_")[0] for r in records})
    if participants != cfg["dataset"]["expected_participants"]:
        raise SystemExit(f"Participants do not match the frozen config: {participants}")
    w, s2 = cfg["windows"], cfg["sensitivity"]["S2"]
    rows = {k: [] for k in ("participant", "record", "activity", "start", "ref", "n_beats", "quality_ok",
                            "a1", "a2", "accel_mag_median", "ppg", "accel")}
    per_record, equivalence, degenerate = {}, {}, 0
    for record in records:
        inputs = load_inputs(record)
        starts = window_starts(inputs.n_samples, inputs.fs, w["window_s"], w["step_s"])
        feats = record_features(inputs, starts, cfg)            # inputs only: no reference passed
        beats = load_reference(record)                          # reference only: annotation file
        win = int(w["window_s"] * inputs.fs)
        ref, n_beats, quality = reference_for_windows(beats, starts, win, inputs.fs, cfg["reference"]["min_beats"],
                                                      s2["rr_min_s"], s2["rr_max_s"])
        # Frozen-method check: per-window A1 errors must equal M5 dsp_hr.check_record exactly.
        m5 = dsp_hr.check_record(record)
        mine = feats["a1"][np.isfinite(ref) & np.isfinite(feats["a1"])] - ref[np.isfinite(ref) & np.isfinite(feats["a1"])]
        equivalence[record] = bool(m5.windows == starts.size and m5.no_reference == int(np.sum(~np.isfinite(ref)))
                                   and np.array_equal(mine, np.asarray(m5.errors_bpm)))
        degenerate += feats["degenerate"]
        n = starts.size
        rows["participant"] += [inputs.participant] * n
        rows["record"] += [record] * n
        rows["activity"] += [inputs.activity] * n
        rows["start"].append(starts)
        rows["ref"].append(ref)
        rows["n_beats"].append(n_beats)
        rows["quality_ok"].append(quality)
        rows["a1"].append(feats["a1"])
        rows["a2"].append(feats["a2"])
        rows["accel_mag_median"].append(feats["accel_mag_median"])
        rows["ppg"].append(feats["ppg"])
        rows["accel"].append(feats["accel"])
        per_record[record] = {"participant": inputs.participant, "activity": inputs.activity,
                              "header_comment": inputs.header_comment, "duration_s": inputs.n_samples / inputs.fs,
                              "beats": int(beats.size), "windows": int(n),
                              "hr_eligible_windows": int(np.isfinite(ref).sum()),
                              "windows_without_reference": int((~np.isfinite(ref)).sum()),
                              "eligible_windows_failing_rr_screen": int((np.isfinite(ref) & ~quality).sum())}
    T = {k: np.array(v) if k in ("participant", "record", "activity") else np.concatenate(v) for k, v in rows.items()}
    for k in ("ref", "a1", "a2"):
        T[k] = np.round(T[k], R6)
    check = {"participants": participants,
             "records_per_participant": {p: [r for r in records if r.startswith(p + "_")] for p in participants},
             "n_records": len(records), "n_windows": int(T["start"].size),
             "n_hr_eligible_windows": int(np.isfinite(T["ref"]).sum()),
             "degenerate_feature_windows": degenerate, "per_record": per_record,
             "a1_matches_m5_dsp_hr": {"records_checked": len(equivalence),
                                      "all_identical": all(equivalence.values()), "per_record": equivalence}}
    if not all(equivalence.values()):
        raise SystemExit(f"A1 differs from the frozen M5 method: {equivalence}")
    return T, check


# ----------------------------------------------------------------------------- stage 2/4: HR
def participant_aggregate(per_participant: dict, metric: str, boot: Boot, exclude=()) -> dict | None:
    vals = [v[metric] for p, v in per_participant.items() if v[metric] is not None and p not in exclude]
    return aggregate(vals, boot(len(vals))) if vals else None


def hr_analysis(T: dict, mask: np.ndarray, cfg: dict, boot: Boot) -> tuple[dict, dict]:
    rows = np.isfinite(T["ref"]) & mask
    y, groups = T["ref"][rows], T["participant"][rows]
    Xp, Xa = T["ppg"][rows], T["accel"][rows]
    alpha = cfg["hr_models"]["A3"]["alpha"]
    preds, folds = {}, {}
    preds["A0"], f0 = lopo_predict(Xp, y, groups, MeanRegressor)
    preds["A1"], preds["A2"] = T["a1"][rows], T["a2"][rows]
    preds["A3"], f3 = lopo_predict(Xp, y, groups, lambda: RidgeRegressor(alpha))
    preds["A4"], f4 = lopo_predict(np.hstack([Xp, Xa]), y, groups, lambda: RidgeRegressor(alpha))
    preds["A5"], f5 = lopo_predict(Xa, y, groups, lambda: RidgeRegressor(alpha))
    preds = {m: np.round(p, R6) for m, p in preds.items()}
    records, participants = T["record"][rows], sorted(set(groups))
    common = np.all([np.isfinite(preds[m]) for m in HR_MODELS], axis=0)
    out = {"n_windows": int(rows.sum()), "n_common_windows": int(common.sum()), "models": {}}
    for m in HR_MODELS:
        err = preds[m] - y
        ok = np.isfinite(err)
        per_p = {}
        for p in participants:
            sel = groups == p
            st = hr_stats(err[sel & ok])
            st["eligible"], st["coverage"] = int(sel.sum()), float((sel & ok).sum() / sel.sum())
            per_p[p] = st
        per_r = {r: hr_stats(err[(records == r) & ok]) for r in dict.fromkeys(records)}
        per_p_common = {p: hr_stats(err[(groups == p) & common]) for p in participants}
        out["models"][m] = {
            "per_participant": per_p, "per_record": per_r, "pooled_windows": hr_stats(err[ok]),
            "coverage": float(ok.mean()),
            "aggregate": {k: participant_aggregate(per_p, k, boot) for k in ("mae", "rmse", "bias")},
            "aggregate_without_s4": {k: participant_aggregate(per_p, k, boot, cfg["sensitivity"]["S3"]["exclude_from_aggregate"])
                                     for k in ("mae", "rmse")},
            "common_windows": {"per_participant_mae": {p: v["mae"] for p, v in per_p_common.items()},
                               "aggregate_mae": participant_aggregate(per_p_common, "mae", boot)},
        }
    comparisons = []
    for a, b, wset in HR_PAIRS:
        key = "per_participant" if wset == "eligible" else None
        if key:
            da = {p: v["mae"] for p, v in out["models"][a]["per_participant"].items()}
            db = {p: v["mae"] for p, v in out["models"][b]["per_participant"].items()}
        else:
            da = out["models"][a]["common_windows"]["per_participant_mae"]
            db = out["models"][b]["common_windows"]["per_participant_mae"]
        diffs = {p: da[p] - db[p] for p in participants if da[p] is not None and db[p] is not None}
        agg = aggregate(list(diffs.values()), boot(len(diffs)))
        comparisons.append({"a": a, "b": b, "window_set": wset, "metric": "MAE difference a - b (bpm; negative = a lower)",
                            "per_participant": diffs, "aggregate": agg,
                            "participants_a_lower": int(sum(d < 0 for d in diffs.values()))})
    out["comparisons"] = comparisons
    out["ridge_folds"] = {m: [{"test": f.test_participant, "n_train": f.n_train, "n_test": f.n_test} for f in fl]
                          for m, fl in (("A3", f3), ("A4", f4), ("A5", f5))}
    table = {"participant": groups, "record": records, "start": T["start"][rows], "ref": y, **preds,
             "activity": T["activity"][rows], "accel_mag_median": T["accel_mag_median"][rows]}
    return out, table


def hr_failure_cases(block: dict, table: dict, cfg: dict) -> dict:
    fa = cfg["failure_analysis"]
    out = {}
    act3 = cfg["label_sets"]["primary_3class"]["map"]
    for m in HR_MODELS:
        mod = block["models"][m]
        per_p = {p: v["mae"] for p, v in mod["per_participant"].items() if v["mae"] is not None}
        per_r = {r: v["mae"] for r, v in mod["per_record"].items() if v["mae"] is not None}
        ranked = sorted(per_r, key=lambda r: -per_r[r])
        err = np.abs(table[m] - table["ref"])
        ok = np.isfinite(err)
        k = max(1, int(np.ceil(fa["top_fraction"] * ok.sum())))
        order = np.argsort(-np.where(ok, err, -np.inf), kind="stable")[:k]
        acts = [act3[a] for a in table["activity"][order]]
        out[m] = {"worst_participant": max(per_p, key=per_p.get), "worst_participant_mae": max(per_p.values()),
                  "worst_record": ranked[0], "worst_record_mae": per_r[ranked[0]],
                  "m5_failure_record_ranks": {r: {"rank_of_19": ranked.index(r) + 1, "mae": per_r[r]}
                                              for r in fa["m5_failure_records"] if r in per_r},
                  "top_error_windows": {
                      "n": int(k), "abs_error_threshold_bpm": float(err[order[-1]]),
                      "activity_counts": {a: acts.count(a) for a in ("walk", "run", "cycle")},
                      "median_ref_hr": float(np.median(table["ref"][order])),
                      "median_accel_mag": float(np.median(table["accel_mag_median"][order])),
                      "all_windows_activity_counts": {a: int(sum(act3[x] == a for x in table["activity"][ok]))
                                                      for a in ("walk", "run", "cycle")},
                      "all_windows_median_ref_hr": float(np.median(table["ref"][ok])),
                      "all_windows_median_accel_mag": float(np.median(table["accel_mag_median"][ok]))}}
    return out


# ----------------------------------------------------------------------------- stage 3/4: activity
def activity_analysis(T: dict, label_set: dict, cfg: dict, boot: Boot) -> tuple[dict, dict]:
    classes = label_set["order"]
    K = len(classes)
    y = np.array([classes.index(label_set["map"][a]) for a in T["activity"]], dtype=np.int64)
    groups, records = T["participant"], T["record"]
    lg = cfg["logistic"]
    C = cfg["activity_models"]["B1"]["C"]
    preds, folds = {}, {}
    preds["B0"], folds["B0"] = lopo_predict(T["accel"], y, groups, lambda: MajorityClassifier(K), dtype=np.int64)
    preds["B1"], folds["B1"] = lopo_predict(T["accel"], y, groups, lambda: LogisticClassifier(K, C, lg["maxiter"], lg["gtol"]), dtype=np.int64)
    preds["B2"], folds["B2"] = lopo_predict(np.hstack([T["accel"], T["ppg"]]), y, groups,
                                            lambda: LogisticClassifier(K, C, lg["maxiter"], lg["gtol"]), dtype=np.int64)
    participants = sorted(set(groups))
    rec_names = list(dict.fromkeys(records))
    rec_true = np.array([y[records == r][0] for r in rec_names])
    out = {"classes": classes, "n_windows": int(y.size), "models": {}}
    for m in ACT_MODELS:
        p = preds[m]
        cm = confusion(y, p, K)
        per_fold = {}
        for q in participants:
            sel = groups == q
            s = classification_summary(confusion(y[sel], p[sel], K), classes)
            per_fold[q] = {"n": s["n"], "accuracy": s["accuracy"], "classes_present": s["classes_present"],
                           "macro_f1": s["macro_f1"], "macro_f1_note": s["macro_f1_note"],
                           "balanced_accuracy": s["balanced_accuracy"]}
        rec_pred = np.array([majority_vote(p[records == r], K) for r in rec_names])
        rec_cm = confusion(rec_true, rec_pred, K)
        fold_info = []
        for f in folds[m]:
            info = {"test": f.test_participant, "n_train": f.n_train, "n_test": f.n_test}
            if isinstance(f.model, LogisticClassifier):
                info.update(converged=f.model.converged_, n_iter=f.model.n_iter_, message=f.model.message_)
            fold_info.append(info)
        out["models"][m] = {
            "pooled": classification_summary(cm, classes), "confusion_matrix": cm.tolist(),
            "per_fold": per_fold,
            "fold_accuracy_aggregate": aggregate([per_fold[q]["accuracy"] for q in participants], boot(len(participants))),
            "record_level": {"confusion_matrix": rec_cm.tolist(), "summary": classification_summary(rec_cm, classes),
                             "per_record": {r: {"true": classes[int(t)], "voted": classes[int(v)],
                                                "window_agreement": float(np.mean(p[records == r] == t))}
                                            for r, t, v in zip(rec_names, rec_true, rec_pred)}},
            "folds": fold_info}
    comps = []
    for a, b in ACT_PAIRS:
        d = {q: out["models"][a]["per_fold"][q]["accuracy"] - out["models"][b]["per_fold"][q]["accuracy"] for q in participants}
        comps.append({"a": a, "b": b, "metric": "per-fold accuracy difference a - b (positive = a higher)",
                      "per_participant": d, "aggregate": aggregate(list(d.values()), boot(len(d))),
                      "participants_a_higher": int(sum(v > 0 for v in d.values()))})
    out["comparisons"] = comps
    table = {"participant": groups, "record": records, "start": T["start"], "true": [classes[i] for i in y],
             **{m: [classes[i] for i in preds[m]] for m in ACT_MODELS}}
    return out, table


# ----------------------------------------------------------------------------- outputs
def fmt(v):
    if v is None:
        return ""
    if isinstance(v, (float, np.floating)):
        return "" if not np.isfinite(v) else f"{float(v):.6f}"
    return str(v)


def write_csv(path: Path, header: list[str], rows) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        for row in rows:
            w.writerow([fmt(v) for v in row])


def write_outputs(out_dir: Path, T, results, hr_tables, act_tables) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "windows.csv",
              ["participant", "record", "activity", "start_sample", "ref_hr_bpm", "ref_beats", "rr_screen_ok", "accel_mag_median_uncalibrated"],
              zip(T["participant"], T["record"], T["activity"], T["start"], T["ref"], T["n_beats"],
                  T["quality_ok"].astype(int), T["accel_mag_median"]))
    write_csv(out_dir / "features.csv", ["record", "start_sample", *PPG_FEATURE_NAMES, *ACCEL_FEATURE_NAMES],
              ([r, s, *p, *a] for r, s, p, a in zip(T["record"], T["start"], T["ppg"], T["accel"])))
    for name, table in hr_tables.items():
        write_csv(out_dir / f"hr_predictions_{name}.csv", ["participant", "record", "start_sample", "ref_hr_bpm", *HR_MODELS],
                  zip(table["participant"], table["record"], table["start"], table["ref"], *(table[m] for m in HR_MODELS)))
    for name, table in act_tables.items():
        write_csv(out_dir / f"activity_predictions_{name}.csv", ["participant", "record", "start_sample", "true", *ACT_MODELS],
                  zip(table["participant"], table["record"], table["start"], table["true"], *(table[m] for m in ACT_MODELS)))
    rows = []
    for analysis, block in results["hr"].items():
        for m, mod in block["models"].items():
            for p, s in mod["per_participant"].items():
                rows.append([analysis, m, p, s["eligible"], s["n"], s["coverage"], s["mae"], s["rmse"], s["bias"],
                             s["sd_error"], s["median_abs_error"], s["loa_low"], s["loa_high"]])
    write_csv(out_dir / "hr_per_participant.csv", ["analysis", "model", "participant", "eligible_windows", "scored_windows",
                                                   "coverage", "mae", "rmse", "bias", "sd_error", "median_abs_error",
                                                   "bland_altman_low", "bland_altman_high"], rows)
    rows = [[analysis, m, r, s["n"], s["mae"], s["rmse"], s["bias"], s["median_abs_error"]]
            for analysis, block in results["hr"].items() for m, mod in block["models"].items()
            for r, s in mod["per_record"].items()]
    write_csv(out_dir / "hr_per_record.csv", ["analysis", "model", "record", "scored_windows", "mae", "rmse", "bias", "median_abs_error"], rows)
    rows = []
    for analysis, block in results["hr"].items():
        for m, mod in block["models"].items():
            for scope, aggs in (("all", mod["aggregate"]), ("without_s4", mod["aggregate_without_s4"]),
                                ("common_windows", {"mae": mod["common_windows"]["aggregate_mae"]})):
                for metric, a in aggs.items():
                    rows.append([analysis, m, scope, metric, a["n_participants"], a["mean"], a["median"], a["min"],
                                 a["max"], a["sd"], a["ci_low"], a["ci_high"]])
    write_csv(out_dir / "hr_aggregate.csv", ["analysis", "model", "scope", "metric", "n_participants", "mean_over_participants",
                                             "median", "min", "max", "sd", "bootstrap_ci_low", "bootstrap_ci_high"], rows)
    rows = []
    for ls, block in results["activity"].items():
        for m, mod in block["models"].items():
            for p, s in mod["per_fold"].items():
                rows.append([ls, m, p, s["n"], s["accuracy"], s["balanced_accuracy"], s["macro_f1"] if s["macro_f1"] is not None else "n/a",
                             s["macro_f1_note"], "|".join(s["classes_present"])])
    write_csv(out_dir / "activity_per_fold.csv", ["label_set", "model", "test_participant", "windows", "accuracy",
                                                  "balanced_accuracy", "macro_f1", "macro_f1_note", "classes_present"], rows)
    rows = []
    for ls, block in results["activity"].items():
        for m, mod in block["models"].items():
            for level, cm in (("window", mod["confusion_matrix"]), ("record", mod["record_level"]["confusion_matrix"])):
                for i, t in enumerate(block["classes"]):
                    for j, p in enumerate(block["classes"]):
                        rows.append([ls, m, level, t, p, cm[i][j]])
    write_csv(out_dir / "activity_confusion.csv", ["label_set", "model", "level", "true", "predicted", "count"], rows)
    rows = [[ls, m, c, s["support"], s["predicted"], s["precision"], s["recall"], s["f1"]]
            for ls, block in results["activity"].items() for m, mod in block["models"].items()
            for c, s in mod["pooled"]["per_class"].items()]
    write_csv(out_dir / "activity_class_metrics.csv", ["label_set", "model", "class", "support", "predicted", "precision", "recall", "f1"], rows)


def provenance(cfg) -> dict:
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        head = "unavailable"
    m6_files = sorted(p for p in M6_DIR.glob("*.py"))
    reused = [ROOT / "src/hyperion_mda" / n for n in ("dsp_hr.py", "wfdb_reader.py", "physionet_source.py", "physionet_adapter.py")]
    return {"config_file": "experiments/m6/m6-lopo-config.json", "config_sha256": sha256(CONFIG_PATH),
            "config_version": cfg["config_version"],
            "dataset_manifest_sha256": sha256(ROOT / cfg["dataset"]["manifest"]),
            "git_head": head, "git_note": "M6 files are uncommitted; their hashes are listed here",
            "source_sha256": {p.relative_to(ROOT).as_posix(): sha256(p) for p in m6_files + reused},
            "python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
            "platform": platform.platform(), "random_seed_bootstrap": cfg["bootstrap"]["seed"]}


A2_RATIO_BANDS = {"near_1x": (0.9, 1.1), "near_2x": (1.8, 2.2), "near_0.5x": (0.45, 0.55)}


def a2_ratio_diagnostic(table: dict) -> dict:
    """POST HOC (added after the first results were viewed): descriptive only, no model changed.
    Fraction of windows whose A2 estimate / reference ratio falls near 1x, 2x or 0.5x, per activity."""
    ratio = table["A2"] / table["ref"]
    out = {"label": "post hoc descriptive diagnostic, added after viewing results; no model or parameter changed",
           "bands": {k: list(v) for k, v in A2_RATIO_BANDS.items()}, "per_activity": {}}
    for act in ("walk", "run", "low_resistance_bike", "high_resistance_bike"):
        v = ratio[table["activity"] == act]
        out["per_activity"][act] = {"n": int(v.size), **{k: float(np.mean((v > lo) & (v < hi))) for k, (lo, hi) in A2_RATIO_BANDS.items()}}
    return out


def run(out_dir: Path | None = None) -> dict:
    cfg = load_config()
    out_dir = out_dir or (ROOT / cfg["outputs_dir"])
    boot = Boot(cfg)
    T, check = build_dataset(cfg)
    all_rows = np.ones(T["start"].size, dtype=bool)
    hr_primary, table_primary = hr_analysis(T, all_rows, cfg, boot)
    hr_s2, table_s2 = hr_analysis(T, T["quality_ok"], cfg, boot)
    act3, table3 = activity_analysis(T, cfg["label_sets"]["primary_3class"], cfg, boot)
    act4, table4 = activity_analysis(T, cfg["label_sets"]["secondary_4class"], cfg, boot)
    results = {"title": "M6 LOPO baselines: PhysioNet Wrist PPG During Exercise v1.0.0",
               "scope": cfg["scope"], "provenance": provenance(cfg), "dataset_check": check,
               "hr": {"primary": hr_primary, "S2_rr_screened": hr_s2},
               "hr_failure_cases": hr_failure_cases(hr_primary, table_primary, cfg),
               "post_hoc_a2_ratio_diagnostic": a2_ratio_diagnostic(table_primary),
               "activity": {"primary_3class": act3, "secondary_4class": act4},
               "sensitivity": {"S1": cfg["sensitivity"]["S1"],
                               "S2": {**cfg["sensitivity"]["S2"], "windows_removed": hr_primary["n_windows"] - hr_s2["n_windows"]},
                               "S3": cfg["sensitivity"]["S3"]}}
    results = clean(results)
    write_outputs(out_dir, T, results, {"primary": table_primary, "S2_rr_screened": table_s2},
                  {"primary_3class": table3, "secondary_4class": table4})
    (out_dir / "results.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8", newline="\n")
    from m6_report import render
    loaded = json.loads((out_dir / "results.json").read_text(encoding="utf-8"))
    (out_dir / "report.md").write_text(render(loaded), encoding="utf-8", newline="\n")
    return loaded


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    res = run(target)
    print("M6 run complete:", res["dataset_check"]["n_windows"], "windows;",
          "A1 identical to M5:", res["dataset_check"]["a1_matches_m5_dsp_hr"]["all_identical"])
