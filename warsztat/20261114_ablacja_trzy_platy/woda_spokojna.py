"""woda_spokojna.py - koordynator 14.11.2026 (prosba Julka 19:43): walidacja w wodzie spokojnej jak u GodÃ¸ (CL, CD, kat, opor) - model B i "same wiry" wobec URANS.
Model: nachylenie dCL/dalfa, opor przy trymie, rozbicie oporu; glebokosci 1,09 / 1,39 / 1,69 m (jak URANS CALM, CALM_Z-0.3, CALM_Z-0.6). URANS: srednie z history.csv."""
import json, sys, csv
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(Path(r"T:\NTNU_GODO_CONTROL_20261109\60_PANELE_I_WYNIKI") / "ZAWIESZENIE"))
import zaw90 as Z
FP, G, BUOY = Z.FP, Z.G, Z.BUOY
RUNS = Path(r"T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset_runs")
out = {"urans": {}, "model": {}}
for tag in ("OVS_CALM_PID2", "OVS_CALM_Z-0.3", "OVS_CALM_Z-0.6", "OVS_CALM_90"):
    f = RUNS / tag / "history.csv"
    if not f.exists(): out["urans"][tag] = "brak"; continue
    rd = csv.reader(open(f)); h = next(rd); R = {}
    for r in rd:
        if len(r) == len(h): R[r[0]] = r
    A = np.array([[float(r[h.index(c)]) for c in ("time_s", "theta_deg", "AF_CL", "AF_CD", "P_drag_W", "z_m", "GODO_eta_at_LE")] for r in R.values()]); A = A[np.argsort(A[:, 0])]
    tE = A[-1, 0]; w = A[:, 0] > tE - 1.0
    out["urans"][tag] = dict(t_end=round(tE, 2), theta=round(A[w, 1].mean(), 3), CL=round(A[w, 2].mean(), 4), CD=round(A[w, 3].mean(), 5), P=round(A[w, 4].mean(), 2),
                             z=round(A[w, 5].mean(), 3), eta_LE=round(A[w, 6].mean(), 3))
for var, kw in (("B", dict(slope=1.0, wave_u=True)), ("wiry", dict(slope=1.0, wave_u=False, free_surface=False))):
    for dz in (0.0, 0.3, 0.6):
        FP.MASS = Z.MASS100; P = Z.FaltinsenPlant(wave_amp=0.0, depth_image=1.09 + dz, **kw)
        res = {}
        for th in (2.5, 3.0, 3.5):
            P.reset(theta_deg=th); P.cmd = np.radians(th)
            rr = [P.step(free_heave=False) for _ in range(6000)]
            L = np.mean([r["L"] for r in rr[3000:]]); Pd = np.mean([r["P_drag_W_strip"] for r in rr[3000:]])
            res[th] = (L / P.q, Pd)
        cl = np.array([res[t][0] for t in (2.5, 3.0, 3.5)]); sl = np.polyfit(np.radians([2.5, 3.0, 3.5]), cl, 1)
        out["model"][f"{var}_glebokosc_{1.09 + dz:.2f}"] = dict(dCLdalfa_per_rad=round(sl[0], 3), dcl_plant=round(float(P.dcl), 3), CL_at=dict((str(t), round(res[t][0], 4)) for t in res),
                                                               P_at=dict((str(t), round(res[t][1], 3)) for t in res), P_CD0_only=round(float(P.cd0 * P.q * Z.U * 0.02), 3))
(HERE / "WODA_SPOKOJNA.json").write_text(json.dumps(out, indent=1), encoding="utf-8"); print(json.dumps(out))

