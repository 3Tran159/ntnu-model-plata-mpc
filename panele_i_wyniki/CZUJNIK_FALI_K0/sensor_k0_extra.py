"""sensor_k0_extra.py - uzupelnienie sensor_k0.py: (1) wieksze k dla czujnika 3 m z wyprzedzeniem serwa 0 / 25 / 50 ms; (2) tabela: zysk przy z'' RMS = 0,36 m/s2
(interpolacja liniowa po k) dla kazdej konfiguracji.  Wynik: SENSOR_K0_SUMMARY.json, SENSOR_K0.png"""
import json, sys
from pathlib import Path
from multiprocessing import Pool
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import sensor_k0 as S
EXTRA = [("d 3 m, szum 2 cm, wyprzedzenie serwa 25 ms", dict(S.S0, d=3.0, t_servo=0.025), (0.25, 0.5, 0.75, 0.87, 1.0, 1.15, 1.3)),
         ("d 3 m, szum 2 cm, wyprzedzenie serwa 50 ms", dict(S.S0, d=3.0, t_servo=0.05), (1.15, 1.3, 1.5)),
         ("d 3 m, szum 2 cm", dict(S.S0, d=3.0), (1.15,))]
def job(a):
    name, sensor, g, j = a; return g, S.run(g, S.PH[j], sensor, seed=1000 * j + int(100 * g))
if __name__ == "__main__":
    out = json.loads(S.OUT.read_text(encoding="utf-8")); ref = out["calm_90_W"]
    with Pool(2) as pool:
        for name, sensor, gains in EXTRA:
            cfg = out.setdefault(name, dict(sensor=sensor, gains={}))["gains"]; todo = [g for g in gains if str(g) not in cfg]
            res = pool.map(job, [(name, sensor, g, j) for g in todo for j in range(4)])
            for g in todo:
                rr = [r for gg, r in res if gg == g]; m = {k: float(np.mean([r[k] for r in rr])) for k in rr[0]}
                for k in ("acc_peak", "rate_max", "th_max", "sat_pct"): m[k] = float(max(r[k] for r in rr))
                for k in ("sub_min", "th_min"): m[k] = float(min(r[k] for r in rr))
                m["dP_pct"] = 100 * (m["P_W"] / ref - 1); cfg[str(g)] = m
            S.OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    summ = {}
    for name, v in out.items():
        if not isinstance(v, dict): continue
        gs = sorted(v["gains"], key=float); acc = np.array([v["gains"][g]["acc_rms"] for g in gs]); dp = np.array([v["gains"][g]["dP_pct"] for g in gs]); kk = np.array([float(g) for g in gs])
        i = int(np.argmin(acc)); s = v["sensor"] or {}; g0 = v["gains"][gs[0]]
        row = dict(margin_ms=None if not s else 1000 * (g0["margin_s"] - s.get("t_servo", 0.0) if g0["margin_s"] < s.get("t_servo", 0.0) else 0.0) , lead_ms=1000 * s.get("t_servo", 0.0) if s and g0["margin_s"] >= s.get("t_servo", 0.0) else 0.0,
                   acc_min=float(acc[i]), k_at_acc_min=float(kk[i]), dP_at_acc_min=float(dp[i]), rate_rms_at_087=v["gains"].get("0.87", {}).get("rate_rms"), sat_max=max(v["gains"][g]["sat_pct"] for g in gs),
                   sub_min=min(v["gains"][g]["sub_min"] for g in gs))
        # punkt z'' = 0,36 na galezi malejacej (k rosnie do minimum)
        a_, d_, k_ = acc[: i + 1], dp[: i + 1], kk[: i + 1]
        if a_.min() <= 0.36 <= a_.max():
            j = int(np.where(a_ <= 0.36)[0][0]); f = (a_[j - 1] - 0.36) / (a_[j - 1] - a_[j]); row.update(dP_at_036=float(d_[j - 1] + f * (d_[j] - d_[j - 1])), k_at_036=float(k_[j - 1] + f * (k_[j] - k_[j - 1])))
        else: row.update(dP_at_036=None, k_at_036=None)
        a75 = 0.75
        if a_.min() <= a75 <= a_.max():
            j = int(np.where(a_ <= a75)[0][0]); f = (a_[j - 1] - a75) / (a_[j - 1] - a_[j]); row["dP_at_075"] = float(d_[j - 1] + f * (d_[j] - d_[j - 1]))
        summ[name] = row
        print(f"{name:48s} zapas/spoznienie {row['margin_ms'] if row['margin_ms'] is not None else 0:+5.0f} ms wyprz {row['lead_ms']:3.0f} | przy 0,36: {row['dP_at_036'] if row['dP_at_036'] is None else round(row['dP_at_036'],1)} % (k {row['k_at_036'] if row['k_at_036'] is None else round(row['k_at_036'],2)}) | przy 0,75: {round(row.get('dP_at_075', float('nan')),1)} | min z'' {row['acc_min']:.2f} przy k {row['k_at_acc_min']} ({row['dP_at_acc_min']:+.1f} %) | kat RMS {row['rate_rms_at_087']} | nasyc {row['sat_max']:.0f} | zan min {row['sub_min']:.2f}")
    (HERE / "SENSOR_K0_SUMMARY.json").write_text(json.dumps(summ, indent=1), encoding="utf-8")
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    for name, st in (("idealny (jak zaw90.py)", "k-o"), ("d 2 m, szum 2 cm (bazowy)", "C0-s"), ("d 2 m, szum 5 cm", "C0:^"), ("d 1 m, szum 2 cm", "C3-v"), ("bazowy, opoznienie 50 ms", "C1-d"), ("bazowy, opoznienie 100 ms", "C1:x"),
                     ("d 3 m, szum 2 cm, wyprzedzenie serwa 25 ms", "C2--p"), ("d 3 m, szum 2 cm, wyprzedzenie serwa 50 ms", "C2-*")):
        v = out[name]["gains"]; gs = sorted(v, key=float); ax.plot([v[g]["acc_rms"] for g in gs], [v[g]["dP_pct"] for g in gs], st, label=name, ms=5, lw=1.2)
    ax.axvline(0.36, color="gray", ls="--", lw=.8); ax.text(0.37, -21, "0,36 m/s2 (Jetfoil)", color="gray", fontsize=8); ax.axhline(0, color="gray", lw=.6)
    ax.set_xlabel("przyspieszenie pionowe kadluba RMS [m/s2]"); ax.set_ylabel("zmiana mocy oporu wzgledem wody spokojnej 90 % [%]")
    ax.set_title("K0 z czujnikiem fali przed platem: w modelu B, 90 %, fala regularna 0,73 m, T 5 s"); ax.legend(fontsize=7.5); ax.grid(alpha=.3); ax.set_xlim(0, 1.6)
    fig.tight_layout(); fig.savefig(HERE / "SENSOR_K0.png", dpi=130)
