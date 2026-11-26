"""mpc_irr3.py - weryfikacja pomyslu Julka: KASKADA czujnikow fali (3 m prognozuje, 1,5 m sprawdza i koryguje) przy BLEDZIE MODELU FALI.

Prawda w symulacji: fala krotkogrzbietowa JONSWAP Hs 1,5 m, Tp 5 s (jak mpc_irr2) + nieznany MPC prad: wzor fali biegnie wzgledem plata
z predkoscia jak przy U + DELTA_TRUE (DELTA_TRUE = 0,7 m/s). Szum czujnikow 2 cm RMS, 5 % zanikow.
Czujniki: sonda na kolumnie (0 m), 1,5 m, 3 m przed platem.
Warianty MPC:
  A  'd3_bez_korekty'  : prognoza z sondy + 3 m, estymator wyuczony bez pradu (DELTA = 0)
  B  'wspolnie'        : sonda + 1,5 + 3 m razem w jednym estymatorze (DELTA = 0) - jak dotad
  C  'kaskada'         : bank estymatorow dla DELTA w {-1,-0,5,0,0,5,1} m/s; kazdy z sondy + 3 m przewiduje, co zaraz zmierzy czujnik 1,5 m;
                         wybierany ten, ktory w ostatnich 2 s mylil sie najmniej (korekta na biezaco)
  D  'kaskada+zapas'   : C + zapas zanurzenia i |z| = 3 x RMS bledu na czujniku 1,5 m (mniej pewna prognoza -> ostrozniej)
  + 'wyrocznia' i 'pid2'.
Wynik: MPC_IRR3_RESULT.json; podglad na zywo jak MPC_IRR.  Wszystko "w modelu wirowym".
"""
import json, sys, time, pickle
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import mpc_irr as M
import mpc_irr2 as M2
from vortex_plant import Plant, C, DEPTH, U
from godo_vortex_env import GodoVortexEnv, pid_policy

DELTA_TRUE = 0.7
DELTAS = (-1.0, -0.5, 0.0, 0.5, 1.0)
S0, S15, S3 = (0, 0), (1.5, 0), (3, 0)
DT, NH, NW, H = M.DT, M.NH, M.NW, M.H


def irr(p, seed, delta):
    p.set_irregular(seed=seed, spread=True); I = p.irr; I["we"] = I["w"] + I["kx"] * (U + delta)


def series(seed, delta, T, rng):
    p = Plant(); irr(p, seed, delta); I = p.irr
    t = np.arange(0, T, DT); ph = -np.outer(t, I["we"]) + I["eps"][None, :]
    wf = ((I["a"] * I["w"] * np.exp(-I["k"] * DEPTH))[None, :] * np.sin(I["kx"][None, :] * M.XQ + ph)).sum(1)
    e0 = (I["a"][None, :] * np.cos(ph)).sum(1); me = {}
    for (d, y) in (S0, S15, S3):
        clean = (I["a"][None, :] * np.cos(-I["kx"][None, :] * d + I["ky"][None, :] * y + ph)).sum(1)
        m = np.empty_like(clean); last = clean[0]
        for i, c in enumerate(clean): last = M2.noisy(c, rng, last); m[i] = last
        me[(d, y)] = m
    return wf, e0, me


def R(hist, sens):
    return np.concatenate([np.asarray(hist[s])[::-5][:NH] for s in sens])


def ridge(X, Y):
    X = np.array(X); lam = 1e-3 * np.trace(X.T @ X) / X.shape[1]
    return np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ np.array(Y))


def fit_bank():
    rng = np.random.default_rng(11); bank = {}
    for dl in DELTAS:
        X03, X0153, Yw, Ye, Yw3, Ye3, Y15 = [], [], [], [], [], [], []
        for s in range(200, 205):
            wf, e0, me = series(s, dl, 300.0, rng)
            for k in range(5 * NH, len(wf) - H, 7):
                h = {q: me[q][k - 5 * NH + 1:k + 1] for q in me}
                X03.append(R(h, (S0, S3))); Yw.append(wf[k - NW + 1:k + 1 + H]); Ye.append(e0[k + 1:k + 1 + H]); Y15.append(me[S15][k])
                if dl == 0.0: X0153.append(R(h, (S0, S15, S3)))
        bank[dl] = dict(Pw=ridge(X03, Yw), Pe=ridge(X03, Ye), P15=ridge(X03, Y15))
        if dl == 0.0: bank["wspolnie"] = dict(Pw=ridge(X0153, Yw), Pe=ridge(X0153, Ye))
        print(f"bank DELTA {dl:+.1f} gotowy", flush=True)
    return bank


def run_episode(seed, ctrl, mdl, bank, T_ep=30.0):
    rng = np.random.default_rng(2000 + seed)
    env = GodoVortexEnv(random_phase=False, n_periods=T_ep / 1.9368)
    p = env.plant; irr(p, seed, DELTA_TRUE); env.reset()
    he = {s: [M2.noisy(p.eta_ahead(s[0], p.t - DT * i, s[1]), rng, 0.0) for i in range(5 * NH)][::-1] for s in (S0, S15, S3)}
    err = {dl: [] for dl in DELTAS}; chosen, sig = 0.0, 0.0; log_sel = []
    if ctrl == "pid2": act, st = pid_policy()
    else: mpc = M.MPC(mdl); th_h, v_h = np.full(M.NL, p.th), np.zeros(M.NL); u = p.cmd
    rows, RW, done, k = [], [], False, 0
    M.EPNO += 1
    while not done:
        # kaskada: kazdy model z banku przewiduje biezacy pomiar 1,5 m z sondy + 3 m; liczymy blad z ostatnich 2 s
        r03 = R(he, (S0, S3))
        for dl in DELTAS:
            err[dl].append((r03 @ bank[dl]["P15"] - he[S15][-1]) ** 2); err[dl] = err[dl][-200:]
        if ctrl == "pid2": a = act(env)
        else:
            if k % M.BLK == 0:
                tf = p.t + DT * np.arange(1, H + 1)
                if ctrl == "wyrocznia":
                    wf_h = np.array([M2.wf_at(p, p.t - DT * i) for i in range(NW)]); wfut = np.array([M2.wf_at(p, t) for t in tf]); efut = np.array([p.eta_LE(t) for t in tf])
                else:
                    if ctrl == "d3_bez_korekty": B, x = bank[0.0], r03
                    elif ctrl == "wspolnie": B, x = bank["wspolnie"], R(he, (S0, S15, S3))
                    else:
                        chosen = min(DELTAS, key=lambda d: np.mean(err[d])) if len(err[0.0]) > 50 else 0.0
                        B, x = bank[chosen], r03
                        sig = float(np.sqrt(np.mean(err[chosen])))
                        mpc.margin = 3 * sig if ctrl == "kaskada+zapas" else 0.0
                    wv = x @ B["Pw"]; efut = x @ B["Pe"]; wf_h = wv[:NW][::-1]; wfut = wv[NW:]
                u = mpc.solve(np.array([p.th, p.w_servo]), th_h, v_h, wf_h, p.z, p.v, wfut, efut, u)
            th_h = np.r_[p.th, th_h[:-1]]; v_h = np.r_[p.v, v_h[:-1]]; a = np.array([u / M.THM])
        o, r, term, trunc, info = env.step(a); rows.append(info); RW.append(r); done = term or trunc; k += 1
        if ctrl.startswith("kaskada") and k % 50 == 0: log_sel.append((round(k * DT, 1), chosen, round(sig, 3)))
        for s in he: he[s] = he[s][1:] + [M2.noisy(p.eta_ahead(s[0], p.t, s[1]), rng, he[s][-1])]
        if k % 50 == 0 or done: M.live_write(seed, ctrl, rows, RW, env, done, term)
        if ctrl != "pid2" and k % 25 == 1:
            tf = p.t + DT * np.arange(1, H + 1); Uplan = np.repeat(mpc.Uprev, M.BLK)[:H]
            _, zpl = mpc.sim(np.array([p.th, p.w_servo]), th_h, v_h, wf_h, p.z, p.v, Uplan, wfut)
            M._atomic(M.LIVE / "live_plan.json", dict(t0=round(k * DT, 2), seed=seed, ctrl=ctrl, dt=DT, eta_pred=np.round(efut, 3).tolist(),
                      eta_true=[round(p.eta_LE(t), 3) for t in tf], theta_plan=np.round(np.degrees(Uplan), 2).tolist(), z_pred=np.round(zpl, 3).tolist(),
                      eta_past=np.round(he[S0][-100:], 3).tolist(), time=time.strftime("%H:%M:%S")))
    n = len(rows); h = slice(max(0, n - 2000), n); A = lambda q: np.array([x[q] for x in rows])[h]
    res = dict(term=bool(term), t_upadek=round(n * DT, 2) if term else None)
    if log_sel: res["wybrane_DELTA"] = sorted({c for _, c, _ in log_sel}); res["DELTA_koncowe"] = log_sel[-1][1]; res["blad_1.5m_rms_sr"] = round(float(np.mean([s for _, _, s in log_sel])), 3)
    if not term:
        res.update(D_rel=float(A("D").mean() / env.D_cw - 1), z_min=float(A("z").min()), z_max=float(A("z").max()), sub_min_c=float(A("sub").min() / C),
                   acc_rms=float(np.sqrt((A("acc") ** 2).mean())))
    return res


if __name__ == "__main__":
    t0 = time.time()
    mdl, _ = pickle.loads((HERE / "MPC_IRR2_MODEL.pkl").read_bytes())
    bf = HERE / "MPC_IRR3_BANK.pkl"
    if bf.exists(): bank = pickle.loads(bf.read_bytes())
    else: bank = fit_bank(); bf.write_bytes(pickle.dumps(bank))
    rf = HERE / "MPC_IRR3_RESULT.json"
    out = dict(opis=__doc__, DELTA_TRUE=DELTA_TRUE, wyniki={})
    if rf.exists(): out["wyniki"] = json.loads(rf.read_text(encoding="utf-8")).get("wyniki", {})
    SEEDS = (1, 3, 4, 5, 6); CTRL = ["pid2", "wyrocznia", "d3_bez_korekty", "wspolnie", "kaskada", "kaskada+zapas"]
    for seed in SEEDS:
        for ctrl in CTRL:
            key = f"fala{seed}_{ctrl}"
            if key in out["wyniki"]: continue
            r = run_episode(seed, ctrl, mdl, bank); out["wyniki"][key] = r
            extra = f" | wybrane DELTA {r.get('wybrane_DELTA')} -> {r.get('DELTA_koncowe')}" if "wybrane_DELTA" in r else ""
            print(f"fala {seed} {ctrl:15s}: " + (f"UPADEK po {r['t_upadek']} s" if r["term"] else
                  f"opor {100*r['D_rel']:+.0f}% | z {r['z_min']:.2f}..{r['z_max']:.2f} | zanurz. min {r['sub_min_c']:.2f}c | zacc RMS {r['acc_rms']:.2f}") + extra, flush=True)
            rf.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    summ = {}
    for ctrl in CTRL:
        rs = [out["wyniki"][f"fala{s}_{ctrl}"] for s in SEEDS]; ok = [r for r in rs if not r["term"]]
        summ[ctrl] = dict(przezyl=f"{len(ok)}/{len(rs)}", opor_sr=None if not ok else round(100 * np.mean([r["D_rel"] for r in ok]), 1))
        print(f"PODSUMOWANIE {ctrl:15s}: przezyl {summ[ctrl]['przezyl']}, opor (gdy przezyl) {summ[ctrl]['opor_sr']} %", flush=True)
    out["podsumowanie"] = summ; rf.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("gotowe", round(time.time() - t0), "s")
