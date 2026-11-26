"""Sceny wynikow (PostPetla3D.java) dla podanych przypadkow; CPU, rdzen 22, np 1. Zamyka po sobie nowe procesy STAR."""
import sys, time
from pathlib import Path
import psutil
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\20_supervisor")
import starrun
HERE = Path(__file__).parent
def star_pids(): return {p.pid for p in psutil.process_iter(["name"]) if any(k in (p.info["name"] or "").lower() for k in ("star", "mpiexec", "hydra"))}
for case in sys.argv[1].split(","):
    cd = HERE / case; (cd / "PostPetla3D.java").write_bytes((HERE / "PostPetla3D.java").read_bytes())
    before = star_pids()
    starrun.launch(cd / "PETLA_KONIEC.sim", cd / "PostPetla3D.java", cd, cpus=(22,), np_=1, timeout_s=3600, gpu=False)
    time.sleep(5)
    for pid in star_pids() - before:
        try: psutil.Process(pid).kill()
        except Exception: pass
