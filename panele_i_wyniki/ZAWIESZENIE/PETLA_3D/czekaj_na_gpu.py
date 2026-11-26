"""Czeka, az (1) Julek zaakceptuje model (plik ZGODA w tym folderze) i (2) GPU bedzie wolne (brak procesu STAR z POL32 / innych
procesow obliczeniowych na GPU poza pomocnikiem MATLAB-a). Potem uruchamia liczenie 3D na GPU: run_p3d.py run <przypadki>.
Sprawdzenie co 2 min, log: czekaj_na_gpu.log. Agent D, 15.11.2026."""
import subprocess, sys, time
from pathlib import Path
import psutil
HERE = Path(__file__).parent; LOG = HERE / "czekaj_na_gpu.log"
CASES = sys.argv[1] if len(sys.argv) > 1 else "P3D_jeden,P3D_petla,P3D_dwuplat,P3D_petla_s03"
PY = r"T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe"
def log(m):
    with open(LOG, "a", encoding="utf-8") as f: f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + m + "\n")
def gpu_busy():
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            cl = " ".join(p.info["cmdline"] or [])
            if "star" in (p.info["name"] or "").lower() and ("-gpgpu" in cl or "CFD_POL32" in cl): return "STAR na GPU: " + str(p.pid)
        except Exception: pass
    try:
        out = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name", "--format=csv,noheader"], capture_output=True, text=True).stdout
        apps = [l for l in out.splitlines() if l.strip() and "matlab" not in l.lower()]
        if apps: return "nvidia-smi: " + apps[0][:80]
    except Exception as e: return "nvidia-smi blad " + str(e)
    return None
log("start, przypadki " + CASES)
while True:
    if (HERE / "STOP").exists(): log("STOP"); break
    ok = (HERE / "ZGODA").exists() and all((HERE / c / "PETLA_SETUP.sim").exists() for c in CASES.split(",")); b = gpu_busy()
    if ok and not b:
        log("GPU wolne i zgoda jest - start liczenia")
        subprocess.run([PY, str(HERE / "run_p3d.py"), "run", CASES], cwd=HERE)
        log("koniec liczenia"); break
    time.sleep(120)
