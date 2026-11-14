"""RECORDED-NON-ASTRONAUT adapter: PhysioNet "Wrist PPG During Exercise" v1.0.0 behind
the existing `WearableAdapter` boundary.

Every record is SHA-256-verified against the pinned owner checksums before reading, and
every signal is checked against its own WFDB header checksum by `wfdb_reader`.
Time base: the uniform 256 Hz sample index declared in the header. The dataset's
wrist timestamp channel (60 s rollover clock with whole-second jumps) is NOT used
to re-time samples; that is a documented limitation.

This is terrestrial laboratory data from 8 adults. It is not astronaut data, not a
spaceflight measurement, not a device connection, and it is never merged with the
NASA lab-data records.
"""

from __future__ import annotations

import math
from pathlib import Path

from .adapters import AdapterError, ChannelSpec, WearableSample
from .physionet_source import PROVENANCE, PhysioNetSourceError, load_manifest, verified_record
from .wfdb_reader import WfdbFormatError, beat_samples, read_annotations, read_header, read_signals

# Signals exposed for playback (header descriptions, exact). Units come from the header.
PLAYBACK_SIGNALS = (
    ("chest_ecg", "Chest ECG"),
    ("wrist_ppg", "Wrist PPG"),
    ("wrist_low_noise_accelerometer_x", "Wrist accelerometer x (low-noise)"),
    ("wrist_low_noise_accelerometer_y", "Wrist accelerometer y (low-noise)"),
    ("wrist_low_noise_accelerometer_z", "Wrist accelerometer z (low-noise)"),
)
LABEL_PREFIX = "RECORDED non-astronaut"


class RecordedPhysioNetAdapter:
    """Replays one verified PhysioNet record. Not a device connection."""

    provenance = PROVENANCE
    is_real_device = False

    def __init__(self, record: str, cache_dir: Path | None = None) -> None:
        try:
            verified = verified_record(record, cache_dir)
            self.header = read_header(verified.header)
            raw = read_signals(self.header, verified.signals)
            self.beats = beat_samples(read_annotations(verified.annotations))
        except (PhysioNetSourceError, WfdbFormatError, OSError) as exc:
            raise AdapterError(str(exc)) from exc
        self.record = record
        self.fs = self.header.fs_hz
        by_name = {s.description: s for s in self.header.signals}
        self._specs, self._raw = [], {}
        for desc, label in PLAYBACK_SIGNALS:
            if desc not in by_name:
                raise AdapterError(f"{record}: expected signal {desc!r} is missing from the header.")
            spec = by_name[desc]
            self._specs.append((desc, label, spec))
            self._raw[desc] = raw[spec.index]
        manifest = load_manifest()
        activity = self.header.comments[0] if self.header.comments else "activity not stated"
        self.name = (f"PhysioNet {manifest['dataset']} v{manifest['version']} · record {record} "
                     f"({activity}) · recorded, non-astronaut")

    def channels(self) -> tuple[ChannelSpec, ...]:
        return tuple(ChannelSpec(f"physionet:{desc}", f"{LABEL_PREFIX} · {label}", spec.units, self.fs)
                     for desc, label, spec in self._specs)

    def duration_s(self) -> float:
        return self.header.n_samples / self.fs

    def read(self, t_start: float, t_end: float) -> list[WearableSample]:
        if not (math.isfinite(t_start) and math.isfinite(t_end)) or t_start < 0 or t_end < t_start:
            raise AdapterError(f"Invalid read window [{t_start}, {t_end}).")
        i0 = math.ceil(round(t_start * self.fs, 9))
        i1 = min(self.header.n_samples, math.ceil(round(t_end * self.fs, 9)))
        out: list[WearableSample] = []
        for desc, _label, spec in self._specs:
            values = self._raw[desc]
            cid = f"physionet:{desc}"
            for i in range(i0, i1):
                out.append(WearableSample(i / self.fs, cid, (values[i] - spec.baseline) / spec.gain,
                                          spec.units, self.provenance))
        return out
