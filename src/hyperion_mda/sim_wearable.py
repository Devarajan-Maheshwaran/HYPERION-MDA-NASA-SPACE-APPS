"""Deterministic SIMULATED wearable signals for the playback demonstration.

Every value here is produced by a fixed formula (no randomness, no data file).
Nothing is measured, nothing comes from a device, and nothing is astronaut data.
The shapes are arbitrary demo waveforms with no physiological or clinical meaning.
These values never enter the NASA lab-data records or any training pipeline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

SIMULATED = "SIMULATED"
DURATION_S = 300  # length of the demo recording, in seconds


@dataclass(frozen=True)
class SimChannel:
    channel_id: str
    label: str
    unit: str
    rate_hz: float


CHANNELS: tuple[SimChannel, ...] = (
    SimChannel("sim:hr-like", "SIMULATED heart-rate-like signal", "bpm (simulated)", 1.0),
    SimChannel("sim:skin-temp-like", "SIMULATED skin-temperature-like signal", "degC (simulated)", 0.5),
    SimChannel("sim:accel-like", "SIMULATED acceleration magnitude", "g (simulated)", 2.0),
)


def value_at(channel_id: str, t_s: float) -> float:
    """Arbitrary deterministic demo waveform for a channel at time t (seconds)."""
    two_pi = 2 * math.pi
    active = 1.0 if 120 <= t_s < 165 else 0.0  # a scripted "movement" segment, for demo only
    if channel_id == "sim:hr-like":
        return 70 + 5 * math.sin(two_pi * t_s / 60) + 2 * math.sin(two_pi * t_s / 11) + 18 * active
    if channel_id == "sim:skin-temp-like":
        return 33.0 + 0.25 * math.sin(two_pi * t_s / 240) - 0.2 * active
    if channel_id == "sim:accel-like":
        return 1.0 + 0.03 * math.sin(two_pi * t_s / 5) + 0.35 * active * (1 + math.sin(two_pi * t_s / 2))
    raise KeyError(f"Unknown simulated channel {channel_id!r}")
