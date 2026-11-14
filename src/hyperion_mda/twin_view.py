"""Wearable-style channel panel ("twin" layout) driven only by the signal registry.

Shows which data channels exist, their single status, and where they come from.
It is NOT a validated physiological digital twin: no health assessment, scores,
risk colours, cutoffs, diagnoses, treatment text or system integrations.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import signal_registry as reg

NOTICE = ("NOT A VALIDATED PHYSIOLOGICAL DIGITAL TWIN · This panel only lists data channels, their status and "
          "their source. It shows no health assessment, scores, risk levels or cutoffs, and is not connected to "
          "any NASA or CSA system.")

# Neutral, non-clinical badge colours (deliberately not red/amber/green). Text always states the status.
BADGE_FG = {
    reg.MEASURED_LAB_SAMPLE: "#1f5aa6",
    reg.RECORDED_NON_ASTRONAUT: "#5b3f99",
    reg.SIMULATED: "#7a5a2b",
    reg.UNAVAILABLE: "#5f6670",
}
BADGE_SYMBOL = {
    reg.MEASURED_LAB_SAMPLE: "■",
    reg.RECORDED_NON_ASTRONAUT: "◆",
    reg.SIMULATED: "◇",
    reg.UNAVAILABLE: "○",
}
OUTLINE = "#8a939c"
SELECT = "#1f5aa6"


def badge(status: str) -> str:
    return f"{BADGE_SYMBOL[status]} {reg.STATUS_TEXT[status]}"


def session_summary(records, mode: str) -> dict[str, str]:
    """Per-channel text describing what the main window has loaded (OSD-575 lab channels only)."""
    summary: dict[str, str] = {}
    if mode != "osdr":
        return summary
    counts: dict[str, list[int]] = {}
    for r in records:
        channel = reg.nasa_lab_channel_for(r.signal, r.unit)
        if channel is None:
            continue
        c = counts.setdefault(channel.channel_id, [0, 0])
        c[0 if r.has_value else 1] += 1
    for cid, (values, missing) in counts.items():
        summary[cid] = f"{values} values loaded" + (f", {missing} NA" if missing else "")
    return summary


class TwinPanel(tk.Toplevel):
    # Body outline regions on the canvas: (region, shape, coordinates, label position)
    BODY = [  # (region, shape, box, label position); body labels show names only, so nothing overlaps
        (reg.REGION_WHOLE_BODY, "rect", (30, 8, 220, 282), (75, 22)),
        (reg.REGION_HEAD, "oval", (95, 34, 155, 90), (125, 62)),
        (reg.REGION_CHEST, "rect", (82, 98, 168, 192), (125, 145)),
        (reg.REGION_WRIST, "oval", (178, 186, 206, 214), (192, 228)),
        (reg.REGION_BLOOD, "rect", (238, 40, 372, 122), (305, 81)),
        (reg.REGION_CABIN, "rect", (238, 162, 372, 244), (305, 203)),
    ]

    def __init__(self, master: tk.Misc, records=(), mode: str = "none") -> None:
        super().__init__(master)
        self.title("HYPERION-MDA · Channel panel (not a validated digital twin)")
        self.geometry("1180x700")
        self.minsize(900, 560)
        self.configure(bg="#101923")
        self.region_filter: str | None = None
        self.summary = session_summary(records, mode)
        self._build()
        self.refresh(records, mode)

    def _build(self) -> None:
        # Persistent notice: packed first, never hidden or replaced.
        self.notice = tk.Label(self, text=NOTICE, bg="#5a3413", fg="#ffe2b8", font=("Segoe UI", 9, "bold"),
                               padx=12, pady=9, justify="center")
        self.notice.pack(side="top", fill="x", padx=16, pady=(12, 8))
        self.notice.bind("<Configure>", lambda e: self.notice.configure(wraplength=max(300, e.width - 30)))

        body = ttk.Frame(self, padding=(16, 0, 16, 12))
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="Body regions (click to filter)", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.canvas = tk.Canvas(left, width=384, height=290, bg="#ffffff", highlightthickness=1,
                                highlightbackground="#c9d1d9")
        self.canvas.pack(pady=(4, 6))
        ttk.Button(left, text="Show all channels", command=lambda: self.set_filter(None)).pack(anchor="w")
        legend = ttk.LabelFrame(left, text="Status legend (exactly one per channel)", padding=8)
        legend.pack(fill="x", pady=(8, 0))
        for status in reg.STATUSES:
            row = ttk.Frame(legend)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=badge(status), fg=BADGE_FG[status], font=("Segoe UI", 9, "bold"),
                     width=22, anchor="w").pack(side="left")
            ttk.Label(row, text=reg.STATUS_MEANING[status], wraplength=220, justify="left",
                      font=("Segoe UI", 8)).pack(side="left")

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True, padx=(14, 0))
        self.heading = tk.StringVar()
        ttk.Label(right, textvariable=self.heading, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        # The session column sits before the long text columns so it is visible without scrolling.
        cols = ("channel", "status", "unit", "session", "region", "sampling")
        table_box = ttk.Frame(right)
        table_box.pack(side="top", fill="both", expand=True)
        self.table = ttk.Treeview(table_box, columns=cols, show="headings", height=12)
        for col, text, width in zip(cols, ("Channel", "Status", "Unit", "This session", "Region",
                                           "Sampling / collection"),
                                    (230, 165, 80, 145, 175, 460)):
            self.table.heading(col, text=text)
            self.table.column(col, width=width, minwidth=60, stretch=False)
        for status, colour in BADGE_FG.items():
            self.table.tag_configure(status, foreground=colour)
        yscroll = ttk.Scrollbar(table_box, orient="vertical", command=self.table.yview)
        xscroll = ttk.Scrollbar(table_box, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        table_box.rowconfigure(0, weight=1)
        table_box.columnconfigure(0, weight=1)
        self.table.bind("<<TreeviewSelect>>", self._show_channel)
        details = ttk.LabelFrame(right, text="Selected channel: source and status", padding=8)
        details.pack(fill="x", pady=(8, 0))
        self.details = tk.StringVar(value="Select a channel to see its source, sampling and status.")
        self.details_label = ttk.Label(details, textvariable=self.details, justify="left", wraplength=700)
        self.details_label.pack(fill="x", anchor="w")
        details.bind("<Configure>", lambda e: self.details_label.configure(wraplength=max(300, e.width - 24)))

    # ----- drawing and filtering ----------------------------------------------------------

    def _draw_body(self) -> None:
        c = self.canvas
        c.delete("all")
        # Plain neutral outline: limbs as lines, regions as clickable shapes. No risk colours.
        c.create_line(125, 90, 125, 98, fill=OUTLINE, width=2)
        c.create_line(82, 104, 52, 200, fill=OUTLINE, width=2)
        c.create_line(168, 104, 186, 188, fill=OUTLINE, width=2)
        c.create_line(102, 192, 98, 274, fill=OUTLINE, width=2)
        c.create_line(148, 192, 152, 274, fill=OUTLINE, width=2)
        counts = {}
        for ch in reg.CHANNELS:
            counts.setdefault(ch.region, []).append(ch.status)
        for region, shape, xy, (lx, ly) in self.BODY:
            selected = self.region_filter == region
            kwargs = dict(outline=SELECT if selected else OUTLINE, width=3 if selected else 1.5,
                          fill="", tags=("region", f"region:{region}"))
            if region == reg.REGION_WHOLE_BODY:
                kwargs["dash"] = (4, 4)
            (c.create_oval if shape == "oval" else c.create_rectangle)(*xy, **kwargs)
            statuses = counts.get(region, [])
            n_meas = statuses.count(reg.MEASURED_LAB_SAMPLE)
            n_unav = statuses.count(reg.UNAVAILABLE)
            boxed = region in (reg.REGION_BLOOD, reg.REGION_CABIN)
            text = f"{region}\n{n_meas} measured · {n_unav} unavailable" if boxed else region
            c.create_text(lx, ly, text=text, font=("Segoe UI", 8), fill="#1d2731",
                          width=124 if boxed else 90, justify="center",
                          tags=("region_label", f"region:{region}"))
        for region, *_ in self.BODY:
            c.tag_bind(f"region:{region}", "<Button-1>", lambda _e, r=region: self.set_filter(r))

    def set_filter(self, region: str | None) -> None:
        self.region_filter = region
        self._draw_body()
        self._fill()

    def refresh(self, records=(), mode: str = "none") -> None:
        self.summary = session_summary(records, mode)
        self._draw_body()
        self._fill()

    def _fill(self) -> None:
        self.table.delete(*self.table.get_children())
        shown = reg.channels_in(self.region_filter)
        order = {r: i for i, r in enumerate(reg.REGIONS)}
        for ch in sorted(shown, key=lambda c: (order[c.region], c.status, c.label)):
            session = self.summary.get(ch.channel_id,
                                       "not loaded" if ch.status == reg.MEASURED_LAB_SAMPLE else "—")
            self.table.insert("", "end", iid=ch.channel_id, tags=(ch.status,),
                              values=(ch.label, badge(ch.status), ch.unit or "—", session,
                                      ch.region, ch.sampling))
        where = self.region_filter or "all regions"
        self.heading.set(f"{len(shown)} channels · {where}")

    def _show_channel(self, _event=None) -> None:
        sel = self.table.selection()
        if not sel:
            return
        ch = next(c for c in reg.CHANNELS if c.channel_id == sel[0])
        self.details.set(
            f"{ch.label}  [{badge(ch.status)}]\n"
            f"Status meaning: {reg.STATUS_MEANING[ch.status]}\n"
            f"Source: {ch.source}\n"
            f"Sampling / collection: {ch.sampling}\n"
            + (f"Unit: {ch.unit}\n" if ch.unit else "")
            + f"Note: {ch.note}")
