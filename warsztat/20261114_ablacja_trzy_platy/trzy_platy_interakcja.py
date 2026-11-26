"""trzy_platy_interakcja.py - koordynator 16.11 (prosba Julka 13:06): uklad +1:-2:+1 z wplywem platow przednich na tylne, "dodatek jak w NDLL Godo".
NDLL (Godo i Steen 2023; Godo 2024, rozdz. 2.1.1-2.1.2): linia nosna z panelami sladu (slad sztywny, unoszony z U, bez deformacji) + czesc funkcji Greena
od powierzchni swobodnej. W naszym modelu 2D (pasek) odpowiedniki dla platu tylnego w odleglosci s za przednim:
 (1) downwash od wirow splywajacych z koncowek przedniego platu (linia nosna, eliptycznie): w = -2 CL U/(pi AR) * 1/2 (1 + s/sqrt(s^2 + (b'/2)^2)), b' = pi b/4,
     skalowany chwilowa cyrkulacja przedniego platu sprzed s/U;
 (2) fala od cyrkulacji przedniego platu (ta sama teoria co 6.145 w modelu B, zgodna z URANS co do ksztaltu): eta(s) = -A sin(k0 s), A = 2 Gamma/U e^(-k0 h),
     k0 = g/U^2; predkosci na glebokosci h: w = U deta/ds e^(-k0 h), u = -U k0 eta e^(-k0 h); opoznienie 2 s/U (predkosc grupowa U/2 wzgledem lodzi).
 opcja 'ind': wlasny opor indukowany kazdego platu D = L^2/(q pi AR) na metr (3D, quasi-statycznie) - konsekwentnie dla wszystkich platow i dla wody spokojnej.
Odniesienie: ten sam uklad trzech platow w wodzie spokojnej z tym samym dodatkiem (K0 kasuje tez staly downwash). Kadlub nieruchomy, reszty sily i momentu jak w trzy_platy_widmo.py.
Uzycie: python trzy_platy_interakcja.py worker K N rdzen | summary"""
import json, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import trzy_platy_widmo as TW
Z, FP, W, U, G_, BUOY = TW.Z, TW.FP, TW.W, TW.U, TW.G_, TW.BUOY
RES = HERE / "wyniki_trzy_interakcja"; RES.mkdir(exist_ok=True)
AR, B_SPAN, RHO = 25.6, 7.99, 1025.0
H, K0W = 1.09, 9.81 / U ** 2; BP = np.pi * B_SPAN / 4
JOBS = [(v, d, Lt, s, sd) for s in ("S1", "S2", "S3") for sd in (0, 1) for Lt in (15.0, 20.0) for v in ("K0", "G1_lim30") for d in ("int", "int+ind")]
CALM = [("calm", d, Lt) for Lt in (15.0, 20.0) for d in ("int", "int+ind")]


def patch(p):
    p._du, p._dw = 0.0, 0.0; orig = p.gust
    def g(x, t, o=orig, p=p):
        u, w = o(x, t); return u + p._du, w + p._dw
    p.gust = g


def simulate(v, d, Lt, sea, seed, T, skip):
    FP.MASS = Z.MASS100; trim = FP.TH_REF_DEG; L0 = FP.MASS * G_ - BUOY; c = np.array([1.0, -2.0, 1.0])
    xs = np.array([-Lt / 2, 0.0, Lt / 2])            # x rosnie ku rufie: plat 0 = przedni
    if sea is None: P = [Z.FaltinsenPlant(wave_amp=0.0, **Z.VB) for _ in xs]
    else: P = [TW.make(x, sea, seed) for x in xs]
    for p in P: p.reset(theta_deg=trim); p.cmd = np.radians(trim); patch(p)
    dt = P[0].dt; n = int(T / dt); q = P[0].q; kq = q * P[0].slope * P[0].dcl; lim = 0.30 * L0
    Gam0 = L0 / (RHO * U); CL0 = L0 / q; wfar = 2 * CL0 * U / (np.pi * AR)
    Gh = np.full((3, n + 1), Gam0); rec = []
    pairs = [(i, j, xs[j] - xs[i]) for j in range(3) for i in range(3) if xs[i] < xs[j]]
    for it in range(n):
        for j in range(3): P[j]._du, P[j]._dw = 0.0, 0.0
        for i, j, s in pairs:
            r1 = Gh[i, max(0, it - int(round(s / U / dt)))] / Gam0; g2 = Gh[i, max(0, it - int(round(2 * s / U / dt)))]
            P[j]._dw += -wfar * 0.5 * (1 + s / np.sqrt(s * s + (BP / 2) ** 2)) * r1
            A = 2 * g2 / U * np.exp(-K0W * H); dec = np.exp(-K0W * H)
            P[j]._dw += -U * A * K0W * np.cos(K0W * s) * dec; P[j]._du += U * K0W * A * np.sin(K0W * s) * dec
        if it % P[0].tick == 0:
            w = np.array([float(np.mean(p.gust(p.F.xc, p.t)[1])) for p in P]); Wm = 0.0
            if v == "G1_lim30": Wm = float(np.clip(float(c @ w) / 6.0, -lim * U / (2 * kq), lim * U / (2 * kq)))
            for j, p in enumerate(P): p.cmd = np.radians(float(np.clip(trim - np.degrees(w[j] / U) + c[j] * np.degrees(Wm / U), -7.5, 7.5)))
        r = [p.step(free_heave=False) for p in P]
        for j in range(3): Gh[j, it + 1] = r[j]["L"] / (RHO * U)
        if it % 10 == 9:
            Pind = [U * 0.02 * x["L"] ** 2 / (q * np.pi * AR) if d == "int+ind" else 0.0 for x in r]
            rec.append([r[0]["t"]] + [x["L"] for x in r] + [x["P_drag_W_strip"] + Pind[k] for k, x in enumerate(r)] + [x["theta_deg"] for x in r] + [x["sub_true"] for x in r])
    a = np.array(rec); a = a[a[:, 0] > skip]
    Ls, Ps, th, sub = a[:, 1:4], a[:, 4:7], a[:, 7:10], a[:, 10:13]; mt = 3 * FP.MASS; F = Ls.sum(1) - 3 * L0; M = (Ls - L0) @ xs
    return dict(v=v, d=d, Lt=Lt, sea=sea, seed=seed, P_plat=[float(Ps[:, j].mean()) for j in range(3)], P_mean=float(Ps.sum(1).mean() / 3),
                acc_heave=float(F.std() / mt), acc_bow=float(M.std() / (mt * (Lt / 4) ** 2) * (Lt / 2)), L_mean_pct=[float(100 * Ls[:, j].mean() / L0) for j in range(3)],
                dL_std_mid=float(100 * Ls[:, 1].std() / L0), sat_pct=float(100 * np.mean(np.abs(th) > 7.49)), sub_min=float(sub.min()), th_mean=[float(th[:, j].mean()) for j in range(3)])


def worker(k, nw, core):
    try:
        import psutil; pr = psutil.Process(); pr.cpu_affinity([core]); pr.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception as e: print("affinity", e)
    jobs = [("calm",) + j[1:] for j in CALM] + JOBS
    for jn, job in enumerate(jobs):
        if jn % nw != k: continue
        f = RES / ("__".join(map(str, job)) + ".json")
        if f.exists(): continue
        t0 = time.time()
        try:
            if job[0] == "calm": r = simulate("K0", job[1], job[2], None, 0, 20.0, 10.0); r["v"] = "calm"
            else: r = simulate(*job, TW.T_SIM, TW.T_SKIP)
        except Exception as e: r = dict(job=list(job), error=repr(e))
        r["wall"] = time.time() - t0; f.write_text(json.dumps(r), encoding="utf-8")


def summary():
    rows = [json.loads(f.read_text(encoding="utf-8")) for f in RES.glob("*.json")]; out = {}
    calm = {(r["d"], r["Lt"]): r for r in rows if r.get("v") == "calm"}
    for (d, Lt), r in calm.items(): out[f"calm|{d}|{Lt:g}"] = dict(P_plat=[round(x, 2) for x in r["P_plat"]], P_mean=round(r["P_mean"], 2), th=[round(x, 2) for x in r["th_mean"]])
    for v in ("K0", "G1_lim30"):
        for d in ("int", "int+ind"):
            for Lt in (15.0, 20.0):
                for s in ("S1", "S2", "S3"):
                    R = [r for r in rows if r.get("v") == v and r.get("d") == d and r.get("Lt") == Lt and r.get("sea") == s and "error" not in r]
                    if not R or (d, Lt) not in calm: continue
                    Pc = calm[(d, Lt)]["P_mean"]
                    out[f"{v}|{d}|{Lt:g}|{s}"] = dict(n=len(R), dP=round(100 * (np.mean([r["P_mean"] for r in R]) / Pc - 1), 1),
                        dP_plat=[round(100 * (np.mean([r["P_plat"][j] for r in R]) / calm[(d, Lt)]["P_plat"][j] - 1), 1) for j in range(3)],
                        acc_heave=round(float(np.mean([r["acc_heave"] for r in R])), 3), acc_bow=round(float(np.mean([r["acc_bow"] for r in R])), 3),
                        dL_std_mid=round(float(np.mean([r["dL_std_mid"] for r in R])), 1), sat=round(float(np.mean([r["sat_pct"] for r in R])), 2), sub_min=round(min(r["sub_min"] for r in R), 2))
    err = [r for r in rows if "error" in r]
    if err: out["bledy"] = err[:3]
    (HERE / "TRZY_PLATY_INTERAKCJA.json").write_text(json.dumps(out, indent=1), encoding="utf-8"); print(json.dumps(out))


if __name__ == "__main__":
    if sys.argv[1] == "worker": worker(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
    else: summary()
