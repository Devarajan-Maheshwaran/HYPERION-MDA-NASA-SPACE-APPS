from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from .chart import prepare_series
from .chart_view import SeriesChart
from .engine import DEMO_FLAG_ABS_Z, CsvLoadError, TelemetryRecord, read_records
from .osdr_cmp import OsdrSchemaError, load_osd575_cmp
from .osdr_source import OsdrSourceError, verified_cmp_file
from .fl_view import FLWindow
from .playback_view import PlaybackWindow
from .recorded_view import RecordedWindow
from .twin_view import TwinPanel

# Banner and footer text for each data source. Nothing here is a diagnosis or alert.
BANNERS = {
    "none": "RESEARCH PROTOTYPE · NO DATA LOADED · NOT FOR MEDICAL DECISIONS",
    "osdr": ("NASA LAB DATA · OSDR OSD-575 · sparse laboratory measurements — not wearable telemetry · serum "
             "metabolic panel (CMP) from the 4 Inspiration4 crew · NOT FOR MEDICAL DECISIONS"),
    "csv": "USER-SELECTED CSV · provenance not verified by this app · NOT FOR MEDICAL DECISIONS",
}
FOOTERS = {
    "none": ("Load the verified NASA OSDR OSD-575 file, or open your own CSV. "
             "This prototype shows descriptive comparisons only; it makes no diagnosis or recommendation."),
    "osdr": ("Each post-flight value (R+) is compared with the same person's pre-flight values (L-) for the same analyte "
             "and unit. The z-score is a descriptive, unvalidated comparison: no flag, threshold, laboratory reference "
             "range, diagnosis, risk alert or recommendation is used or shown. Four people; sparse timepoints."),
    "csv": (f"Observations are scored only against explicitly labelled baseline rows (same subject, signal, unit) "
            f"recorded earlier. The |z| ≥ {DEMO_FLAG_ABS_Z:g} flag is an illustrative display setting, "
            f"not a medical threshold or validated algorithm."),
}


class HyperionApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("HYPERION-MDA · Local Data Demo")
        # Fit the default size to the screen so the footer notice is not hidden behind
        # the taskbar on small/high-DPI displays (e.g. 1536x864 logical at 125 %).
        usable_h = self.winfo_screenheight() - 110
        usable_w = self.winfo_screenwidth() - 40
        self.minsize(min(900, usable_w), min(740, usable_h))
        self.geometry(f"{min(1180, usable_w)}x{min(860, usable_h)}")
        self.records: list[TelemetryRecord] = []
        self.mode = "none"
        self.import_summary = ""
        self._build()
        self._set_mode("none")

    def _build(self) -> None:
        self.configure(bg="#101923")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", rowheight=27, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", padding=(12, 7))

        # Title and subtitle share one line so the separate demo-lane row fits at the minimum size.
        header = tk.Frame(self, bg="#101923", padx=22, pady=10)
        header.pack(fill="x")
        tk.Label(header, text="HYPERION-MDA", fg="#f0f5fa", bg="#101923",
                 font=("Segoe UI", 20, "bold")).pack(side="left")
        tk.Label(header, text="Local data-provenance and descriptive comparison demonstration",
                 fg="#a9bac9", bg="#101923", font=("Segoe UI", 10)).pack(side="left", padx=(14, 0), pady=(6, 0))

        self.banner_text = tk.StringVar()
        self.banner = tk.Label(self, textvariable=self.banner_text, bg="#5a3413", fg="#ffe2b8",
                               font=("Segoe UI", 9, "bold"), padx=12, pady=9, justify="center")
        self.banner.pack(fill="x", padx=22)
        self.banner.bind("<Configure>", lambda e: self.banner.configure(wraplength=max(300, e.width - 30)))

        controls = ttk.Frame(self, padding=(22, 14, 22, 8))
        controls.pack(fill="x")
        ttk.Button(controls, text="Load NASA OSDR OSD-575 CMP (verified)",
                   command=self.load_osdr).pack(side="left")
        ttk.Button(controls, text="Open CSV…", command=self.open_csv).pack(side="left", padx=8)
        ttk.Button(controls, text="Channel panel…", command=self.open_channel_panel).pack(side="left")
        # Separate demo lanes on their own row; each opens its own window and never touches self.records.
        self.recorded_window: RecordedWindow | None = None
        self.twin_panel: TwinPanel | None = None
        self.playback_window: PlaybackWindow | None = None
        self.fl_window: FLWindow | None = None
        lanes = ttk.Frame(self, padding=(22, 0, 22, 4))
        lanes.pack(fill="x")
        ttk.Label(lanes, text="Separate demo lanes:").pack(side="left", padx=(0, 8))
        ttk.Button(lanes, text="Simulated wearable…", command=self.open_playback).pack(side="left")
        ttk.Button(lanes, text="Recorded wearable (PhysioNet)…", command=self.open_recorded).pack(side="left", padx=8)
        ttk.Button(lanes, text="FL simulation…", command=self.open_fl).pack(side="left")
        self.status = tk.StringVar(value="No data loaded")
        status_row = ttk.Frame(self, padding=(22, 0, 22, 4))
        status_row.pack(fill="x")
        ttk.Label(status_row, textvariable=self.status).pack(side="left")

        # Packed first at the bottom so the scoring notice is never clipped by a short window.
        self.footer_text = tk.StringVar()
        footer = tk.Label(self, textvariable=self.footer_text, bg="#101923", fg="#a9bac9",
                          font=("Segoe UI", 9), padx=22, pady=10, anchor="w", justify="left")
        footer.pack(side="bottom", fill="x")
        footer.bind("<Configure>", lambda e: footer.configure(wraplength=max(300, e.width - 44)))
        self.footer = footer

        # Vertical split (user-draggable): table above, chart + full-text details below.
        panes = ttk.PanedWindow(self, orient="vertical")
        panes.pack(fill="both", expand=True, padx=22, pady=(0, 8))
        table_frame = ttk.Frame(panes)
        panes.add(table_frame, weight=1)

        # The table must be a child of table_frame: a widget managed "in_" a frame
        # created after it is stacked beneath that frame and stays hidden.
        cols = ("time", "type", "subject", "signal", "value", "unit", "context", "source", "z", "note", "flags")
        self.table = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = (145, 85, 75, 170, 60, 95, 90, 150, 70, 230, 270)
        for col, width in zip(cols, widths):
            self.table.column(col, width=width, minwidth=55, stretch=(col == "flags"))
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.table.tag_configure("flag", background="#fff0df")
        self.table.bind("<<TreeviewSelect>>", self._show_selected)

        lower = ttk.Frame(panes)
        panes.add(lower, weight=2)
        chart_box = ttk.LabelFrame(lower, text="Values for the selected row's subject · signal · unit", padding=4)
        chart_box.pack(side="left", fill="both", expand=True)
        self.chart = SeriesChart(chart_box, height=260)
        self.chart.pack(fill="both", expand=True)
        details = ttk.LabelFrame(lower, text="Selected row (full text)", padding=(10, 6), width=360)
        details.pack(side="right", fill="y", padx=(8, 0))
        details.pack_propagate(False)
        # Keep the table/chart split proportional on resize (default 45 % table), so shrinking
        # the window never squeezes only the chart. Dragging the sash sets a new proportion.
        self._sash_fraction = 0.45

        def keep_proportion(event: tk.Event) -> None:
            if event.height > 100:  # ignore the 1 px size reported before first layout
                panes.sashpos(0, int(event.height * self._sash_fraction))

        def remember_drag(_event: tk.Event) -> None:
            height = panes.winfo_height()
            if height > 100:
                self._sash_fraction = min(0.85, max(0.15, panes.sashpos(0) / height))

        panes.bind("<Configure>", keep_proportion, add="+")
        panes.bind("<ButtonRelease-1>", remember_drag, add="+")
        self.details = tk.StringVar(value="")
        self.details_label = ttk.Label(details, textvariable=self.details, justify="left", wraplength=1000)
        self.details_label.pack(fill="both", anchor="nw")
        details.bind("<Configure>", lambda e: self.details_label.configure(wraplength=max(200, e.width - 24)))

    # ----- data source handling -------------------------------------------------------

    def _set_mode(self, mode: str) -> None:
        self.mode = mode
        self.banner_text.set(BANNERS[mode])
        self.footer_text.set(FOOTERS[mode])
        osdr = mode == "osdr"
        headings = {
            "time": "Timepoint" if osdr else "Timestamp", "type": "Type", "subject": "Subject",
            "signal": "Analyte" if osdr else "Signal", "value": "Value", "unit": "Unit",
            "context": "Context", "source": "Source", "z": "z (descriptive)" if osdr else "Demo z",
            "note": "Score basis", "flags": "Row warnings" if osdr else "Quality / row warnings / demo flags",
        }
        for col, text in headings.items():
            self.table.heading(col, text=text)

    def _clear(self, mode: str, details: str) -> None:
        self.records = []
        self.table.delete(*self.table.get_children())
        self.chart.show(None)
        self._set_mode(mode)
        self.import_summary = details
        self.details.set(details)
        self._refresh_panel()

    def open_channel_panel(self) -> None:
        """Open (or raise) the registry-driven channel panel. Display only; no scoring."""
        if self.twin_panel is not None and self.twin_panel.winfo_exists():
            self.twin_panel.refresh(self.records, self.mode)
            self.twin_panel.lift()
            return
        self.twin_panel = TwinPanel(self, self.records, self.mode)

    def open_playback(self) -> None:
        """SIMULATED wearable lane (separate window; never merged with NASA records)."""
        if self.playback_window is not None and self.playback_window.winfo_exists():
            self.playback_window.lift()
            return
        self.playback_window = PlaybackWindow(self)

    def open_recorded(self) -> None:
        """RECORDED non-astronaut lane (PhysioNet; separate window; never merged with NASA records)."""
        if self.recorded_window is not None and self.recorded_window.winfo_exists():
            self.recorded_window.lift()
            return
        self.recorded_window = RecordedWindow(self)

    def open_fl(self) -> None:
        """FL SIMULATION on generated toy data (separate window; no NASA or wearable data)."""
        if self.fl_window is not None and self.fl_window.winfo_exists():
            self.fl_window.lift()
            return
        self.fl_window = FLWindow(self)

    def _refresh_panel(self) -> None:
        if self.twin_panel is not None and self.twin_panel.winfo_exists():
            self.twin_panel.refresh(self.records, self.mode)

    def load_osdr(self) -> None:
        """Load only the checksum-verified OSDR file; on any failure, load nothing."""
        try:
            verified = verified_cmp_file()
            records, report = load_osd575_cmp(verified)
        except (OsdrSourceError, OsdrSchemaError, OSError, UnicodeDecodeError) as exc:
            self._clear("none", f"OSDR OSD-575 data NOT loaded.\n\n{exc}")
            self.status.set("OSDR load failed · no data shown")
            messagebox.showerror("OSDR data not loaded", f"{exc}\n\nNo other data was substituted.")
            return
        manifest = verified.manifest
        self._clear("osdr", "")
        self._fill(records)
        missing = len(report.missing_value_lines)
        self.status.set(f"NASA lab data · {report.data_rows} rows · {missing} NA · OSD-575 CMP · SHA-256 verified")
        self.import_summary = "\n".join(
            [f"{manifest['study_id']}: {manifest['study_title']}",
             f"Retrieved {manifest['retrieved_utc']} from NASA OSDR; SHA-256 {manifest['sha256'][:16]}… verified.",
             *report.summary_lines(),
             "Select a row to see its comparison and the chart for that subject and analyte."])
        self.details.set(self.import_summary)

    def open_csv(self) -> None:
        selected = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if selected:
            self.load_path(Path(selected))

    def load_path(self, path: Path) -> None:
        try:
            records, issues = read_records(path)
        except CsvLoadError as exc:
            messagebox.showerror("Could not load CSV", f"{path.name}\n\n{exc}")
            return
        self._clear("csv", "Select a row to see its full score basis and warnings.")
        self._fill(records)
        self.status.set(f"{len(records)} rows · {path.name}")
        if issues:
            messagebox.showwarning("CSV notes", "\n".join(issues[:12]))

    def _fill(self, records: list[TelemetryRecord]) -> None:
        self.records = records
        for record in records:
            flags = "; ".join(record.flags) if record.flags else "—"
            values = (record.timestamp or "—", record.record_type, record.subject_id, record.signal,
                      f"{record.value:g}" if record.has_value else "NA", record.unit, record.context or "—",
                      record.source, f"{record.z_score:.2f}" if record.z_score is not None else "—",
                      record.score_note, flags)
            self.table.insert("", "end", values=values, tags=("flag",) if record.flags else ())
        self._refresh_panel()

    def _show_selected(self, _event: object = None) -> None:
        selection = self.table.selection()
        if not selection:
            return
        record = self.records[self.table.index(selection[0])]
        z = f"{record.z_score:.2f}" if record.z_score is not None else "none"
        warnings = "; ".join(record.flags) if record.flags else "none"
        value = f"{record.value:g}" if record.has_value else "NA (missing in source)"
        if self.mode == "osdr":
            phase = "pre-flight baseline" if record.record_type == "baseline" else "post-flight observation"
            self.details.set(
                f"{record.subject_id} · {record.signal} · {record.timestamp} ({phase})\n"
                f"Value: {value} {record.unit}\n"
                f"Descriptive z (unvalidated): {z}\n"
                f"Score basis: {record.score_note}\n"
                f"Warnings: {warnings}\n"
                f"Source: {record.source_ref}")
        else:
            self.details.set(
                f"Row {record.row_number} · {record.record_type} · {record.timestamp or '(no timestamp)'} · "
                f"{record.subject_id} {record.signal} {value} {record.unit}\n"
                f"Demo z: {z}\nScore basis: {record.score_note}\nWarnings / demo flags: {warnings}")
        self.chart.show(prepare_series(self.records, record))


def main() -> None:
    HyperionApp().mainloop()
