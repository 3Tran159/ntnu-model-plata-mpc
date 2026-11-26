"""usage: python run_diag.py SIM MACRO.java OUT_DIR cores"""
import shutil, sys
from pathlib import Path
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\20_supervisor")
import starrun
import night_queue as nq

sim, macro, case, cores = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), tuple(int(c) for c in sys.argv[4].split(","))
case.mkdir(parents=True, exist_ok=True)
shutil.copy2(sim, case / "diag_input.sim")
nq.compile_macro(case, macro)
print(starrun.launch(case / "diag_input.sim", case / macro, case, cpus=cores, np_=len(cores), timeout_s=3600, gpu=False))
