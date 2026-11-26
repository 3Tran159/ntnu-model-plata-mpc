"""fit_polar.py - czego brakuje w oporze modelu B wzgledem URANS, wyznaczone z URANS z PODZIALEM danych:
  identyfikacja: OVS_PID_BASE2, OVS_PID_PRBS1, OVS_PID_SINE_A2;  sprawdzenie: OVS_PID1/2/3_GODO, OVS_POL_TD3_GODO (nieuzyte do dopasowania).
Metoda: ruch plata z URANS zadany w modelu B (2 pi, z pozioma predkoscia fali, sam CD0); reszta oporu dFx(t) = Fx_URANS - Fx_model [N/m],
  okno: ostatnie 4 pelne okresy spotkania. Trzy postaci poprawki (MNK po czasie na przebiegach identyfikacyjnych):
    K     : dCD = K (CL - CL_REF)^2                  (biegunowa)
    C     : dCD = C                                  (staly dodatek w fali)
    C+K   : dCD = C + K (CL - CL_REF)^2
Wynik: POLAR_FIT.json - wspolczynniki, srednia reszta kazdego przebiegu, blad sredniej mocy oporu po poprawce (identyfikacja i sprawdzenie)."""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import validate_urans as V
from faltinsen_plant import FaltinsenPlant, CL_REF, U, SPAN
ID = ["OVS_PID_BASE2", "OVS_PID_PRBS1", "OVS_PID_SINE_A2"]; VAL = V.RUNS
D = {}
for run in ID + VAL:
    d = V.load(run); P0 = FaltinsenPlant(); a, beta, _ = V.wave_fit(d, P0.ome, P0.Te)
    P = FaltinsenPlant(wave_amp=a, wave_phase=beta); P.reset(theta_deg=d["th"][0], z=d["z"][0], v=d["v"][0], t=d["t"][0] - P.dt)
    n = len(d["t"]); cl = np.zeros(n); fx = np.zeros(n)
    for i in range(n):
        P.th = np.radians(d["th"][i]); P.w_servo = np.radians(d["thd"][i]); P.v = d["v"][i]; P.z = d["z"][i]; r = V.kin_step(P); cl[i] = r["CL"]; fx[i] = r["Fx"]
    w = d["t"] > d["t"][-1] - 4 * P.Te
    D[run] = dict(y=(d["Fx"] - fx)[w], one=np.full(w.sum(), P.q), dcl2=P.q * (cl[w] - CL_REF) ** 2, fxu=d["Fx"][w], fxm=fx[w], var_cl=float(np.var(cl[w])), q=P.q)
def fit(cols):
    A = np.vstack([np.c_[tuple(D[r][c] for c in cols)] for r in ID]); y = np.concatenate([D[r]["y"] for r in ID]); return np.linalg.lstsq(A, y, rcond=None)[0]
out = dict(runs={r: dict(rola="identyfikacja" if r in ID else "sprawdzenie", srednia_reszta_oporu_N_m=float(D[r]["y"].mean()), jako_dCD=float(D[r]["y"].mean() / D[r]["q"]),
                         wariancja_CL_model=D[r]["var_cl"], P_URANS_W=float(U * SPAN * D[r]["fxu"].mean()), P_model_B_W=float(U * SPAN * D[r]["fxm"].mean())) for r in ID + VAL}, fits={})
for name, cols in (("K", ["dcl2"]), ("C", ["one"]), ("C+K", ["one", "dcl2"])):
    c = fit(cols); e = {}
    for r in ID + VAL:
        pred = sum(ci * D[r][k] for ci, k in zip(c, cols)); e[r] = float(100 * ((D[r]["fxm"] + pred).mean() / D[r]["fxu"].mean() - 1))
    out["fits"][name] = dict(coef=dict(zip(cols, map(float, c))), blad_sredniej_mocy_pct=e)
    print(name, np.round(c, 5), {r[4:]: round(v, 1) for r, v in e.items()}, flush=True)
(HERE / "POLAR_FIT.json").write_text(json.dumps(out, indent=1))
