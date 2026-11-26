"""wiener_kontrola.py - kontrole do wiener_vs_fizyka.py (sonda 3 m): (1) fala testowa z 400 skladowych zamiast 80 (czy filtr nie korzysta z widma liniowego),
(2) filtr stanowy uzyty w NIE SWOIM stanie morza, (3) dlugosc filtra 60 / 150 / 300 wspolczynnikow. Wynik: WIENER_KONTROLA.json"""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import widmo_sensor as S, wiener_vs_fizyka as V
from k3 import probe_kernel
d = 3.0; out = {}
def rec(sea, seed, T, N=80):
    P = S.comps(sea, seed)
    if N != 80:
        Hs, Tp = S.SEAS[sea]; wp = 2 * np.pi / Tp; P.set_irregular(Hs=Hs, Tp=Tp, gamma=3.3, seed=seed, N=N, wmin=0.5 * wp, wmax=3.0 * wp)
    _, e, w = S.signals(P, d, T); return e, w, float(np.mean(P.F.xc))
tr = {s: [rec(s, 9000 + 10 * int(s[1]) + j, 300.0)[:2] for j in range(5)] for s in S.SEAS}
for sigma in (0.0, 0.01):
    H = {s: {L: V.wiener([(e, w, 1.0) for e, w in tr[s]], sigma, 0, L=L) for L in (60, 150, 300)} for s in S.SEAS}
    for s in S.SEAS:
        r = {}
        for N in (80, 400):
            e, w, xm = rec(s, 100 * int(s[1]), 600.0, N); m = e + sigma * np.random.default_rng(5).standard_normal(len(e)); kern, _ = probe_kernel(d + xm, dt=0.01)
            r[f"N{N}_fizyka_D"] = V.err(np.convolve(m, kern)[:len(m)], w)
            for L in (60, 150, 300): r[f"N{N}_Wiener_L{L}"] = V.err(np.convolve(m, H[s][L])[:len(m)], w)
            if N == 80:
                for s2 in S.SEAS: r[f"filtr_z_{s2}"] = V.err(np.convolve(m, H[s2][150])[:len(m)], w)
        out[f"sigma{sigma}|{s}"] = r; print(sigma, s, {k: round(v, 1) for k, v in r.items()}, flush=True)
(HERE / "WIENER_KONTROLA.json").write_text(json.dumps(out, indent=1))
