"""mpc_irr.py - MPC na fali NIEREGULARNEJ (JONSWAP Hs 1,5 m, Tp 5 s, gamma 3,3, z dziobu), w modelu wirowym.

Model do MPC (takt 10 ms, identyfikowany na falach nieregularnych, inne ziarna niz test):
  serwo: [th, thd]_{k+1} = As [th, thd]_k + Bs u_k
  sila:  L_k = l0 + sum a_i th_{k-i} + sum b_i v_{k-i} + sum c_i wf_{k-i}      (wf = pionowa predkosc wody w c/4 na sredniej glebokosci)
  nurzanie: v_{k+1} = v_k + dt (L_k + B - m g)/m
  opor:  kwadratowa regresja cech [th-th_ref, thd, v, wf, wf_{k-8}, L-l0]
Przyszla fala wf na horyzoncie 1,94 s:
  'wyrocznia'  - dokladnie (gorna granica),
  'czujnik10'  - liniowy predyktor z historii wf + pomiaru eta 10 m przed nosem (dokladna informacja ~0,5 s naprzod),
  'bez'        - liniowy predyktor tylko z historii wf (jak agent RL: bez podgladu).
Ograniczenia miekkie jak w mpc_linear: zanurzenie >= 2c wzgl. chwilowej powierzchni (przewidywanej tak samo jak wf), |z| <= 0,6 m.
Ocena: 3 realizacje fali (ziarna 1-3), 30 s, srednie z ostatnich 20 s; porownanie z PID2 na tych samych falach.
Wynik: MPC_IRR_RESULT.json (+ .png).  Wszystko "w modelu wirowym".
"""
import json, sys, time, pickle
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
from vortex_plant import Plant, MASS, BUOY, SPAN, U, C, DEPTH
from uvm_step import G
from godo_vortex_env import GodoVortexEnv, pid_policy, TH_REF_DEG, TH_MAX_DEG

NL, NW, H, BLK, DT = 12, 16, 194, 5, 0.01
W_Z, W_DU, W_S = 20.0, 2000.0, 2e4
THR, THM = np.radians(TH_REF_DEG), np.radians(TH_MAX_DEG)
XQ = 0.25 * C
D_SENS = 10.0
NH = 20            # dlugosc historii w predyktorze (co 5 taktow = 1 s)


def wf_at(p, t):
    """pionowa predkosc orbitalna w c/4 na sredniej glebokosci (niezalezna od z plata)"""
    if getattr(p, "irr", None):
        I = p.irr; return float((I["a"] * I["w"] * np.exp(-I["k"] * DEPTH) * np.sin(I["k"] * XQ - I["we"] * t + I["eps"])).sum())
    return float(p.A0 * np.exp(-p.k * DEPTH) * np.sin(p.k * XQ - p.ome * t + p.beta))


# ---------------- identyfikacja ----------------
def collect(seeds=range(100, 108), t_ep=20.0):
    rows = []
    for s in seeds:
        rng = np.random.default_rng(s)
        p = Plant(); p.set_irregular(seed=s); p.reset(theta_deg=TH_REF_DEG); p.cmd = THR
        for _ in range(1000): p.step(free_heave=False)
        integ, kp, A, prbs = 0.0, rng.uniform(4, 14), rng.uniform(0, 3), 0.0
        for k in range(int(t_ep / DT)):
            if k % 15 == 0: prbs = rng.choice([-1, 1]) * rng.uniform(0, 2.0)
            e = -p.z; integ += e * DT
            cmd = TH_REF_DEG + kp * e + 1.2 * integ + A * np.sin(3.24 * p.t + s) + prbs
            p.cmd = np.radians(np.clip(cmd, -TH_MAX_DEG, TH_MAX_DEG))
            th0, thd0, z0, v0, t0 = p.th, p.w_servo, p.z, p.v, p.t
            Ls = Ds = 0.0
            for _ in range(p.tick):
                r = p.step(True); Ls += r["L"]; Ds += r["Fx"]
            rows.append([th0, thd0, z0, v0, p.cmd, Ls / p.tick, Ds / p.tick * SPAN, wf_at(p, t0), s])
            if abs(p.z) > 0.7: break
    return np.array(rows)


def feats(th, thd, v, wf, wf8, L, l0):
    return np.c_[th - THR, thd, v, wf, wf8, L - l0]


def identify(D):
    th, thd, z, v, u, L, Dr, wf, sd = D.T
    same = sd[1:] == sd[:-1]
    X = np.c_[th[:-1], thd[:-1], u[:-1]][same]; Y = np.c_[th[1:], thd[1:]][same]
    S = np.linalg.lstsq(X, Y, rcond=None)[0]; As, Bs = S[:2].T, S[2]
    R, y, rowsF, yD = [], [], [], []
    for k in range(max(NL, NW), len(th)):
        if sd[k - max(NL, NW)] != sd[k]: continue
        R.append(np.r_[1.0, th[k - NL + 1:k + 1][::-1], v[k - NL + 1:k + 1][::-1], wf[k - NW + 1:k + 1][::-1]]); y.append(L[k])
    R = np.array(R); y = np.array(y)
    # ridge na znormalizowanych kolumnach (bez tego wspolliniowe opoznienia th/v/wf daja ogromne naprzemienne wspolczynniki i zly znak dL/dth)
    sc = R.std(0); sc[0] = 1.0; Rn = R / sc; lam = 1e-4 * len(y)
    Iw = np.eye(R.shape[1]); Iw[0, 0] = 0.0
    arx = np.linalg.solve(Rn.T @ Rn + lam * Iw, Rn.T @ y) / sc
    r2L = 1 - np.var(y - R @ arx) / np.var(y)
    print(f"ARX: suma dL/dth {arx[1:1+NL].sum():.0f} N/m/rad, suma dL/dv {arx[1+NL:1+2*NL].sum():.0f}, suma wf {arx[1+2*NL:].sum():.0f}, R2 {r2L:.4f}", flush=True)
    l0 = arx[0] + THR * arx[1:1 + NL].sum()
    wf8 = np.r_[np.zeros(8), wf[:-8]]
    F = feats(th, thd, v, wf, wf8, L, l0)[8:]; Dd = Dr[8:]
    iu = np.triu_indices(6); Q = np.array([np.r_[1.0, f, np.outer(f, f)[iu]] for f in F])
    dq = np.linalg.lstsq(Q, Dd, rcond=None)[0]; r2D = 1 - np.var(Dd - Q @ dq) / np.var(Dd)
    M = np.zeros((6, 6)); M[iu] = dq[7:]; M = 0.5 * (M + M.T)
    return dict(As=As, Bs=Bs, arx=arx, l0=l0, p=dq[1:7], M=M, r2L=r2L, r2D=r2D)


# ---------------- predyktor fali (z pomiaru WYSOKOSCI fali, nie predkosci wody) ----------------
# sonda0: pojemnosciowa sonda na kolumnie (d = 0, nad nosem plata);  dziob3: dodatkowo laser/sonar ~3 m przed platem
MODES = {"sonda0": [0.0], "dziob3": [0.0, 3.0]}


def wave_series(seed, T=400.0, dists=(0.0, 3.0)):
    p = Plant(); p.set_irregular(seed=seed); I = p.irr
    t = np.arange(0, T, DT); ph = -np.outer(t, I["we"]) + I["eps"][None, :]
    wf = ((I["a"] * I["w"] * np.exp(-I["k"] * DEPTH))[None, :] * np.sin(I["k"][None, :] * XQ + ph)).sum(1)
    etas = {d: (I["a"][None, :] * np.cos(-I["k"][None, :] * d + ph)).sum(1) for d in dists}
    return wf, etas


def regs(hist, mode):
    """hist: {d: ostatnie 5*NH probek eta (najnowsza na koncu)}; regresory = probki co 5 taktow (1 s historii) z kazdego czujnika"""
    return np.concatenate([np.asarray(hist[d])[::-5][:NH] for d in MODES[mode]])


def fit_predictor(mode, seeds=range(200, 206)):
    """liniowy (ridge) estymator wf na oknie [k-NW+1 .. k+H] i eta_LE na [k+1 .. k+H] z historii pomiarow eta; dane z innych realizacji"""
    Xs, Yw, Ye = [], [], []
    for s in seeds:
        wf, et = wave_series(s)
        for k in range(5 * NH, len(wf) - H, 7):
            Xs.append(regs({d: et[d][k - 5 * NH + 1:k + 1] for d in et}, mode)); Yw.append(wf[k - NW + 1:k + 1 + H]); Ye.append(et[0.0][k + 1:k + 1 + H])
    X = np.array(Xs); lam = 1e-3 * np.trace(X.T @ X) / X.shape[1]
    A = np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T)
    Pw, Pe = A @ np.array(Yw), A @ np.array(Ye)
    wf, et = wave_series(300, 200.0); q = {}
    for tau in (0, 50, 100, 150):          # R2 estymaty wf: teraz, za 0,5 / 1,0 / 1,5 s (realizacja testowa)
        pr, tr = [], []
        for k in range(5 * NH, len(wf) - H, 11):
            pr.append(regs({d: et[d][k - 5 * NH + 1:k + 1] for d in et}, mode) @ Pw[:, NW - 1 + tau]); tr.append(wf[k + tau])
        q[f"R2_wf_{tau*DT:.1f}s"] = round(float(1 - np.var(np.array(tr) - np.array(pr)) / np.var(tr)), 3)
    return dict(Pw=Pw, Pe=Pe, quality=q)


# ---------------- MPC ----------------
class MPC:
    def __init__(s, m):
        s.m = m; s.nb = H // BLK + (H % BLK > 0)
        s.Fu = np.zeros((s.nb, H, 6)); s.Zu = np.zeros((s.nb, H))
        for j in range(s.nb):
            Uv = np.zeros(H); Uv[j * BLK:(j + 1) * BLK] = 1.0
            s.Fu[j], s.Zu[j] = s.sim(np.zeros(2), np.zeros(NL), np.zeros(NL), np.zeros(NW), 0.0, 0.0, Uv, np.zeros(H), homog=True)
        s.Uprev = None

    def sim(s, xs, th_h, v_h, wf_h, z, v, Uv, wfut, homog=False):
        m = s.m; a = m["arx"]; th_h, v_h, wf_h, xs = th_h.copy(), v_h.copy(), wf_h.copy(), xs.copy()
        f = np.zeros((H, 6)); zz = np.zeros(H)
        for k in range(H):
            th_h = np.r_[xs[0], th_h[:-1]]; v_h = np.r_[v, v_h[:-1]]; wf_h = np.r_[wfut[k], wf_h[:-1]]
            L = (0.0 if homog else a[0]) + a[1:1 + NL] @ th_h + a[1 + NL:1 + 2 * NL] @ v_h + a[1 + 2 * NL:] @ wf_h
            f[k] = [xs[0] - (0.0 if homog else THR), xs[1], v, wf_h[0], wf_h[8] if NW > 8 else 0.0, L - (0.0 if homog else m["l0"])]
            zz[k] = z
            v = v + DT * (L + (0.0 if homog else BUOY - MASS * G)) / MASS; z = z + DT * v
            xs = m["As"] @ xs + m["Bs"] * Uv[k]
        return f, zz

    def solve(s, xs, th_h, v_h, wf_h, z, v, wfut, etafut, u_last):
        f0, z0 = s.sim(xs, th_h, v_h, wf_h, z, v, np.zeros(H), wfut)
        M, p = s.m["M"], s.m["p"]; Fm = s.Fu.transpose(1, 0, 2)
        g = np.einsum("kjf,f->j", Fm, p) + 2 * np.einsum("kjf,fg,kg->j", Fm, M, f0) + 2 * W_Z * s.Zu @ z0
        Hs = 2 * np.einsum("kjf,fg,kig->ji", Fm, M, Fm) + 2 * W_Z * s.Zu @ s.Zu.T
        Dm = np.eye(s.nb) - np.eye(s.nb, k=-1); Hs += 2 * W_DU * Dm.T @ Dm
        e0 = np.zeros(s.nb); e0[0] = u_last; g += -2 * W_DU * Dm.T @ e0
        w, V = np.linalg.eigh(0.5 * (Hs + Hs.T)); w = np.maximum(w, 1e-3 * w.max()); Hs = (V * w) @ V.T
        mg = getattr(s, "margin", 0.0)     # dodatkowy zapas [m] (kaskada: z biezacego bledu prognozy)
        zmax = np.minimum(etafut + DEPTH - 2 * C - mg, 0.5 - mg); zmin = -0.5 + mg; ZT = s.Zu.T

        def fun(x):
            zz = z0 + ZT @ x; e1 = np.maximum(0, zz - zmax); e2 = np.maximum(0, zmin - zz)
            return 0.5 * x @ Hs @ x + g @ x + W_S * (e1 @ e1 + e2 @ e2), Hs @ x + g + 2 * W_S * ZT.T @ (e1 - e2)
        x0 = np.full(s.nb, u_last) if s.Uprev is None else np.r_[s.Uprev[1:], s.Uprev[-1]]
        res = minimize(fun, x0, jac=True, method="L-BFGS-B", bounds=[(-THM, THM)] * s.nb)
        s.Uprev = res.x; return res.x[0]


LIVE = HERE / "runs" / "MPC_IRR"
EPNO = 0


def _atomic(path, obj):
    import os
    tmp = path.with_suffix(".tmp"); tmp.write_text(json.dumps(obj), encoding="utf-8")
    for _ in range(20):                      # Windows: plik moze byc chwilowo otwarty przez serwer podgladu
        try: os.replace(tmp, path); return
        except PermissionError: time.sleep(0.05)


def live_write(seed, ctrl, rows, RW, env, done, term):
    LIVE.mkdir(parents=True, exist_ok=True)
    g = lambda q: [round(float(x[q]), 4) for x in rows]
    _atomic(LIVE / "live_ep.json", dict(alg="mpc", episode=EPNO, step=len(rows), mode=ctrl, sigma=0, seed=seed, R=round(float(sum(RW)), 1), done=bool(done),
                                        term=bool(term) if done else None, loss_c=None, loss_a=None, alpha=None, D_cw=env.D_cw, dt=DT,
                                        z=g("z"), th=g("theta_deg"), cmd=g("theta_deg"), eta=g("eta"), sub=g("sub"), D=g("D"), r=[round(float(x), 3) for x in RW],
                                        time=time.strftime("%H:%M:%S")))


def run_episode(seed, ctrl, mdl=None, pred=None, T_ep=30.0):
    env = GodoVortexEnv(random_phase=False, n_periods=T_ep / 1.9368)
    p = env.plant; p.set_irregular(seed=seed); o, _ = env.reset()
    nh = 5 * NH
    he = {d: [p.eta_ahead(d, p.t - DT * i) for i in range(nh)][::-1] for d in (0.0, 3.0)}      # historia pomiarow eta (sonda, dziob)
    if ctrl == "pid2":
        act, st = pid_policy()
    else:
        mpc = MPC(mdl); th_h, v_h = np.full(NL, p.th), np.zeros(NL); u = p.cmd
    rows, done, k, RW = [], False, 0, []
    global EPNO
    EPNO += 1
    while not done:
        if ctrl == "pid2":
            a = act(env)
        else:
            if k % BLK == 0:
                tf = p.t + DT * np.arange(1, H + 1)
                if ctrl == "wyrocznia":
                    wf_h = np.array([wf_at(p, p.t - DT * i) for i in range(NW)])
                    wfut = np.array([wf_at(p, t) for t in tf]); efut = np.array([p.eta_LE(t) for t in tf])
                else:
                    r = regs(he, ctrl); wv = r @ pred[ctrl]["Pw"]; efut = r @ pred[ctrl]["Pe"]
                    wf_h = wv[:NW][::-1]; wfut = wv[NW:]
                u = mpc.solve(np.array([p.th, p.w_servo]), th_h, v_h, wf_h, p.z, p.v, wfut, efut, u)
            th_h = np.r_[p.th, th_h[:-1]]; v_h = np.r_[p.v, v_h[:-1]]
            a = np.array([u / THM])
        o, r, term, trunc, info = env.step(a); rows.append(info); done = term or trunc; k += 1
        RW.append(r)
        for d in he: he[d] = he[d][1:] + [p.eta_ahead(d, p.t)]
        if k % 50 == 0 or done:
            live_write(seed, ctrl, rows, RW, env, done, term)
        if ctrl != "pid2" and (k % 25 == 1):
            tf = p.t + DT * np.arange(1, H + 1)
            ef_true = [p.eta_LE(t) for t in tf]
            Uplan = np.repeat(mpc.Uprev, BLK)[:H]
            fpl, zpl = mpc.sim(np.array([p.th, p.w_servo]), th_h, v_h, wf_h, p.z, p.v, Uplan, wfut)
            LIVE.mkdir(exist_ok=True)
            _atomic(LIVE / "live_plan.json", dict(t0=round(k * DT, 2), seed=seed, ctrl=ctrl, dt=DT, eta_pred=np.round(efut, 3).tolist(), eta_true=np.round(ef_true, 3).tolist(),
                                                 theta_plan=np.round(np.degrees(Uplan), 2).tolist(), z_pred=np.round(zpl, 3).tolist(),
                                                 eta_past=np.round(he[0.0][-100:], 3).tolist(), time=time.strftime("%H:%M:%S")))
    n = len(rows); h = slice(max(0, n - 2000), n); A = lambda q: np.array([x[q] for x in rows])[h]
    res = dict(term=bool(term), n=n, t_upadek=round(n * DT, 2) if term else None)
    if not term:
        res.update(D_rel=float(A("D").mean() / env.D_cw - 1), P_drag_W=float(A("P_drag_W").mean()), z_min=float(A("z").min()), z_max=float(A("z").max()),
                   sub_min_c=float(A("sub").min() / C), th_min=float(A("theta_deg").min()), th_max=float(A("theta_deg").max()),
                   rate_max=float(np.abs(A("rate")).max()), acc_rms=float(np.sqrt((A("acc") ** 2).mean())), P_shaft_W=float(A("P_act").mean()))
    return res, rows


if __name__ == "__main__":
    t0 = time.time(); mf = HERE / "MPC_IRR_MODEL.pkl"
    if mf.exists():
        mdl, pred = pickle.loads(mf.read_bytes())
    else:
        D = collect(); mdl = identify(D)
        pred = {m: fit_predictor(m) for m in MODES}
        mf.write_bytes(pickle.dumps((mdl, pred)))
    print(f"model: R2 sila {mdl['r2L']:.4f}, R2 opor {mdl['r2D']:.4f}; estymata wf: {{m: pred[m]['quality'] for m in pred}}  ({time.time()-t0:.0f} s)".replace("{{m: pred[m]['quality'] for m in pred}}", str({m: pred[m]['quality'] for m in pred})), flush=True)
    out = dict(fala="JONSWAP Hs 1,5 m, Tp 5 s, gamma 3,3, z dziobu, 30 skladowych", model=dict(r2_lift=mdl["r2L"], r2_drag=mdl["r2D"]),
               predyktor={m: pred[m]["quality"] for m in pred}, wyniki={})
    keep = {}
    for seed in (1, 2, 3):
        for ctrl in ("pid2", "wyrocznia", "dziob3", "sonda0"):
            r, rows = run_episode(seed, ctrl, mdl, pred); out["wyniki"][f"fala{seed}_{ctrl}"] = r
            if seed == 1: keep[ctrl] = rows
            print(f"fala {seed} {ctrl:10s}: " + (f"UPADEK po {r['t_upadek']} s" if r["term"] else
                  f"opor {100*r['D_rel']:+.0f}% | z {r['z_min']:.2f}..{r['z_max']:.2f} | zanurz. min {r['sub_min_c']:.2f}c | kat {r['th_min']:.1f}..{r['th_max']:.1f} | zacc RMS {r['acc_rms']:.2f}"), flush=True)
            (HERE / "MPC_IRR_RESULT.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    (HERE / "MPC_IRR_EP_seed1.json").write_text(json.dumps({c: [{k: float(v) for k, v in x.items()} for x in rows] for c, rows in keep.items()}))
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(4, 1, figsize=(11, 10), sharex=True)
    for name, rows in keep.items():
        t = np.arange(len(rows)) * DT
        for i, (q, lab) in enumerate((("eta", "fala nad LE [m]"), ("z", "z [m]"), ("theta_deg", "kat [deg]"), ("P_drag_W", "moc oporu [W/pasek]"))):
            if q == "eta" and name != "pid2": continue
            ax[i].plot(t, [x[q] for x in rows], label=name, lw=1)
    for a_ in ax: a_.legend(fontsize=8, ncol=4)
    ax[-1].set_xlabel("t [s]"); fig.suptitle("W modelu wirowym: fala nieregularna JONSWAP Hs 1,5 m Tp 5 s (realizacja 1)"); fig.tight_layout()
    fig.savefig(HERE / "MPC_IRR_RESULT.png", dpi=110)
    print("gotowe", round(time.time() - t0), "s", flush=True)
