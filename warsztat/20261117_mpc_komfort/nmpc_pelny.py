"""nmpc_pelny.py - 19.11 15:05 (Julek 14:59: "mielismy odtworzyc dokladnie to co MPC, a nie liczyc po jego uproszczeniach, tylko modelem za kazdym razem").
MPC o TEJ SAMEJ budowie co mpc_komfort.py: horyzont 195 krokow po 10 ms, plan = 39 blokow po 0,05 s, przeliczany co 0,05 s, ten sam koszt
(opor + wspornik + ACT_K*rate^2/U + W_A*acc^2 + W_Z*z^2 + W_DU*zmiany planu + kary miekkie na zanurzenie 2c i |z| <= 0,5 m), kat w +-7,5 deg.
Roznica: ZAMIAST liniowego ARX i regresji oporu - PELNY model Faltinsena B. Dla kazdego planu: przejazd bazowy + 39 przejazdow zaburzonych
(roznice skonczone) daja dokladne czulosci przyspieszenia, wysokosci, predkosci kata i oporu na kazdy blok; z nich krok Gaussa-Newtona
(rozwiazywany L-BFGS-B z ograniczeniami jak w MPC); nowy plan sprawdzany przejazdem pelnego modelu (gorszy od starego -> pol kroku -> stary plan).
Fala regularna Godo (A 0,727 m), 90 %, model zna fale idealnie. Rdzenie 18-22 (obliczenia) + 23. Wynik: NMPC_PELNY.json, log: nmpc_pelny.log.
Uzycie: python nmpc_pelny.py [W_A=1.5] [okresy=9]"""
import os, sys, time, json, pickle, math
WA = sys.argv[1] if len(sys.argv) > 1 else "1.5"; NPER = int(sys.argv[2]) if len(sys.argv) > 2 else 9
os.environ["MPC_W_A"] = WA
import numpy as np, psutil
from scipy.optimize import minimize
import mpc_komfort as MK
Z, FP, U, G, BUOY, MASS, C = MK.Z, MK.FP, MK.U, MK.G, MK.BUOY, MK.MASS, MK.C
H, BL, NB, EPS, MU = 195, 5, 39, 0.002, 20.0
HERE = os.path.dirname(os.path.abspath(__file__)); AK = MK.ACT_K / U


def init(cores, lock):
    with lock:
        c = cores.pop(0) if len(cores) else 18
    psutil.Process().cpu_affinity([c]); psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)


def rollout(a):
    st, x = a; q = pickle.loads(st); T = np.zeros((5, H))
    for k in range(H):
        q.cmd = float(x[min(k // BL, NB - 1)]); Ls = Pd = 0.0
        for _ in range(q.tick):
            r = q.step(free_heave=True); Ls += r["L"]; Pd += r["P_drag_W_strip"]
        T[:, k] = (Pd / q.tick / U, (Ls / q.tick + BUOY) / MASS - G, q.z, q.w_servo, r["sub_true"])
    return T


def cost(T, x, ul):
    D, a, z, td, sub = T
    if not np.all(np.isfinite(T)): return 1e12
    e1, e2, e3 = np.maximum(0, 2 * C - sub), np.maximum(0, z - 0.5), np.maximum(0, -0.5 - z); d = np.diff(np.r_[ul, x])
    return float(D.sum() - MK.STRUT_K * z.sum() + AK * td @ td + MK.W_A * a @ a + MK.W_Z * z @ z + MK.W_S * (e1 @ e1 + e2 @ e2 + e3 @ e3) + MK.W_DU * d @ d)


def gn_step(T0, TJ, x0, ul):
    D0, a0, z0, td0, s0 = T0; J = (TJ - T0[None]) / EPS                      # J[i, wielkosc, k]
    gD, Ja, Jz, Jt = J[:, 0].sum(1), J[:, 1], J[:, 2], J[:, 3]

    def fun(x):
        dx = x - x0; a = a0 + Ja.T @ dx; z = z0 + Jz.T @ dx; td = td0 + Jt.T @ dx
        e1, e2, e3 = np.maximum(0, 2 * C - s0 + Jz.T @ dx), np.maximum(0, z - 0.5), np.maximum(0, -0.5 - z)
        d = np.diff(np.r_[ul, x]); gd = 2 * MK.W_DU * (d - np.r_[d[1:], 0.0])
        v = gD @ dx - MK.STRUT_K * (Jz.T @ dx).sum() + AK * td @ td + MK.W_A * a @ a + MK.W_Z * z @ z + MK.W_S * (e1 @ e1 + e2 @ e2 + e3 @ e3) + MK.W_DU * d @ d + MU * dx @ dx
        g = gD - MK.STRUT_K * Jz.sum(1) + 2 * AK * Jt @ td + 2 * MK.W_A * Ja @ a + 2 * MK.W_Z * Jz @ z + 2 * MK.W_S * (Jz @ e1 + Jz @ e2 - Jz @ e3) + gd + 2 * MU * dx
        return v, g
    return minimize(fun, x0, jac=True, method="L-BFGS-B", bounds=[(-MK.THM, MK.THM)] * NB).x


if __name__ == "__main__":
    import multiprocessing as mp
    psutil.Process().cpu_affinity([22]); psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    mgr = mp.Manager(); cores = mgr.list([18, 19, 20, 21]); lock = mgr.Lock(); pool = mp.Pool(4, initializer=init, initargs=(cores, lock))
    def log(m):
        open(os.path.join(HERE, "nmpc_pelny.log"), "a").write(time.strftime("%H:%M:%S ") + m + "\n")
    p = Z.FaltinsenPlant(wave_amp=0.727, wave_phase=0.4, **Z.VB)
    cl_eq = (FP.MASS * G - BUOY) / p.q; trim = FP.TH_REF_DEG + float(np.degrees((cl_eq - FP.CL_REF) / (p.slope * p.dcl)))
    p.reset(theta_deg=trim); u = math.radians(trim); x = np.full(NB, u); rows = []; T_REL = 1.9368; npl = 0; nrej = 0; t00 = time.time(); E = EPS * np.eye(NB)
    log(f"start W_A {WA}, {NPER} okresow, trim {trim:.3f} deg, plan {NB} blokow x {BL * 10} ms, horyzont {H} krokow")
    for k in range(int(NPER * p.Te / MK.DT)):
        free = p.t >= T_REL - 0.5e-3
        if free and k % BL == 0:
            st = pickle.dumps(p, -1); ul = u; x0 = np.r_[x[1:], x[-1]] if npl else x.copy()
            for it in range(3 if npl == 0 else 1):
                R = pool.map(rollout, [(st, x0)] + [(st, np.clip(x0 + E[i], -MK.THM - EPS, MK.THM + EPS)) for i in range(NB)])
                T0, TJ = R[0], np.array(R[1:]); J0 = cost(T0, x0, ul); xn = gn_step(T0, TJ, x0, ul)
                c1, c2 = pool.map(rollout, [(st, xn), (st, 0.5 * (xn + x0))]); J1, J2 = cost(c1, xn, ul), cost(c2, 0.5 * (xn + x0), ul)
                if J1 <= J0 and J1 <= J2: x0 = xn; Jb = J1
                elif J2 < J0: x0 = 0.5 * (xn + x0); Jb = J2
                else: nrej += 1; Jb = J0
            x = x0; u = float(x[0]); npl += 1
            if npl % 20 == 1: log(f"t {p.t:.2f} z {p.z:+.3f} cmd {math.degrees(u):+.2f} J0 {J0:.1f} -> {Jb:.1f} odrzucone {nrej}/{npl} | {time.time() - t00:.0f} s")
        p.cmd = float(np.clip(u, -MK.THM, MK.THM)); Ls = Pd = 0.0
        for _ in range(p.tick):
            r = p.step(free_heave=free); Ls += r["L"]; Pd += r["P_drag_W_strip"]
        g = p.gust(p.F.xc, p.t)
        rows.append((p.t, Pd / p.tick, (Ls / p.tick + BUOY) / MASS - G, p.z, float(np.mean(g[1])), float(np.mean(g[0])), math.degrees(p.th), r["sub_true"]))
        if len(rows) % 200 == 0: np.save(os.path.join(HERE, f"nmpc_pelny_wa{WA}.npy"), np.array(rows))
    a = np.array(rows); np.save(os.path.join(HERE, f"nmpc_pelny_wa{WA}.npy"), a); b = a[a[:, 0] > a[-1, 0] - 5 * p.Te]
    acc = b[:, 2] - b[:, 2].mean(); w = b[:, 4] - b[:, 4].mean(); uu = b[:, 5] - b[:, 5].mean(); M = MASS * 0.02
    ax = -(b[:, 1] - b[:, 1].mean()) / U / (Z.MASS100 * 0.02)
    out = dict(W_A=WA, okresy=NPER, plany=npl, odrzucone=nrej, P_W=float(b[:, 1].mean()), zysk_W=float(57.03 - b[:, 1].mean()), dP_pct=float(100 * (b[:, 1].mean() / 57.03 - 1)),
               acc_rms=float(acc.std()), w_rms=float(w.std()), kor_acc_w=float(np.corrcoef(acc, w)[0, 1]), kor_acc_u=float(np.corrcoef(acc, uu)[0, 1]),
               ciag_W=float(M * np.mean(acc * w)), sufit_W=float(M * acc.std() * w.std()), ax_rms=float(ax.std()), z_sr=float(b[:, 3].mean()), z_min=float(b[:, 3].min()),
               z_max=float(b[:, 3].max()), sub_min=float(b[:, 7].min()), th_min=float(b[:, 6].min()), th_max=float(b[:, 6].max()), czas_s=time.time() - t00, s_na_plan=(time.time() - t00) / max(npl, 1))
    f = os.path.join(HERE, "NMPC_PELNY.json"); R = json.load(open(f)) if os.path.exists(f) else {}
    R[WA] = out; json.dump(R, open(f, "w"), indent=1); log("KONIEC " + json.dumps(out)); pool.terminate()

