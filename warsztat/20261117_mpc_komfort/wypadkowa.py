# 19.11 (Julek 13:47): kryterium komfortu od WYPADKOWEJ przyspieszen (pionowe + wzdluzne), w modelu Faltinsena B.
# Wzdluzne: a_x = -(Fx - srednie Fx) / M_calej_lodzi (predkosc w modelu stala, wiec a_x liczone z sily; M = 100 % masy na pasek = 31,30 kg).
# Widmo S1-S3: z zapisanych przebiegow MPC (viz_act57_wa*), fala Godo: z SUFIT_MODEL_REG.json (sufit_model_reg.py).
# Wynik: WYPADKOWA.json - krzywe zysk(z'' RMS) i zysk(wypadkowa RMS) oraz zysk przy 0,49 m/s2 dla obu kryteriow.
import json, glob, os, numpy as np
H = os.path.dirname(os.path.abspath(__file__)); U, PC, MTOT, LIM = 12.3466667, 57.056, 1408.5036 / 0.9 * 0.02, 0.4905
out = {}
for sea in ("S1", "S2", "S3"):
    pts = []
    for wa in ("0.03", "0.1", "0.3", "1", "3"):
        rr = []
        for f in sorted(glob.glob(os.path.join(H, f"viz_act57_wa{wa}", f"{sea}__s*.json"))):
            d = json.load(open(f)); c = {k: i for i, k in enumerate(d["cols"])}; A = np.array(d["data"]); t = A[:, c["t"]]
            m = t > 30.0; acc = A[m, c["acc"]]; P = A[m, c["P_foil_W"]]; ax = -(P - P.mean()) / U / MTOT
            rr.append((acc.std(), ax.std(), np.sqrt(acc.var() + ax.var()), PC - P.mean(), np.corrcoef(acc - acc.mean(), ax)[0, 1]))
        if rr: pts.append([float(wa)] + [float(x) for x in np.mean(rr, 0)])
    out[sea] = dict(kolumny=["W_A", "acc_rms", "ax_rms", "wyp_rms", "zysk_W", "kor_acc_ax"], punkty=pts)
f = os.path.join(H, "SUFIT_MODEL_REG.json")
if os.path.exists(f):
    R = json.load(open(f)); pts = []
    for k, v in sorted(R.items(), key=lambda kv: float(kv[0])):
        if "ax_rms" in v: pts.append([float(k), v["acc_rms"], v["ax_rms"], v["wyp_rms"], v["zysk_W"], v["kor_acc_ax"]])
    out["GODO"] = dict(kolumny=["W_A", "acc_rms", "ax_rms", "wyp_rms", "zysk_W", "kor_acc_ax"], punkty=pts)
for k, v in out.items():
    p = np.array(v["punkty"])
    if len(p) < 2: continue
    pc = 57.03 if k == "GODO" else PC
    for nm, col in (("pion", 1), ("wypadkowa", 3)):
        i = np.argsort(p[:, col]); x, y = p[i, col], p[i, 4]
        v[f"zysk_przy_0.49_{nm}_W"] = float(np.interp(LIM, x, y)) if x[0] <= LIM <= x[-1] else None
        v[f"min_{nm}"] = float(x[0])
    print(k)
    for r in v["punkty"]: print("   W_A %5.2f  pion %.3f  wzdluz %.3f  wypadkowa %.3f  zysk %6.2f W (%5.1f %%)  kor %+.2f" % (r[0], r[1], r[2], r[3], r[4], 100 * r[4] / pc, r[5]))
    a, b = v.get("zysk_przy_0.49_pion_W"), v.get("zysk_przy_0.49_wypadkowa_W")
    print("   przy 0,49 m/s2: tylko pion", None if a is None else round(a, 2), "W | wypadkowa", None if b is None else round(b, 2), "W | min wypadkowej", round(v["min_wypadkowa"], 3))
json.dump(out, open(os.path.join(H, "WYPADKOWA.json"), "w"), indent=1)

