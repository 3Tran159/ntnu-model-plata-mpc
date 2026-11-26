"""Luk z innego profilu (kt grubosc, kc cieciwa na srodku luku), na bazie optymalizacji petli G2 w CFD 3D (noc 15/16.11, agent D). Parametry: AR (4-25,6, log), odstep h (0,2-1,2 m), przesuniecie s (-0,4..0,4 m).
Plan: OPT_PLAN.json (Latin Hypercube, seed 7) + plat pojedynczy AR 12 i 16 + powtorki. Rownolegle: siatka (CPU) i liczenie (GPU).
Czeka na koniec chain_g2.py. Wyniki: OPT_WYNIKI.csv (po kazdym przypadku), log opt_p3d.log. STOP: plik STOP_OPT."""
import csv, json, math, subprocess, threading, time
from pathlib import Path
import numpy as np, psutil
import opt_geo
HERE = Path(__file__).parent; PY = r"T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe"; QS = 0.5 * 997.561 * (24 * 1852 / 3600) ** 2 * (8.0 * 0.312 / 2)
LOG = HERE / "otw_p3d.log"
def log(m):
    with open(LOG, "a", encoding="utf-8") as f: f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + m + "\n")
def alive(pat): return any(pat in " ".join(p.info["cmdline"] or []) for p in psutil.process_iter(["cmdline"]) if p.info["cmdline"])
plan_f = HERE / "OTW_PLAN.json"
if plan_f.exists(): plan = json.loads(plan_f.read_text())
else:
    rng = np.random.default_rng(7); n = 32; plan = []
    u = np.column_stack([(rng.permutation(n) + rng.random(n)) / n for _ in range(3)])
    for k, (a, b, c) in enumerate(u):
        ar = math.exp(math.log(4) + a * (math.log(25.6) - math.log(4))); h = 0.2 + b * 1.0; s = -0.4 + c * 0.8
        plan.append(dict(name=f"OPT_{k:02d}", ar=round(ar, 2), gap=round(h, 3), stag=round(s, 3)))
    plan = [dict(name="P3D_AR8_jeden", ar=8, gap=None, stag=0), dict(name="P3D_g2_h04", ar=25.6, gap=0.4, stag=0), dict(name="P3D_AR8_g2_h10", ar=8, gap=1.0, stag=0),
            dict(name="P3D_AR12_jeden", ar=12, gap=None, stag=0), dict(name="P3D_AR16_jeden", ar=16, gap=None, stag=0)] + plan
    plan_f.write_text(json.dumps(plan, indent=1))
log(f"start, {len(plan)} przypadkow; czekam na chain_g2")
while alive("dek_p3d.py") or alive("luk_p3d.py") or alive("te_p3d.py"): time.sleep(60)
log("chain_g2 zakonczony - start optymalizacji")
ready, done = [], set()
def mesh_cpus(): return "18,19,20,21,22" if not alive("k0_cele.py") else "22"
def mesher():
    for p in plan:
        if (HERE / "STOP_OTW").exists(): break
        cd = HERE / p["name"]
        if not (cd / "PETLA_SETUP.sim").exists():
            for f in ("ERROR.json",):
                if (cd / f).exists(): (cd / f).rename(cd / f"ERROR_przed_opt_{time.strftime('%H%M%S')}.json")
            opt_geo.make_case(p["name"], p["ar"], p["gap"], p["stag"], p.get("kt", 1.0), p.get("kc", 1.0), p.get("da", 0.0), p.get("f_up", 1.0), p.get("s_end", 1.0), p.get("ext", 0.0)); cpus = mesh_cpus()
            log(f"siatka {p['name']} AR {p['ar']} h {p['gap']} s {p['stag']} na {cpus}")
            subprocess.run([PY, str(HERE / "run_p3d.py"), "mesh", p["name"], cpus, "23"], cwd=HERE)
        if (cd / "PETLA_SETUP.sim").exists(): ready.append(p)
        else: log(f"siatka {p['name']} NIEUDANA"); done.add(p["name"])
    ready.append(None)
def row(p):
    cd = HERE / p["name"]; w = json.loads((cd / "P3D_WYNIK.json").read_text()); m = json.loads((cd / "P3D_MESH.json").read_text())
    fx, fz = w["Fx_suma"], w["Fz_suma"]; r = dict(name=p["name"], kt=p.get("kt", 1.0), kc=p.get("kc", 1.0), f_up=p.get("f_up", 1.0), s_end=p.get("s_end", 1.0), ext=p.get("ext", 0.0), AR=p["ar"], gap=p["gap"] if p["gap"] else "", stag=p["stag"], cells=m.get("cells"),
        iter=w.get("final_iter"), converged=w.get("converged", False), Fx=fx, Fz=fz, CL=fz / QS, CD=fx / QS, LD=fz / fx)
    for k in ("gorny", "dolny", "luk", "plat"):
        if f"Fz_{k}" in w: r[f"Fz_{k}"] = w[f"Fz_{k}"]; r[f"Fx_{k}"] = w[f"Fx_{k}"]
    return r
th = threading.Thread(target=mesher, daemon=True); th.start(); out = HERE / "OTW_WYNIKI.csv"
while True:
    if (HERE / "STOP_OTW").exists(): log("STOP"); break
    if not ready: time.sleep(20); continue
    p = ready.pop(0)
    if p is None: break
    cd = HERE / p["name"]
    if not (cd / "P3D_WYNIK.json").exists():
        log(f"liczenie {p['name']}"); subprocess.run([PY, str(HERE / "run_p3d.py"), "run", p["name"], "22", "23"], cwd=HERE)
    if (cd / "P3D_WYNIK.json").exists():
        r = row(p); new = not out.exists()
        with open(out, "a", newline="", encoding="utf-8") as f:
            wcsv = csv.DictWriter(f, fieldnames=["name", "kt", "kc", "f_up", "s_end", "ext", "AR", "gap", "stag", "cells", "iter", "converged", "Fx", "Fz", "CL", "CD", "LD",
                                                 "Fz_gorny", "Fx_gorny", "Fz_dolny", "Fx_dolny", "Fz_luk", "Fx_luk", "Fz_plat", "Fx_plat"], extrasaction="ignore")
            if new: wcsv.writeheader()
            wcsv.writerow(r)
        log(f"wynik {p['name']}: CL {r['CL']:.3f} CD {r['CD']:.5f} L/D {r['LD']:.1f}")
    else: log(f"liczenie {p['name']} NIEUDANE")
log("koniec optymalizacji")
