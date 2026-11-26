"""23.11: odczyt dlugosci stref fal w setupie T8 (zapis w miejscu). Rdzenie 18-19."""
import sys, json
from pathlib import Path
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\20_supervisor")
import starrun
HERE = Path(__file__).parent
r = starrun.launch(HERE / "GODO_OVERSET_SETUP_T8.sim", HERE / "SetZonesT8.java", HERE, cpus=(18, 19), np_=1, timeout_s=900)
(HERE / "launch_zones.json").write_text(json.dumps(r, indent=1, default=str))
