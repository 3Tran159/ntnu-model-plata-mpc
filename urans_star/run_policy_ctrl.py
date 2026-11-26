"""run_policy_ctrl.py - KOPIA run_overset_ctrl.py: jedyna roznica - makro z 50_learning/vortex_env/stars (tryb mode=policy, policy_file=...)."""
"""Unattended GodoOversetRun session loop (restart from the newest checkpoint + its controller state).
usage: python run_overset_ctrl.py TAG SETUP_SIM cores|gpu [k=v ...]        (cores e.g. 14,15,16 ; 'gpu' = 1 rank on GPU, host core 21)
Case dir: 70_godo_case/overset_runs/TAG ; reuses the dir if it exists (continues).  Log: session.log
"""
import json, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\20_supervisor")
import starrun
import night_queue as nq

HERE = Path(__file__).parent
tag, setup, where = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
extra = dict(a.split("=", 1) for a in sys.argv[4:])
gpu = where == "gpu"
cores = (21,) if gpu else tuple(int(c) for c in where.split(","))
case = HERE / "overset_runs" / tag
case.mkdir(parents=True, exist_ok=True)
sim = case / setup.name
if not sim.exists():
    shutil.copy2(setup, sim)
geo = json.loads((HERE / "GEOMETRY_GODO.json").read_text())


def compile_copy(case, name):
    r = subprocess.run([nq.JAVAC, "-encoding", "UTF-8", "-nowarn", "-cp", nq.EXT, "-d", str(case / "compiled"), str(case / name)], capture_output=True, text=True, creationflags=nq.FLAG)
    if r.returncode:
        raise RuntimeError("javac %s: %s" % (name, r.stderr[-500:]))
    src = (case / name).read_text(encoding="utf-8", errors="replace")
    if "mode.equals(\"policy\")&&free" not in src:
        raise RuntimeError("makro w katalogu przebiegu nie ma trybu policy - stop")


def log(m):
    with open(case / "session.log", "a") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + m + "\n")


props = {"mode": "pid", "t_end_s": 6 * geo["encounter_period_s"], "dt_s": 1e-3, "release_s": geo["encounter_period_s"],
         "pitch_trim_deg": 3.5, "mass_kg": 12500.0 / (25.6 * 0.312) * 0.02, "kp_deg_per_m": 10, "ki_deg_per_m_s": 2, "kd_deg_s_per_m": 0,
         "tick_steps": 10, "theta_max_deg": 7.5, "rate_max_deg_s": 90, "z_limit_m": 0.75, "submergence_min_m": 0.5 * geo["chord_m"],
         "free_surface_y_m": geo["free_surface_y_m"], "U_ms": geo["U_m_s"], "checkpoint_every_steps": 250,
         "wall_budget_s": 20 * 3600, "stop_file": (case / "STOP").as_posix()}
props.update(extra)
done, tries = False, 0
while not done and tries < int(props.get("max_sessions", 8)):
    lc = case / "LATEST_CHECKPOINT.txt"
    start = Path(lc.read_text().strip()) if lc.exists() else sim
    ctrl = Path(str(start) + ".ctrl")
    if ctrl.exists():
        shutil.copy2(ctrl, case / "CTRL_STATE.properties")
    elif start == sim:
        (case / "CTRL_STATE.properties").unlink(missing_ok=True)
    p = dict(props, initialize=str(start == sim).lower())
    (case / "run.properties").write_text("\n".join("%s=%s" % kv for kv in p.items()) + "\n")
    shutil.copy2(Path(r"T:\NTNU_GODO_CONTROL_20261109\50_learning\vortex_env\stars\GodoOversetRun.java"), case / "GodoOversetRun.java")  # KOPIA z trybem policy
    compile_copy(case, "GodoOversetRun.java")   # 13.11: NIE nq.compile_macro - ono nadpisywalo kopie makra oryginalem z 70_godo_case (tryb policy/mpc ginal -> PID Kp 10)
    (case / "RUN_RESULT.json").unlink(missing_ok=True)
    log("session %d from %s (%s)" % (tries + 1, start.name, "gpu" if gpu else "cpu %s" % (cores,)))
    res = starrun.launch(start, case / "GodoOversetRun.java", case, cpus=cores, np_=1 if gpu else len(cores),
                         timeout_s=21 * 3600, gpu=gpu)
    log("session %d ended rc=%s after %.0f s" % (tries + 1, res.get("returncode"), res.get("seconds", 0)))
    nq.kill_orphans(case)
    rr = case / "RUN_RESULT.json"
    result = json.loads(rr.read_text())["result"] if rr.exists() else None
    done = result in ("DONE", "HOLD_LIMIT", "HOLD_STOP_FILE", "HOLD_CFL", "HOLD_NAN")   # physics holds are terminal (no blind restarts)
    if result:
        log("result %s" % result)
    tries += 1
log("end done=%s sessions=%d" % (done, tries))
