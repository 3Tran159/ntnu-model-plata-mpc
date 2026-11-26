"""V3a noc: woda spokojna, plat pojedynczy vs podzielony, natywny przypadek STAR bez overset, GPU (agent D, 14.11.2026).
Uzywa (tylko odczyt) 00_source/FIXED_FINAL_src.sim i 20_supervisor/starrun.py. Wszystko w tym folderze."""
import json, math, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\20_supervisor")
import starrun

HERE = Path(__file__).parent
SRC = Path(r"T:\NTNU_GODO_CONTROL_20261109\00_source\FIXED_FINAL_src.sim")
JAVAC = r"C:\Program Files\Eclipse Adoptium\jdk-25.0.3.9-hotspot\bin\javac.exe"
EXT = r"E:\Program Files\Siemens\21.04.009-R8\STAR-CCM+21.04.009-R8\star\lib\java\platform\modules\ext\*"
LAM = 9.81 * 25 / (2 * math.pi)
STEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
VARS_ = {
 "single": {"foil_size_scale": 1.0, "foil_y_offsets": "0", "free_surface_y_m": 1.09, "prism_total_m": 6.79e-4,
            "foil_area_m2": 0.00795948899616472},
 "split":  {"foil_size_scale": 0.5, "foil_y_offsets": "0;1.0", "free_surface_y_m": 1.70, "prism_total_m": 6.3e-4,
            "foil_area_m2": 0.00397974449808236},
}
VARS = {k: VARS_[k] for k in ("split", "single")}
status = {"start": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": STEPS, "cases": {}}
def save(): (HERE / "V3A_STATUS.json").write_text(json.dumps(status, indent=1))
for var, vp in VARS.items():
    case = HERE / ("V3A_%s%s" % (var, "_r2" if var == "single" else "")); case.mkdir(exist_ok=True)
    status["cases"][var] = {"dir": str(case), "state": "przygotowanie", "t0": time.strftime("%H:%M:%S")}; save()
    shutil.copy2(SRC, case / "input.sim")
    shutil.copy2(HERE / ("GodoFluidDomain_%s.stl" % var), case / "GodoFluidDomain.stl")
    shutil.copy2(HERE / "BuildGodoSplit.java", case / "BuildGodoSplit.java")
    cc = subprocess.run([JAVAC, "-encoding", "UTF-8", "-nowarn", "-cp", EXT, "-d", str(case / "compiled"), str(case / "BuildGodoSplit.java")],
                        capture_output=True, text=True)
    if cc.returncode:
        (case / "javac_errors.txt").write_text(cc.stderr); status["cases"][var]["state"] = "javac blad"; save(); continue
    props = {"mode": "probe", "base_size_m": 1.0, "dt_s": 0.001, "probe_steps": STEPS, "inner": 12, "cores": "18",
             "chord_m": 0.312, "H_m": 1.5, "wave_H_m": 1e-4, "x0_m": -1.2 * LAM, "band_x1_m": 2.0 * LAM,
             "U_m_s": 24 * 1852 / 3600, "lambda_m": LAM, "bottom_y_m": -LAM, "forcing_length_m": 0.4 * LAM,
             "damping_length_m": 0.8 * LAM, "encounter_period_s": 1.9367999917313226, "conv_window": 1000, "conv_tol": 0.0025, "min_steps": 3000}
    props.update(vp)
    (case / "control.properties").write_text("\n".join("%s=%s" % kv for kv in props.items()) + "\n")
    status["cases"][var]["state"] = "STAR liczy"; save()
    res = starrun.launch(case / "input.sim", case / "BuildGodoSplit.java", case, cpus=(18,), np_=1,
                         timeout_s=8 * 3600, gpu=True)
    st = status["cases"][var]; st["launch"] = res; st["t1"] = time.strftime("%H:%M:%S")
    for f in ("GODO_MESH.json", "COST_PROBE.json", "ERROR.json"):
        if (case / f).exists():
            st[f] = json.loads((case / f).read_text())
    st["state"] = "blad" if (case / "ERROR.json").exists() else "koniec"
    save()
status["end"] = time.strftime("%Y-%m-%d %H:%M:%S"); save()
