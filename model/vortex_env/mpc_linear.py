"""mpc_linear.py - krok 7c: MPC z liniowym modelem identyfikowanym z modelu wirowego, horyzont 1 okres spotkania.

1. Identyfikacja (takt 10 ms) na danych z Plant: PID2 + PRBS +-2 deg + sinusy o roznych fazach/amplitudach.
   serwo:   [th, thd]_{k+1} = As [th, thd]_k + Bs u_k                      (u = komenda kata, rad)
   sila:    L_k = l0 + sum_{i<NL} a_i th_{k-i} + sum_{i<NL} b_i v_{k-i} + c cos(phi_k) + s sin(phi_k)     (ARX, NL = 12)
   nurzanie: v_{k+1} = v_k + dt (L_k + B - m g)/m,  z_{k+1} = z_k + dt v_{k+1}
   opor:    D_k = kwadratowa regresja cech f = [th-th_ref, thd, v, cos phi, sin phi, L-l0]   (21 + 6 + 1 wspolczynnikow)
2. MPC: co 5 taktow (50 ms) minimalizacja  sum D_k + W_Z sum z_k^2 + W_DU sum (du)^2  na 194 taktach,
   komenda blokowana co 5 taktow (39 zmiennych), |theta| <= 7,5 deg (L-BFGS-B, hesjan z regularyzacja do dodatniej okreslonosci).
   Faza fali jest znana (rownowaznie: obserwowane eta i w jak u agenta RL; fala regularna).
3. Ocena w GodoVortexEnv (pelny nieliniowy model wirowy), 4 fazy, porownanie z PID2.
Wyniki: MPC_RESULT.json, MPC_RESULT.png.   Wszystko "w modelu wirowym".
"""
import json, sys, time
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
from vortex_plant import Plant, MASS, BUOY, SPAN, U
from uvm_step import G
from godo_vortex_env import GodoVortexEnv, pid_policy, rollout, TH_REF_DEG, TH_MAX_DEG

NL, H, BLK = 12, 194, 5
W_Z, W_DU = 400.0, 2000.0          # [N/m^2 na pasek], [N/rad^2]
W_S = 2e4                          # kara za naruszenie zanurzenia 2c / |z| 0,6 m [N/m^2]
from vortex_plant import C, DEPTH
THR = np.radians(TH_REF_DEG); THM = np.radians(TH_MAX_DEG)


def collect(seed=0, n_ep=6, t_ep=12.0):
    rng = np.random.default_rng(seed); rows = []
    for e in range(n_ep):
        p = Plant(wave_phase=rng.uniform(0, 2 * np.pi)); p.reset(theta_deg=TH_REF_DEG); p.cmd = THR
        for _ in range(1000): p.step(free_heave=False)
        integ, A, ph, prbs = 0.0, rng.uniform(0, 3.0), rng.uniform(0, 2 * np.pi), 0.0
        kp = rng.uniform(4, 14)
        for k in range(int(t_ep / 0.01)):
            if k % 15 == 0: prbs = rng.choice([-1, 1]) * rng.uniform(0, 2.0)
            e_ = -p.z; integ += e_ * 0.01
            cmd_deg = TH_REF_DEG + kp * e_ + 1.2 * integ + A * np.sin(p.ome * p.t + ph) + prbs
            p.cmd = np.radians(np.clip(cmd_deg, -TH_MAX_DEG, TH_MAX_DEG))
            th0, thd0, z0, v0, t0 = p.th, p.w_servo, p.z, p.v, p.t
            Ls, Ds = 0.0, 0.0
            for _ in range(p.tick):
                r = p.step(True); Ls += r["L"]; Ds += r["Fx"]
            phi = -p.ome * t0 + p.beta
            rows.append([th0, thd0, z0, v0, p.cmd, Ls / p.tick, Ds / p.tick * SPAN, np.cos(phi), np.sin(phi)])
            if abs(p.z) > 0.7: break
    return np.array(rows)


def identify(D):
    th, thd, z, v, u, L, Dr, c, s = D.T
    n = len(th)
    # serwo
    X = np.c_[th[:-1], thd[:-1], u[:-1]]; Y = np.c_[th[1:], thd[1:]]
    S = np.linalg.lstsq(X, Y, rcond=None)[0]; As, Bs = S[:2].T, S[2]
    # ARX sily
    rows, ys = [], []
    for k in range(NL, n):
        rows.append(np.r_[1.0, th[k - NL + 1:k + 1][::-1], v[k - NL + 1:k + 1][::-1], c[k], s[k]]); ys.append(L[k])
    R = np.array(rows); y = np.array(ys); arx = np.linalg.lstsq(R, y, rcond=None)[0]
    r2L = 1 - np.var(y - R @ arx) / np.var(y)
    # opor kwadratowy
    l0 = arx[0] + THR * arx[1:1 + NL].sum()
    F = np.c_[th - THR, thd, v, c, s, L - l0]
    iu = np.triu_indices(6)
    Q = np.array([np.r_[1.0, f, np.outer(f, f)[iu]] for f in F])
    dq = np.linalg.lstsq(Q, Dr, rcond=None)[0]
    r2D = 1 - np.var(Dr - Q @ dq) / np.var(Dr)
    M = np.zeros((6, 6)); M[iu] = dq[7:]; M = 0.5 * (M + M.T)
    return dict(As=As, Bs=Bs, arx=arx, l0=l0, d0=dq[0], p=dq[1:7], M=M, r2L=r2L, r2D=r2D)


class LinMPC:
    def __init__(s, mdl, dt=0.01, ome=None, amp=0.73):
        s.m, s.dt, s.ome, s.amp = mdl, dt, ome, amp
        s.nb = H // BLK + (H % BLK > 0)
        # odpowiedzi na jednostkowe bloki komendy (model liniowy, niezmienny w czasie): cechy f_k i z_k
        s.Fu = np.zeros((s.nb, H, 6)); s.Zu = np.zeros((s.nb, H))
        for j in range(s.nb):
            Uv = np.zeros(H); Uv[j * BLK:(j + 1) * BLK] = 1.0
            f, zz = s.sim(np.zeros(2), np.zeros(NL), np.zeros(NL), 0.0, 0.0, Uv, None, homog=True)
            s.Fu[j], s.Zu[j] = f, zz
        s.Uprev = None

    def sim(s, x_s, th_h, v_h, z, v, Uv, phis, homog=False):
        m = s.m; a = m["arx"]; th_h = th_h.copy(); v_h = v_h.copy(); xs = x_s.copy()
        f = np.zeros((H, 6)); zz = np.zeros(H)
        for k in range(H):
            th_h = np.r_[xs[0], th_h[:-1]]; v_h = np.r_[v, v_h[:-1]]
            cs = (0.0, 0.0) if homog else (np.cos(phis[k]), np.sin(phis[k]))
            L = (0.0 if homog else a[0]) + a[1:1 + NL] @ th_h + a[1 + NL:1 + 2 * NL] @ v_h + a[-2] * cs[0] + a[-1] * cs[1]
            f[k] = [xs[0] - (0.0 if homog else THR), xs[1], v, cs[0], cs[1], L - (0.0 if homog else m["l0"])]
            zz[k] = z
            v = v + s.dt * (L + (0.0 if homog else BUOY - MASS * G)) / MASS
            z = z + s.dt * v
            xs = m["As"] @ xs + m["Bs"] * Uv[k]
        return f, zz

    def solve(s, x_s, th_h, v_h, z, v, t, beta, u_last):
        phis = -s.ome * (t + s.dt * np.arange(H)) + beta
        f0, z0 = s.sim(x_s, th_h, v_h, z, v, np.zeros(H), phis)
        M, p = s.m["M"], s.m["p"]
        # J(x) = sum_k [p.f + f'Mf] + W_Z sum z^2 + W_DU sum du^2 ;  f_k = f0_k + sum_j x_j Fu[j,k]
        Fm = s.Fu.transpose(1, 0, 2)          # H x nb x 6
        g = np.einsum("kjf,f->j", Fm, p) + 2 * np.einsum("kjf,fg,kg->j", Fm, M, f0) + 2 * W_Z * s.Zu @ z0
        Hs = 2 * np.einsum("kjf,fg,kig->ji", Fm, M, Fm) + 2 * W_Z * s.Zu @ s.Zu.T
        Dm = (np.eye(s.nb) - np.eye(s.nb, k=-1)); Hs += 2 * W_DU * Dm.T @ Dm
        e0 = np.zeros(s.nb); e0[0] = u_last; g += -2 * W_DU * Dm.T @ e0
        w, V = np.linalg.eigh(0.5 * (Hs + Hs.T)); w = np.maximum(w, 1e-3 * w.max()); Hs = (V * w) @ V.T
        x0 = np.full(s.nb, u_last) if s.Uprev is None else np.r_[s.Uprev[1:], s.Uprev[-1]]
        # ograniczenia miekkie (kara schodkowa kwadratowa): zanurzenie wzgl. chwilowej powierzchni >= 2c, |z| <= 0,6 m
        eta = s.amp * np.cos(phis)
        zmax = np.minimum(eta + DEPTH - 2 * C, 0.6); zmin = -0.6
        ZT = s.Zu.T                                     # H x nb

        def fun(x):
            zz = z0 + ZT @ x
            e1 = np.maximum(0, zz - zmax); e2 = np.maximum(0, zmin - zz)
            J = 0.5 * x @ Hs @ x + g @ x + W_S * (e1 @ e1 + e2 @ e2)
            return J, Hs @ x + g + 2 * W_S * ZT.T @ (e1 - e2)
        res = minimize(fun, x0, jac=True, method="L-BFGS-B", bounds=[(-THM, THM)] * s.nb)
        s.Uprev = res.x
        return res.x[0]


def mpc_episode(env, mpc, phase):
    o, _ = env.reset(options={"phase": phase}); p = env.plant
    th_h, v_h = np.full(NL, p.th), np.zeros(NL); mpc.Uprev = None
    done, R, rows, u = False, 0.0, [], p.cmd; k = 0
    while not done:
        if k % BLK == 0:
            u = mpc.solve(np.array([p.th, p.w_servo]), th_h, v_h, p.z, p.v, p.t, p.beta, u)
        th_h = np.r_[p.th, th_h[:-1]]; v_h = np.r_[p.v, v_h[:-1]]
        o, r, term, trunc, info = env.step(np.array([u / THM])); R += r; rows.append(info); done = term or trunc; k += 1
    return R, rows, term


def summ(rows, env, term):
    n = len(rows); h = slice(max(0, n - 4 * 194), n); a = lambda k: np.array([x[k] for x in rows])[h]
    return dict(term=bool(term), n=n, D_rel=float(a("D").mean() / env.D_cw - 1), P_drag_W=float(a("P_drag_W").mean()),
                z_min=float(a("z").min()), z_max=float(a("z").max()), th_min=float(a("theta_deg").min()), th_max=float(a("theta_deg").max()),
                rate_max=float(np.abs(a("rate")).max()), acc_rms=float(np.sqrt((a("acc") ** 2).mean())))


if __name__ == "__main__":
    t0 = time.time()
    if len(sys.argv) > 1: W_Z = float(sys.argv[1])
    if len(sys.argv) > 2: W_DU = float(sys.argv[2])
    SUF = f"_WZ{W_Z:g}_WDU{W_DU:g}" if len(sys.argv) > 1 else ""
    import pickle
    mf = HERE / "MPC_ID_MODEL.pkl"
    if mf.exists(): mdl = pickle.loads(mf.read_bytes()); D = np.zeros((0, 9))
    else:
        D = collect(); mdl = identify(D); mf.write_bytes(pickle.dumps(mdl))
    print(f"identyfikacja: {len(D)} probek, R2 sila {mdl['r2L']:.4f}, R2 opor {mdl['r2D']:.4f}, {time.time()-t0:.0f} s", flush=True)
    env = GodoVortexEnv(random_phase=False)
    mpc = LinMPC(mdl, ome=env.plant.ome)
    out = dict(model=dict(r2_lift=mdl["r2L"], r2_drag=mdl["r2D"], W_Z=W_Z, W_DU=W_DU, H=H, BLK=BLK), D_cw_N_strip=env.D_cw, mpc=[], pid2=[])
    traces = {}
    for ph in (0.0, np.pi / 2, np.pi, 1.5 * np.pi):
        R, rows, term = mpc_episode(env, mpc, ph); s_ = summ(rows, env, term); s_["R"] = R; out["mpc"].append(s_)
        if ph == 0.0: traces["mpc"] = rows
        act, st = pid_policy(); R2, rows2, term2 = rollout(env, act, ph, st); s2 = summ(rows2, env, term2); s2["R"] = R2; out["pid2"].append(s2)
        if ph == 0.0: traces["pid2"] = rows2
        print(f"faza {ph:.2f}: MPC D_rel {s_['D_rel']:+.3f} term {term} z {s_['z_min']:.2f}..{s_['z_max']:.2f} th {s_['th_min']:.1f}..{s_['th_max']:.1f} | PID2 D_rel {s2['D_rel']:+.3f}", flush=True)
    (HERE / f"MPC_RESULT{SUF}.json").write_text(json.dumps(out, indent=1))
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(4, 1, figsize=(9, 9), sharex=True)
    for name, rows in traces.items():
        t = np.arange(len(rows)) * 0.01
        for i, (k, lab) in enumerate((("eta", "eta nad LE [m]"), ("z", "z [m]"), ("theta_deg", "kat [deg]"), ("P_drag_W", "moc oporu [W/pasek]"))):
            ax[i].plot(t, [x[k] for x in rows], label=name); ax[i].set_ylabel(lab)
    ax[0].legend(); ax[-1].set_xlabel("t [s]"); fig.suptitle("W modelu wirowym: MPC liniowy vs PID2 (faza 0)"); fig.tight_layout()
    fig.savefig(HERE / f"MPC_RESULT{SUF}.png", dpi=110)
    print("gotowe", time.time() - t0, "s")
