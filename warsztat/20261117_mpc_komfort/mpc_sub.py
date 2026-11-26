"""mpc_faltinsen.py - "idealny przebieg": MPC z pelna znajomoscia fali (wyrocznia) na modelu Faltinsena B, widmo S1-S4, obciazenie 90 %.
Prosba Julka 13.11 20:14: MPC na Faltinsenie, na widmie, z oporem wspornika i kara za zbyt bliska powierzchnie; ma pokazac, jaki ruch plata
jest potrzebny, zeby obnizyc opor (potem: jakie zawieszenie by to umozliwilo). Wszystko "w modelu", nic z URANS.
Budowa jak mpc_irr.py (model wirowy, 11.11): model do MPC identyfikowany z FaltinsenPlant na falach nieregularnych (inne ziarna niz test):
  serwo [th, thd] liniowo; sila L = ARX(th, v, wf); nurzanie m dv/dt = L + B - m g; opor plata = kwadratowa regresja cech (z dodanym z).
Koszt na horyzoncie (suma po taktach 10 ms): opor plata + opor wspornika K*(eta + h - z) [K = 85,5 N/m zanurzenia na m rozpietosci; 338 N/m / 3,955 m]
  + miekka kara za zanurzenie < 2 cieciw pod chwilowa powierzchnia + miekkie |z| <= 0,5 m + mala kara za zmiane kata. Brak kary za komfort (celowo).
Fala: wyrocznia (dokladna przyszla fala na horyzoncie = gorna granica). Horyzont: max(1,94 s, 1 okres spotkania szczytu widma).
Uzycie: python mpc_faltinsen.py worker K N | summary | test.  Wyniki: wyniki/<stan>__s<seed>.json, przebiegi: viz/<stan>__s<seed>.json.  Log: mpc.log, STOP."""
import json, sys, time, pickle, os
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
HERE = Path(__file__).parent; ROOT = Path(r"T:\NTNU_GODO_CONTROL_20261109"); sys.path.insert(0, str(ROOT / "60_PANELE_I_WYNIKI" / "ZAWIESZENIE"))
import zaw90 as Z
FP, U, G, BUOY, C, DEPTH, SPAN = Z.FP, Z.U, Z.G, Z.BUOY, Z.C, 1.09, 0.02
LOAD = 0.9; FP.MASS = LOAD * Z.MASS100; MASS = FP.MASS
SEAS = {"S1": (1.5, 5.0), "S2": (1.0, 3.5), "S3": (1.5, 8.0), "S4": (2.25, 6.0)}
SEEDS, T_EP, T_SKIP, DT = range(1), 300.0, 30.0, 0.01
NL, NW = 12, 16
W_Z, W_DU, W_S = 2.0, 2000.0, 2e4
STRUT_K = 85.5 * SPAN                       # N na metr zanurzenia, na pasek 0,02 m (jak GODO_STRUT_K w godo_vortex_env.py)
THM = np.radians(7.5); XQ = 0.25 * C
ACT_K = float(os.environ.get("MPC_ACT_K", "57"))   # W na (rad/s)^2 na pasek: moc si?ownika kata ~ ACT_K * (dtheta/dt)^2; dopasowane do URANS 13.11 (TD3 13-16, MPC_WZ2 57); 0 = bez kosztu energii
SEAS_RUN = ("S1", "S2", "S3", "S4")
W_A = float(os.environ.get("MPC_W_A", "0"))      # kara za komfort: W_A * acc^2 [N na (m/s2)^2], dodana 17.11
CORE0 = int(os.environ.get("MPC_CORE0", "6"))
SUBC = float(os.environ.get("MPC_SUB_C", "2"))   # 18.11: zasada zanurzenia w cieciwach (bylo na sztywno 2)
VAR = "act%d_wa%g_sub%g" % (round(ACT_K), W_A, SUBC)
RES, VIZ, LOG = HERE / ("wyniki_" + VAR), HERE / ("viz_" + VAR), HERE / "mpc.log"


def log(s):
    print(s, flush=True)
    with open(LOG, "a", encoding="utf-8") as f: f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + s + "\n")


def plant(sea, seed):
    Hs, Tp = SEAS[sea]; wp = 2 * np.pi / Tp
    P = Z.FaltinsenPlant(**Z.VB); P.set_irregular(Hs=Hs, Tp=Tp, gamma=3.3, seed=seed, N=80, wmin=0.5 * wp, wmax=3.0 * wp)
    cl_eq = (FP.MASS * G - BUOY) / P.q; trim = FP.TH_REF_DEG + float(np.degrees((cl_eq - FP.CL_REF) / (P.slope * P.dcl)))
    return P, trim


def wf_at(p, t):
    I = p.irr; return float((I["a"] * I["w"] * np.exp(-I["k"] * DEPTH) * np.sin(I["k"] * XQ - I["we"] * t + I["eps"])).sum())


def collect(t_ep=40.0):
    rows = []
    for sea in SEAS:
        for s in range(900, 904):
            rng = np.random.default_rng(s); p, trim = plant(sea, s); p.reset(theta_deg=trim); p.cmd = np.radians(trim)
            for _ in range(1000): p.step(free_heave=False)
            integ, kp, A, prbs = 0.0, rng.uniform(2, 10), rng.uniform(0, 3), 0.0
            for k in range(int(t_ep / DT)):
                if k % 15 == 0: prbs = rng.choice([-1, 1]) * rng.uniform(0, 2.5)
                e = -p.z; integ += e * DT
                cmd = trim + kp * e + 1.0 * integ + A * np.sin(2.5 * p.t + s) + prbs
                p.cmd = np.radians(np.clip(cmd, -7.5, 7.5)); th0, thd0, z0, v0, t0 = p.th, p.w_servo, p.z, p.v, p.t; Ls = Ds = 0.0
                for _ in range(p.tick):
                    r = p.step(True); Ls += r["L"]; Ds += r["Fx"]
                rows.append([th0, thd0, z0, v0, p.cmd, Ls / p.tick, Ds / p.tick * SPAN, wf_at(p, t0), 1000 * int(sea[1]) + s])
                if abs(p.z) > 0.8: break
    return np.array(rows)


def feats(th, thd, v, wf, wf8, L, l0, z, thr):
    return np.c_[th - thr, thd, v, wf, wf8, L - l0, z]


def identify(D, thr):
    th, thd, z, v, u, L, Dr, wf, sd = D.T
    same = sd[1:] == sd[:-1]
    X = np.c_[th[:-1], thd[:-1], u[:-1]][same]; Y = np.c_[th[1:], thd[1:]][same]
    S = np.linalg.lstsq(X, Y, rcond=None)[0]; As, Bs = S[:2].T, S[2]
    R, y = [], []
    for k in range(max(NL, NW), len(th)):
        if sd[k - max(NL, NW)] != sd[k]: continue
        R.append(np.r_[1.0, th[k - NL + 1:k + 1][::-1], v[k - NL + 1:k + 1][::-1], wf[k - NW + 1:k + 1][::-1]]); y.append(L[k])
    R = np.array(R); y = np.array(y); sc = R.std(0); sc[0] = 1.0; Rn = R / sc; lam = 1e-4 * len(y); Iw = np.eye(R.shape[1]); Iw[0, 0] = 0
    arx = np.linalg.solve(Rn.T @ Rn + lam * Iw, Rn.T @ y) / sc; r2L = 1 - np.var(y - R @ arx) / np.var(y)
    l0 = arx[0] + thr * arx[1:1 + NL].sum()
    wf8 = np.r_[np.zeros(8), wf[:-8]]; F = feats(th, thd, v, wf, wf8, L, l0, z, thr)[8:]; Dd = Dr[8:]
    nf = F.shape[1]; iu = np.triu_indices(nf); Q = np.array([np.r_[1.0, f, np.outer(f, f)[iu]] for f in F])
    dq = np.linalg.lstsq(Q, Dd, rcond=None)[0]; r2D = 1 - np.var(Dd - Q @ dq) / np.var(Dd)
    M = np.zeros((nf, nf)); M[iu] = dq[1 + nf:]; M = 0.5 * (M + M.T)
    return dict(As=As, Bs=Bs, arx=arx, l0=l0, p=dq[1:1 + nf], M=M, r2L=r2L, r2D=r2D, thr=thr)


class MPC:
    def __init__(s, m, H, BLK):
        s.m, s.H, s.BLK = m, H, BLK; s.nb = H // BLK + (H % BLK > 0); nf = len(m["p"])
        s.Fu = np.zeros((s.nb, H, nf)); s.Zu = np.zeros((s.nb, H))
        for j in range(s.nb):
            Uv = np.zeros(H); Uv[j * BLK:(j + 1) * BLK] = 1.0
            s.Fu[j], s.Zu[j] = s.sim(np.zeros(2), np.zeros(NL), np.zeros(NL), np.zeros(NW), 0.0, 0.0, Uv, np.zeros(H), homog=True)
        s.Uprev = None

    def sim(s, xs, th_h, v_h, wf_h, z, v, Uv, wfut, homog=False):
        m = s.m; a = m["arx"]; thr = 0.0 if homog else m["thr"]; th_h, v_h, wf_h, xs = th_h.copy(), v_h.copy(), wf_h.copy(), xs.copy()
        f = np.zeros((s.H, len(m["p"]))); zz = np.zeros(s.H)
        for k in range(s.H):
            th_h = np.r_[xs[0], th_h[:-1]]; v_h = np.r_[v, v_h[:-1]]; wf_h = np.r_[wfut[k], wf_h[:-1]]
            L = (0.0 if homog else a[0]) + a[1:1 + NL] @ th_h + a[1 + NL:1 + 2 * NL] @ v_h + a[1 + 2 * NL:] @ wf_h
            f[k] = [xs[0] - thr, xs[1], v, wf_h[0], wf_h[8], L - (0.0 if homog else m["l0"]), z]; zz[k] = z
            v = v + DT * (L + (0.0 if homog else BUOY - MASS * G)) / MASS; z = z + DT * v
            xs = m["As"] @ xs + m["Bs"] * Uv[k]
        return f, zz

    def solve(s, xs, th_h, v_h, wf_h, z, v, wfut, etafut, u_last):
        f0, z0 = s.sim(xs, th_h, v_h, wf_h, z, v, np.zeros(s.H), wfut)
        M, p = s.m["M"].copy(), s.m["p"]; Fm = s.Fu.transpose(1, 0, 2); M[1, 1] += ACT_K / U; M[5, 5] += W_A / MASS ** 2     # koszt energii si?ownika: P_act/U jako rownowazna sila [N na pasek]
        g = np.einsum("kjf,f->j", Fm, p) + 2 * np.einsum("kjf,fg,kg->j", Fm, M, f0) + 2 * W_Z * s.Zu @ z0 - STRUT_K * s.Zu.sum(1)
        Hs = 2 * np.einsum("kjf,fg,kig->ji", Fm, M, Fm) + 2 * W_Z * s.Zu @ s.Zu.T
        Dm = np.eye(s.nb) - np.eye(s.nb, k=-1); Hs += 2 * W_DU * Dm.T @ Dm
        e0 = np.zeros(s.nb); e0[0] = u_last; g += -2 * W_DU * Dm.T @ e0
        w, V = np.linalg.eigh(0.5 * (Hs + Hs.T)); w = np.maximum(w, 1e-3 * w.max()); Hs = (V * w) @ V.T
        zmax = np.minimum(etafut + DEPTH - SUBC * C, 0.5); zmin = -0.5; ZT = s.Zu.T

        def fun(x):
            zz = z0 + ZT @ x; e1 = np.maximum(0, zz - zmax); e2 = np.maximum(0, zmin - zz)
            return 0.5 * x @ Hs @ x + g @ x + W_S * (e1 @ e1 + e2 @ e2), Hs @ x + g + 2 * W_S * ZT.T @ (e1 - e2)
        x0 = np.full(s.nb, u_last) if s.Uprev is None else np.r_[s.Uprev[1:], s.Uprev[-1]]
        res = minimize(fun, x0, jac=True, method="L-BFGS-B", bounds=[(-THM, THM)] * s.nb)
        s.Uprev = res.x; return res.x[0]


def model(sea_trim):
    mf = HERE / "MPC_FALT_MODEL.pkl"
    if mf.exists(): return pickle.loads(mf.read_bytes())
    t0 = time.time(); D = collect(); m = identify(D, np.radians(sea_trim)); mf.write_bytes(pickle.dumps(m))
    log(f"model MPC: R2 sila {m['r2L']:.4f}, R2 opor {m['r2D']:.4f}, suma dL/dth {m['arx'][1:1+NL].sum():.0f} N/m/rad, {len(D)} probek, {time.time()-t0:.0f} s"); return m


def run(sea, seed, m, T=T_EP, viz=True):
    p, trim = plant(sea, 100 * int(sea[1]) + seed)          # te same realizacje co widmo_s1s4.py (seed 100*nr + s)
    Te = 1.0 / (2 * np.pi / SEAS[sea][1] * (1 + 2 * np.pi / SEAS[sea][1] * U / G) / (2 * np.pi))
    H = max(194, int(round(Te / DT))); BLK = 5 if H <= 250 else 10; mpc = MPC(m, H, BLK)
    p.reset(theta_deg=trim); u = np.radians(trim); th_h, v_h = np.full(NL, p.th), np.zeros(NL); rec = []
    for k in range(int(T / DT)):
        free = p.t >= 1.0
        if free and k % BLK == 0:
            tf = p.t + DT * np.arange(1, H + 1)
            wf_h = np.array([wf_at(p, p.t - DT * i) for i in range(NW)]); wfut = np.array([wf_at(p, t) for t in tf]); efut = np.array([p.eta_LE(t) for t in tf])
            u = mpc.solve(np.array([p.th, p.w_servo]), th_h, v_h, wf_h, p.z, p.v, wfut, efut, u)
        th_h = np.r_[p.th, th_h[:-1]]; v_h = np.r_[p.v, v_h[:-1]]; p.cmd = float(np.clip(u, -THM, THM)); Ls = 0.0; Pd = 0.0
        for _ in range(p.tick):
            r = p.step(free_heave=free); Ls += r["L"]; Pd += r["P_drag_W_strip"]
        sub = r["sub_true"]; acc = (Ls / p.tick + BUOY) / MASS - G
        rec.append((p.t, r["eta_LE"], p.z, np.degrees(p.th), acc, Pd / p.tick, U * STRUT_K * max(sub, 0.0), sub, p.v))
        if not np.isfinite(p.z) or abs(p.z) > 1.5: raise RuntimeError("niestabilne")
    a = np.array(rec); b = a[a[:, 0] > T_SKIP]; acc = b[:, 4]
    out = dict(sea=sea, seed=seed, H_steps=H, P_foil_W=float(b[:, 5].mean()), P_strut_W=float(b[:, 6].mean()), acc_rms=float(acc.std()),
               acc_peak=float(np.abs(acc).max()), z_min=float(b[:, 2].min()), z_max=float(b[:, 2].max()), z_std=float(b[:, 2].std()),
               sub_min=float(b[:, 7].min()), t_below_2c_pct=float(100 * np.mean(b[:, 7] < 2 * C)), t_below_1c_pct=float(100 * np.mean(b[:, 7] < C)),
               th_min=float(b[:, 3].min()), th_max=float(b[:, 3].max()), sat_pct=float(100 * np.mean(np.abs(b[:, 3]) > 7.45)), v_rms=float(b[:, 8].std()),
               ACT_K=ACT_K, rate2=float(np.mean(np.gradient(np.radians(b[:, 3]), DT) ** 2)))
    out["P_act_est_W"] = 57.0 * out["rate2"]; out["P_act_est_low_W"] = 15.0 * out["rate2"]
    if viz:
        VIZ.mkdir(exist_ok=True); v = b[::5]
        (VIZ / f"{sea}__s{seed}.json").write_text(json.dumps(dict(sea=sea, seed=seed, cols=["t", "eta_LE", "z_foil", "theta_deg", "acc", "P_foil_W", "P_strut_W", "sub", "v"],
                                                                  data=np.round(v, 4).tolist())), encoding="utf-8")
    return out


def strut_ref():
    """odniesienie: plat sztywno na glebokosci projektowej, woda spokojna, 90 %: opor plata (CALM_90 z widmo_s1s4) + wspornik przy h = 1,09 m"""
    calm = json.loads((ROOT / "60_PANELE_I_WYNIKI" / "WIDMO_S1S4" / "CALM_90.json").read_text())["P_W"]
    return dict(P_foil_calm_W=calm, P_strut_calm_W=U * STRUT_K * DEPTH, P_total_calm_W=calm + U * STRUT_K * DEPTH)


def worker(k, nw):
    import psutil; me = psutil.Process(); me.cpu_affinity([CORE0 + k]); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    RES.mkdir(exist_ok=True); m = model(plant("S1", 0)[1])
    jobs = [(s, sd) for sd in SEEDS for s in SEAS_RUN]
    for i, (s, sd) in enumerate(jobs):
        if i % nw != k: continue
        if (HERE / "STOP").exists(): log(f"w{k}: STOP"); return
        f = RES / f"{s}__s{sd}.json"
        if f.exists(): continue
        t0 = time.time()
        try:
            r = run(s, sd, m); f.write_text(json.dumps(r), encoding="utf-8")
            log(f"w{k} {VAR}: {s} s{sd}: silownik ~{r['P_act_est_W']:.1f} W, plat {r['P_foil_W']:.1f} W + wspornik {r['P_strut_W']:.1f} W, z {r['z_min']:.2f}..{r['z_max']:.2f} m, z'' RMS {r['acc_rms']:.2f}, zan.min {r['sub_min']:.2f} m, <2c {r['t_below_2c_pct']:.1f} %, {time.time()-t0:.0f} s")
        except Exception as e:
            f.write_text(json.dumps(dict(sea=s, seed=sd, error=str(e))), encoding="utf-8"); log(f"w{k}: {s} s{sd}: BLAD {e}")
    log(f"w{k}: koniec")


def summary():
    ref = strut_ref(); rows = [json.loads(p.read_text()) for p in RES.glob("*.json")]; out = {}
    for s in SEAS:
        R = [r for r in rows if r["sea"] == s and "error" not in r]
        if not R: continue
        mn = lambda q: float(np.mean([r[q] for r in R])); tot = [r["P_foil_W"] + r["P_strut_W"] for r in R]
        out[s] = dict(n=len(R), P_foil_W=mn("P_foil_W"), P_strut_W=mn("P_strut_W"), dP_total_pct=100 * (np.mean(tot) / ref["P_total_calm_W"] - 1),
                      dP_total_range=[100 * (min(tot) / ref["P_total_calm_W"] - 1), 100 * (max(tot) / ref["P_total_calm_W"] - 1)],
                      dP_foil_pct=100 * (mn("P_foil_W") / ref["P_foil_calm_W"] - 1), acc_rms=mn("acc_rms"), acc_peak=max(r["acc_peak"] for r in R),
                      z_std=mn("z_std"), z_range=[min(r["z_min"] for r in R), max(r["z_max"] for r in R)], sub_min=min(r["sub_min"] for r in R),
                      below_2c_pct=mn("t_below_2c_pct"), below_1c_pct=mn("t_below_1c_pct"), sat_pct=mn("sat_pct"), errors=sum("error" in r for r in rows if r["sea"] == s))
    for s in out:
        R = [r for r in rows if r["sea"] == s and "error" not in r]; out[s]["P_act_est_W"] = float(np.mean([r["P_act_est_W"] for r in R])); out[s]["P_act_est_low_W"] = float(np.mean([r["P_act_est_low_W"] for r in R]))
        out[s]["dP_total_z_silownikiem_pct"] = 100 * ((out[s]["P_foil_W"] + out[s]["P_strut_W"] + out[s]["P_act_est_W"]) / ref["P_total_calm_W"] - 1)
    (HERE / ("MPC_FALT_WIDMO_" + VAR + ".json")).write_text(json.dumps(dict(odniesienie=ref, wyniki=out), indent=1), encoding="utf-8"); print(json.dumps(dict(ref=ref, out=out), indent=0))


if __name__ == "__main__":
    if sys.argv[1] == "worker": worker(int(sys.argv[2]), int(sys.argv[3]))
    elif sys.argv[1] == "summary": summary()
    elif sys.argv[1] == "test":
        import psutil; psutil.Process().cpu_affinity([23])
        m = model(plant("S1", 0)[1]); t0 = time.time(); r = run("S1", 0, m, T=40.0, viz=False); print(r, round(time.time() - t0), "s na 40 s"); print(strut_ref())
