"""Run BuildGodoCase.java (mesh / cost probe / mesh-convergence levels) unattended.

usage: python run_godo.py <tag> <mode mesh|probe> <base_size_m> <dt_s> <probe_steps> <cpus e.g. 12,13> [np]
Case folder: 70_godo_case/runs/<tag>_B<base>_dt<dt>_<stamp>/ with input.sim (copy of the frozen Mini FIXED checkpoint),
GodoFluidDomain.stl, BuildGodoCase.java, control.properties, stdout.log, GODO_MESH.json, COST_PROBE.json, *.sim, *.png
"""
import json, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\20_supervisor")
import starrun

HERE = Path(__file__).parent
SRC = Path(r"T:\NTNU_GODO_CONTROL_20261109\00_source\FIXED_FINAL_src.sim")
GEO = json.loads((HERE / "GEOMETRY_GODO.json").read_text())
JAVAC = r"C:\Program Files\Eclipse Adoptium\jdk-25.0.3.9-hotspot\bin\javac.exe"
EXT = r"E:\Program Files\Siemens\21.04.009-R8\STAR-CCM+21.04.009-R8\star\lib\java\platform\modules\ext\*"

tag, mode, base, dt, steps, cpus = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), int(sys.argv[5]), sys.argv[6]
np_ = int(sys.argv[7]) if len(sys.argv) > 7 else len(cpus.split(","))
gpu = len(sys.argv) > 8 and sys.argv[8] == "gpu"
case = HERE / "runs" / ("%s_B%g_dt%g_np%d%s_%s" % (tag, base, dt, np_, "_gpu" if gpu else "", time.strftime("%Y%m%d_%H%M%S")))
case.mkdir(parents=True)
shutil.copy2(SRC, case / "input.sim")
shutil.copy2(HERE / "GodoFluidDomain.stl", case / "GodoFluidDomain.stl")
shutil.copy2(HERE / "BuildGodoCase.java", case / "BuildGodoCase.java")
cc = subprocess.run([JAVAC, "-encoding", "UTF-8", "-nowarn", "-cp", EXT, "-d", str(case / "compiled"), str(case / "BuildGodoCase.java")],
                    capture_output=True, text=True)
if cc.returncode:
    (case / "javac_errors.txt").write_text(cc.stderr); raise SystemExit("javac failed")
props = {"mode": mode, "base_size_m": base, "dt_s": dt, "probe_steps": steps, "inner": 12, "cores": cpus,
         "chord_m": GEO["chord_m"], "free_surface_y_m": GEO["free_surface_y_m"], "H_m": GEO["H_m"],
         "x0_m": GEO["domain_x_m"][0], "band_x1_m": GEO["domain_x_m"][1] - 0.8 * GEO["lambda_deep_m"],
         "U_m_s": GEO["U_m_s"], "lambda_m": GEO["lambda_deep_m"], "bottom_y_m": GEO["domain_y_m"][0],
         "forcing_length_m": 0.4 * GEO["lambda_deep_m"], "damping_length_m": 0.8 * GEO["lambda_deep_m"],
         "foil_area_m2": 0.00795948899616472, "encounter_period_s": GEO["encounter_period_s"]}
(case / "control.properties").write_text("\n".join("%s=%s" % kv for kv in props.items()) + "\n")
res = starrun.launch(case / "input.sim", case / "BuildGodoCase.java", case, cpus=tuple(int(c) for c in cpus.split(",")),
                     np_=np_, timeout_s=6 * 3600, gpu=gpu)
summary = {"case": str(case), "props": props, "launch": res}
for f in ("GODO_MESH.json", "COST_PROBE.json", "ERROR.json"):
    if (case / f).exists():
        summary[f] = json.loads((case / f).read_text())
(case / "RUN_SUMMARY.json").write_text(json.dumps(summary, indent=1))
print(json.dumps(summary, indent=1))
