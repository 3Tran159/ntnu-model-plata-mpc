"""trzy_platy_widmo.py - koordynator 16.11 (zgoda Julka 11:18): uklad +1:-2:+1 na widmie S1-S4 w modelu Faltinsena B.
Trzy platy na osobnych wspornikach w x = -L, 0, +L; to samo pole fali przesuniete w przestrzeni (faza skladowej + kx*x). Kadlub nieruchomy:
liczymy opor trzech platow, reszte sumy sil (nurzanie) i momentu (kolysanie). Bez wplywu platow na siebie (wersja 1).
Warianty: K0 (G=0: kazdy kasuje swoj podmuch), G1_lim30 (tryb +1:-2:+1, sila platu srodkowego obcieta do +-30 % L0), G1 (bez obciecia),
oraz 'staly' - jeden plat nieruchomy (kat staly, bez nurzania) jako sufit. 100 % obciazenia na plat, 660 s, pierwsze 60 s odrzucone.
Uzycie: python trzy_platy_widmo.py worker K N rdzen | summary"""
import json, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(Path(r"T:\NTNU_GODO_CONTROL_20261109\60_PANELE_I_WYNIKI") / "ZAWIESZENIE")); sys.path.insert(0, str(Path(r"T:\NTNU_GODO_CONTROL_20261109\60_PANELE_I_WYNIKI") / "WIDMO_S1S4"))
import zaw90 as Z
import widmo_s1s4 as W
FP, U, G_, BUOY = Z.FP, Z.U, Z.G, Z.BUOY
RES = HERE / "wyniki_trzy_widmo"; RES.mkdir(exist_ok=True)
T_SIM, T_SKIP = 660.0, 60.0
JOBS = [(v, Lt, s, sd) for s in ("S1", "S2", "S3", "S4") for sd in (0, 1) for Lt in (15.0, 20.0) for v in ("K0", "G1_lim30", "G1")]
JOBS += [("staly", 0.0, s, sd) for s in ("S1", "S2", "S3", "S4") for sd in (0, 1)]


def make(x, sea, seed):
    Hs, Tp = W.SEAS[sea]; P = Z.FaltinsenPlant(**Z.VB); P.set_irregular(Hs=Hs, Tp=Tp, gamma=3.3, seed=100 * int(sea[1]) + seed)
    P.irr["eps"] = P.irr["eps"] + P.irr["kx"] * x
    return P


def run(v, Lt, sea, seed):
    FP.MASS = Z.MASS100; trim = FP.TH_REF_DEG; L0 = FP.MASS * G_ - BUOY
    xs = np.array([0.0]) if v == "staly" else np.array([-Lt / 2, 0.0, Lt / 2]); c = np.array([1.0, -2.0, 1.0])
    P = [make(x, sea, seed) for x in xs]
    for p in P: p.reset(theta_deg=trim); p.cmd = np.radians(trim)
    kq = P[0].q * P[0].slope * P[0].dcl; n = int(T_SIM / P[0].dt); rec = []; lim = 0.30 * L0
    for i in range(n):
        if i % P[0].tick == 0 and v != "staly":
            w = np.array([float(np.mean(p.gust(p.F.xc, p.t)[1])) for p in P]); Wm = float(c @ w) / 6.0
            if v == "K0": Wm = 0.0
            if v == "G1_lim30": Wm = float(np.clip(Wm, -lim / (2 * kq / U), lim / (2 * kq / U)))
            for j, p in enumerate(P): p.cmd = np.radians(float(np.clip(trim - np.degrees(w[j] / U) + c[j] * np.degrees(Wm / U), -7.5, 7.5)))
        r = [p.step(free_heave=False) for p in P]
        if i % 10 == 9: rec.append([r[0]["t"]] + [x["L"] for x in r] + [x["P_drag_W_strip"] for x in r] + [x["theta_deg"] for x in r] + [x["sub_true"] for x in r])
    a = np.array(rec); a = a[a[:, 0] > T_SKIP]; m = len(xs)
    Ls, Ps, th, sub = a[:, 1:1 + m], a[:, 1 + m:1 + 2 * m], a[:, 1 + 2 * m:1 + 3 * m], a[:, 1 + 3 * m:1 + 4 * m]
    F = Ls.sum(1) - m * L0; M = (Ls - L0) @ xs; mt = m * FP.MASS
    out = dict(v=v, Lt=Lt, sea=sea, seed=seed, P_mean=float(Ps.sum(1).mean() / m), dL_std_pct=[float(100 * Ls[:, j].std() / L0) for j in range(m)],
               dL_max_pct=[float(100 * np.abs(Ls[:, j] - L0).max() / L0) for j in range(m)], acc_heave=float(F.std() / mt),
               acc_bow=float(M.std() / (mt * max(Lt / 4, 1e-9) ** 2) * (Lt / 2)) if m == 3 else 0.0,
               sat_pct=float(100 * np.mean(np.abs(th) > 7.49)), sub_min=float(sub.min()))
    return out


def calm():
    FP.MASS = Z.MASS100; P = Z.FaltinsenPlant(wave_amp=0.0, **Z.VB); P.reset(theta_deg=FP.TH_REF_DEG); P.cmd = np.radians(FP.TH_REF_DEG)
    return float(np.mean([P.step(free_heave=False)["P_drag_W_strip"] for _ in range(20000)][10000:]))


def worker(k, n, core):
    try:
        import psutil; p = psutil.Process(); p.cpu_affinity([core]); p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception as e: print("affinity", e)
    for j, job in enumerate(JOBS):
        if j % n != k: continue
        f = RES / ("__".join(map(str, job)) + ".json")
        if f.exists(): continue
        t0 = time.time()
        try: r = run(*job)
        except Exception as e: r = dict(v=job[0], Lt=job[1], sea=job[2], seed=job[3], error=repr(e))
        r["wall"] = time.time() - t0; f.write_text(json.dumps(r), encoding="utf-8")


def summary():
    Pc = calm(); rows = [json.loads(f.read_text(encoding="utf-8")) for f in RES.glob("*.json")]; out = {"P_calm": Pc}
    for r in rows:
        if "error" in r: out[f'{r["v"]}|{r["Lt"]:g}|{r["sea"]}|{r["seed"]}'] = r["error"]; continue
    keys = sorted({(r["v"], r["Lt"], r["sea"]) for r in rows if "error" not in r})
    for v, Lt, s in keys:
        R = [r for r in rows if "error" not in r and (r["v"], r["Lt"], r["sea"]) == (v, Lt, s)]
        out[f"{v}|{Lt:g}|{s}"] = dict(n=len(R), dP=round(100 * (np.mean([r["P_mean"] for r in R]) / Pc - 1), 1), acc_heave=round(float(np.mean([r["acc_heave"] for r in R])), 3),
                                     acc_bow=round(float(np.mean([r["acc_bow"] for r in R])), 3), dL_std_mid=round(float(np.mean([r["dL_std_pct"][min(1, len(r["dL_std_pct"]) - 1)] for r in R])), 1),
                                     dL_max=round(float(max(max(r["dL_max_pct"]) for r in R)), 1), sat=round(float(np.mean([r["sat_pct"] for r in R])), 2), sub_min=round(min(r["sub_min"] for r in R), 2))
    (HERE / "TRZY_PLATY_WIDMO.json").write_text(json.dumps(out, indent=1), encoding="utf-8"); print(json.dumps(out))


if __name__ == "__main__":
    if sys.argv[1] == "worker": worker(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
    else: summary()
