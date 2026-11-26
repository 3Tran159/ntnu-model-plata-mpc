"""k3_widmo.py - K3 (i K0 z sonda, K0P) na widmie S1-S4 tym samym run() co widmo_s1s4.py koordynatora (agent D, 13.11.2026).
widmo_s1s4.py tylko importowany, nic w nim nie zmieniam; jego wyniki i CALM_90.json tylko czytam.
Przypadki K3 wpisywane do W.CASES na czas przebiegu; W.run() dostaje klase K3 / K0P przez chwilowa podmiane Z.Susp / Z.FaltinsenPlant.
Wyniki: K3_WIDMO\\wyniki\\<przypadek>__<stan>__s<seed>.json (wznowienie pomija gotowe), log K3_WIDMO\\k3_widmo.log, STOP: plik K3_WIDMO\\STOP.
Uzycie:  python k3_widmo.py test                 (2 przypadki x 40 s na S1 - kontrola, ok. 1 min)
         python k3_widmo.py worker K N [rdzen0]  (K-ty z N procesow; rdzen rdzen0+K, domyslnie bez przypinania; priorytet ponizej normalnego)
         python k3_widmo.py summary              (K3_WIDMO\\K3_WIDMO.json + porownanie z WIDMO_S1S4.json, jesli jest)"""
import json, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; ROOT = HERE.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT / "WIDMO_S1S4"))
import widmo_s1s4 as W
import zaw90 as Z
from k3 import K3, K0P
OUT = HERE / "K3_WIDMO"; RES, LOG = OUT / "wyniki", OUT / "k3_widmo.log"
KAPPA = (13.0, 57.0)                                          # W/(rad/s)^2 na pasek: moc silownika kata = kappa * omega^2 (koordynator 20:50, dopasowanie do URANS)
S = dict(fn=0.2, zeta=0.0, stroke=0.5)                       # miekka sprezyna gazowa jak K1_miekkie_f0.2_s0.5, skok +-0,5 m
CASES = {   # "rigid": K0P (sztywny plat, kat z sondy);  "susp": K3 (dwie masy, pradnica polaktywna)
    "K0P_85_sonda3m":            dict(rigid=dict(k_wave=0.85, probe_d=3.0)),       # R3-2: K0_85 z sonda zamiast idealnej wiedzy
    "K0P_85_sonda6m":            dict(rigid=dict(k_wave=0.85, probe_d=6.0)),
    "K3_sky":                    dict(susp=dict(S, c_rel=0.0, c_sky=1.0)),           # polaktywny skyhook, bez katu
    "K3_odzysk":                 dict(susp=dict(S, c_rel=1.0, c_sky=0.0)),           # tylko odzysk (pradnica = tlumienie wody)
    "K3_sky+odzysk":             dict(susp=dict(S, c_rel=0.5, c_sky=1.0)),
    "K3_sky+odzysk+K0_50_sonda": dict(susp=dict(S, c_rel=0.5, c_sky=1.0, k_wave=0.5, probe_d=6.0)),
    "K3_sky+K0_85_sonda6m":      dict(susp=dict(S, c_rel=0.0, c_sky=1.0, k_wave=0.85, probe_d=6.0)),
    "K3_sky+K0_85_idealny":      dict(susp=dict(S, c_rel=0.0, c_sky=1.0, k_wave=0.85, preview="ideal")),
}


def log(s):
    print(s, flush=True)
    with open(LOG, "a", encoding="utf-8") as f: f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + s + "\n")


def run(case, sea, seed, viz=False):
    kw = CASES[case]; old = (W.CASES.get(case), Z.Susp, Z.FaltinsenPlant)
    try:
        if "rigid" in kw:
            K0P.CFG = dict(kw["rigid"], seed=1000 + seed); Z.FaltinsenPlant = K0P; W.CASES[case] = {}; cls = K0P
        else:
            Z.Susp = K3; W.CASES[case] = dict(susp=dict(kw["susp"], seed=1000 + seed)); cls = K3
        if viz: W.VIZ = OUT / "viz"; W.VIZ.mkdir(parents=True, exist_ok=True)
        r = W.run(case, sea, seed, viz=viz); r.update(cls.last); r["koncepcja"] = kw
        return r
    finally:
        if old[0] is None: W.CASES.pop(case, None)
        else: W.CASES[case] = old[0]
        Z.Susp, Z.FaltinsenPlant = old[1], old[2]


def worker(k, nw, core0=None):
    import psutil; me = psutil.Process(); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    if core0 is not None: me.cpu_affinity([core0 + k])
    RES.mkdir(parents=True, exist_ok=True)
    jobs = [(c, s, sd) for sd in W.SEEDS for s in W.SEAS for c in CASES]
    for idx, (c, s, sd) in enumerate(jobs):
        if idx % nw != k: continue
        if (OUT / "STOP").exists(): log(f"w{k}: STOP"); return
        f = RES / f"{c}__{s}__s{sd}.json"
        if f.exists(): continue
        t0 = time.time()
        try:
            r = run(c, s, sd, viz=(sd == 0)); f.write_text(json.dumps(r), encoding="utf-8")
            log(f"w{k}: {c} {s} s{sd}: P {r['P_W']:.2f} W, z'' RMS {r['acc_rms']:.3f}, MSI {r['MSI_2h_pct']:.1f} %, pradnica {r['P_gen_el_W_per_m']:.0f} W/m el., "
                f"kat RMS {r['rate_rms_deg_s']:.1f} deg/s, blad w {r['w_est_err_rel']}, zan.min {r['sub_min']:.2f} m, {time.time() - t0:.0f} s")
        except Exception as e:
            f.write_text(json.dumps(dict(case=c, sea=s, seed=sd, error=str(e))), encoding="utf-8"); log(f"w{k}: {c} {s} s{sd}: BLAD {e}")
    log(f"w{k}: koniec")


def summary():
    ref = W.calm_ref(); rows = [json.loads(p.read_text()) for p in RES.glob("*.json")]; out = {}
    for c in CASES:
        for s in W.SEAS:
            R = [r for r in rows if r["case"] == c and r["sea"] == s and "error" not in r]
            if not R: continue
            m = lambda k: float(np.mean([r[k] for r in R if r.get(k) is not None])) if any(r.get(k) is not None for r in R) else None
            Pdrag_m = m("P_W") / 0.02
            out[f"{c}|{s}"] = dict(n=len(R), dP_pct=100 * (m("P_W") / ref - 1), acc_rms=m("acc_rms"), acc_wk=m("acc_wk_rms"), MSI=m("MSI_2h_pct"),
                                   acc_1_10=m("acc_1_10"), acc_peak=max(r["acc_peak"] for r in R), sub_min=min(r["sub_min"] for r in R),
                                   surv_pct=100 * np.mean([not (r["sub_min"] < W.C or r["bottomed"]) for r in R]), stroke=max(r["stroke_absmax"] for r in R),
                                   P_gen_el_W_per_m=m("P_gen_el_W_per_m"), eta_gen_ZALOZENIE=0.7,
                                   dP_brutto_pct=100 * (m("P_W") / ref - 1), dP_net_pct=100 * ((Pdrag_m - m("P_gen_el_W_per_m")) / (ref / 0.02) - 1),
                                   rate_rms_deg_s=m("rate_rms_deg_s"), w_est_err_rel=m("w_est_err_rel"),
                                   # moc silownika kata P_act = kappa * omega_RMS^2 na pasek 0,02 m, kappa = 13-57 W/(rad/s)^2 (dopasowanie do URANS, R3-3, koordynator 20:50)
                                   P_act_W_strip=[k * np.radians(m("rate_rms_deg_s")) ** 2 for k in KAPPA] if m("rate_rms_deg_s") else None,
                                   P_act_pct_calm=[100 * k * np.radians(m("rate_rms_deg_s")) ** 2 / ref for k in KAPPA] if m("rate_rms_deg_s") else None,
                                   errors=sum(1 for r in rows if r["case"] == c and r["sea"] == s and "error" in r))
    f = ROOT / "WIDMO_S1S4" / "WIDMO_S1S4.json"
    ref_cases = json.loads(f.read_text())["wyniki"] if f.exists() else {}
    (OUT / "K3_WIDMO.json").write_text(json.dumps(dict(P_calm_90_W=ref, wyniki=out, koncepcje=CASES, odniesienie_koordynatora=ref_cases), indent=1), encoding="utf-8")
    for k, v in out.items():
        pa = v["P_act_pct_calm"]; pa = f"{pa[0]:.1f}-{pa[1]:.1f} %" if pa else "-"
        print(f"{k:38s} opor brutto {v['dP_brutto_pct']:+6.1f} %, netto z pradnica (eta 0,7 zalozenie) {v['dP_net_pct']:+6.1f} %, silownik {pa} wody spok.  "
              f"z'' {v['acc_rms']:.3f}  MSI {v['MSI']:.1f} %  przezycie {v['surv_pct']:.0f} %")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    if sys.argv[1] == "worker": worker(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else None)
    elif sys.argv[1] == "summary": summary()
    elif sys.argv[1] == "test":
        W.T_SIM, W.T_SKIP = 40.0, 10.0
        for c in ("K0P_85_sonda3m", "K0P_85_sonda6m", "K3_sky+odzysk+K0_50_sonda"):
            t0 = time.time(); r = run(c, "S1", 0)
            print(c, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items() if k in
                      ("P_W", "acc_rms", "MSI_2h_pct", "sub_min", "stroke_absmax", "P_damper_W_per_m", "P_gen_el_W_per_m", "rate_rms_deg_s", "w_est_err_rel", "kern_lost")},
                  f"{time.time() - t0:.0f} s", flush=True)
