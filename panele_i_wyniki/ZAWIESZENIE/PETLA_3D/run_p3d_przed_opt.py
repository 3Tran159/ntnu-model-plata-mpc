"""Kolejka 3D petli platow (agent D, 15.11.2026). Uzycie:
  python run_p3d.py mesh P3D_petla[,P3D_jeden,...]   -> siatka + sceny PNG + PETLA_SETUP.sim (CPU, rdzenie 22-23, np 2)
  python run_p3d.py run  P3D_jeden,P3D_petla,...       -> liczenie na GPU (rdzen 2), wznowienie z PETLA_CKPT.sim po awarii (do 8 prob)
Status: P3D_STATUS.json. Po kazdym uruchomieniu zamykane sa wiszace procesy STAR uruchomione przez ten skrypt (tylko nowe PID-y)."""
import json, subprocess, sys, time
from pathlib import Path
import psutil
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\20_supervisor")
import starrun
HERE = Path(__file__).parent
JAVAC = r"C:\Program Files\Eclipse Adoptium\jdk-25.0.3.9-hotspot\bin\javac.exe"
EXT = r"E:\Program Files\Siemens\21.04.009-R8\STAR-CCM+21.04.009-R8\star\lib\java\platform\modules\ext\*"
BODIES = {"P3D_jeden": "plat", "P3D_dwuplat": "gorny,dolny", "P3D_petla": "gorny,dolny,plytka", "P3D_petla_s03": "gorny,dolny,plytka"}
phase, cases = sys.argv[1], sys.argv[2].split(",")
st_file = HERE / "P3D_STATUS.json"
status = json.loads(st_file.read_text()) if st_file.exists() else {}
def save(): st_file.write_text(json.dumps(status, indent=1))
def star_pids(): return {p.pid for p in psutil.process_iter(["name"]) if "star" in (p.info["name"] or "").lower() or "mpiexec" in (p.info["name"] or "").lower() or "hydra" in (p.info["name"] or "").lower()}
def launch(case, sim, cpus, np_, gpu, timeout):
    cd = HERE / case
    subprocess.run([JAVAC, "-encoding", "UTF-8", "-nowarn", "-cp", EXT, "-d", str(cd / "compiled"), str(HERE / "BuildPetla3D.java")], check=True)
    (cd / "BuildPetla3D.java").write_bytes((HERE / "BuildPetla3D.java").read_bytes())
    before = star_pids()
    res = starrun.launch(sim, cd / "BuildPetla3D.java", cd, cpus=cpus, np_=np_, timeout_s=timeout, gpu=gpu)
    time.sleep(5)
    for pid in star_pids() - before:                      # tylko procesy powstale w tym uruchomieniu
        try: psutil.Process(pid).kill()
        except Exception: pass
    return res
S_FULL = 8.0 * 0.312
def geo(ar):
    import math; b = math.sqrt(ar * S_FULL); return b / 2, S_FULL / b      # pol rozpietosci, cieciwa jednego platu
G2 = json.loads((HERE / "GEOMETRIA_G2.json").read_text()) if (HERE / "GEOMETRIA_G2.json").exists() else {}
for _c, _g in G2.items(): BODIES[_c] = "dolny,luk,gorny"
BODIES.update({"P3D_AR8_jeden": "plat", "P3D_AR4_jeden": "plat"})
def props(case, mode):
    if case in G2:                                          # petla G2 (jedna bryla, luk)
        g = G2[case]; C = g["cieciwa_platu_m"]; hs = g["pol_rozp_m"]; gap = g["odstep_m"]
        ex = {"foil_lev": f"0:{gap};0:0", "plate_x": "0:0", "plate_ylo": g["y_poczatku_luku_m"] - 0.05, "plate_yhi": hs + 0.05, "gap_m": gap, "zmax_m": gap + 0.3}
    elif case in ("P3D_AR8_jeden", "P3D_AR4_jeden"):
        hs, C = geo(8 if "AR8" in case else 4); ex = {"foil_lev": "0:0.5"}
    else:
        hs = 4.0; C = 0.312 if case == "P3D_jeden" else 0.156
        ex = {"P3D_jeden": {"foil_lev": "0:0.5"}, "P3D_dwuplat": {"foil_lev": "0:1.0;0:0"}, "P3D_petla": {"foil_lev": "0:1.0;0:0", "plate_x": "0:0"},
              "P3D_petla_s03": {"foil_lev": "0:1.0;0.3:0", "plate_x": "0:0.3"}}[case]
    p = {"mode": mode, "bodies": BODIES[case], "stl_files": "bryla", "chord_m": C, "prism_total_m": 6.79e-4 * (C / 0.312) ** 0.1,
         "cells_per_chord": 40, "base_size_m": 0.8, "U_m_s": 24 * 1852 / 3600, "max_iter": 3000, "min_iter": 800,
         "conv_window": 300, "conv_tol": 0.001, "save_every": 250, "half_span_m": hs, "ymax_m": hs + 0.3,
         "xmax_m": 1.2 * (2 * C if case in G2 else C) + 0.2}
    p.update(ex)
    (HERE / case / "control.properties").write_text("\n".join(f"{k}={v}" for k, v in p.items()) + "\n")
for case in cases:
    cd = HERE / case; st = status.setdefault(case, {})
    if phase == "mesh":
        st.update(mesh="siatkowanie", mesh_t0=time.strftime("%H:%M:%S")); save(); props(case, "mesh")
        r = launch(case, "-new", (22, 23), 2, False, 3 * 3600)
        st.update(mesh="blad" if (cd / "ERROR.json").exists() or not (cd / "PETLA_SETUP.sim").exists() else "gotowa", mesh_t1=time.strftime("%H:%M:%S"), mesh_launch=r["returncode"])
        if (cd / "P3D_MESH.json").exists(): st["mesh_info"] = json.loads((cd / "P3D_MESH.json").read_text())
        save()
    else:
        props(case, "run"); st.update(run="liczy", run_t0=time.strftime("%H:%M:%S"), proby=0); save()
        for k in range(8):
            if (cd / "P3D_WYNIK.json").exists(): break
            sim = cd / ("PETLA_CKPT.sim" if (cd / "PETLA_CKPT.sim").exists() else "PETLA_SETUP.sim")
            st["proby"] = k + 1; st["start_z"] = sim.name; save()
            launch(case, sim, (23,), 1, True, 6 * 3600)
        st.update(run="koniec" if (cd / "P3D_WYNIK.json").exists() else "blad", run_t1=time.strftime("%H:%M:%S")); save()
