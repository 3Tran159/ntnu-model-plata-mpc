# 19.11 (Julek 16:10/16:12): MPC z kara za WYPADKOWA przyspieszen: W_A * (z''^2 + x''^2) zamiast W_A * z''^2.
# x'' = -(D - srednia D w horyzoncie) / M_calej_lodzi_na_pasek; D z modelu oporu MPC (regresja kwadratowa) -> koszt 4. stopnia, liczony w fun().
# Reszta bez zmian (mpc_komfort.MPC, mpc_falt_bridge.Bridge). Uzycie:
#   python mpc_wyp.py reg W_A RDZEN [W_AX]        fala Godo, harness jak sufit_model_reg.py -> WYPADKOWA_MPC.json["GODO"][W_A]
#   python mpc_wyp.py sea S1 SEED W_A RDZEN [T]   widmo, mpc_komfort.run -> WYPADKOWA_MPC.json["S1"][W_A][SEED]
import sys, json, math, os, time
import numpy as np, psutil
from scipy.optimize import minimize
MODE = sys.argv[1]
if MODE == "reg": WA, CORE = sys.argv[2], int(sys.argv[3]); WAX = float(sys.argv[4]) if len(sys.argv) > 4 else float(WA)
else: SEA, SEED, WA, CORE = sys.argv[2], int(sys.argv[3]), sys.argv[4], int(sys.argv[5]); TSIM = float(sys.argv[6]) if len(sys.argv) > 6 else 300.0; WAX = float(WA)
me = psutil.Process(); me.cpu_affinity([CORE]); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
sys.argv = ["mpc_falt_bridge.py", "-", WA, "0.2", "import"]
import mpc_falt_bridge as FB
MK, FP = FB.MK, FB.MK.FP; Z = MK.Z; MTOT = Z.MASS100 * 0.02; U = MK.U
H0 = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(H0, "WYPADKOWA_MPC.json")


def solve(s, xs, th_h, v_h, wf_h, z, v, wfut, etafut, u_last):
    f0, z0 = s.sim(xs, th_h, v_h, wf_h, z, v, np.zeros(s.H), wfut)
    M0, p = s.m["M"], s.m["p"]; M = M0.copy(); Fm = s.Fu.transpose(1, 0, 2); M[1, 1] += MK.ACT_K / U; M[5, 5] += MK.W_A / MK.MASS ** 2
    g = np.einsum("kjf,f->j", Fm, p) + 2 * np.einsum("kjf,fg,kg->j", Fm, M, f0) + 2 * MK.W_Z * s.Zu @ z0 - MK.STRUT_K * s.Zu.sum(1)
    Hs = 2 * np.einsum("kjf,fg,kig->ji", Fm, M, Fm) + 2 * MK.W_Z * s.Zu @ s.Zu.T
    Dm = np.eye(s.nb) - np.eye(s.nb, k=-1); Hs += 2 * MK.W_DU * Dm.T @ Dm
    e0 = np.zeros(s.nb); e0[0] = u_last; g += -2 * MK.W_DU * Dm.T @ e0
    w, V = np.linalg.eigh(0.5 * (Hs + Hs.T)); w = np.maximum(w, 1e-3 * w.max()); Hs = (V * w) @ V.T
    zmax = np.minimum(etafut + MK.DEPTH - 2 * MK.C, 0.5); zmin = -0.5; ZT = s.Zu.T; kx = WAX / MTOT ** 2

    def fun(x):
        zz = z0 + ZT @ x; e1 = np.maximum(0, zz - zmax); e2 = np.maximum(0, zmin - zz)
        f = f0 + np.einsum("kjf,j->kf", Fm, x); fM = f @ M0; D = f @ p + np.einsum("kf,kf->k", fM, f); dD = D - D.mean()
        J = 0.5 * x @ Hs @ x + g @ x + MK.W_S * (e1 @ e1 + e2 @ e2) + kx * dD @ dD
        gr = Hs @ x + g + 2 * MK.W_S * ZT.T @ (e1 - e2) + 2 * kx * np.einsum("k,kjf,kf->j", dD, Fm, p + 2 * fM)
        return J, gr
    x0 = np.full(s.nb, u_last) if s.Uprev is None else np.r_[s.Uprev[1:], s.Uprev[-1]]
    res = minimize(fun, x0, jac=True, method="L-BFGS-B", bounds=[(-MK.THM, MK.THM)] * s.nb)
    s.Uprev = res.x; return res.x[0]


MK.MPC.solve = solve


def zapisz(k1, k2, out, k3=None):
    for _ in range(50):
        try:
            R = json.load(open(OUT)) if os.path.exists(OUT) else {}
            if k3 is None: R.setdefault(k1, {})[k2] = out
            else: R.setdefault(k1, {}).setdefault(k2, {})[k3] = out
            tmp = OUT + ".%d.tmp" % os.getpid(); json.dump(R, open(tmp, "w"), indent=1); os.replace(tmp, OUT); return
        except Exception: time.sleep(0.2)


t00 = time.time()
if MODE == "reg":
    p = Z.FaltinsenPlant(wave_amp=0.727, wave_phase=0.4, **Z.VB); br = FB.Bridge()
    cl_eq = (FP.MASS * MK.G - MK.BUOY) / p.q; trim = FP.TH_REF_DEG + float(np.degrees((cl_eq - FP.CL_REF) / (p.slope * p.dcl)))
    p.reset(theta_deg=trim); rows = []; seq = 0; T_REL = 1.9368
    for k in range(int(15 * p.Te / FB.DT)):
        free = p.t >= T_REL - 0.5e-3
        cmd = br.step(seq, p.t, p.z, p.v, math.degrees(p.th), math.degrees(p.w_servo), p.eta_LE(), free); seq += 1
        p.cmd = math.radians(cmd); Ls = Pd = 0.0
        for _ in range(p.tick):
            r = p.step(free_heave=free); Ls += r["L"]; Pd += r["P_drag_W_strip"]
        g = p.gust(p.F.xc, p.t); rows.append((p.t, Pd / p.tick, (Ls / p.tick + MK.BUOY) / FP.MASS - MK.G, p.z, float(np.mean(g[1]))))
    a = np.array(rows); b = a[a[:, 0] > a[-1, 0] - 8 * p.Te]
    acc = b[:, 2] - b[:, 2].mean(); w = b[:, 4] - b[:, 4].mean(); ax = -(b[:, 1] - b[:, 1].mean()) / U / MTOT
    out = dict(W_A=WA, W_AX=WAX, zysk_W=float(57.03 - b[:, 1].mean()), zysk_pct=float(100 * (1 - b[:, 1].mean() / 57.03)), acc_rms=float(acc.std()), ax_rms=float(ax.std()),
               wyp_rms=float(np.sqrt(acc.var() + ax.var())), kor_acc_ax=float(np.corrcoef(acc, ax)[0, 1]), kor_acc_w=float(np.corrcoef(acc, w)[0, 1]),
               ciag_W=float(FP.MASS * np.mean(acc * w)), z_sr=float(b[:, 3].mean()), czas_s=round(time.time() - t00))
    zapisz("GODO", "%s_%g" % (WA, WAX), out); print(json.dumps(out), flush=True)
else:
    from pathlib import Path
    MK.VIZ = Path(H0) / ("viz_wyp_wa%s" % WA); m = MK.model(MK.plant("S1", 0)[1]); r = MK.run(SEA, SEED, m, T=TSIM, viz=True)
    d = json.load(open(MK.VIZ / f"{SEA}__s{SEED}.json")); c = {k: i for i, k in enumerate(d["cols"])}; A = np.array(d["data"]); P = A[:, c["P_foil_W"]]; acc = A[:, c["acc"]]
    ax = -(P - P.mean()) / U / MTOT
    out = dict(W_A=WA, T=TSIM, zysk_W=float(57.056 - P.mean()), zysk_pct=float(100 * (1 - P.mean() / 57.056)), acc_rms=float(acc.std()), ax_rms=float(ax.std()),
               wyp_rms=float(np.sqrt(acc.var() + ax.var())), kor_acc_ax=float(np.corrcoef(acc - acc.mean(), ax)[0, 1]), z_min=r["z_min"], z_max=r["z_max"], sub_min=r["sub_min"], czas_s=round(time.time() - t00))
    zapisz(SEA, WA, out, str(SEED)); print(json.dumps(out), flush=True)
