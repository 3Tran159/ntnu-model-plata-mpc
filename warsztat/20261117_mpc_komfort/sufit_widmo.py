# 19.11 (Julek: "policz ten wzor na widmie tez"): sufit zysku na falach nieregularnych S1-S3, MPC W_A 0,03...3, w modelu Faltinsena B.
# w(t) na glebokosci plata z eta nad krawedzia natarcia: kazda skladowa o czestosci spotkania we -> w0 = g(-1+sqrt(1+4 we U/g))/(2U), k = w0^2/g,
# w^ = i * w0 * exp(-k h) * eta^  (fala czolowa, teoria liniowa, h = srednie zanurzenie 1,09 - srednie z).
import json, glob, os, numpy as np, psutil
psutil.Process().cpu_affinity([22])
H = os.path.dirname(os.path.abspath(__file__)); U, G, M, PC = 12.3466667, 9.81, 1408.5 * 0.02, 57.056
out = {}
for wa in ("0.03", "0.1", "0.3", "1", "3"):
    for sea in ("S1", "S2", "S3"):
        rows = []
        for f in sorted(glob.glob(os.path.join(H, f"viz_act57_wa{wa}", f"{sea}__s*.json"))):
            d = json.load(open(f)); c = {k: i for i, k in enumerate(d["cols"])}; A = np.array(d["data"])
            t, eta, acc, P, z = A[:, c["t"]], A[:, c["eta_LE"]], A[:, c["acc"]], A[:, c["P_foil_W"]], A[:, c["z_foil"]]
            dt = t[1] - t[0]; n = len(t); h = 1.09 - z.mean()
            E = np.fft.rfft(eta - eta.mean()); we = 2 * np.pi * np.fft.rfftfreq(n, dt)
            w0 = G * (-1 + np.sqrt(1 + 4 * we * U / G)) / (2 * U); k = w0 * w0 / G
            w = np.fft.irfft(1j * w0 * np.exp(-k * h) * E, n)
            m = (t > t[0] + 10) & (t < t[-1] - 10)
            a = acc[m] - acc[m].mean(); ww = w[m] - w[m].mean()
            rows.append(dict(zysk=PC - P[m].mean(), ciag=M * np.mean(a * ww), sufit=M * a.std() * ww.std(), kor=np.corrcoef(a, ww)[0, 1], acc=a.std(), w_rms=ww.std(), h=h))
        if not rows: continue
        r = {k: float(np.mean([x[k] for x in rows])) for k in rows[0]}; r["n"] = len(rows); out[f"WA{wa}|{sea}"] = r
        print(f"W_A {wa:>4s} {sea}: acc {r['acc']:.2f} w_rms {r['w_rms']:.3f} kor {r['kor']:+.2f} | zysk {r['zysk']:6.2f} W | M<acc*w> {r['ciag']:6.2f} W | sufit {r['sufit']:6.2f} W | h {r['h']:.2f} m", flush=True)
json.dump(out, open(os.path.join(H, "SUFIT_WIDMO.json"), "w"), indent=1)
