# 19.11 (Julek 11:43: jak blisko MPC jest do wzoru w modelu na fali Godo): ten sam harness co "mpc_falt_bridge.py - W_A KI test",
# ale z zapisem z'' i pionowej predkosci wody w na placie -> M<z''w>, sufit, korelacja. Wynik: SUFIT_MODEL_REG.json. Rdzen 21.
import sys, json, math, os
import numpy as np, psutil
psutil.Process().cpu_affinity([21])
WA = sys.argv[1] if len(sys.argv) > 1 else "1.5"
sys.argv = ["mpc_falt_bridge.py", "-", WA, "0.2", "import"]
import mpc_falt_bridge as FB
MK, FP = FB.MK, FB.MK.FP
Z = MK.Z; p = Z.FaltinsenPlant(wave_amp=0.727, wave_phase=0.4, **Z.VB); br = FB.Bridge()
cl_eq = (FP.MASS * MK.G - MK.BUOY) / p.q; trim = FP.TH_REF_DEG + float(np.degrees((cl_eq - FP.CL_REF) / (p.slope * p.dcl)))
p.reset(theta_deg=trim); rows = []; seq = 0; T_REL = 1.9368
for k in range(int(15 * p.Te / FB.DT)):
    free = p.t >= T_REL - 0.5e-3
    cmd = br.step(seq, p.t, p.z, p.v, math.degrees(p.th), math.degrees(p.w_servo), p.eta_LE(), free); seq += 1
    p.cmd = math.radians(cmd); Ls = Pd = 0.0
    for _ in range(p.tick):
        r = p.step(free_heave=free); Ls += r["L"]; Pd += r["P_drag_W_strip"]
    g = p.gust(p.F.xc, p.t); w = float(np.mean(g[1])); u = float(np.mean(g[0]))
    rows.append((p.t, Pd / p.tick, (Ls / p.tick + MK.BUOY) / FP.MASS - MK.G, p.z, w, u))
a = np.array(rows); b = a[a[:, 0] > a[-1, 0] - 8 * p.Te]
acc = b[:, 2] - b[:, 2].mean(); w = b[:, 4] - b[:, 4].mean(); u = b[:, 5] - b[:, 5].mean(); M = FP.MASS; ax = -(b[:, 1] - b[:, 1].mean()) / MK.U / (Z.MASS100 * 0.02)
out = dict(W_A=WA, P_W=float(b[:, 1].mean()), zysk_W=float(57.03 - b[:, 1].mean()), dP_pct=float(100 * (b[:, 1].mean() / 57.03 - 1)), acc_rms=float(acc.std()),
           w_rms=float(w.std()), u_rms=float(u.std()), kor_acc_w=float(np.corrcoef(acc, w)[0, 1]), kor_acc_u=float(np.corrcoef(acc, u)[0, 1]),
           ciag_W=float(M * np.mean(acc * w)), sufit_W=float(M * acc.std() * w.std()), z_sr=float(b[:, 3].mean()), M=float(M), ax_rms=float(ax.std()), kor_acc_ax=float(np.corrcoef(acc, ax)[0, 1]), wyp_rms=float(np.sqrt(acc.var() + ax.var())))
H = os.path.dirname(os.path.abspath(__file__)); f = os.path.join(H, "SUFIT_MODEL_REG.json")
R = json.load(open(f)) if os.path.exists(f) else {}
R[WA] = out; json.dump(R, open(f, "w"), indent=1); print(json.dumps(out))

