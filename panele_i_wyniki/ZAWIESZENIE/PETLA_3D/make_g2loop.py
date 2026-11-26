"""Petla G2: jedna bryla - plat dolny -> luk o ciaglej krzywiznie -> plat gorny (polowa rozpietosci, symetria y = 0).
Sciezka w plaszczyznie y-z: odcinek prosty, luk z krzywizna k(s) = A sin^2(pi s / L) (k = 0 na koncach -> G2, obrot o 180 st.),
odcinek prosty z powrotem. Przekroj (ten sam NACA66-012 MOD, tepa krawedz splywu) przesuwany wzdluz sciezki, prostopadle do niej.
Kat natarcia w ukladzie lokalnym: alpha * cos(phi) (dol +2,9 st., gora -2,9 st. w ukladzie odwroconym = oba platy niosa w gore).
Patche: dolny / luk / gorny. Agent D, 15.11.2026.  usage: python make_g2loop.py"""
import json, math
from pathlib import Path
import numpy as np, trimesh
import make_geo3d as G
HERE = Path(__file__).parent; S_FULL = 8.0 * 0.312; ALPHA = G.ALPHA; SEC = G.SEC; NB = 80


def bend_shape():
    s = np.linspace(0, 1, 4001); A = 2 * math.pi                        # L = 1
    phi = A * (s / 2 - np.sin(2 * math.pi * s) / (4 * math.pi))
    ds = s[1] - s[0]; y = np.concatenate([[0], np.cumsum((np.cos(phi[1:]) + np.cos(phi[:-1])) / 2 * ds)])
    z = np.concatenate([[0], np.cumsum((np.sin(phi[1:]) + np.sin(phi[:-1])) / 2 * ds)])
    return s, phi, y, z


def loop(c, half, gap):
    s, phi, yb, zb = bend_shape(); L = gap / zb[-1]; w = L * yb.max(); y0 = half - w
    idx = np.linspace(0, len(s) - 1, NB + 1).round().astype(int)
    st = [(-0.05, 0.0, 0.0)]                                               # (y, z, phi) stacje sciezki
    st += [(y0 + L * yb[i], L * zb[i], phi[i]) for i in idx]
    st += [(-0.05, gap, math.pi)]
    xs, ts = SEC[:, 0] * c, SEC[:, 1] * c; xc = 0.25 * c; rings = []
    for y, z, ph in st:
        a = ALPHA * math.cos(ph); ny, nz = -math.sin(ph), math.cos(ph)  # normalna do sciezki
        x = xc + (xs - xc) * math.cos(a) + ts * math.sin(a); t = -(xs - xc) * math.sin(a) + ts * math.cos(a)
        rings.append(np.column_stack([x, y + t * ny, z + t * nz]))
    n = len(SEC); T = []; lab = []
    for k in range(len(rings) - 1):
        P0, P1 = rings[k], rings[k + 1]; part = "dolny" if k == 0 else ("gorny" if k == len(rings) - 2 else "luk")
        for i in range(n):
            j = (i + 1) % n; T += [(P0[i], P1[j], P0[j]), (P0[i], P1[i], P1[j])]; lab += [part, part]
    for a, b, cc in G.TRI_CAP:
        T.append((rings[0][a], rings[0][b], rings[0][cc])); lab.append("dolny")
        T.append((rings[-1][a], rings[-1][cc], rings[-1][b])); lab.append("gorny")
    m = trimesh.Trimesh(np.array(T).reshape(-1, 3), np.arange(3 * len(T)).reshape(-1, 3), process=True); m.merge_vertices()
    flip = m.volume < 0
    return T, lab, dict(L_luku_m=L, szerokosc_luku_m=w, y_poczatku_luku_m=y0, watertight=bool(m.is_watertight), objetosc_m3=float(abs(m.volume)), odwrocone=bool(flip)), flip


CASES = {"P3D_g2_h04": (25.6, 0.4), "P3D_AR8_g2_h04": (8, 0.4), "P3D_AR8_g2_h10": (8, 1.0), "P3D_AR4_g2_h04": (4, 0.4)}
info = {}
for case, (ar, gap) in CASES.items():
    b = math.sqrt(ar * S_FULL); half = b / 2; c = S_FULL / b / 2
    T, lab, inf, flip = loop(c, half, gap)
    if flip: T = [(a, cc, b_) for a, b_, cc in T]
    cd = HERE / case; cd.mkdir(exist_ok=True)
    G.write(cd / "domena.stl", G.box(-8.0, 24.0, 0.0, 12.0, -8.0, 9.0))
    lab = np.array(lab); G.write(cd / "bryla.stl", {k: [T[i] for i in np.where(lab == k)[0]] for k in ("dolny", "luk", "gorny")})
    info[case] = dict(AR=ar, odstep_m=gap, pol_rozp_m=half, cieciwa_platu_m=c, **inf)
(HERE / "GEOMETRIA_G2.json").write_text(json.dumps(info, indent=1)); print(json.dumps(info, indent=1))
