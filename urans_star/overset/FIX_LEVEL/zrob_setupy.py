"""24.11: setupy fali Godo (B1.0, OV_SHORT30*) z poziomem wody 1,39 i 1,69 m nad osia plata (plat nieruchomy na 3 glebokosciach). Rdzenie 18-19."""
import shutil, sys, json
from pathlib import Path
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\20_supervisor")
import starrun
HERE = Path(__file__).parent
src = sorted((HERE.parent).glob("OV_SHORT30*"))[-1] / "GODO_OVERSET_SETUP_B1.0.sim"
shutil.copy2(src, HERE / "input.sim")
for t in ("139", "169"):
    r = starrun.launch(HERE / "input.sim", HERE / f"SetLevelFixL{t}.java", HERE, cpus=(18, 19), np_=1, timeout_s=1800)
    (HERE / f"launch_L{t}.json").write_text(json.dumps(r, indent=1, default=str))
    print(t, (HERE / f"GODO_OVERSET_SETUP_B1.0_L{t}.sim").exists(), flush=True)