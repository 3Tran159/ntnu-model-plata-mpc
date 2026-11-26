import sys, json
from pathlib import Path
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\20_supervisor")
import starrun
G = Path(r"T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\GUI_T8")
r = starrun.launch(Path(r"T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset_runs\OVS_CEL_000g_T8_90\END_t13.6870.sim"), G / "DodajIZapisz.java", G / "run_dodaj", cpus=(18, 19), np_=1, timeout_s=1800)
(G / "launch_dodaj.json").write_text(json.dumps(r, indent=1, default=str)); print(r.get("returncode"))