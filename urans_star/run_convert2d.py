"""usage: python run_convert2d.py SETUP_3D.sim OUT_DIR cores"""
import shutil, sys
from pathlib import Path
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\20_supervisor")
import starrun
import night_queue as nq

HERE = Path(__file__).parent
src, case, cores = Path(sys.argv[1]), Path(sys.argv[2]), tuple(int(c) for c in sys.argv[3].split(","))
case.mkdir(parents=True, exist_ok=True)
shutil.copy2(src, case / "input3d.sim")
nq.compile_macro(case, "ConvertOverset2D.java")
print(starrun.launch(case / "input3d.sim", case / "ConvertOverset2D.java", case, cpus=cores, np_=len(cores), timeout_s=3600, gpu=False))
