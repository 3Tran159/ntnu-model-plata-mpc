"""Generator geometrii do optymalizacji: petla G2 z trzema parametrami (wydluzenie AR przy stalej powierzchni 2,496 m2,
odstep gora-dol h [m], przesuniecie dolnego platu s [m], + = dolny z tylu) albo plat pojedynczy o danym AR.
Wpis do GEOMETRIA_G2.json (petle) / GEOMETRIA_MONO.json (pojedyncze), ktore czyta run_p3d.py. Agent D, 15.11.2026."""
import json, math
from pathlib import Path
import numpy as np, trimesh
import make_geo3d as G
HERE = Path(__file__).parent; S_FULL = 8.0 * 0.312; ALPHA = G.ALPHA; SEC = G.SEC; NB = 80


def bend_shape():
    s = np.linspace(0, 1, 4001); phi = 2 * math.pi * (s / 2 - np.sin(2 * math.pi * s) / (4 * math.pi)); ds = s[1] - s[0]
    y = np.concatenate([[0], np.cumsum((np.cos(phi[1:]) + np.cos(phi[:-1])) / 2 * ds)])
    z = np.concatenate([[0], np.cumsum((np.sin(phi[1:]) + np.sin(phi[:-1])) / 2 * ds)])
    return s, phi, y, z


def rings_loop(c, half, gap, stag):
    s, phi, yb, zb = bend_shape(); L = gap / zb[-1]; w = L * yb.max(); y0 = half - w
    idx = np.linspace(0, len(s) - 1, NB + 1).round().astype(int)
    st = [(-0.05, 0.0, 0.0)] + [(y0 + L * yb[i], L * zb[i], phi[i]) for i in idx] + [(-0.05, gap, math.pi)]
    xs, ts = SEC[:, 0] * c, SEC[:, 1] * c; xc = 0.25 * c; R = []
    for y, z, ph in st:
        a = ALPHA * math.cos(ph); ny, nz = -math.sin(ph), math.cos(ph); dx = stag * (1 - ph / math.pi)
        x = dx + xc + (xs - xc) * math.cos(a) + ts * math.sin(a); t = -(xs - xc) * math.sin(a) + ts * math.cos(a)
        R.append(np.column_stack([x, y + t * ny, z + t * nz]))
    return R, dict(L_luku_m=L, szerokosc_luku_m=w, y_poczatku_luku_m=y0)


def tri(R, names):
    n = len(SEC); T, lab = [], []
    for k in range(len(R) - 1):
        part = names[0] if k == 0 else (names[2] if k == len(R) - 2 else names[1])
        for i in range(n):
            j = (i + 1) % n; T += [(R[k][i], R[k + 1][j], R[k][j]), (R[k][i], R[k + 1][i], R[k + 1][j])]; lab += [part, part]
    for a, b, cc in G.TRI_CAP:
        T.append((R[0][a], R[0][b], R[0][cc])); lab.append(names[0]); T.append((R[-1][a], R[-1][cc], R[-1][b])); lab.append(names[2])
    m = trimesh.Trimesh(np.array(T).reshape(-1, 3), np.arange(3 * len(T)).reshape(-1, 3), process=True); m.merge_vertices()
    if m.volume < 0: T = [(a, cc, b) for a, b, cc in T]
    return T, np.array(lab), bool(m.is_watertight)


def make_case(name, ar, gap=None, stag=0.0):
    b = math.sqrt(ar * S_FULL); half = b / 2; cd = HERE / name; cd.mkdir(exist_ok=True)
    G.write(cd / "domena.stl", G.box(-8.0, 24.0, 0.0, 12.0, -8.0, 9.0))
    if gap is None:                                          # plat pojedynczy, cieciwa S/b, srodek na z = 0,5
        c = S_FULL / b; xs, ts = SEC[:, 0] * c, SEC[:, 1] * c; xc = 0.25 * c; R = []
        for y in (-0.05, half):
            x = xc + (xs - xc) * math.cos(ALPHA) + ts * math.sin(ALPHA); z = 0.5 - (xs - xc) * math.sin(ALPHA) + ts * math.cos(ALPHA)
            R.append(np.column_stack([x, np.full_like(x, y), z]))
        T, lab, wt = tri(R, ("plat", "plat", "plat")); f = HERE / "GEOMETRIA_MONO.json"
        info = dict(AR=ar, pol_rozp_m=half, cieciwa_m=c, watertight=wt)
    else:
        c = S_FULL / b / 2; R, inf = rings_loop(c, half, gap, stag); T, lab, wt = tri(R, ("dolny", "luk", "gorny")); f = HERE / "GEOMETRIA_G2.json"
        info = dict(AR=ar, odstep_m=gap, przesuniecie_m=stag, pol_rozp_m=half, cieciwa_platu_m=c, watertight=wt, **inf)
    G.write(cd / "bryla.stl", {k: [T[i] for i in np.where(lab == k)[0]] for k in dict.fromkeys(lab)})
    allg = json.loads(f.read_text()) if f.exists() else {}; allg[name] = info; f.write_text(json.dumps(allg, indent=1))
    return info
