"""Prepare imported rows for the time-series view (no Tk; unit-testable).

This only re-arranges imported values for display. It adds no thresholds,
bands, interpolation, or interpretation, and it does not change any score.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

from .engine import TelemetryRecord

MIN_PLOT_POINTS = 2


@dataclass(frozen=True)
class ChartPoint:
    time_utc: datetime | None  # None on a mission-relative axis (no calendar time exists)
    value: float
    record_type: str
    row_number: int
    selected: bool
    x_label: str = ""          # e.g. "R+45" on a mission-relative axis
    x_key: tuple | None = None


@dataclass(frozen=True)
class ChartSeries:
    subject_id: str
    signal: str
    unit: str
    points: tuple[ChartPoint, ...]
    unplotted_rows: tuple[int, ...]  # same series, but no valid time or no value (e.g. NA)
    message: str = ""                # non-empty → explain instead of plotting
    axis: str = "utc"                # "utc" or "mission" (ordered labels, not to scale)
    x_slots: tuple = ()              # mission axis: every (key, label) in the series, incl. NA rows

    @property
    def plottable(self) -> bool:
        return not self.message

    @property
    def selected_point(self) -> ChartPoint | None:
        return next((p for p in self.points if p.selected), None)


def prepare_series(records: list[TelemetryRecord], selected: TelemetryRecord) -> ChartSeries:
    """Collect every row with the selected row's subject, signal, and unit.

    Rows with a valid, offset-bearing timestamp become points (UTC, in
    chronological order; ties keep file order). Other rows in the series are
    listed in ``unplotted_rows`` and never placed on the time axis.
    """
    if not selected.has_group_key:
        return ChartSeries(selected.subject_id, selected.signal, selected.unit, (), (),
                           "Cannot chart this row: its subject, signal, or unit is missing, "
                           "so it cannot be grouped with other readings.")
    members = [r for r in records if r.group_key == selected.group_key]
    if any(r.parsed_time is None and r.order_key is not None for r in members):
        return _mission_series(members, selected)
    timed = sorted((r for r in members if r.parsed_time is not None and r.has_value),
                   key=lambda r: (r.parsed_time, r.row_number))
    points = tuple(ChartPoint(r.parsed_time.astimezone(timezone.utc), r.value, r.record_type,
                              r.row_number, r.row_number == selected.row_number) for r in timed)
    unplotted = tuple(sorted(r.row_number for r in members if r.parsed_time is None or not r.has_value))

    message = ""
    if len(points) < MIN_PLOT_POINTS:
        message = (f"Too few valid timestamps to plot: {len(points)} of {len(members)} row(s) in this "
                   f"series have a valid ISO 8601 timestamp with a UTC offset; at least "
                   f"{MIN_PLOT_POINTS} are needed. All rows remain listed in the table.")
    return ChartSeries(selected.subject_id, selected.signal, selected.unit, points, unplotted, message)


def _mission_series(members: list[TelemetryRecord], selected: TelemetryRecord) -> ChartSeries:
    """Mission-relative labels (e.g. L-92 … R+194): ordered, evenly spaced, never dated."""
    plotted = sorted((r for r in members if r.order_key is not None and r.has_value),
                     key=lambda r: (r.order_key, r.row_number))
    points = tuple(ChartPoint(None, r.value, r.record_type, r.row_number,
                              r.row_number == selected.row_number, x_label=r.timestamp, x_key=r.order_key)
                   for r in plotted)
    unplotted = tuple(sorted(r.row_number for r in members if r.order_key is None or not r.has_value))
    message = ""
    if len(points) < MIN_PLOT_POINTS:
        message = (f"Too few values to plot: {len(points)} of {len(members)} row(s) in this series have "
                   f"a value and a recognised timepoint; at least {MIN_PLOT_POINTS} are needed. "
                   "All rows remain listed in the table.")
    slots = tuple(sorted({(r.order_key, r.timestamp) for r in members if r.order_key is not None}))
    return ChartSeries(selected.subject_id, selected.signal, selected.unit, points, unplotted,
                       message, axis="mission", x_slots=slots)


def padded_range(low: float, high: float, fraction: float = 0.08) -> tuple[float, float]:
    """Axis limits with a little padding; widens a zero-width range so it can be drawn."""
    if high < low:
        low, high = high, low
    span = high - low
    if span == 0:
        pad = abs(low) * 0.05 or 1.0
        return low - pad, high + pad
    return low - span * fraction, high + span * fraction


def nice_ticks(low: float, high: float, max_ticks: int = 5) -> list[float]:
    """Round-numbered tick values (steps of 1, 2, or 5 × 10^k) inside [low, high]."""
    if high <= low or max_ticks < 2:
        return [low]
    raw = (high - low) / (max_ticks - 1)
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in (1, 2, 5, 10) if m * magnitude >= raw)
    first = math.ceil(low / step) * step
    ticks, value = [], first
    while value <= high + step * 1e-9:
        ticks.append(round(value, 10))
        value += step
    return ticks
