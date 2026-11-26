"""Build (and optionally probe) the overset GodÃ¸ case.  usage: python run_overset_build.py TAG mode cores [gpu] [k=v ...]
   e.g.  python run_overset_build.py OV_B1 probe 14,15,16,17,18,19,20
"""
import json, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\20_supervisor")
import starrun

HERE = Path(__file__).parent
SRC = HERE / "night" / "MEDIUM" / "GODO_SETUP_B1.0.sim"
JAVAC = r"C:\Program Files\Eclipse Adoptium\jdk-25.0.3.9-hotspot\bin\javac.exe"
EXT = r"E:\Program Files\Siemens\21.04.009-R8\STAR-CCM+21.04.009-R8\star\lib\java\platform\modules\ext\*"
tag, mode, cores = sys.argv[1], sys.argv[2], tuple(int(c) for c in sys.argv[3].split(","))
gpu = len(sys.argv) > 4 and sys.argv[4] == "gpu"
extra = dict(a.split("=", 1) for a in sys.argv[(5 if gpu else 4):])
geo = json.loads((HERE / "GEOMETRY_GODO.json").read_text())
case = HERE / "overset" / ("%s_%s" % (tag, time.strftime("%Y%m%d_%H%M%S")))
case.mkdir(parents=True)
shutil.copy2(SRC, case / "input.sim")
for f in [p.name for p in HERE.glob("GodoBackground*.stl")] + ["GodoOverset.stl", "BuildGodoOverset.java"]:
    shutil.copy2(HERE / f, case / f)
cc = subprocess.run([JAVAC, "-encoding", "UTF-8", "-nowarn", "-cp", EXT, "-d", str(case / "compiled"), str(case / "BuildGodoOverset.java")],
                    capture_output=True, text=True)
if cc.returncode:
    (case / "javac_errors.txt").write_text(cc.stderr); raise SystemExit("javac failed")
props = {"mode": mode, "base_size_m": 1.0, "dt_s": 1e-3, "chord_m": geo["chord_m"], "free_surface_y_m": geo["free_surface_y_m"],
         "H_m": geo["H_m"], "x0_m": geo["domain_x_m"][0], "band_x1_m": geo["domain_x_m"][1] - 0.8 * geo["lambda_deep_m"],
         "pivot_x_m": 0.25 * geo["chord_m"], "pivot_y_m": 0.0, "mass_kg": 12500.0 / (25.6 * 0.312) * 0.02,
         "release_time_s": geo["encounter_period_s"], "ramp_time_s": 0.5, "travel_cell_pct": 1.0,
         "probe_steps": 30, "probe_pitch_deg": 1.0, "probe_release_s": 0.005}
props.update(extra)
(case / "control.properties").write_text("\n".join("%s=%s" % kv for kv in props.items()) + "\n")
res = starrun.launch(case / "input.sim", case / "BuildGodoOverset.java", case, cpus=cores, np_=1 if gpu else len(cores),
                     timeout_s=3 * 3600, gpu=gpu)
out = {"case": str(case), "launch": res}
for f in ("GODO_OVERSET.json", "OVERSET_PROBE.json", "ERROR.json"):
    if (case / f).exists():
        out[f] = json.loads((case / f).read_text())
(case / "RUN_SUMMARY.json").write_text(json.dumps(out, indent=1))
print(json.dumps({k: v for k, v in out.items() if k != "launch"}, indent=1)[:4000])
