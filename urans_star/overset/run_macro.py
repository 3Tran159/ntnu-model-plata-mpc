"""python run_macro.py <Macro.java> <input.sim> <case_dir> [cores] [gpu]  -- compile + run one STAR batch macro (no GPU by default)"""
import shutil, subprocess, sys, json
from pathlib import Path
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\20_supervisor")
import starrun
JAVAC = r"C:\Program Files\Eclipse Adoptium\jdk-25.0.3.9-hotspot\bin\javac.exe"
EXT = r"E:\Program Files\Siemens\21.04.009-R8\STAR-CCM+21.04.009-R8\star\lib\java\platform\modules\ext\*"
macro, sim, case = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
cores = tuple(int(c) for c in (sys.argv[4] if len(sys.argv) > 4 else "14").split(","))
gpu = len(sys.argv) > 5 and sys.argv[5] == "gpu"
case.mkdir(parents=True, exist_ok=True)
shutil.copy2(macro, case / macro.name)
if sim.parent != case:
    shutil.copy2(sim, case / sim.name); sim = case / sim.name
r = subprocess.run([JAVAC, "-encoding", "UTF-8", "-nowarn", "-cp", EXT, "-d", str(case / "compiled"), str(case / macro.name)], capture_output=True, text=True)
if r.returncode:
    (case / "javac_errors.txt").write_text(r.stderr); print(r.stderr[-3000:]); raise SystemExit(1)
res = starrun.launch(sim, case / macro.name, case, cpus=cores, np_=1 if gpu else len(cores), timeout_s=float(7200), gpu=gpu)
print(json.dumps({k: v for k, v in res.items() if k != "bound"}))
