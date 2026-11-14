"""Sensor-adapter boundary for wearable streams, plus a playback session.

`WearableAdapter` is the interface a future real wearable adapter would implement.
**No real device adapter exists in this project**; the only implementation is
`SimulatedPlaybackAdapter`, which replays the deterministic SIMULATED signals from
`sim_wearable.py` so that the boundary and the playback controls can be exercised.

Every sample crossing the boundary is validated (finite value, known channel, exact
unit, non-negative and strictly increasing time per channel, declared provenance).
Invalid input raises `AdapterError` with a readable message; nothing is repaired.
Samples are `WearableSample` objects, a different type from the NASA lab records,
and nothing here imports or writes the NASA lab-data pipeline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from . import sim_wearable


class AdapterError(Exception):
    """Malformed or inconsistent data at the adapter boundary."""


@dataclass(frozen=True)
class ChannelSpec:
    channel_id: str
    label: str
    unit: str
    rate_hz: float


@dataclass(frozen=True)
class WearableSample:
    t_s: float
    channel_id: str
    value: float
    unit: str
    provenance: str  # e.g. "SIMULATED"; a real adapter would declare its own, verified source


@runtime_checkable
class WearableAdapter(Protocol):
    """Interface for wearable sources.

    A future real adapter must: declare `provenance` truthfully, set `is_real_device`
    only when a device is actually connected and verified, list its channels with
    exact units, and return samples for a time window. It must not invent values.
    """

    name: str
    provenance: str
    is_real_device: bool

    def channels(self) -> tuple[ChannelSpec, ...]: ...

    def duration_s(self) -> float: ...

    def read(self, t_start: float, t_end: float) -> list[WearableSample]: ...


class SimulatedPlaybackAdapter:
    """Replays the deterministic SIMULATED waveforms. Not a device connection."""

    name = "Simulated playback (deterministic, no device)"
    provenance = sim_wearable.SIMULATED
    is_real_device = False

    def channels(self) -> tuple[ChannelSpec, ...]:
        return tuple(ChannelSpec(c.channel_id, c.label, c.unit, c.rate_hz) for c in sim_wearable.CHANNELS)

    def duration_s(self) -> float:
        return float(sim_wearable.DURATION_S)

    def read(self, t_start: float, t_end: float) -> list[WearableSample]:
        if not (math.isfinite(t_start) and math.isfinite(t_end)) or t_start < 0 or t_end < t_start:
            raise AdapterError(f"Invalid read window [{t_start}, {t_end}).")
        samples: list[WearableSample] = []
        end = min(t_end, self.duration_s())
        for ch in self.channels():
            step = 1.0 / ch.rate_hz
            k = math.ceil(round(t_start / step, 9))
            while (t := round(k * step, 9)) < end:
                samples.append(WearableSample(t, ch.channel_id, sim_wearable.value_at(ch.channel_id, t),
                                              ch.unit, self.provenance))
                k += 1
        return samples


def validate_samples(samples: list[WearableSample], adapter: WearableAdapter) -> list[WearableSample]:
    """Reject anything malformed instead of repairing it."""
    specs = {c.channel_id: c for c in adapter.channels()}
    last_t: dict[str, float] = {}
    for s in samples:
        if not isinstance(s, WearableSample):
            raise AdapterError(f"Unexpected sample type {type(s).__name__}; expected WearableSample.")
        if s.channel_id not in specs:
            raise AdapterError(f"Unknown channel {s.channel_id!r} from {adapter.name}.")
        if s.unit != specs[s.channel_id].unit:
            raise AdapterError(f"Unit {s.unit!r} does not match {specs[s.channel_id].unit!r} for {s.channel_id}.")
        if not isinstance(s.value, (int, float)) or not math.isfinite(s.value):
            raise AdapterError(f"Non-finite value at t={s.t_s} s on {s.channel_id}; not imputed.")
        if not math.isfinite(s.t_s) or s.t_s < 0:
            raise AdapterError(f"Invalid time {s.t_s!r} on {s.channel_id}.")
        if s.channel_id in last_t and s.t_s <= last_t[s.channel_id]:
            raise AdapterError(f"Time not increasing on {s.channel_id} at t={s.t_s} s.")
        if s.provenance != adapter.provenance:
            raise AdapterError(f"Sample provenance {s.provenance!r} differs from adapter {adapter.provenance!r}.")
        last_t[s.channel_id] = s.t_s
    return samples


class PlaybackSession:
    """Start / pause / reset / seek over an adapter's time range. Pure logic (no Tk)."""

    def __init__(self, adapter: WearableAdapter, window_s: float = 60.0, step_s: float = 1.0) -> None:
        if not isinstance(adapter, WearableAdapter):
            raise AdapterError("Adapter does not implement the WearableAdapter interface.")
        if window_s <= 0 or step_s <= 0:
            raise AdapterError("Window and step must be positive.")
        self.adapter = adapter
        self.window_s = window_s
        self.step_s = step_s
        self.position_s = 0.0
        self.running = False

    @property
    def finished(self) -> bool:
        return self.position_s >= self.adapter.duration_s()

    def start(self) -> None:
        if self.finished:
            self.reset()
        self.running = True

    def pause(self) -> None:
        self.running = False

    def reset(self) -> None:
        self.running = False
        self.position_s = 0.0

    def seek(self, t_s: float) -> None:
        try:
            t = float(t_s)
        except (TypeError, ValueError):
            raise AdapterError(f"Cannot seek to {t_s!r}: not a number.") from None
        if not math.isfinite(t):
            raise AdapterError(f"Cannot seek to {t_s!r}: not a finite time.")
        self.position_s = min(max(t, 0.0), self.adapter.duration_s())

    def tick(self) -> bool:
        """Advance one step if running. Returns True if the position changed."""
        if not self.running:
            return False
        self.position_s = min(self.position_s + self.step_s, self.adapter.duration_s())
        if self.finished:
            self.running = False
        return True

    def visible(self) -> list[WearableSample]:
        """Validated samples in the window ending at the current position."""
        start = max(0.0, self.position_s - self.window_s)
        return validate_samples(self.adapter.read(start, self.position_s), self.adapter)
