"""slope_from_calm.py - nachylenie dCL/dalfa profilu w URANS w WODZIE SPOKOJNEJ (OVS_CALM_PID2), dwa stany ustalone:
 (1) nurzanie zablokowane, kat 3,5 deg (t = 0,90-1,00 s);  (2) po zwolnieniu, PID ustalony (t = 3,5-4,0 s), kat efektywny = theta - v/U.
Szacunek zgrubny: stan (1) jeszcze narasta (CL +0,0014 w ostatnich 0,09 s), wiec nachylenie jest raczej zanizone. Wynik: SLOPE_CALM.json"""
import csv, json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
from faltinsen_plant import FaltinsenPlant, U
rows = list(csv.DictReader(open(HERE.parents[1] / "30_URANS_STAR" / "overset_runs" / "OVS_CALM_PID2" / "history.csv")))
g = lambda k: np.array([float(r[k]) for r in rows]); t, th, cl, v = g("time_s"), g("theta_deg"), g("AF_CL"), g("v_m_s")
a = (t > 0.90) & (t <= 1.00); b = (t > 3.5) & (t <= 4.0)
al1 = th[a].mean(); al2 = (th[b] - np.degrees(v[b] / U)).mean()
slope = (cl[a].mean() - cl[b].mean()) / np.radians(al1 - al2); P = FaltinsenPlant()
out = dict(CL_1=float(cl[a].mean()), alfa_1_deg=float(al1), CL_2=float(cl[b].mean()), alfa_2_deg=float(al2), dCL_dalfa_per_rad=float(slope),
           over_2pi=float(slope / (2 * np.pi)), over_model_slope_with_image=float(slope / P.dcl), model_slope_per_rad=float(P.dcl))
print(json.dumps(out, indent=1)); (HERE / "SLOPE_CALM.json").write_text(json.dumps(out, indent=1))
