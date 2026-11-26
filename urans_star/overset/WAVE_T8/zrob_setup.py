"""23.11: setup fali T 8 s / H 1,5 m z setupu overset uzywanego przez OVS_*_90 (OV_SHORT30*), jak WAVE_T4. Rdzenie 18-19 (wolne)."""
import shutil, sys, json
from pathlib import Path
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\20_supervisor")
import starrun
HERE = Path(__file__).parent
src = sorted((HERE.parent).glob("OV_SHORT30*"))[-1] / "GODO_OVERSET_SETUP_B1.0.sim"
shutil.copy2(src, HERE / "input.sim")
r = starrun.launch(HERE / "input.sim", HERE / "SetWaveT8.java", HERE, cpus=(18, 19), np_=1, timeout_s=1800)
(HERE / "launch_result.json").write_text(json.dumps(r, indent=1, default=str))
print(src, (HERE / "SET_WAVE.txt").read_text() if (HERE / "SET_WAVE.txt").exists() else "BRAK SET_WAVE.txt", (HERE / "GODO_OVERSET_SETUP_T8.sim").exists())
