"""trzy_platy.py - koordynator 16.11: dzwignia +1:-2:+1. Trzy platy na osobnych wspornikach, rozstaw L, kadlub nieruchomy (liczymy reszty sily i momentu).
Kazdy plat: K0 100 % (kasuje swoj podmuch) + G * c_i * (modalny podmuch W_m = sum c_j w_j / sum c_j^2), c = (+1, -2, +1).
Model Faltinsena B, fala regularna H 1,5 m T 5 s, 100 % na kazdy plat, 30 s, ostatnie 3 okresy. Bez wplywu platow na siebie (wersja 1).
Uzycie: python trzy_platy.py L G"""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(Path(r"T:\NTNU_GODO_CONTROL_20261109\60_PANELE_I_WYNIKI") / "ZAWIESZENIE"))
import zaw90 as Z
FP, U, G_, BUOY = Z.FP, Z.U, Z.G, Z.BUOY
Lsp, Gm = float(sys.argv[1]), float(sys.argv[2]); TE = 1.9368; T = 30.0; k = (2 * np.pi / 5.0) ** 2 / 9.81
FP.MASS = Z.MASS100; xs = np.array([-Lsp, 0.0, Lsp]); c = np.array([1.0, -2.0, 1.0])
P = [Z.FaltinsenPlant(wave_amp=0.733, wave_phase=float(-k * x), slope=1.0, wave_u=True) for x in xs]
trim = FP.TH_REF_DEG
for p in P: p.reset(theta_deg=trim); p.cmd = np.radians(trim)
L0 = FP.MASS * G_ - BUOY
n = int(T / P[0].dt); rec = []
for i in range(n):
    if i % P[0].tick == 0:
        w = np.array([float(np.mean(p.gust(p.F.xc, p.t)[1])) for p in P]); Wm = float(c @ w) / float(c @ c)
        for j, p in enumerate(P):
            p.cmd = np.radians(float(np.clip(trim - np.degrees(w[j] / U) + Gm * c[j] * np.degrees(Wm / U), -7.5, 7.5)))
    r = [p.step(free_heave=False) for p in P]
    if i % 10 == 9: rec.append([r[0]["t"]] + [x["L"] for x in r] + [x["P_drag_W_strip"] for x in r] + [x["theta_deg"] for x in r])
a = np.array(rec); m = a[:, 0] > T - 3 * TE; Ls = a[m, 1:4]; Ps = a[m, 4:7]; th = a[m, 7:10]; Pcalm = 61.09
F = Ls.sum(1) - 3 * L0; M = (Ls - L0) @ xs
out = dict(L=Lsp, G=Gm, dP_suma_pct=round(100 * (Ps.sum(1).mean() / (3 * Pcalm) - 1), 2), dP_plat=[round(100 * (Ps[:, j].mean() / Pcalm - 1), 1) for j in range(3)],
           F_std_pct=round(100 * F.std() / (3 * L0), 2), M_std_N_m=round(float(M.std()), 1), M_std_pct_L0L=round(100 * M.std() / (L0 * max(Lsp, 1e-9)), 2),
           dL_amp_pct=[round(100 * (Ls[:, j].max() - Ls[:, j].min()) / 2 / L0, 1) for j in range(3)], th_range=[[round(th[:, j].min(), 2), round(th[:, j].max(), 2)] for j in range(3)])
(HERE / f"TRZY_PLATY_L{Lsp:g}_G{Gm:g}.json").write_text(json.dumps(out), encoding="utf-8"); print(json.dumps(out))
