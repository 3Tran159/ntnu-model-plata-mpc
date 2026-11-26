"""Komplet scen PostPelny3D.java (natywne, zapisane w PETLA_KONIEC.sim) dla podanych przypadkow. CPU rdzen 22. Zamyka tylko wlasne procesy."""
import sys, json, time
from pathlib import Path
import psutil
sys.path.insert(0, r"T:\\NTNU_GODO_CONTROL_20261109\\20_supervisor")
import starrun
HERE = Path(__file__).parent; G = json.loads((HERE / "GEOMETRIA_G2.json").read_text())
for case in sys.argv[1].split(","):
    cd = HERE / case; g = G[case]
    (cd / "post.properties").write_text(f"hs={g['pol_rozp_m']}\ngap={g['odstep_m']}\nc={g['cieciwa_platu_m']}\nyluk={g['pol_rozp_m']}\nU=12.347\nrho=997.561\n")
    (cd / "PostPelny3D.java").write_bytes((HERE / "PostPelny3D.java").read_bytes())
    r = starrun.launch(cd / "PETLA_KONIEC.sim", cd / "PostPelny3D.java", cd, cpus=(22,), np_=1, timeout_s=3600, gpu=False)
    time.sleep(5)
    for pid, _n in r.get("bound") or []:
        try: psutil.Process(int(pid)).kill()
        except Exception: pass
    print(case, r.get("returncode"), flush=True)
