"""Deterministic, label-free window features from wrist PPG and wrist accelerometer only.

Every function here takes `RecordInputs` (which has no ECG field) or plain arrays.
Nothing here receives beat annotations or reference HR. Only frequency-domain and
scale-invariant features are used (amplitudes are uncalibrated).
"""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, find_peaks, sosfiltfilt

from m6_data import RecordInputs  # also puts src/ on sys.path
from hyperion_mda import dsp_hr   # frozen M5 method (constants + rate helper), not modified


def m5_filtered_ppg(ppg: np.ndarray, fs: float) -> np.ndarray:
    """Exactly the M5 dsp_hr preprocessing: Butterworth band-pass, zero-phase, whole record."""
    sos = butter(dsp_hr.FILTER_ORDER, dsp_hr.BAND_HZ, btype="bandpass", fs=fs, output="sos")
    return sosfiltfilt(sos, ppg)


def a1_estimate(segment: np.ndarray, fs: float) -> float | None:
    """Frozen M5 peak-interval estimate for one window (same calls as dsp_hr.check_record)."""
    peaks, _ = find_peaks(segment, distance=int(dsp_hr.MIN_PEAK_DISTANCE_S * fs),
                          prominence=dsp_hr.PROMINENCE_FRACTION_OF_SD * float(np.std(segment)))
    return dsp_hr._rate_from_intervals(peaks, fs)


def spectrum(x: np.ndarray, fs: float, nfft: int) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x, dtype=float) - float(np.mean(x))
    sd = float(np.std(x))
    if sd > 0:
        x = x / sd
    power = np.abs(np.fft.rfft(x * np.hanning(x.size), nfft)) ** 2
    return np.fft.rfftfreq(nfft, 1.0 / fs), power


def band_features(freqs: np.ndarray, power: np.ndarray, band: tuple[float, float],
                  width: float) -> tuple[np.ndarray, float, bool]:
    """Relative power per bin within the band, dominant frequency, degenerate flag."""
    lo, hi = band
    n_bins = int(round((hi - lo) / width))
    edges = lo + width * np.arange(n_bins + 1)
    inband = (freqs >= lo) & (freqs < hi)
    total = float(power[inband].sum())
    if not total > 0:
        return np.full(n_bins, 1.0 / n_bins), (lo + hi) / 2.0, True
    rel = np.array([power[(freqs >= a) & (freqs < b)].sum() / total for a, b in zip(edges[:-1], edges[1:])])
    dominant = float(freqs[inband][int(np.argmax(power[inband]))])
    return rel, dominant, False


def ppg_window_features(filtered_segment: np.ndarray, fs: float, cfg: dict):
    f, p = spectrum(filtered_segment, fs, cfg["spectrum"]["nfft"])
    c = cfg["ppg_features"]
    rel, dom, degenerate = band_features(f, p, tuple(c["band_hz"]), c["bin_width_hz"])
    return np.concatenate([rel, [dom]]), dom, degenerate


def accel_window_features(acc_segment: np.ndarray, fs: float, cfg: dict):
    mag = np.sqrt(np.sum(acc_segment ** 2, axis=1))
    f, p = spectrum(mag, fs, cfg["spectrum"]["nfft"])
    c = cfg["accel_features"]
    rel, dom, degenerate = band_features(f, p, tuple(c["band_hz"]), c["bin_width_hz"])
    centred = acc_segment - acc_segment.mean(axis=0)
    sds = centred.std(axis=0)
    corr = []
    for i, j in ((0, 1), (0, 2), (1, 2)):
        denom = sds[i] * sds[j]
        corr.append(float(np.mean(centred[:, i] * centred[:, j]) / denom) if denom > 0 else 0.0)
    total = float(np.sqrt(np.sum(sds ** 2)))
    shares = np.log(np.maximum(sds / total, 1e-6)) if total > 0 else np.full(3, np.log(1 / np.sqrt(3)))
    return np.concatenate([rel, [dom], corr, shares]), degenerate


def record_features(inputs: RecordInputs, starts: np.ndarray, cfg: dict) -> dict:
    """All per-window inputs-derived quantities for one record. No reference used."""
    fs = inputs.fs
    win = int(cfg["windows"]["window_s"] * fs)
    filtered = m5_filtered_ppg(inputs.ppg, fs)
    ppg_f, acc_f, a1, a2, mag_med, degenerate = [], [], [], [], [], 0
    for s in starts:
        seg = filtered[s:s + win]
        pf, dom, d1 = ppg_window_features(seg, fs, cfg)
        af, d2 = accel_window_features(inputs.accel[s:s + win], fs, cfg)
        est = a1_estimate(seg, fs)
        ppg_f.append(pf)
        acc_f.append(af)
        a1.append(np.nan if est is None else est)
        a2.append(60.0 * dom)
        mag_med.append(float(np.median(np.sqrt(np.sum(inputs.accel[s:s + win] ** 2, axis=1)))))
        degenerate += int(d1) + int(d2)
    return {"ppg": np.array(ppg_f), "accel": np.array(acc_f), "a1": np.array(a1), "a2": np.array(a2),
            "accel_mag_median": np.array(mag_med), "degenerate": degenerate}


PPG_FEATURE_NAMES = [f"ppg_rel_{0.5 + 0.25 * i:.2f}-{0.75 + 0.25 * i:.2f}Hz" for i in range(14)] + ["ppg_dominant_hz"]
ACCEL_FEATURE_NAMES = ([f"acc_rel_{0.25 + 0.25 * i:.2f}-{0.5 + 0.25 * i:.2f}Hz" for i in range(19)]
                       + ["acc_dominant_hz", "acc_corr_xy", "acc_corr_xz", "acc_corr_yz",
                          "acc_logsd_share_x", "acc_logsd_share_y", "acc_logsd_share_z"])
