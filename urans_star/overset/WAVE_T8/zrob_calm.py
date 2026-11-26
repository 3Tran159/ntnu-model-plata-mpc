"""24.11: woda spokojna w domenie T8 (z GODO_OVERSET_SETUP_T8.sim, strefy 25/60 m). Rdzenie 18-19."""
import sys, json
from pathlib import Path
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\20_supervisor")
import starrun
HERE = Path(__file__).parent
r = starrun.launch(HERE / "GODO_OVERSET_SETUP_T8.sim", HERE / "SetCalmT8.java", HERE, cpus=(18, 19), np_=1, timeout_s=1800)
(HERE / "launch_calm.json").write_text(json.dumps(r, indent=1, default=str))
print((HERE / "GODO_OVERSET_SETUP_T8_CALM.sim").exists())