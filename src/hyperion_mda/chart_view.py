"""Tk canvas that draws a prepared ChartSeries. Markers only, no connecting lines.

Points are not joined, so the chart never implies values between readings.
No thresholds, bands, or interpretation are drawn.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime, timezone

from .chart import ChartSeries, nice_ticks, padded_range

BG = "#ffffff"
AXIS = "#55606b"
GRID = "#e6eaee"
TEXT = "#1d2731"
MUTED = "#66727e"
BASELINE = "#2f6db5"
OBSERVATION = "#c4581b"
SELECTED = "#101923"
FONT = ("Segoe UI", 9)
FONT_BOLD = ("Segoe UI", 10, "bold")

MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM = 64, 20, 72, 70


class SeriesChart(tk.Canvas):
    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, bg=BG, highlightthickness=1, highlightbackground="#c9d1d9", **kwargs)
        self.series: ChartSeries | None = None
        self.placeholder = "Select a row to chart its subject, signal, and unit over time."
        self.bind("<Configure>", lambda _e: self.redraw())

    def show(self, series: ChartSeries | None, placeholder: str | None = None) -> None:
        self.series = series
        if placeholder:
            self.placeholder = placeholder
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width, height = max(self.winfo_width(), 200), max(self.winfo_height(), 120)
        series = self.series
        if series is None:
            self._centered(width, height, self.placeholder)
            return
        self.create_text(12, 10, anchor="nw", font=FONT_BOLD, fill=TEXT,
                         text=f"{series.signal} ({series.unit}) · subject {series.subject_id}")
        self.create_text(12, 28, anchor="nw", font=FONT, fill=MUTED,
                         text="Imported values only · markers not joined (no interpolation) · not a clinical view")
        if not series.plottable:
            self._centered(width, height, series.message)
            return
        self._plot(series, width, height)

    def _centered(self, width: int, height: int, text: str) -> None:
        self.create_text(width / 2, height / 2, text=text, fill=MUTED, font=FONT,
                         width=max(180, width - 40), justify="center", tags=("message",))

    def _plot(self, series: ChartSeries, width: int, height: int) -> None:
        x0, y0 = MARGIN_LEFT, MARGIN_TOP
        x1, y1 = width - MARGIN_RIGHT, height - MARGIN_BOTTOM
        if x1 - x0 < 60 or y1 - y0 < 40:
            self._centered(width, height, "Enlarge the window to see the chart.")
            return
        mission = series.axis == "mission"
        if mission:
            # Ordered labels, evenly spaced: "days before launch" and "days after return"
            # use different reference points, so true spacing is not drawn.
            # Every timepoint in the series gets a slot, including ones whose value is NA,
            # so a missing reading shows as a visible gap rather than disappearing.
            keys = [k for k, _ in series.x_slots] or sorted({p.x_key for p in series.points})
            slot = {k: i for i, k in enumerate(keys)}
            labels = dict(series.x_slots) or {p.x_key: p.x_label for p in series.points}

            def pos(p) -> float:
                return float(slot[p.x_key])
            t_lo, t_hi = -0.5, len(keys) - 0.5
        else:
            def pos(p) -> float:
                return p.time_utc.timestamp()
            times = [pos(p) for p in series.points]
            t_lo, t_hi = padded_range(min(times), max(times), 0.04)
        values = [p.value for p in series.points]
        v_lo, v_hi = padded_range(min(values), max(values))

        def sx(t: float) -> float:
            return x0 + (t - t_lo) / (t_hi - t_lo) * (x1 - x0)

        def sy(v: float) -> float:
            return y1 - (v - v_lo) / (v_hi - v_lo) * (y1 - y0)

        # Grid and round-number value ticks.
        for v in nice_ticks(v_lo, v_hi, 5 if y1 - y0 >= 100 else 3):
            y = sy(v)
            self.create_line(x0, y, x1, y, fill=GRID)
            self.create_text(x0 - 6, y, anchor="e", text=f"{v:g}", font=FONT, fill=MUTED)
        if mission:
            for k in keys:
                x = sx(slot[k])
                self.create_line(x, y1, x, y1 + 4, fill=AXIS)
                self.create_text(x, y1 + 7, anchor="n", text=labels[k], font=FONT, fill=MUTED,
                                 tags=("xtick",))
            pre = [slot[k] for k in keys if k[0] == 0]
            post = [slot[k] for k in keys if k[0] == 1]
            if pre and post:  # the flight itself happens between the last L- and first R+ label
                xm = sx((max(pre) + min(post)) / 2)
                self.create_line(xm, y0, xm, y1, fill=AXIS, dash=(3, 3), tags=("flight_marker",))
                self.create_text(xm, y0 + 2, anchor="n", text="flight", font=FONT, fill=MUTED)
            axis_title = "Mission timepoint (L-n before launch · R+n after return; not to scale)"
        else:
            # Time ticks (UTC), evenly spaced across the padded range.
            same_day = series.points[0].time_utc.date() == series.points[-1].time_utc.date()
            tick_count = max(2, min(6, int((x1 - x0) // 110)))
            for i in range(tick_count):
                t = t_lo + (t_hi - t_lo) * i / (tick_count - 1)
                x = sx(t)
                self.create_line(x, y1, x, y1 + 4, fill=AXIS)
                stamp = datetime.fromtimestamp(t, tz=timezone.utc)
                label = stamp.strftime("%H:%M") if same_day else stamp.strftime("%m-%d %H:%M")
                self.create_text(x, y1 + 7, anchor="n", text=label, font=FONT, fill=MUTED)
            day = series.points[0].time_utc.strftime("%Y-%m-%d")
            axis_title = f"Time (UTC){', ' + day if same_day else ''}"
        self.create_line(x0, y1, x1, y1, fill=AXIS)
        self.create_line(x0, y0, x0, y1, fill=AXIS)
        self.create_text((x0 + x1) / 2, y1 + 22, anchor="n", font=FONT, fill=TEXT, text=axis_title,
                         tags=("axis_title",))
        if y1 - y0 >= 120:  # rotated axis label only when it fits; the title always names signal and unit
            self.create_text(14, (y0 + y1) / 2, angle=90, font=FONT, fill=TEXT,
                             text=f"{series.signal} ({series.unit})")

        for p in series.points:
            x, y = sx(pos(p)), sy(p.value)
            if p.record_type == "baseline":
                self.create_oval(x - 4, y - 4, x + 4, y + 4, fill=BASELINE, outline=BASELINE,
                                 tags=("point", "baseline"))
            else:
                self.create_polygon(x, y - 6, x + 6, y, x, y + 6, x - 6, y, fill=BG, outline=OBSERVATION,
                                    width=2, tags=("point", "observation"))
        chosen = series.selected_point
        if chosen is not None:
            x, y = sx(pos(chosen)), sy(chosen.value)
            self.create_oval(x - 10, y - 10, x + 10, y + 10, outline=SELECTED, width=2, tags=("selected",))
            where = chosen.x_label if mission else f"{chosen.time_utc:%H:%M} UTC"
            ref = "line" if mission else "row"
            selected_text = (f"◯ selected: {ref} {chosen.row_number} · {chosen.record_type} · "
                             f"{chosen.value:g} {series.unit} · {where}")
            short_text = f"◯ selected: {ref} {chosen.row_number}"
        elif mission:
            selected_text = "Selected row has no value (NA) or no recognised timepoint, so it is not plotted."
            short_text = "Selected row not plotted (missing value)"
        else:
            selected_text = "Selected row has no valid timestamp, so it is not plotted."
            short_text = "Selected row not plotted (invalid timestamp)"
        self._legend(selected_text, short_text, chosen is None, width)

        if series.unplotted_rows:
            rows = ", ".join(str(r) for r in series.unplotted_rows[:8])
            more = "…" if len(series.unplotted_rows) > 8 else ""
            # Placed below the axis title (never on top of it); details stay in the table.
            self.create_text(x0, y1 + 38, anchor="nw", font=FONT, fill=OBSERVATION, width=x1 - x0,
                             text=(f"Not plotted (NA or no valid time; still in table): "
                                   f"{'lines' if mission else 'rows'} {rows}{more}"),
                             tags=("note",))

    def _legend(self, selected_text: str, short_text: str, warn: bool, width: int) -> None:
        """Own row under the subtitle, so it never overlaps the title or the points."""
        x, y = 14, 50
        self.create_oval(x, y - 4, x + 8, y + 4, fill=BASELINE, outline=BASELINE)
        self.create_text(x + 13, y, anchor="w", text="baseline", font=FONT, fill=TEXT)
        x += 78
        self.create_polygon(x + 4, y - 6, x + 10, y, x + 4, y + 6, x - 2, y, fill=BG, outline=OBSERVATION, width=2)
        self.create_text(x + 15, y, anchor="w", text="observation", font=FONT, fill=TEXT)
        room = width - (x + 100) - 8
        if tkfont.Font(font=FONT_BOLD).measure(selected_text) > room:
            selected_text = short_text  # full details remain in the "Selected row" panel
        self.create_text(x + 100, y, anchor="w", text=selected_text, font=FONT_BOLD,
                         fill=OBSERVATION if warn else SELECTED, tags=("selected_label",))
