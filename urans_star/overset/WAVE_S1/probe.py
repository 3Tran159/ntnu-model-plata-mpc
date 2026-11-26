"""20.11 22:00: rozpoznanie API fali superpozycji na kopii setupu fali T4 (nic nie zapisuje). Rdzen 23."""
import sys, json, shutil
from pathlib import Path
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\20_supervisor")
import starrun
HERE = Path(__file__).parent
src = sorted((HERE.parent).glob("OV_SHORT30*"))[-1] / "GODO_OVERSET_SETUP_B1.0.sim"
if not (HERE / "input.sim").exists(): shutil.copy2(src, HERE / "input.sim")
r = starrun.launch(HERE / (sys.argv[2] if len(sys.argv) > 2 else "input.sim"), HERE / sys.argv[1], HERE, cpus=(23,), np_=1, timeout_s=900)
(HERE / ("launch_" + sys.argv[1] + ".json")).write_text(json.dumps(r, indent=1, default=str))
print(json.dumps(r, default=str)[:400])

