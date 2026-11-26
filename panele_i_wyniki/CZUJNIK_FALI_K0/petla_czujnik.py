"""petla_czujnik.py - zlecenie C-Z2 (skrzynka 13.11 21:55): petla zamknieta K0 85 % (plat sztywny, PID1, obciazenie 90 %) na widmie S1-S4 z sonda fali,
cztery warianty szacunku pionowej predkosci wody na placie:  ideal / fizyka_D (k3.probe_kernel) / Wiener_ogolny (jeden filtr S1-S4) / Wiener_stanowy.
Wszystko "w modelu" (Faltinsen B). Petla i miary jak widmo_s1s4.run (koordynator) dla przypadku K0_85; roznica tylko w zrodle predkosci wody.
Sonda: wzniesienie d m przed krawedzia natarcia, 100 Hz, szum bialy 1 cm (ziarno 50000 + seed), bez opoznienia - jak K0P w k3.py. Bez poprawki na polozenie plata (jak D).
Filtry Wienera: wiener_vs_fizyka.wiener, 150 wspolczynnikow, projekt z szumem 1 cm, zapisy uczace o INNYCH ziarnach (9000 + 10 nr + 0..4, po 300 s).
Realizacje testowe: seed 100 nr + s, pasmo 0,5-3 wp, 80 skladowych; T_SIM 660 s, pierwsze 60 s odrzucone (10 min miar).
Uzycie: python petla_czujnik.py worker K N | summary.   Wynik: wyniki_petla/<wariant>_d<d>__<stan>__s<seed>.json (wznowienie pomija gotowe), log petla_czujnik.log, PETLA_CZUJNIK.json"""
import json, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "ZAWIESZENIE"))
import widmo_sensor as S, wiener_vs_fizyka as V
from k3 import probe_kernel
W = S.W; FP, U, G, BUOY = S.FP, S.U, S.G, S.BUOY; SEAS = S.SEAS; C = 0.312
RES, LOG = HERE / "wyniki_petla", HERE / "petla_czujnik.log"
T_SIM, T_SKIP, SIGMA, GAIN = 660.0, 60.0, 0.01, 0.85
VARS = ("ideal", "fizyka_D", "Wiener_ogolny", "Wiener_stanowy")
JOBS = [(v, s, sd, 3.0) for sd in (0, 1, 2) for s in SEAS for v in VARS]
JOBS += [(v, s, 0, 6.0) for s in SEAS for v in ("fizyka_D", "Wiener_ogolny")]            # dodatek: sonda 6 m, 1 realizacja
JOBS += [(v, s, 0, 1.5) for s in SEAS for v in ("Wiener_ogolny", "Wiener_stanowy")]      # dodatek: sonda 1,5 m, 1 realizacja


def kernel(var, sea, d):
    if var == "fizyka_D":
        P = S.comps(sea, 0); return probe_kernel(d + float(np.mean(P.F.xc)), dt=0.01)[0]
    seas = list(SEAS) if var == "Wiener_ogolny" else [sea]; tr = []
    for s in seas:
        for j in range(5):
            P = S.comps(s, 9000 + 10 * int(s[1]) + j); _, e, w = S.signals(P, d, 300.0); tr.append((e, w, 1.0 / w.std() if var == "Wiener_ogolny" else 1.0))
    return V.wiener(tr, SIGMA, 0)


def run(var, sea, seed, d):
    kern = None if var == "ideal" else kernel(var, sea, d)
    P = S.comps(sea, 100 * int(sea[1]) + seed); cl_eq = (FP.MASS * G - BUOY) / P.q; trim = FP.TH_REF_DEG + float(np.degrees((cl_eq - FP.CL_REF) / (P.slope * P.dcl)))
    P.reset(theta_deg=trim); ie = 0.0; n = int(round(T_SIM / P.dt)); rec = np.zeros((n // 10, 7)); j = 0; rng = np.random.default_rng(50000 + seed)
    buf = None if kern is None else np.zeros(len(kern)); wg = wt = 0.0
    for i in range(n):
        free = P.t >= 1.0
        if i % P.tick == 0:
            cmd = trim
            if free: ie = float(np.clip(ie + (-P.z) * P.tick * P.dt, -1, 1)); cmd = trim + W.PID1[0] * (-P.z) + W.PID1[1] * ie
            wt = float(np.mean(P.gust(P.F.xc, P.t)[1]))
            if kern is None: wg = wt
            else:
                buf[1:] = buf[:-1]; buf[0] = P.eta_ahead(d) + SIGMA * rng.standard_normal(); wg = float(kern @ buf)
            cmd -= GAIN * float(np.degrees(wg / U)); P.cmd = np.radians(float(np.clip(cmd, -7.5, 7.5)))
        r = P.step(free_heave=free)
        if i % 10 == 9:
            rec[j] = (r["t"], r["z"], r["theta_deg"], (r["L"] + BUOY) / FP.MASS - G, r["P_drag_W_strip"], r["sub_true"], wg - wt); j += 1
            if not np.isfinite(rec[j - 1, 3]): raise RuntimeError("niestabilne")
    b = rec[:j]; b = b[b[:, 0] > T_SKIP]; acc = b[:, 3]; fs = 100.0
    pk = acc[1:-1][(np.abs(acc[1:-1]) >= np.abs(acc[:-2])) & (np.abs(acc[1:-1]) >= np.abs(acc[2:]))]; pk = np.sort(np.abs(pk))[::-1]
    awk, awf = W.iso_weight(acc, fs, "Wk"), W.iso_weight(acc, fs, "Wf"); wtrue_ms = None
    return dict(var=var, sea=sea, seed=seed, d=d, sigma=SIGMA, gain=GAIN, Hs_model=float(P.irr["Hs_check"]), T_s=float(b[-1, 0] - b[0, 0]), P_W=float(b[:, 4].mean()),
                acc_rms=float(acc.std()), acc_peak=float(np.abs(acc).max()), acc_1_10=float(pk[:max(1, len(pk) // 10)].mean()), acc_wk_rms=float(awk.std()),
                acc_wf_rms=float(awf.std()), MSI_2h_pct=float(awf.std() * np.sqrt(7200) / 3), z_std=float(b[:, 1].std()), sub_min=float(b[:, 5].min()),
                t_below_1c_pct=float(100 * np.mean(b[:, 5] < C)), th_min=float(b[:, 2].min()), th_max=float(b[:, 2].max()), sat_pct=float(100 * np.mean(np.abs(b[:, 2]) > 7.49)),
                rate_rms_deg_s=float(np.gradient(b[:, 2], 0.01).std()), w_err_rms=float(np.sqrt(np.mean(b[:, 6] ** 2))))


def worker(k, nw):
    RES.mkdir(exist_ok=True)
    for idx, (v, s, sd, d) in enumerate(JOBS):
        f = RES / f"{v}_d{d:g}__{s}__s{sd}.json"
        if idx % nw != k or f.exists(): continue
        if (HERE / "STOP").exists(): return
        t0 = time.time()
        try: r = run(v, s, sd, d); msg = f"P {r['P_W']:.2f} W, z'' RMS {r['acc_rms']:.3f} (Wk {r['acc_wk_rms']:.3f}), blad w {r['w_err_rms']:.3f} m/s, zan.min {r['sub_min']:.2f}"
        except Exception as e: r = dict(var=v, sea=s, seed=sd, d=d, error=str(e)); msg = f"BLAD {e}"
        f.write_text(json.dumps(r), encoding="utf-8")
        with open(LOG, "a", encoding="utf-8") as fl: fl.write(time.strftime("%Y-%m-%d %H:%M:%S ") + f"w{k}: {v} d{d:g} {s} s{sd}: {msg}, {time.time() - t0:.0f} s\n")


def summary():
    ref = W.calm_ref(); rows = [json.loads(p.read_text()) for p in sorted(RES.glob("*.json"))]; out = {}
    for d in (3.0, 6.0, 1.5):
        for s in SEAS:
            for v in VARS:
                R = [r for r in rows if r["var"] == v and r["sea"] == s and r["d"] == d and "error" not in r]
                if not R: continue
                m = lambda k: float(np.mean([r[k] for r in R]))
                o = dict(n=len(R), dP_pct=100 * (m("P_W") / ref - 1), dP_range=[100 * (min(r["P_W"] for r in R) / ref - 1), 100 * (max(r["P_W"] for r in R) / ref - 1)], acc_rms=m("acc_rms"),
                         acc_rms_range=[min(r["acc_rms"] for r in R), max(r["acc_rms"] for r in R)], acc_wk=m("acc_wk_rms"), MSI=m("MSI_2h_pct"), acc_1_10=m("acc_1_10"),
                         acc_peak=max(r["acc_peak"] for r in R), sub_min=min(r["sub_min"] for r in R), below_1c_pct=m("t_below_1c_pct"), sat_pct=m("sat_pct"), rate=m("rate_rms_deg_s"), w_err=m("w_err_rms"))
                out[f"d{d:g}|{s}|{v}"] = o
                print(f"d {d:g} m {s} {v:15s} n={o['n']}: dP {o['dP_pct']:+6.1f} %, z'' RMS {o['acc_rms']:.3f}, Wk {o['acc_wk']:.3f}, MSI {o['MSI']:.1f} %, 1/10 {o['acc_1_10']:.2f}, szczyt {o['acc_peak']:.2f}, zan.min {o['sub_min']:.2f} m, <1c {o['below_1c_pct']:.2f} %, kat {o['rate']:.1f} deg/s, nasyc. {o['sat_pct']:.2f} %, blad w {o['w_err']:.3f} m/s")
    (HERE / "PETLA_CZUJNIK.json").write_text(json.dumps(dict(P_calm_90_W=ref, errors=[r for r in rows if "error" in r], wyniki=out), indent=1), encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1] == "worker": worker(int(sys.argv[2]), int(sys.argv[3]))
    elif sys.argv[1] == "summary": summary()
    elif sys.argv[1] == "test":
        T_SIM, T_SKIP = 30.0, 10.0
        for v in VARS:
            t0 = time.time(); r = run(v, "S2", 0, 3.0); print(v, round(r["P_W"], 2), round(r["acc_rms"], 3), round(r["w_err_rms"], 3), round(time.time() - t0, 1), flush=True)
