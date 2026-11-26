"""mbpo_residual.py - MBPO krok 1 (z fizyka jako podstawa): model wirowy + POPRAWKA nauczona z URANS.

Idea (Julek 12.11): model wirowy jest za optymistyczny, gdy plat "jedzie" z fala (PID1: -17 % mocy oporu).
Zamiast uczyc caly model od zera (klasyczne MBPO, sieci na stanach), uczymy tylko RESZTE: dL, dFx = URANS - model wirowy,
przy tych samych zadanych ruchach (kat theta(t), nurzanie z(t), v(t), fala dopasowana z eta nad LE).

Krok 1 (ten skrypt, bez nowego CFD):
  a) odtworzenie kinematyczne kazdego przebiegu URANS w modelu wirowym -> reszty co 10 ms
  b) cechy: theta, dtheta/dt, v, z, eta_LE, w fali na poziomie sredniej powierzchni, lokalne zanurzenie, CL_lin modelu,
     opoznione o 20/50/100 ms (pamiec sladu), kwadraty glownych cech
  c) regresja grzbietowa (ridge) i mala siec (2x64, torch), walidacja "zostaw jeden przebieg" (leave-one-run-out)
  d) zapis: MBPO_RESIDUAL.json (R2 reszt, blad sredniej mocy oporu przed/po poprawce, per przebieg), mbpo_residual.pkl (model)
Krok 2 (osobno): ResidualPlant w petli zamknietej -> test kroku 5 (PID1/PID3/BASE2) i trening agenta na poprawionym modelu.
Wszystko "w modelu wirowym (poprawionym z URANS)".
"""
import csv, json, pickle, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import vortex_plant as VP
from vortex_plant import Plant, C, DEPTH, U, SPAN, MASS, BUOY, CL_REF, CL_MAX, K_STALL, FS_S, FS_K

OVR = Path(r"T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset_runs")
RUNS = ["OVS_PID_BASE2", "OVS_PID_PRBS1", "OVS_PID_SINE_A2", "OVS_PID1_GODO", "OVS_PID3_GODO", "OVS_PID2_GODO", "OVS_CALM_PID2"]
T_REL = 1.9368            # zwolnienie nurzania
LAGS = (2, 5, 10)         # x 10 ms
EVERY = 10                # probkowanie cech co 10 ms


def load(run):
    f = OVR / run / "history.csv"
    if not f.exists(): return None
    R = {}
    for r in csv.DictReader(open(f)):
        try: R[round(float(r["time_s"]), 6)] = r
        except Exception: pass
    t = np.array(sorted(R)); c = lambda k: np.array([float(R[x][k]) for x in t])
    d = dict(t=t, th=np.radians(c("theta_deg")), thd=np.radians(c("theta_rate_deg_s")), z=c("z_m"), v=c("v_m_s"),
             CL=c("AF_CL"), Fx=c("AF_Fx") / SPAN, eta=c("GODO_eta_at_LE"))
    if t[-1] < 2 * T_REL + 0.5: return None
    return d


def wave_fit(d, P0):
    m = d["t"] > 0.3; n = int(((d["t"][m][-1] - d["t"][m][0]) // P0.Te) * round(P0.Te / 1e-3))
    if n < 100: return 0.0, 0.0
    e = d["eta"][m][:n]; tt = d["t"][m][:n]
    zc = 2 * np.mean((e - e.mean()) * np.exp(-1j * P0.ome * tt)); return abs(zc), -np.angle(zc)


def kin_step(p, th, w_, z, v):
    """krok modelu wirowego z ZADANYM ruchem (bez serwa i bez rownania nurzania) - jak Plant.step po aktualizacji stanu"""
    dt = p.dt; p.th, p.w_servo, p.z, p.v = th, w_, z, v
    t_new = p.t + dt; F = p.F
    ug, wg = p.gust(F.xv, t_new); _, wc = p.gust(F.xc, t_new); hd = -v; thp = th - p.th_ref
    rw = p.S["wave"].step(0.0, 0.0, 0.0, gust_c=wc, gust_v=(ug, wg)); rp = p.S["pitch"].step(thp, w_, 0.0)
    rh = p.S["heave"].step(0.0, 0.0, hd); rf = p.Sf.step(thp, w_, hd, gust_c=wc, gust_v=(ug, wg))
    cal = p.cal; Ls = 0.0
    for key, r in (("wave", rw), ("pitch", rp), ("heave", rh)):
        buf = p.buf[key]; buf.append(r["L"]); nd = int(round(cal["d_" + key + "_s"] / dt))
        Ld = buf[-1 - nd] if len(buf) > nd else buf[0]
        if len(buf) > nd + 2: del buf[0]
        Ls += cal["k_" + key] * Ld
    CL_lin = CL_REF + Ls / p.q
    s_loc = max(0.05, p.eta_LE(t_new) - (z - DEPTH)); CL_lin *= float(np.interp(s_loc, FS_S, FS_K))
    if CL_lin > 0.9 * CL_MAX: CL_sat = 0.9 * CL_MAX + 0.1 * CL_MAX * np.tanh((CL_lin - 0.9 * CL_MAX) / (0.1 * CL_MAX))
    else: CL_sat = CL_lin
    Fx = rf["Fx"] + (p.cd_visc + p.k_pol * (CL_sat - CL_REF) ** 2 + K_STALL * max(0.0, CL_lin - CL_sat) ** 2) * p.q
    p.t = t_new; p.n += 1
    return CL_sat, CL_lin, Fx, s_loc


def base_feats(th, thd, v, z, eta, w, sub, cll):
    return np.c_[th - VP.np.radians(VP.TH_REF_DEG), thd, v, z, eta, w, sub - DEPTH, cll - CL_REF]


def features(B):
    """B: macierz cech bazowych (co 10 ms) -> cechy z opoznieniami i kwadratami"""
    n = len(B); cols = [B]
    for L in LAGS:
        S = np.vstack([np.repeat(B[:1], L, 0), B[:-L]])[:, [0, 1, 2, 5]]; cols.append(S)
    q = B[:, [0, 1, 2, 5, 7]]; cols.append(q * q); cols.append((B[:, 0] * B[:, 2])[:, None]); cols.append((B[:, 0] * B[:, 5])[:, None])
    return np.hstack(cols)


def replay_run(run):
    d = load(run)
    if d is None: return None
    P0 = Plant(); a, beta = wave_fit(d, P0)
    p = Plant(wave_amp=a, wave_phase=beta); p.reset(theta_deg=np.degrees(d["th"][0]), z=d["z"][0], v=d["v"][0], t=d["t"][0] - p.dt)
    out = []
    for i in range(len(d["t"])):
        CLm, CLl, Fxm, sub = kin_step(p, d["th"][i], d["thd"][i], d["z"][i], d["v"][i])
        if i % EVERY == 0:
            out.append((d["t"][i], d["th"][i], d["thd"][i], d["v"][i], d["z"][i], d["eta"][i], p.w_surface(d["t"][i]), sub, CLl,
                        CLm * p.q, d["CL"][i] * p.q, Fxm, d["Fx"][i]))
    A = np.array(out)
    keep = A[:, 0] >= T_REL
    return dict(run=run, a=a, beta=beta, A=A, keep=keep, q=p.q)


class Ridge:
    def fit(s, X, y, lam):
        s.mu, s.sd = X.mean(0), X.std(0) + 1e-9; Z = (X - s.mu) / s.sd; s.ym = y.mean(0)
        s.W = np.linalg.solve(Z.T @ Z + lam * len(Z) * np.eye(Z.shape[1]), Z.T @ (y - s.ym)); return s
    def predict(s, X): return ((X - s.mu) / s.sd) @ s.W + s.ym


def mlp_fit(X, y, epochs=400, seed=0):
    import torch
    torch.manual_seed(seed); torch.set_num_threads(1)
    mu, sd = X.mean(0), X.std(0) + 1e-9; ym, ys = y.mean(0), y.std(0) + 1e-9
    Xt = torch.tensor((X - mu) / sd, dtype=torch.float32); yt = torch.tensor((y - ym) / ys, dtype=torch.float32)
    net = torch.nn.Sequential(torch.nn.Linear(X.shape[1], 64), torch.nn.Tanh(), torch.nn.Linear(64, 64), torch.nn.Tanh(), torch.nn.Linear(64, y.shape[1]))
    opt = torch.optim.Adam(net.parameters(), lr=2e-3, weight_decay=1e-3)
    for ep in range(epochs):
        perm = torch.randperm(len(Xt))
        for k in range(0, len(Xt), 512):
            idx = perm[k:k + 512]; opt.zero_grad(); loss = ((net(Xt[idx]) - yt[idx]) ** 2).mean(); loss.backward(); opt.step()
    net.eval()
    def pred(Xn):
        with torch.no_grad(): return net(torch.tensor((Xn - mu) / sd, dtype=torch.float32)).numpy() * ys + ym
    return pred, dict(state=net.state_dict(), mu=mu, sd=sd, ym=ym, ys=ys, nin=X.shape[1])


def r2(y, yh): return float(1 - np.sum((y - yh) ** 2) / max(1e-12, np.sum((y - y.mean()) ** 2)))


if __name__ == "__main__":
    t0 = time.time(); data = {}
    for run in RUNS:
        r = replay_run(run)
        if r is None: print(run, "brak / za krotki", flush=True); continue
        data[run] = r
        A, k = r["A"], r["keep"]
        print(f"{run:18s} fala a={r['a']:.3f} m | srednio: L URANS {A[k,10].mean():8.1f} model {A[k,9].mean():8.1f} N/m | "
              f"Fx URANS {A[k,12].mean():7.1f} model {A[k,11].mean():7.1f} N/m | moc oporu URANS {U*A[k,12].mean()*SPAN:5.1f} W, model {U*A[k,11].mean()*SPAN:5.1f} W", flush=True)
    sets = {}
    for run, r in data.items():
        A, k = r["A"], r["keep"]
        X = features(base_feats(*[A[:, j] for j in (1, 2, 3, 4, 5, 6, 7, 8)]))[k]
        Y = np.c_[A[k, 10] - A[k, 9], A[k, 12] - A[k, 11]]          # dL, dFx [N/m]
        sets[run] = (X, Y, A[k])
    res = dict(opis=__doc__, przebiegi={}, cv={})
    for meth in ("ridge", "mlp"):
        for test in sets:
            Xtr = np.vstack([sets[r][0] for r in sets if r != test]); Ytr = np.vstack([sets[r][1] for r in sets if r != test])
            Xte, Yte, Ate = sets[test]
            if meth == "ridge": Yh = Ridge().fit(Xtr, Ytr, 1e-3).predict(Xte)
            else: Yh = mlp_fit(Xtr, Ytr)[0](Xte)
            P_u = U * Ate[:, 12].mean() * SPAN; P_m = U * Ate[:, 11].mean() * SPAN; P_c = U * (Ate[:, 11] + Yh[:, 1]).mean() * SPAN
            res["cv"][f"{meth}|{test}"] = dict(R2_dL=r2(Yte[:, 0], Yh[:, 0]), R2_dFx=r2(Yte[:, 1], Yh[:, 1]),
                                              P_URANS_W=round(P_u, 2), P_model_W=round(P_m, 2), P_poprawiony_W=round(P_c, 2),
                                              blad_model_pct=round(100 * (P_m / P_u - 1), 1), blad_poprawiony_pct=round(100 * (P_c / P_u - 1), 1))
            c = res["cv"][f"{meth}|{test}"]
            print(f"CV {meth:5s} test={test:18s}: R2 dL {c['R2_dL']:+.2f}, dFx {c['R2_dFx']:+.2f} | moc oporu URANS {c['P_URANS_W']} W, model {c['P_model_W']} W ({c['blad_model_pct']:+.1f} %), "
                  f"poprawiony {c['P_poprawiony_W']} W ({c['blad_poprawiony_pct']:+.1f} %)", flush=True)
    Xall = np.vstack([s[0] for s in sets.values()]); Yall = np.vstack([s[1] for s in sets.values()])
    rid = Ridge().fit(Xall, Yall, 1e-3); _, mlp = mlp_fit(Xall, Yall)
    pickle.dump(dict(ridge=rid, mlp=mlp, lags=LAGS, every=EVERY, runs=list(sets)), open(HERE / "mbpo_residual.pkl", "wb"))
    res["przebiegi"] = {r: dict(a=data[r]["a"], n=int(data[r]["keep"].sum())) for r in data}
    (HERE / "MBPO_RESIDUAL.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print("gotowe", round(time.time() - t0), "s")
