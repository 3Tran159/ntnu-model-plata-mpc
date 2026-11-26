# 22.11 (Julek 22:03: "kiedy ten wzor nie dziala"): analiza prob obalenia wzoru. Dla kazdego przebiegu z falsyfikacja.ps1:
# zysk vs ciag M*sr(z''*w) vs ciag + czlon poziomy; stabilnosc okna (P_drag w 1. i 2. polowie okna); okres spotkania; g/(U*we).
# Dodatkowo: test krotkiego okna na T5 0,05 g (seria_zapis\T5_cel0.4905.npy): wzor vs zysk w oknach 1, 2, 4, 8 okresow.
import json, os, glob, numpy as np
D = os.path.dirname(os.path.abspath(__file__)); M = 28.17007; G = 9.81; U = 12.35; PC = 57.03
mapa = {}
for l in open(os.path.join(D, "falsyfikacja_mapa.txt"), encoding="utf-8", errors="ignore"):
    if " = " in l: k, v = l.strip().split(" = ", 1); mapa[k] = v
out = {}
print(f"{'przebieg':16s} {'opis':42s} {'z_rms':>6s} {'ciag':>7s} {'czl2':>6s} {'zysk':>7s} {'zysk-ciag-czl2':>14s} {'P 1/2 pol':>13s} {'g/(U we)':>8s}")
for k, v in mapa.items():
    f = os.path.join(D, "cel_reg_zapis", k + ".json"); s = os.path.join(D, "seria_zapis", k + ".npy")
    if not os.path.exists(f): continue
    o = json.load(open(f))
    if "ciag_W" not in o: print(k, "BLAD/niestabilne"); continue
    b = np.load(s); h = len(b) // 2; p1, p2 = float(b[:h, 1].mean()), float(b[h:, 1].mean())
    T = float(k[1:].split("_")[0]); w0 = 2 * np.pi / T; we = w0 + w0 * w0 / G * U
    r = dict(opis=v, acc=o["acc_rms"], ciag=o["ciag_W"], czlon2=o["czlon2_dokl_W"], zysk=o["zysk_W"], sufit=o["sufit_W"], kor=o["kor"],
             reszta2=o["zysk_W"] - o["ciag_W"] - o["czlon2_dokl_W"], P_pol1=p1, P_pol2=p2, stabilne=abs(p1 - p2) < 0.1 * PC, g_Uwe=G / (U * we), okno_s=float(b[-1, 0] - b[0, 0]))
    out[k] = r
    print(f"{k:16s} {v[:42]:42s} {r['acc']:6.2f} {r['ciag']:7.2f} {r['czlon2']:6.2f} {r['zysk']:7.2f} {r['reszta2']:14.2f} {p1:6.1f}/{p2:6.1f} {r['g_Uwe']:8.2f}{'' if r['stabilne'] else '  NIESTABILNE'}")
# krotkie okna
s = os.path.join(D, "seria_zapis", "T5_cel0.4905.npy")
if os.path.exists(s):
    b = np.load(s); t = b[:, 0]; dt = t[1] - t[0]; Te = 2 * np.pi / 3.2446; out["_krotkie_okna_T5_005g"] = {}
    print("\nKrotkie okna (T5, 0,05 g): okno -> rozrzut (zysk - ciag) miedzy oknami")
    for n in (0.5, 1, 2, 4, 8):
        L = int(round(n * Te / dt)); R = []
        for i0 in range(0, len(b) - L, max(1, L // 2)):
            c = b[i0:i0 + L]; a = c[:, 2] - c[:, 2].mean(); w = c[:, 4] - c[:, 4].mean(); R.append((PC - c[:, 1].mean()) - M * np.mean(a * w))
        R = np.array(R); out["_krotkie_okna_T5_005g"][str(n)] = dict(min=float(R.min()), max=float(R.max()), sd=float(R.std()))
        print(f"  {n:4.1f} okresu: min {R.min():7.2f}  max {R.max():7.2f}  sd {R.std():6.2f} W")
json.dump(out, open(os.path.join(D, "FALSYFIKACJA.json"), "w"), indent=1)
