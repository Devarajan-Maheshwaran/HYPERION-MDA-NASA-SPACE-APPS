"""Methods check: heart rate from wrist PPG compared with the dataset's reference ECG beats.

NON-ASTRONAUT methods demonstration on PhysioNet "Wrist PPG During Exercise" v1.0.0
(8 adults, terrestrial lab exercise). It measures how far a simple, documented PPG
peak-interval estimate is from the hand-marked reference ECG R-peaks in the same
windows. It is NOT a validated algorithm, NOT a clinical measurement, and it makes
no claim about astronauts or spaceflight. Requires numpy and scipy (project .venv).

All parameters below were fixed before any result was computed and are reported
with the results. Time base: the uniform 256 Hz sample index (see physionet_adapter).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.signal import butter, find_peaks, sosfiltfilt

from .physionet_adapter import RecordedPhysioNetAdapter
from .physionet_source import load_manifest

WINDOW_S = 8.0
STEP_S = 2.0
BAND_HZ = (0.5, 4.0)            # 30-240 per minute pass band
FILTER_ORDER = 3
MIN_PEAK_DISTANCE_S = 0.33      # caps detectable rate near 180 per minute
PROMINENCE_FRACTION_OF_SD = 0.5
MIN_BEATS = 3

PARAMETERS = {
    "window_s": WINDOW_S, "step_s": STEP_S, "band_hz": BAND_HZ, "filter": f"Butterworth order {FILTER_ORDER}, zero-phase (sosfiltfilt)",
    "min_peak_distance_s": MIN_PEAK_DISTANCE_S, "prominence": f"{PROMINENCE_FRACTION_OF_SD} x window SD",
    "min_beats_per_window": MIN_BEATS, "reference": "60 / median RR of hand-marked ECG beats (code 1) in the window",
    "estimate": "60 / median interval of PPG peaks in the window", "time_base": "uniform 256 Hz sample index",
}


@dataclass
class RecordResult:
    record: str
    participant: str
    activity: str
    windows: int = 0
    compared: int = 0
    no_ppg_estimate: int = 0
    no_reference: int = 0
    errors_bpm: list[float] = field(default_factory=list)

    @property
    def median_abs_error(self) -> float | None:
        return float(np.median(np.abs(self.errors_bpm))) if self.errors_bpm else None

    @property
    def mean_error(self) -> float | None:
        return float(np.mean(self.errors_bpm)) if self.errors_bpm else None


def _rate_from_intervals(samples: np.ndarray, fs: float) -> float | None:
    if samples.size < MIN_BEATS:
        return None
    intervals = np.diff(samples) / fs
    return float(60.0 / np.median(intervals)) if intervals.size else None


def check_record(record: str) -> RecordResult:
    adapter = RecordedPhysioNetAdapter(record)
    fs = adapter.fs
    spec = next(s for d, _l, s in adapter._specs if d == "wrist_ppg")
    ppg = (np.asarray(adapter._raw["wrist_ppg"], dtype=float) - spec.baseline) / spec.gain
    sos = butter(FILTER_ORDER, BAND_HZ, btype="bandpass", fs=fs, output="sos")
    filtered = sosfiltfilt(sos, ppg)
    beats = np.asarray(adapter.beats)
    result = RecordResult(record, record.split("_")[0],
                          adapter.header.comments[0] if adapter.header.comments else "not stated")
    win, step, n = int(WINDOW_S * fs), int(STEP_S * fs), adapter.header.n_samples
    for start in range(0, n - win + 1, step):
        result.windows += 1
        ref = _rate_from_intervals(beats[(beats >= start) & (beats < start + win)], fs)
        if ref is None:
            result.no_reference += 1
            continue
        segment = filtered[start:start + win]
        peaks, _ = find_peaks(segment, distance=int(MIN_PEAK_DISTANCE_S * fs),
                              prominence=PROMINENCE_FRACTION_OF_SD * float(np.std(segment)))
        est = _rate_from_intervals(peaks, fs)
        if est is None:
            result.no_ppg_estimate += 1
            continue
        result.compared += 1
        result.errors_bpm.append(est - ref)
    return result


def run_check(records: list[str] | None = None) -> list[RecordResult]:
    return [check_record(r) for r in (records or load_manifest()["records"])]
