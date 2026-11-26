"""widmo_s1s4.py - Krok 3 na widmie (koordynator, 13.11.2026, zgoda Julka 18:30). Wszystko "w modelu" (Faltinsen B), nic z URANS.
Stany morza S1-S4 z karty stalych (JONSWAP gamma 3,3, czolowo, 24 kn), obciazenie 90 %, 5 realizacji (seed 0-4) x 1260 s (pierwsze 60 s odrzucone).
Koncepcje: PID1 (sztywny), K0 (gladki sterownik, kasowanie k), K1 (zawieszenie bierne, w tym "Baja" z dlugim skokiem), K0+K1.
Model i klasy z zaw90.py (agent D) - bez zmian; tu tylko fala nieregularna, miary widmowe (ISO 2631-1 Wk, Wf, MSI 2 h) i zapis przebiegow do wizualizacji.
Uzycie:  python widmo_s1s4.py worker K N   (K-ty z N procesow; rdzen 18+K, priorytet ponizej normalnego)
         python widmo_s1s4.py summary       (zbiorcze WIDMO_S1S4.json + tabela .md)
Wynik: wyniki/<przypadek>__<stan>__s<seed>.json (zapis po kazdym przebiegu; wznowienie pomija gotowe), przebiegi do wizualizacji: viz/*.json (seed 0).
Stop: plik STOP w tym katalogu. Log: widmo.log"""
import json, sys, time, ctypes, os
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE.parent / "ZAWIESZENIE"))
import zaw90 as Z
FP, U, G, BUOY = Z.FP, Z.U, Z.G, Z.BUOY
RES, VIZ, LOG = HERE / "wyniki", HERE / "viz", HERE / "widmo.log"
SEAS = {"S1": (1.5, 5.0), "S2": (1.0, 3.5), "S3": (1.5, 8.0), "S4": (2.25, 6.0)}
SEEDS, T_SIM, T_SKIP, LOAD, C = range(5), 1260.0, 60.0, 0.9, 0.312
PID1 = (2.01, 0.196)
CASES = {"PID1_sztywny": {}, "K0_50": dict(gain=0.5), "K0_85": dict(gain=0.85), "K0_100": dict(gain=1.0),
         "K1_miekkie_f0.2_s0.5": dict(susp=dict(fn=0.2, zeta=0.5, stroke=0.5)),
         "K1_Baja_f0.3_s1.0": dict(susp=dict(fn=0.3, zeta=0.5, stroke=1.0)),
         "K0_50+K1_f0.2": dict(gain=0.5, susp=dict(fn=0.2, zeta=0.5, stroke=0.5)),
         "K0_85+K1_Baja": dict(gain=0.85, susp=dict(fn=0.3, zeta=0.5, stroke=1.0))}


def log(s):
    with open(LOG, "a", encoding="utf-8") as f: f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + s + "\n")


def iso_weight(x, fs, kind):
    """ISO 2631-1 (1997): filtr Wk (komfort) albo Wf (choroba morska) w dziedzinie czestotliwosci; zwraca przebieg wazony"""
    p = dict(Wk=(0.4, 100, 12.5, 12.5, 0.63, 2.37, 0.91, 3.35, 0.91), Wf=(0.08, 0.63, np.inf, 0.25, 0.86, 0.0625, 0.80, 0.1, 0.80))[kind]
    f1, f2, f3, f4, q4, f5, q5, f6, q6 = p; X = np.fft.rfft(x - x.mean()); f = np.fft.rfftfreq(len(x), 1 / fs); s = 2j * np.pi * f
    w = lambda fr: 2 * np.pi * fr
    H = s ** 2 / (s ** 2 + np.sqrt(2) * w(f1) * s + w(f1) ** 2) * w(f2) ** 2 / (s ** 2 + np.sqrt(2) * w(f2) * s + w(f2) ** 2)
    H *= (1 + (s / w(f3) if np.isfinite(f3) else 0)) / (1 + s / (q4 * w(f4)) + s ** 2 / w(f4) ** 2)
    H *= (s ** 2 + s * w(f5) / q5 + w(f5) ** 2) / (s ** 2 + s * w(f6) / q6 + w(f6) ** 2)      # stopien w gore: nisko (f5/f6)^2, wysoko 1
    return np.fft.irfft(X * H, len(x))


def run(case, sea, seed, viz=False):
    kw = CASES[case]; gain, susp = kw.get("gain", 0.0), kw.get("susp"); Hs, Tp = SEAS[sea]
    FP.MASS = LOAD * Z.MASS100
    P = (Z.Susp if susp else Z.FaltinsenPlant)(**Z.VB); wp = 2 * np.pi / Tp; P.set_irregular(Hs=Hs, Tp=Tp, gamma=3.3, seed=100 * int(sea[1]) + seed, N=80, wmin=0.5 * wp, wmax=3.0 * wp)   # pasmo 0,5-3 wp, 80 skladowych
    cl_eq = (FP.MASS * G - BUOY) / P.q; trim = FP.TH_REF_DEG + float(np.degrees((cl_eq - FP.CL_REF) / (P.slope * P.dcl)))
    if susp: P.setup(**susp)
    P.reset(theta_deg=trim); ie = 0.0; n = int(round(T_SIM / P.dt)); rec = np.zeros((n // 10, 9)); j = 0; Ediss = 0.0
    for i in range(n):
        free = P.t >= 1.0
        if i % P.tick == 0:
            zc = P.zh if susp else P.z; cmd = trim
            if free: ie = float(np.clip(ie + (-zc) * P.tick * P.dt, -1, 1)); cmd = trim + PID1[0] * (-zc) + PID1[1] * ie
            if gain: cmd -= gain * float(np.degrees(float(np.mean(P.gust(P.F.xc, P.t)[1])) / U))
            P.cmd = np.radians(float(np.clip(cmd, -7.5, 7.5)))
        r = P.step(free_heave=free)
        if i % 10 == 9:          # zapis 100 Hz
            acc = P.ah if susp else (r["L"] + BUOY) / FP.MASS - G
            d = (P.z - P.zh) if susp else 0.0
            pd = P.cs * (P.v - P.vh) ** 2 if susp else 0.0
            rec[j] = (r["t"], r["eta_LE"], r["z"], P.zh if susp else r["z"], r["theta_deg"], acc, r["P_drag_W_strip"], r["sub_true"], d); j += 1
            Ediss += pd * 0.01
            if not np.isfinite(acc): raise RuntimeError("niestabilne")
    a = rec[:j]; b = a[a[:, 0] > T_SKIP]; fs = 100.0; acc = b[:, 5]; T = b[-1, 0] - b[0, 0]
    pk = acc[1:-1][(np.abs(acc[1:-1]) >= np.abs(acc[:-2])) & (np.abs(acc[1:-1]) >= np.abs(acc[2:]))]; pk = np.sort(np.abs(pk))[::-1]
    awk, awf = iso_weight(acc, fs, "Wk"), iso_weight(acc, fs, "Wf")
    out = dict(case=case, sea=sea, seed=seed, Hs=Hs, Tp=Tp, Hs_model=float(P.irr["Hs_check"]), T_s=float(T), P_W=float(b[:, 6].mean()),
               acc_rms=float(acc.std()), acc_peak=float(np.abs(acc).max()), acc_1_10=float(pk[:max(1, len(pk) // 10)].mean()),
               acc_wk_rms=float(awk.std()), acc_wf_rms=float(awf.std()), MSI_2h_pct=float(awf.std() * np.sqrt(7200) / 3),
               z_hull_std=float(b[:, 3].std()), sub_min=float(b[:, 7].min()), t_below_1c_pct=float(100 * np.mean(b[:, 7] < C)),
               emerged=bool(b[:, 7].min() < 0), th_min=float(b[:, 4].min()), th_max=float(b[:, 4].max()),
               sat_pct=float(100 * np.mean(np.abs(b[:, 4]) > 7.49)), stroke_absmax=float(np.abs(b[:, 8]).max()),
               bottomed=bool(susp is not None and np.abs(b[:, 8]).max() > susp["stroke"]), P_damper_W_per_m=float(Ediss / a[-1, 0]))
    if viz:
        w = (a[:, 0] >= 300) & (a[:, 0] < 360); v = a[w][::5]      # 60 s przy 20 Hz
        (VIZ / f"{case}__{sea}.json").write_text(json.dumps(dict(case=case, sea=sea, cols=["t", "eta_LE", "z_foil", "z_hull", "theta_deg", "acc", "P_W", "sub", "stroke"],
                                                               data=np.round(v, 4).tolist())), encoding="utf-8")
    return out


def calm_ref():
    f = HERE / "CALM_90.json"
    if f.exists(): return json.loads(f.read_text())["P_W"]
    FP.MASS = LOAD * Z.MASS100; P = Z.FaltinsenPlant(wave_amp=0.0, **Z.VB)
    cl_eq = (FP.MASS * G - BUOY) / P.q; trim = FP.TH_REF_DEG + float(np.degrees((cl_eq - FP.CL_REF) / (P.slope * P.dcl))); P.reset(theta_deg=trim)
    Pw = [P.step(free_heave=False)["P_drag_W_strip"] for _ in range(20000)]; v = float(np.mean(Pw[10000:]))
    f.write_text(json.dumps(dict(P_W=v, trim_deg=trim))); return v


def worker(k, nw):
    import psutil; me = psutil.Process(); me.cpu_affinity([18 + k]); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    RES.mkdir(exist_ok=True); VIZ.mkdir(exist_ok=True)
    jobs = [(c, s, sd) for sd in SEEDS for s in SEAS for c in CASES]
    for idx, (c, s, sd) in enumerate(jobs):
        if idx % nw != k: continue
        if (HERE / "STOP").exists(): log(f"w{k}: STOP"); return
        f = RES / f"{c}__{s}__s{sd}.json"
        if f.exists(): continue
        t0 = time.time()
        try:
            r = run(c, s, sd, viz=(sd == 0)); f.write_text(json.dumps(r), encoding="utf-8")
            log(f"w{k}: {c} {s} s{sd}: P {r['P_W']:.2f} W, z'' RMS {r['acc_rms']:.3f} (Wk {r['acc_wk_rms']:.3f}), MSI {r['MSI_2h_pct']:.1f} %, zan.min {r['sub_min']:.2f} m, {time.time() - t0:.0f} s")
        except Exception as e:
            f.write_text(json.dumps(dict(case=c, sea=s, seed=sd, error=str(e))), encoding="utf-8"); log(f"w{k}: {c} {s} s{sd}: BLAD {e}")
    log(f"w{k}: koniec")


def summary():
    ref = calm_ref(); rows = [json.loads(p.read_text()) for p in RES.glob("*.json")]; out = {}
    for c in CASES:
        for s in SEAS:
            R = [r for r in rows if r["case"] == c and r["sea"] == s and "error" not in r]
            if not R: continue
            m = lambda k: float(np.mean([r[k] for r in R])); rg = lambda k: [float(min(r[k] for r in R)), float(max(r[k] for r in R))]
            out[f"{c}|{s}"] = dict(n=len(R), dP_pct=100 * (m("P_W") / ref - 1), dP_range=[100 * (x / ref - 1) for x in rg("P_W")], acc_rms=m("acc_rms"),
                                   acc_wk=m("acc_wk_rms"), MSI=m("MSI_2h_pct"), acc_1_10=m("acc_1_10"), acc_peak=max(r["acc_peak"] for r in R),
                                   sub_min=min(r["sub_min"] for r in R), below_1c_pct=m("t_below_1c_pct"), surv_pct=100 * np.mean([not (r["sub_min"] < C or r["bottomed"]) for r in R]),
                                   sat_pct=m("sat_pct"), stroke=max(r["stroke_absmax"] for r in R), P_damper=m("P_damper_W_per_m"),
                                   errors=sum(1 for r in rows if r["case"] == c and r["sea"] == s and "error" in r))
    (HERE / "WIDMO_S1S4.json").write_text(json.dumps(dict(P_calm_90_W=ref, wyniki=out), indent=1), encoding="utf-8"); print(json.dumps(out, indent=0)[:3000])


if __name__ == "__main__":
    if sys.argv[1] == "worker": worker(int(sys.argv[2]), int(sys.argv[3]))
    elif sys.argv[1] == "summary": summary()
    elif sys.argv[1] == "test":
        print(calm_ref()); t0 = time.time()
        T_SIM = 70.0; r = run("K0_85+K1_Baja", "S2", 0); print(r, time.time() - t0)
        fs = 100; f = 0.516; tt = np.arange(0, 200, 1 / fs); x = np.sin(2 * np.pi * f * tt)
        print("Wk(0,52 Hz)", iso_weight(x, fs, "Wk")[5000:15000].std() / x.std(), "Wf", iso_weight(x, fs, "Wf")[5000:15000].std() / x.std())
