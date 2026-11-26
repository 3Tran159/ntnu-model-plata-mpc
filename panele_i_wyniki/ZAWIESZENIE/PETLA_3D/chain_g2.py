"""Noc 15/16.11: krepe platy i petla G2. Siatki (CPU 22-23) -> liczenie (GPU, host 23). Log: chain_g2.log."""
import subprocess, time
from pathlib import Path
HERE = Path(__file__).parent; PY = r"T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe"
CASES = "P3D_AR8_jeden,P3D_AR8_g2_h04,P3D_g2_h04,P3D_AR8_g2_h10,P3D_AR4_jeden,P3D_AR4_g2_h04"
def log(m):
    with open(HERE / "chain_g2.log", "a", encoding="utf-8") as f: f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + m + "\n")
log("start siatek " + CASES); subprocess.run([PY, str(HERE / "run_p3d.py"), "mesh", CASES], cwd=HERE)
ok = ",".join(c for c in CASES.split(",") if (HERE / c / "PETLA_SETUP.sim").exists())
log("siatki gotowe: " + ok); subprocess.run([PY, str(HERE / "run_p3d.py"), "run", ok], cwd=HERE); log("koniec")
