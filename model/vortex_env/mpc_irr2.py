"""mpc_irr2.py - MPC: ktory uklad czujnikow fali? Fala KROTKOGRZBIETOWA (JONSWAP Hs 1,5 m, Tp 5 s, cos^2 kierunkow) + szum pomiaru.

Czujniki mierza WYSOKOSC fali (sonda pojemnosciowa / laser / sonar): szum 2 cm RMS, 5 % zanikow (trzymana ostatnia wartosc).
Uklady (d = metry przed nosem plata, y = metry w bok):
  sonda0      : (0,0)
  d3          : (0,0) (3,0)
  d1.5+3      : (0,0) (1.5,0) (3,0)
  d3+boki     : (0,0) (3,0) (3,-1.5) (3,+1.5)
  d6          : (0,0) (6,0)
  + wyrocznia (dokladna przyszla fala) i PID2 jako odniesienia.
Model MPC i estymatory identyfikowane na innych realizacjach tej samej fali krotkogrzbietowej (z szumem).
Wynik: MPC_IRR2_RESULT.json; podglad na zywo jak MPC_IRR (runs/MPC_IRR).  Wszystko "w modelu wirowym".
"""
import json, sys, time, pickle
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import mpc_irr as M
from vortex_plant import Plant, C, DEPTH
from godo_vortex_env import GodoVortexEnv, pid_policy

SPREAD = True
NOISE, DROP = 0.02, 0.05
SENS = {"sonda0": [(0, 0)], "d3": [(0, 0), (3, 0)], "d1.5+3": [(0, 0), (1.5, 0), (3, 0)],
        "d3+boki": [(0, 0), (3, 0), (3, -1.5), (3, 1.5)], "d6": [(0, 0), (6, 0)]}
ALLS = sorted({s for v in SENS.values() for s in v})
DT, NH, NW, H = M.DT, M.NH, M.NW, M.H


def wf_at(p, t):
    I = p.irr
    return float((I["a"] * I["w"] * np.exp(-I["k"] * DEPTH) * np.sin(I["kx"] * M.XQ - I["we"] * t + I["eps"])).sum())


M.wf_at = wf_at


def irr(p, seed):
    p.set_irregular(seed=seed, spread=SPREAD)


def noisy(x, rng, last):
    if rng.uniform() < DROP: return last
    return x + NOISE * rng.standard_normal()


def wave_series(seed, T=400.0, rng=None):
    p = Plant(); irr(p, seed); I = p.irr
    t = np.arange(0, T, DT); ph = -np.outer(t, I["we"]) + I["eps"][None, :]
    wf = ((I["a"] * I["w"] * np.exp(-I["k"] * DEPTH))[None, :] * np.sin(I["kx"][None, :] * M.XQ + ph)).sum(1)
    e0 = (I["a"][None, :] * np.cos(ph)).sum(1)
    meas = {}
    for (d, y) in ALLS:
        clean = (I["a"][None, :] * np.cos(-I["kx"][None, :] * d + I["ky"][None, :] * y + ph)).sum(1)
        if rng is None: meas[(d, y)] = clean; continue
        m = np.empty_like(clean); last = clean[0]
        for i, c in enumerate(clean): last = noisy(c, rng, last); m[i] = last
        meas[(d, y)] = m
    return wf, e0, meas


def regs(hist, mode):
    return np.concatenate([np.asarray(hist[s])[::-5][:NH] for s in SENS[mode]])


def fit_all():
    rng = np.random.default_rng(7)
    data = {s: wave_series(s, 400.0, rng) for s in range(200, 206)}
    test = wave_series(300, 200.0, rng)
    pred = {}
    for mode in SENS:
        X, Yw, Ye = [], [], []
        for s, (wf, e0, me) in data.items():
            for k in range(5 * NH, len(wf) - H, 7):
                X.append(regs({q: me[q][k - 5 * NH + 1:k + 1] for q in me}, mode)); Yw.append(wf[k - NW + 1:k + 1 + H]); Ye.append(e0[k + 1:k + 1 + H])
        X = np.array(X); lam = 1e-3 * np.trace(X.T @ X) / X.shape[1]
        A = np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T)
        Pw, Pe = A @ np.array(Yw), A @ np.array(Ye)
        wf, e0, me = test; q = {}
        for tau in (0, 25, 50, 100, 150):
            pr, tr = [], []
            for k in range(5 * NH, len(wf) - H, 11):
                pr.append(regs({qq: me[qq][k - 5 * NH + 1:k + 1] for qq in me}, mode) @ Pw[:, NW - 1 + tau]); tr.append(wf[k + tau])
            q[f"{tau*DT:.2f}s"] = round(float(1 - np.var(np.array(tr) - np.array(pr)) / np.var(tr)), 3)
        pred[mode] = dict(Pw=Pw, Pe=Pe, quality=q)
        print(f"estymata wf {mode:8s}: " + "  ".join(f"{k} {v:.3f}" for k, v in q.items()), flush=True)
    return pred


def collect_spread(seeds=range(100, 108)):
    orig = Plant.set_irregular
    def si(self, *a, **k): k["spread"] = SPREAD; return orig(self, *a, **k)
    Plant.set_irregular = si
    try: return M.collect(seeds)
    finally: Plant.set_irregular = orig


def run_episode(seed, ctrl, mdl, pred, T_ep=30.0):
    rng = np.random.default_rng(1000 + seed)
    env = GodoVortexEnv(random_phase=False, n_periods=T_ep / 1.9368)
    p = env.plant; irr(p, seed); env.reset()
    he = {}
    for s in ALLS:
        h = [p.eta_ahead(s[0], p.t - DT * i, s[1]) for i in range(5 * NH)][::-1]
        he[s] = [noisy(x, rng, x) for x in h]
    if ctrl == "pid2": act, st = pid_policy()
    else: mpc = M.MPC(mdl); th_h, v_h = np.full(M.NL, p.th), np.zeros(M.NL); u = p.cmd
    rows, RW, done, k = [], [], False, 0
    M.EPNO += 1
    while not done:
        if ctrl == "pid2": a = act(env)
        else:
            if k % M.BLK == 0:
                tf = p.t + DT * np.arange(1, H + 1)
                if ctrl == "wyrocznia":
                    wf_h = np.array([wf_at(p, p.t - DT * i) for i in range(NW)]); wfut = np.array([wf_at(p, t) for t in tf]); efut = np.array([p.eta_LE(t) for t in tf])
                else:
                    r_ = regs(he, ctrl); wv = r_ @ pred[ctrl]["Pw"]; efut = r_ @ pred[ctrl]["Pe"]; wf_h = wv[:NW][::-1]; wfut = wv[NW:]
                u = mpc.solve(np.array([p.th, p.w_servo]), th_h, v_h, wf_h, p.z, p.v, wfut, efut, u)
            th_h = np.r_[p.th, th_h[:-1]]; v_h = np.r_[p.v, v_h[:-1]]; a = np.array([u / M.THM])
        o, r, term, trunc, info = env.step(a); rows.append(info); RW.append(r); done = term or trunc; k += 1
        for s in ALLS: he[s] = he[s][1:] + [noisy(p.eta_ahead(s[0], p.t, s[1]), rng, he[s][-1])]
        if k % 50 == 0 or done: M.live_write(seed, ctrl, rows, RW, env, done, term)
        if ctrl != "pid2" and k % 25 == 1:
            tf = p.t + DT * np.arange(1, H + 1); Uplan = np.repeat(mpc.Uprev, M.BLK)[:H]
            _, zpl = mpc.sim(np.array([p.th, p.w_servo]), th_h, v_h, wf_h, p.z, p.v, Uplan, wfut)
            M._atomic(M.LIVE / "live_plan.json", dict(t0=round(k * DT, 2), seed=seed, ctrl=ctrl, dt=DT, eta_pred=np.round(efut, 3).tolist(),
                      eta_true=[round(p.eta_LE(t), 3) for t in tf], theta_plan=np.round(np.degrees(Uplan), 2).tolist(), z_pred=np.round(zpl, 3).tolist(),
                      eta_past=np.round(he[(0, 0)][-100:], 3).tolist(), time=time.strftime("%H:%M:%S")))
    n = len(rows); h = slice(max(0, n - 2000), n); A = lambda q: np.array([x[q] for x in rows])[h]
    res = dict(term=bool(term), t_upadek=round(n * DT, 2) if term else None)
    if not term:
        res.update(D_rel=float(A("D").mean() / env.D_cw - 1), z_min=float(A("z").min()), z_max=float(A("z").max()), sub_min_c=float(A("sub").min() / C),
                   th_min=float(A("theta_deg").min()), th_max=float(A("theta_deg").max()), acc_rms=float(np.sqrt((A("acc") ** 2).mean())))
    return res


if __name__ == "__main__":
    t0 = time.time(); mf = HERE / "MPC_IRR2_MODEL.pkl"
    if mf.exists(): mdl, pred = pickle.loads(mf.read_bytes())
    else:
        mdl = M.identify(collect_spread()); pred = fit_all(); mf.write_bytes(pickle.dumps((mdl, pred)))
    out = dict(fala="JONSWAP Hs 1,5 m, Tp 5 s, gamma 3,3, krotkogrzbietowa cos^2, 90 skladowych; szum czujnikow 2 cm RMS, 5 % zanikow",
               czujniki={k: [list(s) for s in v] for k, v in SENS.items()}, estymata_R2={m: pred[m]["quality"] for m in pred}, wyniki={})
    SEEDS = (1, 3, 4, 5, 6)      # realizacja 2 odrzucona: gleboka dolina juz w chwili startu, wszystko (tez PID2) pada po 0,15 s
    rf = HERE / "MPC_IRR2_RESULT.json"
    if rf.exists(): out["wyniki"] = json.loads(rf.read_text(encoding="utf-8")).get("wyniki", {})
    for seed in SEEDS:
        for ctrl in ["pid2", "wyrocznia"] + list(SENS):
            if f"fala{seed}_{ctrl}" in out["wyniki"]: continue
            r = run_episode(seed, ctrl, mdl, pred); out["wyniki"][f"fala{seed}_{ctrl}"] = r
            print(f"fala {seed} {ctrl:9s}: " + (f"UPADEK po {r['t_upadek']} s" if r["term"] else
                  f"opor {100*r['D_rel']:+.0f}% | z {r['z_min']:.2f}..{r['z_max']:.2f} | zanurz. min {r['sub_min_c']:.2f}c | zacc RMS {r['acc_rms']:.2f}"), flush=True)
            (HERE / "MPC_IRR2_RESULT.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    summ = {}
    for ctrl in ["pid2", "wyrocznia"] + list(SENS):
        rs = [out["wyniki"][f"fala{s}_{ctrl}"] for s in SEEDS]; ok = [r for r in rs if not r["term"]]
        summ[ctrl] = dict(przezyl=f"{len(ok)}/{len(rs)}", opor_sr=None if not ok else round(100 * np.mean([r["D_rel"] for r in ok]), 1))
        print(f"PODSUMOWANIE {ctrl:9s}: przezyl {summ[ctrl]['przezyl']}, opor (gdy przezyl) {summ[ctrl]['opor_sr']} %", flush=True)
    out["podsumowanie"] = summ
    (HERE / "MPC_IRR2_RESULT.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("gotowe", round(time.time() - t0), "s")
