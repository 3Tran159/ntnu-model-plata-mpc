"""nmpc_reg.py - 19.11 13:20 (Julek: "co jakbysmy Faltinsena liczyli za kazdym krokiem a nie uproszczona wersje MPC").
MPC z PELNYM modelem Faltinsena B w petli przewidywania (zamiast liniowego ARX + regresji oporu): koszt planu liczony przez przejazd kopii
modelu przez caly horyzont (1,95 s), gradient roznicami skonczonymi (rownolegle, rdzenie 18-22), L-BFGS-B, plan = 13 blokow po 0,15 s,
przeliczany co 0,05 s. Ten sam koszt co mpc_komfort.py: opor + wspornik + ACT_K*rate^2/U + W_A*acc^2 + W_Z*z^2 + kary miekkie.
Fala regularna Godo (A 0,727 m), 90 %, fala znana idealnie (model w petli ja zna). Wynik: NMPC_REG.json, log: nmpc_reg.log.
Uzycie: python nmpc_reg.py [W_A=1.5] [liczba okresow=10]"""
import os, sys, time, json, pickle, math
WA = sys.argv[1] if len(sys.argv) > 1 else "1.5"; NPER = int(sys.argv[2]) if len(sys.argv) > 2 else 10
os.environ["MPC_W_A"] = WA
import numpy as np, psutil
from scipy.optimize import minimize
import mpc_komfort as MK
Z, FP, U, G, BUOY, MASS, C = MK.Z, MK.FP, MK.U, MK.G, MK.BUOY, MK.MASS, MK.C
H, BL, NB, RE, EPS = 195, 15, 13, 5, 0.002
HERE = os.path.dirname(os.path.abspath(__file__))


def init(cores, lock):
    with lock:
        c = cores.pop(0) if len(cores) else 18
    psutil.Process().cpu_affinity([c])


def rollout(a):
    st, x, ulast = a; q = pickle.loads(st); J = 0.0
    for k in range(H):
        q.cmd = float(x[min(k // BL, NB - 1)]); Ls = Pd = 0.0
        for _ in range(q.tick):
            r = q.step(free_heave=True); Ls += r["L"]; Pd += r["P_drag_W_strip"]
        acc = (Ls / q.tick + BUOY) / MASS - G; z = q.z; sub = r["sub_true"]
        J += Pd / q.tick / U - MK.STRUT_K * z + MK.ACT_K / U * q.w_servo ** 2 + MK.W_A * acc * acc + MK.W_Z * z * z \
            + MK.W_S * (max(0.0, 2 * C - sub) ** 2 + max(0.0, z - 0.5) ** 2 + max(0.0, -0.5 - z) ** 2)
        if not math.isfinite(J): return 1e12
    d = np.diff(np.r_[ulast, x]); return J + MK.W_DU * float(d @ d)


if __name__ == "__main__":
    import multiprocessing as mp
    psutil.Process().cpu_affinity([23])
    mgr = mp.Manager(); cores = mgr.list([18, 19, 20, 21, 22]); lock = mgr.Lock(); pool = mp.Pool(5, initializer=init, initargs=(cores, lock))
    def log(m):
        open(os.path.join(HERE, "nmpc_reg.log"), "a").write(time.strftime("%H:%M:%S ") + m + "\n")
    p = Z.FaltinsenPlant(wave_amp=0.727, wave_phase=0.4, **Z.VB)
    cl_eq = (FP.MASS * G - BUOY) / p.q; trim = FP.TH_REF_DEG + float(np.degrees((cl_eq - FP.CL_REF) / (p.slope * p.dcl)))
    p.reset(theta_deg=trim); u = math.radians(trim); x = np.full(NB, u); rows = []; T_REL = 1.9368; nre = 0; t00 = time.time()
    log(f"start W_A {WA}, {NPER} okresow, trim {trim:.3f} deg, Te {p.Te:.4f}")
    for k in range(int(NPER * p.Te / MK.DT)):
        free = p.t >= T_REL - 0.5e-3
        if free and k % RE == 0:
            st = pickle.dumps(p, -1); ul = u
            def fun(xx):
                X = [xx] + [xx + EPS * np.eye(NB)[i] for i in range(NB)]
                v = pool.map(rollout, [(st, xi, ul) for xi in X]); return v[0], (np.array(v[1:]) - v[0]) / EPS
            res = minimize(fun, x, jac=True, method="L-BFGS-B", bounds=[(-MK.THM, MK.THM)] * NB, options=dict(maxiter=3, maxfun=5))
            x = res.x; u = float(x[0]); nre += 1
            if nre % 20 == 1: log(f"t {p.t:.2f} z {p.z:+.3f} cmd {math.degrees(u):+.2f} J {res.fun:.1f} nfev {res.nfev} | {time.time() - t00:.0f} s")
        p.cmd = float(np.clip(u, -MK.THM, MK.THM)); Ls = Pd = 0.0
        for _ in range(p.tick):
            r = p.step(free_heave=free); Ls += r["L"]; Pd += r["P_drag_W_strip"]
        g = p.gust(p.F.xc, p.t)
        rows.append((p.t, Pd / p.tick, (Ls / p.tick + BUOY) / MASS - G, p.z, float(np.mean(g[1])), float(np.mean(g[0])), math.degrees(p.th), r["sub_true"]))
        if len(rows) % 200 == 0: np.save(os.path.join(HERE, f"nmpc_reg_wa{WA}.npy"), np.array(rows))
    a = np.array(rows); np.save(os.path.join(HERE, f"nmpc_reg_wa{WA}.npy"), a); b = a[a[:, 0] > a[-1, 0] - 6 * p.Te]
    acc = b[:, 2] - b[:, 2].mean(); w = b[:, 4] - b[:, 4].mean(); uu = b[:, 5] - b[:, 5].mean(); M = MASS * 0.02
    out = dict(W_A=WA, okresy=NPER, P_W=float(b[:, 1].mean()), zysk_W=float(57.03 - b[:, 1].mean()), dP_pct=float(100 * (b[:, 1].mean() / 57.03 - 1)), acc_rms=float(acc.std()),
               w_rms=float(w.std()), kor_acc_w=float(np.corrcoef(acc, w)[0, 1]), kor_acc_u=float(np.corrcoef(acc, uu)[0, 1]), ciag_W=float(M * np.mean(acc * w)),
               sufit_W=float(M * acc.std() * w.std()), z_sr=float(b[:, 3].mean()), z_min=float(b[:, 3].min()), z_max=float(b[:, 3].max()), sub_min=float(b[:, 7].min()),
               th_min=float(b[:, 6].min()), th_max=float(b[:, 6].max()), czas_s=time.time() - t00)
    f = os.path.join(HERE, "NMPC_REG.json"); R = json.load(open(f)) if os.path.exists(f) else {}
    R[WA] = out; json.dump(R, open(f, "w"), indent=1); log("KONIEC " + json.dumps(out)); pool.terminate()
