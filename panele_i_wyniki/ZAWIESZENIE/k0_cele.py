"""k0_cele.py - K0 (sterowanie katem z wyprzedzeniem fali, sztywny wspornik) na widmie S1-S4: przemiatanie wzmocnienia k,
zeby dla kazdego stanu morza i celu komfortu 0,02-0,10 g znalezc najwiekszy zysk na oporze; plus rozbicie zysku na czesc
od pionowej predkosci wody w i od poziomej u (wariant wave_u=False). Agent D, 15.11.2026.
Ten sam run() co widmo_s1s4.py koordynatora (tylko import, nic tam nie zmieniam). Stany morza jako zastepcze miejsca:
S2 ~ Sztokholm, S1 ~ Trondheim, S3/S4 ~ Bergen (do czasu danych falowych dla tras).
Wyniki: K0_CELE\\wyniki\\<przypadek>__<stan>__s<seed>.json (wznowienie pomija gotowe), log K0_CELE\\k0_cele.log, STOP: plik K0_CELE\\STOP.
Uzycie: python k0_cele.py worker K N RDZEN0 | summary"""
import json, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; ROOT = HERE.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT / "WIDMO_S1S4"))
import widmo_s1s4 as W
import zaw90 as Z
OUT = HERE / "K0_CELE"; RES, LOG = OUT / "wyniki", OUT / "k0_cele.log"
GAINS = (0.0, 0.25, 0.5, 0.65, 0.75, 0.85, 0.92, 1.0)
CASES = {f"K0_k{g:.2f}": dict(gain=g, wave_u=True) for g in GAINS}
CASES.update({f"K0_k{g:.2f}_bez_u": dict(gain=g, wave_u=False) for g in (0.0, 0.5, 0.85)})
TARGETS_G = (0.02, 0.03, 0.05, 0.07, 0.10)
MIEJSCA = {"S2": "Sztokholm (zastepczo)", "S1": "Trondheim (zastepczo)", "S3": "Bergen, martwa fala (zastepczo)", "S4": "Bergen, wysoka fala (zastepczo)"}


def log(s):
    print(s, flush=True)
    with open(LOG, "a", encoding="utf-8") as f: f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + s + "\n")


def run(case, sea, seed):
    kw = CASES[case]; old = (W.CASES.get(case), Z.VB)
    try:
        W.CASES[case] = dict(gain=kw["gain"]) if kw["gain"] else {}
        Z.VB = dict(Z.VB, wave_u=kw["wave_u"])
        r = W.run(case, sea, seed); r.update(gain=kw["gain"], wave_u=kw["wave_u"]); return r
    finally:
        if old[0] is None: W.CASES.pop(case, None)
        else: W.CASES[case] = old[0]
        Z.VB = old[1]


def worker(k, nw, core0):
    import psutil; me = psutil.Process(); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); me.cpu_affinity([core0 + k])
    RES.mkdir(parents=True, exist_ok=True)
    jobs = [(c, s, sd) for sd in W.SEEDS for s in W.SEAS for c in CASES]
    for idx, (c, s, sd) in enumerate(jobs):
        if idx % nw != k: continue
        if (OUT / "STOP").exists(): log(f"w{k}: STOP"); return
        f = RES / f"{c}__{s}__s{sd}.json"
        if f.exists(): continue
        t0 = time.time()
        try:
            r = run(c, s, sd); f.write_text(json.dumps(r), encoding="utf-8")
            log(f"w{k}: {c} {s} s{sd}: P {r['P_W']:.2f} W, z'' RMS {r['acc_rms']:.3f}, zan.min {r['sub_min']:.2f} m, nasyc. {r['sat_pct']:.1f} %, {time.time() - t0:.0f} s")
        except Exception as e:
            f.write_text(json.dumps(dict(case=c, sea=s, seed=sd, error=str(e))), encoding="utf-8"); log(f"w{k}: {c} {s} s{sd}: BLAD {e}")
    log(f"w{k}: koniec")


def summary():
    ref = W.calm_ref(); rows = [json.loads(p.read_text()) for p in RES.glob("*.json")]; tab = {}
    for c, kw in CASES.items():
        for s in W.SEAS:
            R = [r for r in rows if r["case"] == c and r["sea"] == s and "error" not in r]
            if not R: continue
            m = lambda q: float(np.mean([r[q] for r in R]))
            tab[f"{c}|{s}"] = dict(gain=kw["gain"], wave_u=kw["wave_u"], n=len(R), dP_pct=100 * (m("P_W") / ref - 1), acc_rms=m("acc_rms"),
                                   acc_wf=m("acc_wf_rms"), MSI=m("MSI_2h_pct"), sub_min=min(r["sub_min"] for r in R),
                                   emerged_pct=100 * np.mean([r["emerged"] for r in R]), sat_pct=m("sat_pct"))
    best = {}
    for s in W.SEAS:          # krzywa zysk(z'') z wave_u=True, interpolacja liniowa po k; cel: najwiekszy zysk przy z'' <= cel
        pts = sorted([(v["gain"], v["acc_rms"], v["dP_pct"]) for kk, v in tab.items() if kk.endswith("|" + s) and v["wave_u"]])
        if len(pts) < 2: continue
        g = np.array([p[0] for p in pts]); a = np.array([p[1] for p in pts]); d = np.array([p[2] for p in pts])
        gf = np.linspace(g.min(), g.max(), 401); af = np.interp(gf, g, a); df = np.interp(gf, g, d)
        best[s] = {"miejsce": MIEJSCA[s]}
        for tg in TARGETS_G:
            ok = af <= tg * W.G
            best[s][f"{tg:.2f} g"] = dict(k=float(gf[ok][np.argmin(df[ok])]), dP_pct=float(df[ok].min())) if ok.any() else None
        us = {}
        for gg in (0.0, 0.5, 0.85):
            a1, a0 = tab.get(f"K0_k{gg:.2f}|{s}"), tab.get(f"K0_k{gg:.2f}_bez_u|{s}")
            if a1 and a0: us[f"k{gg:.2f}"] = dict(dP_z_u=a1["dP_pct"], dP_bez_u=a0["dP_pct"], czesc_od_u=a1["dP_pct"] - a0["dP_pct"])
        best[s]["rozbicie_w_u"] = us
    (OUT / "K0_CELE.json").write_text(json.dumps(dict(P_calm_W=ref, tabela=tab, najlepsze=best), indent=1), encoding="utf-8")
    print(json.dumps(best, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "worker": worker(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
    elif sys.argv[1] == "summary": summary()
    elif sys.argv[1] == "test":
        W.T_SIM = 40.0; W.T_SKIP = 10.0
        for c in ("K0_k0.85", "K0_k0.85_bez_u"): t0 = time.time(); r = run(c, "S1", 0); print(c, round(r["P_W"], 2), round(r["acc_rms"], 3), round(time.time() - t0, 1), "s")
