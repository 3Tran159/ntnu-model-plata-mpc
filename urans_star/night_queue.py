"""Overnight mesh/time-step convergence queue on the GPU (GodÃ¸ conditions, FIXED foil), fully unattended.

Order: MEDIUM (B 1.0, dt 1 ms) -> COARSE (B 1.414) -> FINE (B 0.707) -> MEDIUM_DT05 (B 1.0, dt 0.5 ms)
Each variant: (1) BuildGodoCase mode=mesh -> GODO_SETUP_B*.sim  (2) GodoRun until t_end = 6 encounter periods.
Robustness:
  - Windows kept awake (SetThreadExecutionState, released at the end)
  - a GodoRun session that dies/hangs is restarted from LATEST_CHECKPOINT.txt (history.csv appended), max 3 restarts
  - heartbeat: RUN_STATE.json must update at least every 20 min, otherwise the session tree is killed and restarted
  - a variant that fails 3 times is skipped, the queue continues
Status for the dashboard / Claude: 70_godo_case/NIGHT_STATUS.json, log: night_queue.log
"""
import ctypes, json, os, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\20_supervisor")
import starrun

HERE = Path(__file__).parent
RUNS = HERE / "night"
SRC = Path(r"T:\NTNU_GODO_CONTROL_20261109\00_source\FIXED_FINAL_src.sim")
GEO = json.loads((HERE / "GEOMETRY_GODO.json").read_text())
JAVAC = r"C:\Program Files\Eclipse Adoptium\jdk-25.0.3.9-hotspot\bin\javac.exe"
EXT = r"E:\Program Files\Siemens\21.04.009-R8\STAR-CCM+21.04.009-R8\star\lib\java\platform\modules\ext\*"
FLAG = subprocess.CREATE_NO_WINDOW
TE = GEO["encounter_period_s"]
T_END = 6 * TE
HOST_CORE = int(os.environ.get("GODO_HOST_CORE", "21"))
VARIANTS = [("MEDIUM", 1.0, 1e-3), ("COARSE", 1.41421356, 1e-3), ("FINE", 0.70710678, 1e-3), ("MEDIUM_DT05", 1.0, 5e-4)]
if os.environ.get("GODO_VARIANTS"):   # e.g. COARSE:1.41421356:0.001,FINE_DT0707:0.70710678:0.00070710678
    VARIANTS = [(a, float(b), float(c)) for a, b, c in (x.split(":") for x in os.environ["GODO_VARIANTS"].split(","))]


def kill_orphans(case):
    """STAR clients whose server died keep the GPU context busy; kill the ones belonging to this case only."""
    import base64
    ps = "Get-CimInstance Win32_Process -Filter \"Name='star-ccm+.exe' or Name='starccm+.exe'\" | Select-Object ProcessId,CommandLine | ConvertTo-Json"
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, creationflags=FLAG).stdout
        procs = json.loads(out) if out.strip() else []
        procs = [procs] if isinstance(procs, dict) else procs
        for p in procs:
            cl = p.get("CommandLine") or ""
            if "-encoded-session" not in cl:
                continue
            enc = cl.split("-encoded-session", 1)[1].split()[0]
            try:
                path = base64.b64decode(enc + "=" * (-len(enc) % 4)).decode("utf8", "ignore")
            except Exception:
                continue
            if str(case).lower() in path.lower():
                subprocess.run(["taskkill", "/PID", str(p["ProcessId"]), "/T", "/F"], capture_output=True, creationflags=FLAG)
                log("%s: killed orphan STAR process %s" % (case.name, p["ProcessId"]))
    except Exception as e:
        log("orphan check failed: %r" % e)


def log(msg):
    with open(HERE / "night_queue.log", "a", encoding="utf8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")


def status(d):
    d["time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (HERE / "NIGHT_STATUS.json").write_text(json.dumps(d, indent=1))


def compile_macro(case, name):
    shutil.copy2(HERE / name, case / name)
    r = subprocess.run([JAVAC, "-encoding", "UTF-8", "-nowarn", "-cp", EXT, "-d", str(case / "compiled"), str(case / name)],
                       capture_output=True, text=True, creationflags=FLAG)
    if r.returncode:
        raise RuntimeError("javac %s: %s" % (name, r.stderr[-500:]))


def setup(case, base, dt):
    shutil.copy2(SRC, case / "input.sim"); shutil.copy2(HERE / "GodoFluidDomain.stl", case / "GodoFluidDomain.stl")
    compile_macro(case, "BuildGodoCase.java")
    props = {"mode": "mesh", "base_size_m": base, "dt_s": dt, "inner": 12, "cores": str(HOST_CORE),
             "chord_m": GEO["chord_m"], "free_surface_y_m": GEO["free_surface_y_m"], "H_m": GEO["H_m"],
             "x0_m": GEO["domain_x_m"][0], "band_x1_m": GEO["domain_x_m"][1] - 0.8 * GEO["lambda_deep_m"],
             "U_m_s": GEO["U_m_s"], "lambda_m": GEO["lambda_deep_m"], "bottom_y_m": GEO["domain_y_m"][0],
             "forcing_length_m": 0.4 * GEO["lambda_deep_m"], "damping_length_m": 0.8 * GEO["lambda_deep_m"],
             "foil_area_m2": 0.00795948899616472, "encounter_period_s": TE, "prism_total_m": 6.79e-4}
    (case / "control.properties").write_text("\n".join("%s=%s" % kv for kv in props.items()) + "\n")
    starrun.launch(case / "input.sim", case / "BuildGodoCase.java", case, cpus=(HOST_CORE,), np_=1, timeout_s=3600, gpu=True)
    sims = sorted(case.glob("GODO_SETUP_B*.sim"))
    if not sims:
        raise RuntimeError("setup failed: " + ((case / "ERROR.json").read_text() if (case / "ERROR.json").exists() else "no sim"))
    return sims[-1]


def run_session(case, sim, dt, initialize):
    compile_macro(case, "GodoRun.java")
    props = {"t_end_s": T_END, "dt_s": dt, "checkpoint_every_steps": int(round(TE / 8 / dt)), "initialize": str(initialize).lower(),
             "wall_budget_s": 20 * 3600, "stop_file": (case / "STOP").as_posix()}
    (case / "run.properties").write_text("\n".join("%s=%s" % kv for kv in props.items()) + "\n")
    env_ok = True
    t0 = time.time()
    # launch without blocking so the heartbeat can be watched
    import threading
    res = {}
    th = threading.Thread(target=lambda: res.update(starrun.launch(sim, case / "GodoRun.java", case, cpus=(HOST_CORE,), np_=1,
                                                                    timeout_s=22 * 3600, gpu=True)), daemon=True)
    th.start()
    while th.is_alive():
        th.join(60)
        hb = case / "RUN_STATE.json"
        ref = max(hb.stat().st_mtime if hb.exists() else 0.0, t0 + 600)   # >= 30 min grace for load/initialise
        if time.time() - ref > 1200:
            log("%s: heartbeat lost -> killing session" % case.name)
            try:
                pid = int((case / "launcher.pid").read_text())
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=FLAG)
            except Exception as e:
                log("kill failed: %r" % e)
            th.join(120)
            break
        try:
            st = json.loads(hb.read_text())
            status({"variant": case.name, "progress": st, "queue": [v[0] for v in VARIANTS]})
        except Exception:
            pass
    kill_orphans(case)
    return (case / "RUN_RESULT.json").exists() and json.loads((case / "RUN_RESULT.json").read_text())["result"] == "DONE"


def main():
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    RUNS.mkdir(exist_ok=True)
    log("night queue start, t_end %.3f s (6 periods)" % T_END)
    summary = []
    try:
        for name, base, dt in VARIANTS:
            case = RUNS / name
            case.mkdir(exist_ok=True)
            entry = {"variant": name, "base_m": base, "dt_s": dt, "case": str(case)}
            try:
                sim = next(iter(sorted(case.glob("GODO_SETUP_B*.sim"))), None)
                for attempt in range(3):          # STAR GPU sessions occasionally die at start-up ("Connection reset")
                    if sim:
                        break
                    try:
                        sim = setup(case, base, dt)
                    except Exception as e:
                        log("%s: setup attempt %d failed: %r" % (name, attempt + 1, e))
                        for f in ("ERROR.json", "GODO_MESH.json", "input.sim"):
                            try:
                                (case / f).unlink()
                            except Exception:
                                pass
                        time.sleep(60)
                if not sim:
                    raise RuntimeError("setup failed 3 times")
                mesh = json.loads((case / "GODO_MESH.json").read_text()); entry["cells"] = mesh.get("cells")
                done, tries = (case / "RUN_RESULT.json").exists() and json.loads((case / "RUN_RESULT.json").read_text())["result"] == "DONE", 0
                while not done and tries < 8:
                    lc = case / "LATEST_CHECKPOINT.txt"
                    start = Path(lc.read_text().strip()) if lc.exists() else sim
                    log("%s: session %d from %s" % (name, tries + 1, start.name))
                    if (case / "RUN_RESULT.json").exists():
                        (case / "RUN_RESULT.json").unlink()
                    done = run_session(case, start, dt, initialize=(start == sim))
                    tries += 1
                entry["done"] = done; entry["sessions"] = tries
            except Exception as e:
                entry["error"] = repr(e); log("%s: %r" % (name, e))
            summary.append(entry)
            (HERE / "NIGHT_SUMMARY.json").write_text(json.dumps(summary, indent=1))
            log("%s finished: %s" % (name, entry))
    finally:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        status({"variant": None, "finished": True, "summary": summary})
        log("night queue end")


if __name__ == "__main__":
    main()
