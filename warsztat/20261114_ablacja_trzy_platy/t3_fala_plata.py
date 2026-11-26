"""t3_fala_plata.py - koordynator 15.11: analiza OVS_CALM_100_FALA (woda spokojna 100 %, 20 s, sondy fali za platem) i OVS_PID1_90."""
import csv, json
from pathlib import Path
import numpy as np
RUNS = Path(r"T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset_runs")
def load(tag):
    rd = csv.reader(open(RUNS / tag / "history.csv")); h = next(rd); R = {}
    for r in rd:
        if len(r) == len(h): R[r[0]] = r
    rows = sorted(R.values(), key=lambda r: float(r[0]))
    D = {}
    for i, k in enumerate(h):
        try: D[k] = np.array([float(r[i]) for r in rows])
        except ValueError: pass
    return D
out = {}
D = load("OVS_CALM_100_FALA"); t = D["time_s"]
out["opor_2s"] = {f"{a}-{a+2}": round(float(D["P_drag_W"][(t >= a) & (t < a + 2)].mean()), 2) for a in range(0, 20, 2)}
out["CL_2s"] = {f"{a}-{a+2}": round(float(D["AF_CL"][(t >= a) & (t < a + 2)].mean()), 4) for a in range(0, 20, 2)}
out["theta_z_ost2s"] = [round(float(D["theta_deg"][t > 18].mean()), 3), round(float(D["z_m"][t > 18].mean()), 3)]
g = {}
for k in D:
    if k.startswith("GODO_eta_x"):
        e = D[k]; x = float(k[len("GODO_eta_x"):])
        g[x] = dict(mean_ost4s=round(float(e[t > 16].mean()), 3), min_ost4s=round(float(e[t > 16].min()), 3), max_ost4s=round(float(e[t > 16].max()), 3),
                    mean_2s={f"{a}": round(float(e[(t >= a) & (t < a + 2)].mean()), 3) for a in range(0, 20, 4)})
out["sondy"] = {str(k): g[k] for k in sorted(g)}
xs = np.array(sorted(g)); prof = np.array([g[x]["mean_ost4s"] for x in xs])
out["profil_x"] = [round(float(x), 1) for x in xs]; out["profil_eta_ost4s"] = [round(float(p), 3) for p in prof]
P = load("OVS_PID1_90"); tp = P["time_s"]; Te = 1.9368; te = tp[-1]
for n in (3, 4):
    m = tp > te - n * Te; out[f"PID1_90_P{n}"] = round(float(P["P_drag_W"][m].mean()), 2)
    a = np.gradient(P["v_m_s"], tp)[m]; out[f"PID1_90_acc{n}"] = round(float(a.std()), 3)
out["PID1_90_okresy"] = [round(float(P["P_drag_W"][(tp > te - (k + 1) * Te) & (tp <= te - k * Te)].mean()), 2) for k in range(5)]
print(json.dumps(out))
