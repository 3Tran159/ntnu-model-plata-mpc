"""19.11 (zgoda Julka 09:08 'spokojna woda na koniec'): setup spokojnej wody na gestej siatce GF (B 0,707), ta sama makra SetCalmWater.java co CALM (H -> 1e-4 m). Rdzenie 2-9."""
import shutil, sys, json
from pathlib import Path
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\20_supervisor")
import starrun
HERE = Path(__file__).parent
src = sorted(p for p in (HERE.parent).glob("OVG_GF_*") if p.is_dir())[-1]
src = sorted(src.glob("GODO_OVERSET_SETUP_B*.sim"))[0]
shutil.copy2(src, HERE / "input.sim")
shutil.copy2(HERE.parent / "CALM" / "SetCalmWater.java", HERE / "SetCalmWater.java")
r = starrun.launch(HERE / "input.sim", HERE / "SetCalmWater.java", HERE, cpus=tuple(range(2, 10)), np_=1, timeout_s=1800)
(HERE / "launch_result.json").write_text(json.dumps(r, indent=1, default=str))
print(src, (HERE / "SET_CALM.txt").read_text() if (HERE / "SET_CALM.txt").exists() else "BRAK SET_CALM.txt", (HERE / "GODO_OVERSET_SETUP_CALM.sim").exists())
