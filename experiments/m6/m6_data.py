"""M6 data access. Reuses the audited M5 reader (SHA-256-verified files, header checksums).

Model inputs and the HR reference are loaded by two separate functions:
- `load_inputs` returns ONLY wrist PPG and the wrist low-noise accelerometer. The
  ECG waveform is read by the WFDB reader (it reads every channel to verify the
  checksums) but is discarded immediately and is not stored anywhere.
- `load_reference` returns ONLY the hand-marked beat sample indices from the
  annotation file. It never reads the signal file.

RECORDED-NON-ASTRONAUT data (8 adults, terrestrial lab exercise). Not astronaut data.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

M6_DIR = Path(__file__).resolve().parent
ROOT = M6_DIR.parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hyperion_mda.physionet_source import load_manifest, verified_record  # noqa: E402
from hyperion_mda.wfdb_reader import beat_samples, read_annotations, read_header, read_signals  # noqa: E402

CONFIG_PATH = M6_DIR / "m6-lopo-config.json"
PPG_SIGNAL = "wrist_ppg"
ACCEL_SIGNALS = ("wrist_low_noise_accelerometer_x", "wrist_low_noise_accelerometer_y",
                 "wrist_low_noise_accelerometer_z")
ECG_SIGNAL = "chest_ecg"


def load_config(path: Path = CONFIG_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class RecordInputs:
    """Model inputs for one record. Deliberately has no ECG field."""
    record: str
    participant: str
    activity: str          # from the record name: walk / run / low_resistance_bike / high_resistance_bike
    header_comment: str
    fs: float
    n_samples: int
    ppg: np.ndarray        # (n,) physical units as declared in the header (uncalibrated)
    accel: np.ndarray      # (n, 3) physical units as declared in the header (uncalibrated)


def participant_of(record: str) -> str:
    return record.split("_", 1)[0]


def activity_of(record: str) -> str:
    return record.split("_", 1)[1]


def record_names() -> list[str]:
    return list(load_manifest()["records"])


def load_inputs(record: str, cache_dir: Path | None = None) -> RecordInputs:
    verified = verified_record(record, cache_dir)
    header = read_header(verified.header)
    raw = read_signals(header, verified.signals)
    by_name = {s.description: s for s in header.signals}
    missing = [d for d in (PPG_SIGNAL, *ACCEL_SIGNALS) if d not in by_name]
    if missing:
        raise ValueError(f"{record}: header lacks {missing}")

    def physical(desc: str) -> np.ndarray:
        spec = by_name[desc]
        return (np.asarray(raw[spec.index], dtype=float) - spec.baseline) / spec.gain

    ppg = physical(PPG_SIGNAL)
    accel = np.column_stack([physical(d) for d in ACCEL_SIGNALS])
    del raw  # the ECG channel (and every other unused channel) is dropped here
    return RecordInputs(record, participant_of(record), activity_of(record),
                        header.comments[0] if header.comments else "not stated",
                        float(header.fs_hz), int(header.n_samples), ppg, accel)


def load_reference(record: str, cache_dir: Path | None = None) -> np.ndarray:
    """Hand-marked beat sample indices (annotation code 1). Reads only the .atr file."""
    verified = verified_record(record, cache_dir)
    return np.asarray(beat_samples(read_annotations(verified.annotations)), dtype=np.int64)


def window_starts(n_samples: int, fs: float, window_s: float, step_s: float) -> np.ndarray:
    win, step = int(window_s * fs), int(step_s * fs)
    return np.arange(0, n_samples - win + 1, step, dtype=np.int64)


def reference_for_windows(beats: np.ndarray, starts: np.ndarray, win: int, fs: float,
                          min_beats: int, rr_min_s: float, rr_max_s: float):
    """Per window: reference HR (nan if < min_beats), beat count, RR-quality flag (S2)."""
    ref = np.full(starts.size, np.nan)
    n_beats = np.zeros(starts.size, dtype=np.int64)
    quality_ok = np.ones(starts.size, dtype=bool)
    for i, s in enumerate(starts):
        b = beats[(beats >= s) & (beats < s + win)]
        n_beats[i] = b.size
        rr = np.diff(b) / fs
        if rr.size:
            quality_ok[i] = bool(np.all((rr >= rr_min_s) & (rr <= rr_max_s)))
        if b.size >= min_beats:
            ref[i] = 60.0 / float(np.median(rr))
    return ref, n_beats, quality_ok
