"""RECORDED non-astronaut wearable window (PhysioNet Wrist PPG During Exercise v1.0.0).

Lists the verified records, plays one back through the `WearableAdapter` boundary,
and shows the PPG-vs-reference-ECG heart-rate methods check. Never touches the NASA
lab-data records. Not astronaut data; not a device connection; no clinical meaning.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .adapters import AdapterError
from .physionet_adapter import RecordedPhysioNetAdapter
from .physionet_source import PhysioNetSourceError, load_manifest
from .playback_view import PlaybackWindow

REC_BANNER = ("RECORDED · NON-ASTRONAUT · PhysioNet \"Wrist PPG During Exercise\" v1.0.0 · 8 adults, terrestrial "
              "lab exercise study (walk, run, cycling) · SHA-256-verified local copy · units as declared in the WFDB "
              "header; amplitudes not calibrated · not astronaut data · not a stress dataset · no health meaning")
CHECK_NOTE = ("Methods check only: compares a simple PPG peak-interval heart-rate estimate with the dataset's "
              "hand-marked reference ECG beats in the same windows. Parameters were fixed before any result was "
              "computed. Time base: the uniform 256 Hz sample index (the wrist timestamp channel has 60 s rollover "
              "and whole-second jumps and is not used). n = 8 participants; not validated; not astronaut data; "
              "no clinical meaning.")


class RecordedWindow(tk.Toplevel):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title("HYPERION-MDA · RECORDED non-astronaut wearable (PhysioNet)")
        self.geometry("1100x700")
        self.minsize(860, 560)
        self.configure(bg="#101923")
        self.manifest = load_manifest()
        self.player: PlaybackWindow | None = None
        self.results = None
        self._build()

    def _build(self) -> None:
        self.banner = tk.Label(self, text=REC_BANNER, bg="#2f3f5a", fg="#dde8ff", font=("Segoe UI", 9, "bold"),
                               padx=12, pady=9, justify="center")
        self.banner.pack(side="top", fill="x", padx=16, pady=(12, 6))
        self.banner.bind("<Configure>", lambda e: self.banner.configure(wraplength=max(300, e.width - 30)))
        cite = (f"Licence: {self.manifest['license']}. Cite: Jarchi & Casson, Data 2017, doi:10.3390/data2010001; "
                f"PhysioNet (doi:{self.manifest['doi']}). Data is downloaded on demand and never redistributed.")
        ttk.Label(self, text=cite, padding=(16, 0), wraplength=1040, justify="left").pack(fill="x")

        controls = ttk.Frame(self, padding=(16, 8))
        controls.pack(fill="x")
        ttk.Label(controls, text="Record:").pack(side="left")
        self.record = tk.StringVar(value=self.manifest["records"][0])
        ttk.Combobox(controls, textvariable=self.record, values=self.manifest["records"], state="readonly",
                     width=26).pack(side="left", padx=6)
        ttk.Button(controls, text="Play record", command=self.play).pack(side="left", padx=6)
        ttk.Button(controls, text="Run HR methods check", command=self.run_check).pack(side="left")

        self.note = tk.StringVar(value=CHECK_NOTE)
        ttk.Label(self, textvariable=self.note, padding=(16, 2), wraplength=1040, justify="left").pack(fill="x")
        cols = ("record", "activity", "windows", "compared", "mae", "bias")
        box = ttk.Frame(self, padding=(16, 6, 16, 12))
        box.pack(fill="both", expand=True)
        self.table = ttk.Treeview(box, columns=cols, show="headings", height=14)
        for col, text, width in zip(cols, ("Record", "Activity (header comment)", "Windows", "Compared",
                                           "Median |PPG − ref| (bpm)", "Mean PPG − ref (bpm)"),
                                    (180, 260, 80, 90, 180, 170)):
            self.table.heading(col, text=text)
            self.table.column(col, width=width, minwidth=60, stretch=(col == "activity"))
        scroll = ttk.Scrollbar(box, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side="left", fill="both", expand=True)
        scroll.pack(side="left", fill="y")

    def play(self) -> None:
        try:
            adapter = RecordedPhysioNetAdapter(self.record.get())
        except (AdapterError, PhysioNetSourceError) as exc:
            messagebox.showerror("Recorded data not loaded", f"{exc}\n\nNo other data was substituted.", parent=self)
            return
        if self.player is not None and self.player.winfo_exists():
            self.player.destroy()
        self.player = PlaybackWindow(self, adapter, banner=REC_BANNER + f" · record {adapter.record}",
                                     title=f"HYPERION-MDA · RECORDED non-astronaut playback · {adapter.record}",
                                     window_s=8.0, step_s=0.25, banner_bg="#2f3f5a", line="#1f4f8a")

    def run_check(self) -> None:
        try:
            from . import dsp_hr
        except ImportError as exc:
            messagebox.showerror("HR methods check unavailable",
                                 f"This check needs numpy and scipy ({exc}). Use the project .venv "
                                 "(see README).", parent=self)
            return
        try:
            results = dsp_hr.run_check()
        except (AdapterError, PhysioNetSourceError) as exc:
            messagebox.showerror("Recorded data not loaded", f"{exc}\n\nNo other data was substituted.", parent=self)
            return
        self.results = results
        self.table.delete(*self.table.get_children())
        for r in results:
            self.table.insert("", "end", values=(r.record, r.activity, r.windows, r.compared,
                                                 f"{r.median_abs_error:.2f}", f"{r.mean_error:+.2f}"))
        params = "; ".join(f"{k}={v}" for k, v in dsp_hr.PARAMETERS.items())
        self.note.set(CHECK_NOTE + f"\nParameters: {params}")
