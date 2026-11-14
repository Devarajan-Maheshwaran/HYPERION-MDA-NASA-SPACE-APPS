"""Minimal, standard-library WFDB reader for the formats used by PhysioNet `wrist/1.0.0`.

Supports exactly what the verified files use, and refuses anything else:
* header (.hea) record and signal lines;
* signal storage format 16 (little-endian 16-bit two's complement, interleaved);
* MIT annotation format (.atr), including SKIP/NUM/SUB/CHN/AUX codes.

Correctness is checked against the record's OWN header on every read: each signal's
first sample must equal the header "initial value", and the 16-bit sum of all its
samples must equal the header "checksum". A mismatch raises `WfdbFormatError`.
Physical values are (raw - baseline) / gain in the header's units; nothing is resampled.
"""

from __future__ import annotations

import re
import struct
import sys
from array import array
from dataclasses import dataclass
from pathlib import Path

_GAIN = re.compile(r"^(?P<gain>[-+0-9.eE]+)(\((?P<baseline>-?\d+)\))?(/(?P<units>.+))?$")


class WfdbFormatError(Exception):
    """The WFDB file is malformed or uses a feature this reader does not support."""


@dataclass(frozen=True)
class SignalSpec:
    index: int
    file_name: str
    fmt: int
    gain: float
    baseline: int
    units: str
    initial_value: int
    checksum: int
    description: str


@dataclass(frozen=True)
class Header:
    record: str
    n_signals: int
    fs_hz: float
    n_samples: int
    signals: tuple[SignalSpec, ...]
    comments: tuple[str, ...]


@dataclass(frozen=True)
class Annotation:
    sample: int
    code: int


def read_header(path: Path) -> Header:
    lines = path.read_text(encoding="ascii").splitlines()
    comments = tuple(l[1:].strip() for l in lines if l.startswith("#"))
    content = [l for l in lines if l.strip() and not l.startswith("#")]
    if not content:
        raise WfdbFormatError(f"{path.name}: empty header.")
    parts = content[0].split()
    if len(parts) < 4:
        raise WfdbFormatError(f"{path.name}: record line needs name, signal count, frequency and length.")
    try:
        n_sig, fs, n_samp = int(parts[1]), float(parts[2]), int(parts[3])
    except ValueError:
        raise WfdbFormatError(f"{path.name}: malformed record line {content[0]!r}.") from None
    specs = []
    for i, line in enumerate(content[1:1 + n_sig]):
        f = line.split(maxsplit=8)
        if len(f) < 9:
            raise WfdbFormatError(f"{path.name}: signal line {i + 1} is incomplete.")
        m = _GAIN.match(f[2])
        if not m:
            raise WfdbFormatError(f"{path.name}: cannot parse gain field {f[2]!r}.")
        fmt = int(f[1])
        if fmt != 16:
            raise WfdbFormatError(f"{path.name}: signal format {fmt} is not supported (only 16).")
        specs.append(SignalSpec(index=i, file_name=f[0], fmt=fmt, gain=float(m["gain"]),
                                baseline=int(m["baseline"] or 0), units=m["units"] or "",
                                initial_value=int(f[5]), checksum=int(f[6]), description=f[8].strip()))
    if len(specs) != n_sig:
        raise WfdbFormatError(f"{path.name}: expected {n_sig} signal lines, found {len(specs)}.")
    if len({s.file_name for s in specs}) != 1:
        raise WfdbFormatError(f"{path.name}: multi-file records are not supported.")
    return Header(parts[0], n_sig, fs, n_samp, tuple(specs), comments)


def _signed16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value >= 0x8000 else value


def read_signals(header: Header, dat_path: Path) -> list[array]:
    """Raw ADC values per signal (array of int16), verified against header checksums."""
    raw = array("h")
    data = dat_path.read_bytes()
    expected = header.n_samples * header.n_signals * 2
    if len(data) != expected:
        raise WfdbFormatError(f"{dat_path.name}: {len(data)} bytes, expected {expected} "
                              f"({header.n_samples} samples x {header.n_signals} signals x 2).")
    raw.frombytes(data)
    if sys.byteorder != "little":
        raw.byteswap()
    channels = [raw[i::header.n_signals] for i in range(header.n_signals)]
    for spec, values in zip(header.signals, channels):
        if values[0] != spec.initial_value:
            raise WfdbFormatError(f"{dat_path.name}: {spec.description} first sample {values[0]} "
                                  f"!= header initial value {spec.initial_value}.")
        if _signed16(sum(values)) != spec.checksum:
            raise WfdbFormatError(f"{dat_path.name}: {spec.description} checksum mismatch.")
    return channels


def to_physical(spec: SignalSpec, values: array) -> list[float]:
    if spec.gain == 0:
        raise WfdbFormatError(f"{spec.description}: gain is zero.")
    return [(v - spec.baseline) / spec.gain for v in values]


def read_annotations(path: Path) -> list[Annotation]:
    """MIT-format annotations: (sample index, annotation code)."""
    data = path.read_bytes()
    if len(data) % 2:
        raise WfdbFormatError(f"{path.name}: odd byte count.")
    words = struct.unpack(f"<{len(data) // 2}H", data)
    out: list[Annotation] = []
    t, i = 0, 0
    while i < len(words):
        word = words[i]
        code, value = word >> 10, word & 0x3FF
        i += 1
        if code == 0 and value == 0:
            break                                     # end of file marker
        if code == 59:                                # SKIP: 32-bit interval, high word first
            if i + 2 > len(words):
                raise WfdbFormatError(f"{path.name}: truncated SKIP.")
            hi, lo = words[i], words[i + 1]
            skip = (hi << 16) | lo
            t += skip - (1 << 32) if skip & 0x80000000 else skip
            i += 2
        elif code == 63:                              # AUX: value = byte length, padded to even
            i += (value + 1) // 2
        elif code in (60, 61, 62):                    # NUM / SUB / CHN modifiers
            continue
        else:
            t += value
            out.append(Annotation(sample=t, code=code))
    return out


# MIT annotation code 1 is a normal beat ("N"). In wrist/1.0.0 the reference ECG peaks
# are all code 1; each .atr also starts with header pseudo-annotations at sample <= 0
# (a NOTE with aux "## time resolution: 256" and a code-0 marker), and s9_walk has one
# in-record NOTE (code 22). Verified against the official wfdb package for all 19 records.
BEAT_CODE = 1


def beat_samples(annotations: list[Annotation]) -> list[int]:
    """Sample indices of beat annotations only (code 1); metadata and notes excluded."""
    return [a.sample for a in annotations if a.code == BEAT_CODE and a.sample > 0]
