"""Independent verification of M6 outputs.

Recomputes the reported metrics from the raw per-window prediction CSVs using only
the standard library (csv, math): it shares no metric code with run_m6.py. It then
checks results.json, the summary CSVs, and that report.md is exactly what
m6_report.render(results.json) produces.

Usage:  .venv\\Scripts\\python experiments\\m6\\verify_m6.py [outputs_dir]
Exit code 0 = every check passed.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

M6_DIR = Path(__file__).resolve().parent
TOL = 2e-6
HR_MODELS = ["A0", "A1", "A2", "A3", "A4", "A5"]
ACT_MODELS = ["B0", "B1", "B2"]


class Checker:
    def __init__(self):
        self.passed, self.failures = 0, []

    def close(self, what, got, want, tol=TOL):
        if got is None or want is None:
            ok = got is None and want is None
        else:
            ok = abs(got - want) <= tol
        self._record(ok, f"{what}: recomputed {got} vs reported {want}")

    def equal(self, what, got, want):
        self._record(got == want, f"{what}: recomputed {got!r} vs reported {want!r}")

    def _record(self, ok, msg):
        if ok:
            self.passed += 1
        else:
            self.failures.append(msg)


def read(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def mean(v):
    return sum(v) / len(v)


def hr_metrics(errors):
    if not errors:
        return None, None, None
    return (mean([abs(e) for e in errors]), math.sqrt(mean([e * e for e in errors])), mean(errors))


def verify_hr(c: Checker, out: Path, results: dict) -> None:
    for analysis in ("primary", "S2_rr_screened"):
        rows = read(out / f"hr_predictions_{analysis}.csv")
        block = results["hr"][analysis]
        c.equal(f"hr/{analysis} window count", len(rows), block["n_windows"])
        for m in HR_MODELS:
            by_p, by_r, pooled = defaultdict(list), defaultdict(list), []
            for row in rows:
                if row[m] == "":
                    continue
                e = float(row[m]) - float(row["ref_hr_bpm"])
                by_p[row["participant"]].append(e)
                by_r[row["record"]].append(e)
                pooled.append(e)
            mod = block["models"][m]
            maes, rmses = [], []
            for p, rep in mod["per_participant"].items():
                mae, rmse, bias = hr_metrics(by_p[p])
                c.close(f"hr/{analysis}/{m}/{p} MAE", mae, rep["mae"])
                c.close(f"hr/{analysis}/{m}/{p} RMSE", rmse, rep["rmse"])
                c.close(f"hr/{analysis}/{m}/{p} bias", bias, rep["bias"])
                c.equal(f"hr/{analysis}/{m}/{p} n", len(by_p[p]), rep["n"])
                maes.append(mae)
                rmses.append(rmse)
            for r, rep in mod["per_record"].items():
                c.close(f"hr/{analysis}/{m}/{r} MAE", hr_metrics(by_r[r])[0], rep["mae"])
            c.close(f"hr/{analysis}/{m} aggregate MAE", mean(maes), mod["aggregate"]["mae"]["mean"])
            c.close(f"hr/{analysis}/{m} aggregate RMSE", mean(rmses), mod["aggregate"]["rmse"]["mean"])
            c.close(f"hr/{analysis}/{m} pooled MAE", hr_metrics(pooled)[0], mod["pooled_windows"]["mae"])
            c.close(f"hr/{analysis}/{m} pooled RMSE", hr_metrics(pooled)[1], mod["pooled_windows"]["rmse"])
            keep = [v for p, v in zip(mod["per_participant"], maes) if p != "s4"]
            c.close(f"hr/{analysis}/{m} aggregate MAE without s4", mean(keep), mod["aggregate_without_s4"]["mae"]["mean"])
        for comp in block["comparisons"]:
            for p, d in comp["per_participant"].items():
                key = "per_participant" if comp["window_set"] == "eligible" else None
                if key:
                    a = block["models"][comp["a"]]["per_participant"][p]["mae"]
                    b = block["models"][comp["b"]]["per_participant"][p]["mae"]
                else:
                    a = block["models"][comp["a"]]["common_windows"]["per_participant_mae"][p]
                    b = block["models"][comp["b"]]["common_windows"]["per_participant_mae"][p]
                c.close(f"hr/{analysis} {comp['a']}-{comp['b']} {p}", a - b, d, tol=3 * TOL)
            c.close(f"hr/{analysis} {comp['a']}-{comp['b']} mean", mean(list(comp["per_participant"].values())),
                    comp["aggregate"]["mean"], tol=3 * TOL)
    # summary CSV must mirror results.json
    for row in read(out / "hr_per_participant.csv"):
        rep = results["hr"][row["analysis"]]["models"][row["model"]]["per_participant"][row["participant"]]
        c.close(f"hr_per_participant.csv {row['analysis']}/{row['model']}/{row['participant']} MAE", float(row["mae"]), rep["mae"])


def confusion(pairs, classes):
    cm = [[0] * len(classes) for _ in classes]
    for t, p in pairs:
        cm[classes.index(t)][classes.index(p)] += 1
    return cm


def macro_f1(cm, classes):
    present = [k for k in range(len(classes)) if sum(cm[k]) > 0]
    if len(present) < 2:
        return None
    f1s = []
    for k in present:
        tp, pred, true = cm[k][k], sum(row[k] for row in cm), sum(cm[k])
        if pred == 0 or tp == 0:
            f1s.append(0.0)
        else:
            prec, rec = tp / pred, tp / true
            f1s.append(2 * prec * rec / (prec + rec))
    return mean(f1s)


def verify_activity(c: Checker, out: Path, results: dict) -> None:
    for ls in ("primary_3class", "secondary_4class"):
        rows = read(out / f"activity_predictions_{ls}.csv")
        block = results["activity"][ls]
        classes = block["classes"]
        c.equal(f"act/{ls} window count", len(rows), block["n_windows"])
        for m in ACT_MODELS:
            mod = block["models"][m]
            cm = confusion([(r["true"], r[m]) for r in rows], classes)
            c.equal(f"act/{ls}/{m} confusion", cm, mod["confusion_matrix"])
            c.close(f"act/{ls}/{m} accuracy", sum(cm[k][k] for k in range(len(classes))) / len(rows), mod["pooled"]["accuracy"])
            c.close(f"act/{ls}/{m} macro-F1", macro_f1(cm, classes), mod["pooled"]["macro_f1"])
            for p, rep in mod["per_fold"].items():
                fold = [(r["true"], r[m]) for r in rows if r["participant"] == p]
                fcm = confusion(fold, classes)
                c.close(f"act/{ls}/{m}/{p} accuracy", sum(t == q for t, q in fold) / len(fold), rep["accuracy"])
                c.close(f"act/{ls}/{m}/{p} macro-F1", macro_f1(fcm, classes), rep["macro_f1"])
                if rep["macro_f1"] is None:
                    c.equal(f"act/{ls}/{m}/{p} n/a note", rep["macro_f1_note"], "n/a: single-class test fold")
            votes = []
            for rec in dict.fromkeys(r["record"] for r in rows):
                rr = [r for r in rows if r["record"] == rec]
                counts = [sum(r[m] == k for r in rr) for k in classes]
                votes.append((rr[0]["true"], classes[counts.index(max(counts))]))
            c.equal(f"act/{ls}/{m} record-level confusion", confusion(votes, classes), mod["record_level"]["confusion_matrix"])
    for row in read(out / "activity_confusion.csv"):
        block = results["activity"][row["label_set"]]
        cls = block["classes"]
        mod = block["models"][row["model"]]
        cm = mod["confusion_matrix"] if row["level"] == "window" else mod["record_level"]["confusion_matrix"]
        c.equal(f"activity_confusion.csv {row['label_set']}/{row['model']}/{row['level']}/{row['true']}->{row['predicted']}",
                int(row["count"]), cm[cls.index(row["true"])][cls.index(row["predicted"])])


def verify_windows(c: Checker, out: Path, results: dict) -> None:
    rows = read(out / "windows.csv")
    c.equal("windows.csv count", len(rows), results["dataset_check"]["n_windows"])
    keys = {(r["record"], r["start_sample"]) for r in rows}
    c.equal("windows unique (record, start)", len(keys), len(rows))
    c.equal("participant = record prefix", all(r["record"].split("_")[0] == r["participant"] for r in rows), True)
    c.equal("participants", sorted({r["participant"] for r in rows}), results["dataset_check"]["participants"])
    c.equal("records", len({r["record"] for r in rows}), 19)
    c.equal("A1 identical to M5", results["dataset_check"]["a1_matches_m5_dsp_hr"]["all_identical"], True)


def verify_report(c: Checker, out: Path, results: dict) -> None:
    sys.path.insert(0, str(M6_DIR))
    from m6_report import render
    c.equal("report.md == render(results.json)", (out / "report.md").read_text(encoding="utf-8") == render(results), True)


def verify(out: Path) -> Checker:
    results = json.loads((out / "results.json").read_text(encoding="utf-8"))
    c = Checker()
    verify_windows(c, out, results)
    verify_hr(c, out, results)
    verify_activity(c, out, results)
    verify_report(c, out, results)
    return c


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else M6_DIR / "outputs"
    checker = verify(target)
    print(f"{checker.passed} checks passed, {len(checker.failures)} failed")
    for msg in checker.failures[:50]:
        print("FAIL", msg)
    sys.exit(1 if checker.failures else 0)
