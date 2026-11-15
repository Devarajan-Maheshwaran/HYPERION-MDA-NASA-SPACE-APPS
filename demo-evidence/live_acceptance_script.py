"""Final live acceptance: one continuous session of the real app under its Tk mainloop.
Runs the 8 workflows, hooks Tk callback exceptions and dialogs, measures event-loop gaps
(freeze detection), and scans every visible widget text for lane labels / clinical terms."""
import re
import sys
import time
import traceback

sys.path.insert(0, r"C:\NASA SPACE APP CHALLENGE\src")
from hyperion_mda import app  # noqa: E402

LOG, dialogs, cb_errors = [], [], []
app.messagebox.showerror = lambda t, m, **k: dialogs.append(("ERROR", t, m))
app.messagebox.showwarning = lambda t, m, **k: dialogs.append(("WARN", t, m))
RESULT = {}
CLINICAL = re.compile(r"diagnos|healthy|unhealthy|abnormal|disease|treat|prescri|"
                      r"flight[- ]ready|nasa[- ]approved|clinically valid|normal range|at risk", re.I)


def log(m):
    LOG.append(m)
    print(m, flush=True)


def texts(widget):
    out = []
    for opt in ("text", "title"):
        try:
            v = widget.cget(opt) if opt == "text" else (widget.title() if hasattr(widget, "title") else "")
            if v:
                out.append(str(v))
        except Exception:
            pass
    try:
        if widget.winfo_class() == "Treeview":
            for c in widget["columns"]:
                out.append(str(widget.heading(c, "text")))
    except Exception:
        pass
    for ch in widget.winfo_children():
        out.extend(texts(ch))
    return out


def scan(name, win, must):
    allt = " | ".join(texts(win))
    hits = sorted({m.group(0) for m in CLINICAL.finditer(allt)})
    ok = all(s.lower() in allt.lower() for s in must)
    log(f"   labels[{name}] required {must}: {'present' if ok else 'MISSING'}; clinical-term hits: {hits or 'none'}")
    if hits:
        for t in texts(win):
            if CLINICAL.search(t):
                log(f"      context: {t[:160]!r}")
    return ok


def toplevels(w):
    return [c for c in w.winfo_children() if c.winfo_class() == "Toplevel"]


w = app.HyperionApp()
w.report_callback_exception = lambda et, ev, tb: cb_errors.append("".join(traceback.format_exception(et, ev, tb)))

# heartbeat freeze detector
hb = {"last": time.perf_counter(), "max": 0.0, "step": "start", "per": {}}


def tick():
    now = time.perf_counter()
    gap = now - hb["last"]
    hb["last"] = now
    hb["max"] = max(hb["max"], gap)
    hb["per"][hb["step"]] = max(hb["per"].get(hb["step"], 0.0), gap)
    w.after(50, tick)


w.after(50, tick)
steps, st = [], {}


def step(delay, label):
    def deco(fn):
        steps.append((delay, label, fn))
        return fn
    return deco


def check(wf, cond, detail):
    RESULT.setdefault(wf, True)
    RESULT[wf] &= bool(cond)
    log(f"   {'PASS' if cond else 'FAIL'} {wf}: {detail}")


@step(800, "1 launch")
def s1():
    b = w.banner_text.get()
    check("1 launch", "NO DATA LOADED" in b and w.winfo_viewable(), f"title={w.title()!r} banner={b!r}")
    check("1 launch", len(w.table.get_children()) == 0, "table empty at launch")
    scan("main@launch", w, ["RESEARCH PROTOTYPE", "NOT FOR MEDICAL DECISIONS"])


@step(300, "2 nasa")
def s2():
    w.load_osdr(); w.update()
    s, rows = w.status.get(), w.table.get_children()
    check("2 nasa", "NASA lab data" in s and "SHA-256 verified" in s and len(rows) == 531, f"status={s!r} rows={len(rows)}")
    post = next(r for r in rows if w.table.item(r, "values")[0] == "R+1")
    w.table.selection_set(post); w.table.focus(post); w._show_selected(); w.update()
    d = w.details.get()
    check("2 nasa", bool(d.strip()), f"details first line={d.splitlines()[0]!r}")
    log(f"   banner after load={w.banner_text.get()!r}")
    st["nasa_rows"] = len(rows); st["nasa_status"] = s
    scan("main@nasa", w, ["NASA"])


@step(300, "3 channels")
def s3():
    w.open_channel_panel(); w.update()
    p = toplevels(w)[-1]
    p.set_filter("Wrist"); p.update()
    n = len(p.table.get_children())
    check("3 channels", n == 10, f"title={p.title()!r} heading={p.heading.get()!r} rows={n}")
    p.set_filter(None); p.update()
    check("3 channels", len(p.table.get_children()) == 49, f"all regions rows={len(p.table.get_children())}")
    scan("channels", p, ["Simulated", "Unavailable"])
    p.destroy()


@step(300, "4 sim")
def s4():
    w.open_playback(); w.update()
    pb = toplevels(w)[-1]; st["sim"] = pb
    st["sim_t0"] = pb.position_text.get()
    pb.start()


@step(3500, "4 sim")
def s4b():
    pb = st["sim"]
    t1 = pb.position_text.get()
    check("4 sim", t1 != st["sim_t0"], f"position {st['sim_t0']!r} -> {t1!r} after ~3.5 s")
    scan("sim", pb, ["SIMULATED", "not astronaut"])
    pb.pause()
    p1 = pb.position_text.get()
    st["sim_paused"] = p1


@step(1000, "4 sim")
def s4c():
    pb = st["sim"]
    check("4 sim", pb.position_text.get() == st["sim_paused"], f"pause holds at {st['sim_paused']!r}")
    pb.destroy()


@step(300, "5 recorded")
def s5():
    w.open_recorded(); w.update()
    rec = toplevels(w)[-1]; st["rec"] = rec
    rec.record.set("s3_low_resistance_bike")
    rec.play(); rec.update()
    pl = rec.player
    st["rec_t0"] = pl.position_text.get()
    pl.start()


@step(3500, "5 recorded")
def s5b():
    pl = st["rec"].player
    t1 = pl.position_text.get()
    check("5 recorded", t1 != st["rec_t0"], f"{pl.title()!r}: {st['rec_t0']!r} -> {t1!r}")
    scan("recorded-player", pl, ["RECORDED", "non-astronaut"])
    scan("recorded-browser", st["rec"], ["non-astronaut"])
    pl.pause(); pl.destroy()


@step(300, "6 hr")
def s6():
    rec = st["rec"]
    t0 = time.time(); rec.run_check(); rec.update()
    rows = rec.table.get_children()
    vals = [rec.table.item(r, "values") for r in rows]
    check("6 hr", len(rows) == 19, f"{len(rows)} rows in {time.time() - t0:.1f}s")
    log(f"   first row={vals[0]}")
    log(f"   last row={vals[-1]}")
    scan("hr-check", rec, ["non-astronaut"])
    rec.destroy()


@step(300, "7 fl")
def s7():
    w.open_fl(); w.update()
    fl = toplevels(w)[-1]
    fl.run_simulation(); fl.update()
    n = len(fl.table.get_children())
    check("7 fl", n == 15, f"summary={fl.summary.get()[:110]!r} rows={n}")
    scan("fl", fl, ["SIMULATION"])
    fl.destroy()


# 8: switching — several windows open at once, interleaved, then reopen everything
@step(300, "8 switch")
def s8():
    w.open_channel_panel(); w.open_playback(); w.open_recorded(); w.open_fl(); w.update()
    tl = toplevels(w)
    st["multi"] = tl
    check("8 switch", len(tl) == 4, f"{len(tl)} windows open simultaneously: {[t.title()[:40] for t in tl]}")
    tl[1].start()                        # simulated playback running
    tl[2].record.set("s1_walk"); tl[2].play(); tl[2].update()
    tl[2].player.start()                 # recorded playback running concurrently
    tl[3].run_simulation()               # FL while both play
    for t in tl:
        t.lift(); t.update()
    w.lift(); w._show_selected(); w.update()
    st["sim_a"] = tl[1].position_text.get(); st["rec_a"] = tl[2].player.position_text.get()


@step(2500, "8 switch")
def s8b():
    tl = st["multi"]
    sa, ra = tl[1].position_text.get(), tl[2].player.position_text.get()
    check("8 switch", sa != st["sim_a"] and ra != st["rec_a"], f"concurrent: sim {st['sim_a']!r}->{sa!r}, rec {st['rec_a']!r}->{ra!r}")
    check("8 switch", len(w.table.get_children()) == st["nasa_rows"] and w.status.get() == st["nasa_status"],
          "main NASA table/status unchanged by other lanes")
    # close in non-creation order
    tl[2].player.pause(); tl[2].player.destroy(); tl[1].pause()
    for t in (tl[3], tl[1], tl[0], tl[2]):
        t.destroy()
    w.update()
    check("8 switch", len(toplevels(w)) == 0, "all windows closed cleanly")


@step(300, "8 switch")
def s8c():
    w.load_osdr(); w.update()   # reload lane
    check("8 switch", len(w.table.get_children()) == 531, f"NASA reload rows={len(w.table.get_children())}")
    w.open_playback(); w.update(); pb = toplevels(w)[-1]; st["sim2"] = pb
    st["sim2_t0"] = pb.position_text.get(); pb.start()


@step(1500, "8 switch")
def s8d():
    pb = st["sim2"]
    check("8 switch", pb.position_text.get() != st["sim2_t0"], f"reopened playback advances: {pb.position_text.get()!r}")
    pb.pause(); pb.destroy()
    w.open_recorded(); w.update(); r = toplevels(w)[-1]
    r.run_check(); r.update()
    check("8 switch", len(r.table.get_children()) == 19, "HR check rerun after switching: 19 rows")
    r.destroy()


@step(500, "end")
def done():
    log("")
    log(f"Tk callback exceptions: {len(cb_errors)}")
    for e in cb_errors:
        log(e)
    log(f"Dialogs: {dialogs or 'none'}")
    log("Event-loop max gap per step (s): " + ", ".join(f"{k}={v:.2f}" for k, v in hb["per"].items()))
    log("WORKFLOWS: " + ", ".join(f"{k}={'PASS' if v else 'FAIL'}" for k, v in RESULT.items()))
    allok = all(RESULT.values()) and not cb_errors and not [d for d in dialogs if d[0] == "ERROR"]
    log(f"CONTINUOUS LIVE SESSION: {'PASS' if allok else 'FAIL'}")
    w.destroy()


def run_steps(i=0):
    if i < len(steps):
        delay, label, fn = steps[i]

        def go():
            hb["step"] = label
            log(f"[{label}] {fn.__name__}")
            try:
                fn()
            except Exception as exc:
                RESULT[label] = False
                log(f"   STEP RAISED {type(exc).__name__}: {exc}\n{traceback.format_exc()}")
            run_steps(i + 1)
        w.after(delay, go)


run_steps()
T0 = time.time()
w.mainloop()
log(f"MAINLOOP EXITED CLEANLY after {time.time() - T0:.1f}s")
