"""FL SIMULATION window: shows clients, rounds and the FedAvg aggregation flow.

Single computer, generated toy data. Not habitats, not real data, not a privacy
protection, and no performance or clinical claims.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from . import fl_sim

FL_BANNER = ("FL SIMULATION · one computer, generated toy data · simulated clients are not habitats, sites or "
             "devices · no privacy protection (FedAvg alone is not privacy; no differential privacy) · "
             "no performance or clinical claims · framework-free FedAvg (not Flower)")
BOX = "#5b3f99"
MUTED = "#66727e"


class FLWindow(tk.Toplevel):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title("HYPERION-MDA · FL SIMULATION (toy data, single computer)")
        self.geometry("1050x680")
        self.minsize(820, 560)
        self.configure(bg="#101923")
        self.run: fl_sim.FLRun | None = None
        self._build()

    def _build(self) -> None:
        self.banner = tk.Label(self, text=FL_BANNER, bg="#3b2f5a", fg="#e8ddff", font=("Segoe UI", 9, "bold"),
                               padx=12, pady=9, justify="center")
        self.banner.pack(side="top", fill="x", padx=16, pady=(12, 6))
        self.banner.bind("<Configure>", lambda e: self.banner.configure(wraplength=max(300, e.width - 30)))

        controls = ttk.Frame(self, padding=(16, 6))
        controls.pack(fill="x")
        ttk.Label(controls, text=f"Simulated clients ({fl_sim.MIN_CLIENTS}–{fl_sim.MAX_CLIENTS}):").pack(side="left")
        self.clients = tk.StringVar(value="3")
        ttk.Spinbox(controls, from_=fl_sim.MIN_CLIENTS, to=fl_sim.MAX_CLIENTS, textvariable=self.clients,
                    width=4).pack(side="left", padx=(4, 14))
        ttk.Label(controls, text=f"Rounds ({fl_sim.MIN_ROUNDS}–{fl_sim.MAX_ROUNDS}):").pack(side="left")
        self.rounds = tk.StringVar(value="5")
        ttk.Spinbox(controls, from_=fl_sim.MIN_ROUNDS, to=fl_sim.MAX_ROUNDS, textvariable=self.rounds,
                    width=4).pack(side="left", padx=(4, 14))
        ttk.Label(controls, text="Seed: 7 (fixed, reproducible)").pack(side="left")
        ttk.Button(controls, text="Run FL simulation", command=self.run_simulation).pack(side="left", padx=14)

        self.summary = tk.StringVar(value="Choose clients and rounds, then run. Nothing has been run yet.")
        ttk.Label(self, textvariable=self.summary, padding=(16, 2), wraplength=980,
                  justify="left").pack(fill="x")
        self.flow = tk.Canvas(self, height=190, bg="#ffffff", highlightthickness=1, highlightbackground="#c9d1d9")
        self.flow.pack(fill="x", padx=16, pady=6)

        cols = ("round", "client", "n", "update", "global")
        box = ttk.Frame(self, padding=(16, 0, 16, 12))
        box.pack(fill="both", expand=True)
        self.table = ttk.Treeview(box, columns=cols, show="headings", height=10)
        for col, text, width in zip(cols, ("Round", "Simulated client", "Toy samples (n)",
                                           "Local update size", "Global weights after FedAvg (w1, w2, bias)"),
                                    (70, 150, 120, 140, 420)):
            self.table.heading(col, text=text)
            self.table.column(col, width=width, minwidth=60, stretch=(col == "global"))
        scroll = ttk.Scrollbar(box, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side="left", fill="both", expand=True)
        scroll.pack(side="left", fill="y")

    def run_simulation(self) -> None:
        try:
            run = fl_sim.run_fedavg(self.clients.get(), self.rounds.get())
        except ValueError as exc:
            messagebox.showerror("FL SIMULATION input", str(exc), parent=self)
            return
        self.run = run
        self.table.delete(*self.table.get_children())
        for log in run.logs:
            g = ", ".join(f"{x:+.3f}" for x in log.global_weights)
            for u in log.updates:
                self.table.insert("", "end", values=(log.round_no, u.client_id, u.n, f"{u.update_size:.4f}", g))
        total = sum(run.client_sizes.values())
        self.summary.set(
            f"FL SIMULATION complete: {run.n_clients} simulated clients ({total} generated toy points in total), "
            f"{run.rounds} rounds, seed {run.seed}. Each round: every client trains locally on its own toy points; "
            f"the server receives only (weights, n) and averages them weighted by n (FedAvg). "
            f"Toy data and weights have no clinical or astronaut meaning.")
        self._draw_flow()

    def _draw_flow(self) -> None:
        c = self.flow
        c.delete("all")
        if self.run is None:
            return
        width = max(c.winfo_width(), 600)
        n = self.run.n_clients
        server = (width / 2 - 150, 128, width / 2 + 150, 178)
        c.create_rectangle(*server, outline=BOX, width=2, tags=("server",))
        c.create_text(width / 2, 153, text="Simulated server: FedAvg (weighted by client n)",
                      font=("Segoe UI", 9, "bold"), fill=BOX)
        slot = width / n
        for i, (cid, size) in enumerate(self.run.client_sizes.items()):
            cx = slot * (i + 0.5)
            c.create_rectangle(cx - 58, 14, cx + 58, 58, outline=BOX, width=1.5, tags=("client",))
            c.create_text(cx, 36, text=f"{cid}\nn = {size} (toy)", font=("Segoe UI", 8), fill=BOX, justify="center")
            c.create_line(cx, 58, width / 2, server[1], arrow="last", fill=MUTED, tags=("up",))
        c.create_text(12, 92, anchor="w", font=("Segoe UI", 8), fill=MUTED,
                      text="↓ only local weights + n are passed to the server step (client toy data is not)        "
                           "↑ global weights sent back each round")
