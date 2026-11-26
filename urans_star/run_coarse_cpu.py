"""Diagnostic + production: COARSE (B 1.414, dt 1 ms) on CPU cores, to test whether the random server exits are GPU-specific.
Restart loop from LATEST_CHECKPOINT.txt like night_queue (max 8 sessions). Log: night/COARSE_CPU/cpu_queue.log"""
import json, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\20_supervisor")
import starrun
import night_queue as nq

CORES = tuple(range(6, 14))
case = nq.RUNS / "COARSE_CPU"
case.mkdir(exist_ok=True)
src = nq.RUNS / "COARSE" / "GODO_SETUP_B1.41421356.sim"
sim = case / src.name
if not sim.exists():
    shutil.copy2(src, sim); shutil.copy2(nq.RUNS / "COARSE" / "GODO_MESH.json", case / "GODO_MESH.json")


def log(m):
    with open(case / "cpu_queue.log", "a") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + m + "\n")


done, tries = False, 0
while not done and tries < 8:
    lc = case / "LATEST_CHECKPOINT.txt"
    start = Path(lc.read_text().strip()) if lc.exists() else sim
    nq.compile_macro(case, "GodoRun.java")
    props = {"t_end_s": nq.T_END, "dt_s": 1e-3, "checkpoint_every_steps": 242, "initialize": str(start == sim).lower(),
             "wall_budget_s": 20 * 3600, "stop_file": (case / "STOP").as_posix()}
    (case / "run.properties").write_text("\n".join("%s=%s" % kv for kv in props.items()) + "\n")
    (case / "RUN_RESULT.json").unlink(missing_ok=True)
    log("session %d from %s" % (tries + 1, start.name))
    res = starrun.launch(start, case / "GodoRun.java", case, cpus=CORES, np_=len(CORES), timeout_s=21 * 3600, gpu=False)
    log("session %d ended rc=%s after %.0f s" % (tries + 1, res.get("returncode"), res.get("seconds", 0)))
    nq.kill_orphans(case)
    done = (case / "RUN_RESULT.json").exists() and json.loads((case / "RUN_RESULT.json").read_text())["result"] == "DONE"
    tries += 1
log("end done=%s sessions=%d" % (done, tries))
