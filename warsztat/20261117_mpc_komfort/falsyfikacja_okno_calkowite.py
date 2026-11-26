# 23.11 13:30: falsyfikacja przeliczona na oknie z CALKOWITA liczba okresow spotkania (ostatnie N*Te, N = floor(dostepne/Te)).
# Powod: okno 20 s = 10,3 okresu dawalo M*g*sr(w) do 6,7 W (H 2 m) - sr(w) != 0 przy niecalkowitym oknie, a M*g = 276 N.
import os, json, glob, numpy as np
D = os.path.dirname(os.path.abspath(__file__)); M = 28.17007; G = 9.81; U = 12.35; PC = 57.03
out = {}
print(f"{'przebieg':20s} {'N':>3s} {'Mg sr(w)':>8s} {'Mg sr(zd)':>9s} {'zysk':>7s} {'ciag':>7s} {'czl2':>6s} {'nadwyzka':>9s} {'(przy 20 s)':>11s}")
for s in sorted(glob.glob(os.path.join(D, "seria_zapis", "T*_cel*.npy"))):
    k = os.path.basename(s)[:-4]
    try: T = float(k[1:].split("_")[0])
    except ValueError: continue
    b = np.load(s); t = b[:, 0]; w0 = 2 * np.pi / T; we = w0 + w0 * w0 / G * U; Te = 2 * np.pi / we; dt = t[1] - t[0]
    N = int((t[-1] - t[0]) // Te); n = int(round(N * Te / dt)); c = b[-n:]
    a, w, zd, u = c[:, 2], c[:, 4], c[:, 5], c[:, 6]
    zysk = PC - float(c[:, 1].mean()); ciag = M * float(np.mean((a - a.mean()) * (w - w.mean())))
    czl2 = M * float(np.mean(u / (U + u) * (G + a) * (zd - w)))
    o = json.load(open(os.path.join(D, "cel_reg_zapis", k + ".json"))) if os.path.exists(os.path.join(D, "cel_reg_zapis", k + ".json")) else {}
    stary = o.get("zysk_W", np.nan) - o.get("ciag_W", np.nan) - o.get("czlon2_dokl_W", np.nan)
    out[k] = dict(N=N, Mg_sr_w=M * G * float(w.mean()), Mg_sr_zd=M * G * float(zd.mean()), zysk=zysk, ciag=ciag, czlon2=czl2, nadwyzka=zysk - ciag - czl2, nadwyzka_stare_okno=float(stary))
    r = out[k]
    print(f"{k:20s} {N:3d} {r['Mg_sr_w']:8.2f} {r['Mg_sr_zd']:9.2f} {zysk:7.2f} {ciag:7.2f} {czl2:6.2f} {r['nadwyzka']:9.2f} {stary:11.2f}")
json.dump(out, open(os.path.join(D, "FALSYFIKACJA_OKNO_CALKOWITE.json"), "w"), indent=1)
