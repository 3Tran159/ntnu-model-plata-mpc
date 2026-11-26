"""awaryjny.py - zlecenie C-Z5 (skrzynka 14.11 07:45): tryb awaryjny filtru Wienera w petli zamknietej przy zmianie stanu morza.
Wszystko "w modelu" (Faltinsen B, 90 %, plat sztywny, PID1 + kasowanie 85 % jak K0_85 w widmo_s1s4.py). Sonda 3 m przed krawedzia natarcia, 100 Hz, szum 1 cm.
Fala: stan A przez 365 s, liniowe przejscie 10 s (360-370 s), potem stan B do 665 s; te same realizacje co WIDMO_S1S4 (seed 100 nr + s, pasmo 0,5-3 wp, 80 skladowych),
obie na wspolnej osi czasu (jak w adaptacja.py). Czas 0 w wynikach = srodek przejscia (365 s). Pierwsze 60 s odrzucone.
Warianty szacunku pionowej predkosci wody:
  bank          - bank 7 filtrow Wienera (okresy szczytu 3,0-9,0 s), wybor co 10 s z okna 60 s wg czestosci szczytu f_p (adaptacja.choose)
  ogolny        - jeden filtr wspolny S1-S4
  wzorzec       - najlepszy filtr banku dla stanu A do chwili 0, potem najlepszy dla stanu B (wybor bezblednie i natychmiast)
  awaryjny_XX   - bank jak wyzej + przelaczenie na filtr wspolny, gdy f_p z okna 20 s i z okna 120 s roznia sie o wiecej niz XX % (|ln(f20/f120)| > ln(1 + XX/100));
                  sprawdzane co 2 s, tryb awaryjny trzymany co najmniej 10 s od ostatniego przekroczenia progu
  ideal         - dokladna predkosc wody (odniesienie)
Uzycie: python awaryjny.py worker K N | summary.  Wynik: wyniki_awaryjny/*.json, AWARYJNY.json, log awaryjny.log"""
import json, sys, time, pickle
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "ZAWIESZENIE"))
import widmo_sensor as S, wiener_vs_fizyka as V, adaptacja as A
W = S.W; FP, U, G, BUOY = S.FP, S.U, S.G, S.BUOY; SEAS = S.SEAS
RES, LOG, CACHE = HERE / "wyniki_awaryjny", HERE / "awaryjny.log", HERE / "awaryjny_filtry.pkl"
T0, T_SIM, T_SKIP, D, SIG, GAIN = 365.0, 665.0, 60.0, 3.0, 0.01, 0.85
SEG = ((-300, 0), (0, 30), (30, 120), (120, 300))
BEST = {"S1": "Tp5.2", "S2": "Tp3.6", "S3": "Tp7.5", "S4": "Tp6.2"}       # najlepszy filtr banku dla stanu (ADAPTACJA.json)
VARS = ("ideal", "bank", "ogolny", "wzorzec", "awaryjny_15", "awaryjny_25", "awaryjny_40")
JOBS = [(v, tr, sd) for sd in range(3) for tr in (("S3", "S2"), ("S2", "S3")) for v in VARS]


def filters():
    if CACHE.exists(): return pickle.loads(CACHE.read_bytes())
    B = {f"Tp{tp:g}": A.member(1.5, tp, 9500 + 10 * i) for i, tp in enumerate(A.GRID)}
    tr = [(e, w, 1.0 / w.std()) for s in SEAS for e, w in [A.sig(*SEAS[s], 9000 + 10 * int(s[1]) + j, 300.0) for j in range(5)]]
    out = dict(B=B, hgen=V.wiener(tr, SIG, 0)); CACHE.write_bytes(pickle.dumps(out)); return out


def run(var, s1, s2, seed):
    F = None if var == "ideal" else filters()
    P1 = S.comps(s1, 100 * int(s1[1]) + seed); P2 = S.comps(s2, 100 * int(s2[1]) + seed); P = P1; I1, I2 = P1.irr, P2.irr
    I = {k: np.concatenate([I1[k], I2[k]]) for k in ("a", "w", "k", "kx", "ky", "mu", "we", "eps")}; I["Hs_check"] = 0.0; P.irr = I; a1, a2 = I1["a"].copy(), I2["a"].copy(); n1 = len(a1)
    cl_eq = (FP.MASS * G - BUOY) / P.q; trim = FP.TH_REF_DEG + float(np.degrees((cl_eq - FP.CL_REF) / (P.slope * P.dcl)))
    I["a"][:n1] = a1; I["a"][n1:] = 0.0; P.reset(theta_deg=trim); ie = 0.0; n = int(round(T_SIM / P.dt)); nt = n // P.tick; rec = np.zeros((n // 10, 7)); j = 0
    rng = np.random.default_rng(50000 + seed); meas = np.zeros(nt); kt = 0; wg = wt = 0.0; thr = float(var.split("_")[1]) / 100 if var.startswith("awaryjny") else None
    cur = BEST[s1]; fb = False; fb_until = -1.0; rlast = -1.0
    for i in range(n):
        free = P.t >= 1.0; r = min(1.0, max(0.0, (P.t - (T0 - 5.0)) / 10.0))
        if r != rlast: I["a"][:n1] = a1 * (1 - r); I["a"][n1:] = a2 * r; rlast = r
        if i % P.tick == 0:
            cmd = trim
            if free: ie = float(np.clip(ie + (-P.z) * P.tick * P.dt, -1, 1)); cmd = trim + W.PID1[0] * (-P.z) + W.PID1[1] * ie
            wt = float(np.mean(P.gust(P.F.xc, P.t)[1]))
            if var == "ideal": wg = wt
            else:
                meas[kt] = P.eta_ahead(D) + SIG * rng.standard_normal(); kt += 1
                if var in ("bank",) or thr is not None:
                    if kt % 1000 == 0 and kt >= 6000: cur = A.choose(F["B"], meas[kt - 6000:kt])
                    if thr is not None and kt % 200 == 0 and kt >= 12000:
                        if abs(np.log(A.fpeak(meas[kt - 2000:kt]) / A.fpeak(meas[kt - 12000:kt]))) > np.log(1 + thr): fb_until = P.t + 10.0
                        fb = P.t < fb_until
                elif var == "wzorzec": cur = BEST[s1] if P.t < T0 else BEST[s2]
                h = F["hgen"] if (var == "ogolny" or fb) else F["B"][cur]["h"]; L = min(len(h), kt); wg = float(h[:L] @ meas[kt - L:kt][::-1])
            cmd -= GAIN * float(np.degrees(wg / U)); P.cmd = np.radians(float(np.clip(cmd, -7.5, 7.5)))
        o = P.step(free_heave=free)
        if i % 10 == 9:
            rec[j] = (o["t"] - T0, (o["L"] + BUOY) / FP.MASS - G, o["P_drag_W_strip"], o["sub_true"], wg - wt, wt, 1.0 if fb else 0.0); j += 1
            if not np.isfinite(rec[j - 1, 1]): raise RuntimeError("niestabilne")
    b = rec[:j]; out = dict(var=var, s1=s1, s2=s2, seed=seed, seg={})
    for a, c in SEG:
        q = b[(b[:, 0] >= a) & (b[:, 0] < c)]
        out["seg"][f"{a}..{c}"] = dict(P_W=float(q[:, 2].mean()), acc_rms=float(q[:, 1].std()), acc_peak=float(np.abs(q[:, 1]).max()), w_err_rms=float(np.sqrt(np.mean(q[:, 4] ** 2))),
                                      w_rms=float(np.sqrt(np.mean(q[:, 5] ** 2))), sub_min=float(q[:, 3].min()), awaryjny_pct=float(100 * q[:, 6].mean()))
    return out


def worker(k, nw):
    RES.mkdir(exist_ok=True)
    for idx, (v, (s1, s2), sd) in enumerate(JOBS):
        f = RES / f"{v}__{s1}-{s2}__s{sd}.json"
        if idx % nw != k or f.exists(): continue
        if (HERE / "STOP").exists(): return
        t0 = time.time()
        try: r = run(v, s1, s2, sd); msg = " | ".join(f"{k2}: {100 * (x['P_W'] / 57.056 - 1):+.1f} %, {x['acc_rms']:.3f}, blad {x['w_err_rms']:.3f}, aw. {x['awaryjny_pct']:.0f} %" for k2, x in r["seg"].items())
        except Exception as e: r = dict(var=v, s1=s1, s2=s2, seed=sd, error=repr(e)); msg = f"BLAD {e!r}"
        f.write_text(json.dumps(r), encoding="utf-8")
        with open(LOG, "a", encoding="utf-8") as fl: fl.write(time.strftime("%Y-%m-%d %H:%M:%S ") + f"w{k}: {v} {s1}->{s2} s{sd}: {msg}, {time.time() - t0:.0f} s\n")


def summary():
    ref = W.calm_ref(); rows = [json.loads(p.read_text()) for p in sorted(RES.glob("*.json"))]; out = {}
    for s1, s2 in (("S3", "S2"), ("S2", "S3")):
        for v in VARS:
            R = [r for r in rows if r["var"] == v and r["s1"] == s1 and r.get("seg")]
            if not R: continue
            o = {}
            for a, c in SEG:
                k = f"{a}..{c}"; m = lambda key: float(np.mean([r["seg"][k][key] for r in R]))
                o[k] = dict(n=len(R), dP_pct=100 * (m("P_W") / ref - 1), acc_rms=m("acc_rms"), acc_peak=max(r["seg"][k]["acc_peak"] for r in R), w_err_rms=m("w_err_rms"),
                            w_err_pct=100 * m("w_err_rms") / m("w_rms"), sub_min=min(r["seg"][k]["sub_min"] for r in R), awaryjny_pct=m("awaryjny_pct"))
            out[f"{s1}->{s2}|{v}"] = o
            print(f"{s1}->{s2} {v:12s} n={len(R)}: " + " | ".join(f"{k}: {x['dP_pct']:+5.1f} %, z'' {x['acc_rms']:.3f}, blad {x['w_err_rms']:.3f} m/s ({x['w_err_pct']:.0f} %), aw. {x['awaryjny_pct']:.0f} %" for k, x in o.items()))
    (HERE / "AWARYJNY.json").write_text(json.dumps(dict(P_calm_90_W=ref, errors=[r for r in rows if "error" in r], wyniki=out), indent=1), encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1] == "worker": worker(int(sys.argv[2]), int(sys.argv[3]))
    elif sys.argv[1] == "summary": summary()
    elif sys.argv[1] == "test":
        filters(); T0, T_SIM = 130.0, 180.0; SEG = ((-60, 0), (0, 30), (30, 50))
        for v in ("bank", "awaryjny_25"):
            t0 = time.time(); r = run(v, "S3", "S2", 0); print(v, {k: (round(x["P_W"], 1), round(x["acc_rms"], 3), round(x["w_err_rms"], 3), round(x["awaryjny_pct"])) for k, x in r["seg"].items()}, round(time.time() - t0), flush=True)
