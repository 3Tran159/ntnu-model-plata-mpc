"""Run the native flap controller (10_macros/GodoControl.java) on a Godø-condition setup .sim.

usage: python run_godo_ctrl.py <tag> <mode> <steps> <cpus> <setup.sim> [gpu] [key=value ...]
Geometry keys for the Godø case are set here (hinge scaled from the Mini case by c/1.19).
"""
import json, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\20_supervisor")
import starrun

HERE = Path(__file__).parent
MACRO = Path(r"T:\NTNU_GODO_CONTROL_20261109\10_macros\GodoControl.java")
JAVAC = r"C:\Program Files\Eclipse Adoptium\jdk-25.0.3.9-hotspot\bin\javac.exe"
EXT = r"E:\Program Files\Siemens\21.04.009-R8\STAR-CCM+21.04.009-R8\star\lib\java\platform\modules\ext\*"
S = 0.312 / 1.19

tag, mode, steps, cpus, setup = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], Path(sys.argv[5])
gpu = len(sys.argv) > 6 and sys.argv[6] == "gpu"
extra = dict(a.split("=", 1) for a in sys.argv[(7 if gpu else 6):])
case = HERE / "ctrl_runs" / ("%s_%s" % (tag, time.strftime("%Y%m%d_%H%M%S")))
case.mkdir(parents=True)
shutil.copy2(setup, case / "input.sim")
shutil.copy2(MACRO, case / "GodoControl.java")
cc = subprocess.run([JAVAC, "-encoding", "UTF-8", "-nowarn", "-cp", EXT, "-d", str(case / "compiled"), str(case / "GodoControl.java")],
                    capture_output=True, text=True)
if cc.returncode:
    (case / "javac_errors.txt").write_text(cc.stderr); raise SystemExit("javac failed")
props = {"mode": mode, "steps": steps, "tick_steps": 10, "expected_time_s": 0.0, "expected_dt_s": 0.001,
         "initialize_if_t0": "true", "hinge_x_m": 0.8 * 0.312, "hinge_y_m": 0.02128173276777 * S, "geom_scale": S, "U_ms": 12.3467,
         "cfl_report": "GODO_interfaceCFL", "cl_target": 0.24, "delta_max_deg": 2.0, "rate_max_deg_s": 30.0,
         "test_amp_deg": 1.0, "wall_budget_s": 20000, "stop_file": (case / "STOP").as_posix()}
props.update(extra)
(case / "control.properties").write_text("\n".join("%s=%s" % kv for kv in props.items()) + "\n")
res = starrun.launch(case / "input.sim", case / "GodoControl.java", case, cpus=tuple(int(c) for c in cpus.split(",")),
                     np_=len(cpus.split(",")) if not gpu else 1, timeout_s=float(props["wall_budget_s"]) + 1800, gpu=gpu)
out = {"case": str(case), "props": props, "launch": res}
for f in ("FC_RESULT.json", "ERROR.json", "FC_POWER_REPORTS.json"):
    if (case / f).exists():
        out[f] = json.loads((case / f).read_text())
(case / "RUN_SUMMARY.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
