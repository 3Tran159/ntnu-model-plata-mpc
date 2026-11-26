"""Watcher #2: MAP_FF, MAP_FF180, PI_LP_KP05 vs FIXED_LONG (same start state, same window).
Writes 30_runs/COMPARISON_<name>.json and 30_runs/PLOT_<name>.png when both cases are finished.
"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from watch_and_analyze import newest, done, comparison, RUNS
from analyze_case import load

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception:
    plt = None


def plot(name, a_case, f_case):
    if plt is None:
        return
    a, b = load(a_case), load(f_case)
    n = min(len(a["time_s"]), len(b["time_s"]))
    fig, ax = plt.subplots(4, 1, figsize=(10, 11), sharex=True)
    t = a["time_s"][:n]
    ax[0].plot(t, b["eta_m3_m"][:n] if "eta_m3_m" in b.dtype.names else t * 0, "k", lw=.8, label="eta x=-3 m (FIXED)")
    ax[0].set_ylabel("eta [m]"); ax[0].legend()
    ax[1].plot(t, a["cmd_deg"][:n], label="command"); ax[1].plot(t, a["meas_deg"][:n], "--", label="measured mesh angle")
    ax[1].set_ylabel("flap [deg]"); ax[1].legend()
    ax[2].plot(t, b["CL"][:n], "k", lw=.8, label="FIXED"); ax[2].plot(t, a["CL"][:n], lw=.8, label=name)
    ax[2].set_ylabel("CL"); ax[2].legend()
    ax[3].plot(t, b["CD"][:n], "k", lw=.8, label="FIXED"); ax[3].plot(t, a["CD"][:n], lw=.8, label=name)
    ax[3].set_ylabel("CD"); ax[3].set_xlabel("t [s]"); ax[3].legend()
    fig.tight_layout(); fig.savefig(RUNS / ("PLOT_%s.png" % name), dpi=110); plt.close(fig)


def main():
    names = ["MAP_FF", "MAP_FF180", "PI_LP_KP05"]
    while True:
        fx = newest("FIXED_LONG")
        pending = 0
        for nm in names:
            out = RUNS / ("COMPARISON_%s.json" % nm)
            c = newest(nm)
            if out.exists():
                continue
            pending += 1
            if done(c) and (done(fx) or nm == "PI_LP_KP05" and fx and (fx / "history.csv").exists()
                            and sum(1 for _ in open(fx / "history.csv")) > 1101):
                try:
                    out.write_text(json.dumps(comparison(c, fx), indent=1))
                    plot(nm, c, fx)
                except Exception as e:  # e.g. partial last line while FIXED_LONG still writes: retry later
                    (RUNS / ("COMPARISON_%s.retry" % nm)).write_text(repr(e))
                    if out.exists():
                        out.unlink()
        if pending == 0:
            break
        time.sleep(120)


if __name__ == "__main__":
    main()
