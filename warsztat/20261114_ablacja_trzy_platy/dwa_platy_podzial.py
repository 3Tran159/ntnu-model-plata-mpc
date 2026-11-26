"""dwa_platy_podzial.py - koordynator 15.11 (spor z Julkiem 19:14): dwa identyczne platy w tym samym miejscu i tym samym podmuchu, kadlub nieruchomy (idealny komfort).
Warianty: 'oba_sztywne' (zaden nie zmienia kata - suma sily skacze), 'rowno' (oba K0 100 %: kazdy kasuje swoj podmuch), 'julek' (A sztywny bierze podmuch, B zbija kat o tyle, zeby suma byla stala).
Model Faltinsena B (zaw90.FaltinsenPlant), fala regularna H 1,5 m T 5 s, 100 %, okno ostatnie 3 okresy z 30 s. Uwaga: B ma staly CD0 (bez biegunowej profilu) - test sprawdza TYLKO bilans pochylenia sily / ciagu.
Uzycie: python dwa_platy_podzial.py <wariant>"""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(Path(r"T:\NTNU_GODO_CONTROL_20261109\60_PANELE_I_WYNIKI") / "ZAWIESZENIE"))
import zaw90 as Z
FP, U, G, BUOY = Z.FP, Z.U, Z.G, Z.BUOY
var = sys.argv[1]; LIM = float(sys.argv[2]) if len(sys.argv) > 2 else 7.5; TE = 1.9368; T = 30.0
FP.MASS = Z.MASS100
A = Z.FaltinsenPlant(wave_amp=0.733, slope=1.0, wave_u=True); B = Z.FaltinsenPlant(wave_amp=0.733, slope=1.0, wave_u=True)
trim = FP.TH_REF_DEG
for P in (A, B): P.reset(theta_deg=trim); P.cmd = np.radians(trim)
L0 = FP.MASS * G - BUOY; kq = A.q * A.slope * A.dcl          # dL/dtheta [N/m na rad]
n = int(T / A.dt); rec = []; LA = L0; LB = L0
for i in range(n):
    if i % A.tick == 0:
        wB = float(np.mean(B.gust(B.F.xc, B.t)[1])); wA = float(np.mean(A.gust(A.F.xc, A.t)[1]))
        if var == "oba_sztywne": cA, cB = trim, trim
        elif var.startswith("rowno"): cA, cB = trim - np.degrees(wA / U), trim - np.degrees(wB / U)
        elif var == "julek3":
            if wA < 0: cB = trim; cA = trim - np.degrees(wA / U) - np.degrees((LB - L0) / kq)
            else: cA, cB = trim - np.degrees(wA / U), trim - np.degrees(wB / U)
        elif var == "julek2":
            if wA > 0: cA = trim; cB = trim - np.degrees(wB / U) - np.degrees((LA - L0) / kq)
            else: cA, cB = trim - np.degrees(wA / U), trim - np.degrees(wB / U)
        else: cA = trim; cB = trim - np.degrees(wB / U) - np.degrees((LA - L0) / kq)
        A.cmd, B.cmd = np.radians(np.clip(cA, -LIM, LIM)), np.radians(np.clip(cB, -LIM, LIM))
    ra = A.step(free_heave=False, th_max_deg=LIM, rate_max_deg_s=90.0 * LIM / 7.5); rb = B.step(free_heave=False, th_max_deg=LIM, rate_max_deg_s=90.0 * LIM / 7.5); LA = ra["L"]; LB = rb["L"]
    if i % 10 == 9: rec.append((ra["t"], ra["L"], rb["L"], ra["P_drag_W_strip"], rb["P_drag_W_strip"], ra["theta_deg"], rb["theta_deg"], wB))
r = np.array(rec); w = r[:, 0] > T - 3 * TE; Pcalm = 61.09
out = dict(wariant=var, P_A=round(r[w, 3].mean(), 2), P_B=round(r[w, 4].mean(), 2), P_suma=round(r[w, 3].mean() + r[w, 4].mean(), 2),
           dP_suma_pct=round(100 * ((r[w, 3].mean() + r[w, 4].mean()) / (2 * Pcalm) - 1), 2),
           L_suma_std_pct=round(100 * (r[w, 1] + r[w, 2]).std() / (2 * L0), 2), L_A_amp_pct=round(100 * (r[w, 1].max() - r[w, 1].min()) / 2 / L0, 1),
           L_B_amp_pct=round(100 * (r[w, 2].max() - r[w, 2].min()) / 2 / L0, 1), th_A=[round(r[w, 5].min(), 2), round(r[w, 5].max(), 2)], th_B=[round(r[w, 6].min(), 2), round(r[w, 6].max(), 2)])
(HERE / f"DWA_PLATY_{var}_lim{LIM:g}.json").write_text(json.dumps(out), encoding="utf-8"); print(json.dumps(out))




m = r[:, 0] > T - TE; s = r[m][::2]
(HERE / f'DWA_PLATY_TS_{var}.json').write_text(json.dumps(dict(t=np.round(s[:, 0] - s[0, 0], 3).tolist(), LA=np.round(s[:, 1] / L0, 4).tolist(), LB=np.round(s[:, 2] / L0, 4).tolist(), PA=np.round(s[:, 3], 2).tolist(), PB=np.round(s[:, 4], 2).tolist(), thA=np.round(s[:, 5], 3).tolist(), thB=np.round(s[:, 6], 3).tolist(), w=np.round(s[:, 7], 4).tolist())), encoding='utf-8')


